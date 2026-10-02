package vascular

import (
	"math"
	"sync"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
	"ignite-core/pkg/segmentation"
)

// FrangiOptions defines parameters for multiscale vesselness filtering.
type FrangiOptions struct {
	Scales          []float32 // Multiscale smoothing scales, e.g. [1.5, 2.5, 4.0, 6.0]
	Beta            float32   // Blobness sensitivity (default 0.5)
	C               float32   // Contrast sensitivity (default 8.0)
	DetectCoolVeins bool      // Also detect cooler/hypoperfused vessels
	EdgeMarginPx    float32   // Exclusion margin from tissue boundary (default 14.0 px)
	EdgeRampPx      float32   // Transition ramp width for boundary distance attenuation (default 8.0 px)
}

// DefaultFrangiOptions returns standard parameters for clinical thermal vascular mapping.
func DefaultFrangiOptions() FrangiOptions {
	return FrangiOptions{
		Scales:          []float32{1.5, 2.5, 4.0, 6.0},
		Beta:            0.5,
		C:               8.0,
		DetectCoolVeins: true,
		EdgeMarginPx:    14.0,
		EdgeRampPx:      8.0,
	}
}

// Separable 1D Gaussian kernel
func gaussianKernel1D(sigma float32) ([]float32, int) {
	radius := int(math.Ceil(float64(2.5 * sigma)))
	if radius < 1 {
		radius = 1
	}
	size := 2*radius + 1
	kernel := make([]float32, size)
	sig2 := 2.0 * sigma * sigma
	var sum float32

	for i := -radius; i <= radius; i++ {
		v := float32(math.Exp(float64(-float32(i*i) / sig2)))
		kernel[i+radius] = v
		sum += v
	}
	for i := range kernel {
		kernel[i] /= sum
	}
	return kernel, radius
}

// Convolve1DHorizontal applies a 1D filter horizontally across rows.
func convolve1DHorizontal(src *imageutil.FloatMatrix, kernel []float32, radius int) *imageutil.FloatMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewFloatMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		r0 := wid * chunk
		r1 := r0 + chunk
		if r1 > h {
			r1 = h
		}
		if r0 >= r1 {
			continue
		}
		wg.Add(1)
		go func(start, end int) {
			defer wg.Done()
			for y := start; y < end; y++ {
				row := y * w
				for x := 0; x < w; x++ {
					var sum float32
					for k := -radius; k <= radius; k++ {
						px := x + k
						if px < 0 {
							px = 0
						} else if px >= w {
							px = w - 1
						}
						sum += src.Data[row+px] * kernel[k+radius]
					}
					dst.Data[row+x] = sum
				}
			}
		}(r0, r1)
	}
	wg.Wait()
	return dst
}

// Convolve1DVertical applies a 1D filter vertically across columns using AVX2 SIMD FMA.
func convolve1DVertical(src *imageutil.FloatMatrix, kernel []float32, radius int) *imageutil.FloatMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewFloatMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		r0 := wid * chunk
		r1 := r0 + chunk
		if r1 > h {
			r1 = h
		}
		if r0 >= r1 {
			continue
		}
		wg.Add(1)
		go func(start, end int) {
			defer wg.Done()
			for y := start; y < end; y++ {
				dstRow := dst.Data[y*w : (y+1)*w]
				for k := -radius; k <= radius; k++ {
					py := y + k
					if py < 0 {
						py = 0
					} else if py >= h {
						py = h - 1
					}
					coeff := kernel[k+radius]
					srcRow := src.Data[py*w : (py+1)*w]
					morphology.FMAVectorFloat32(srcRow, dstRow, coeff)
				}
			}
		}(r0, r1)
	}
	wg.Wait()
	return dst
}

// Separable Gaussian Blur: O(2K) instead of O(K^2)
func gaussianBlurSeparable(src *imageutil.FloatMatrix, sigma float32) *imageutil.FloatMatrix {
	kernel, radius := gaussianKernel1D(sigma)
	tmp := convolve1DHorizontal(src, kernel, radius)
	return convolve1DVertical(tmp, kernel, radius)
}

// extendSkinBorder fills background pixels within margin of foreground with dilated skin values
// using a fast frontier BFS to prevent steep step cliffs at the skin-air interface during Gaussian blur.
func extendSkinBorder(src *imageutil.FloatMatrix, mask *imageutil.GrayMatrix, iterations int) *imageutil.FloatMatrix {
	w, h := src.Width, src.Height
	ext := imageutil.NewFloatMatrix(w, h)
	copy(ext.Data, src.Data)
	if mask == nil {
		return ext
	}

	filled := make([]bool, w*h)
	for i, v := range mask.Data {
		if v > 0 {
			filled[i] = true
		}
	}

	// Find initial boundary frontier (background pixels adjacent to mask)
	frontier := make([]int, 0, 8192)
	for y := 0; y < h; y++ {
		row := y * w
		for x := 0; x < w; x++ {
			idx := row + x
			if filled[idx] {
				continue
			}
			if (x > 0 && filled[idx-1]) || (x < w-1 && filled[idx+1]) || (y > 0 && filled[idx-w]) || (y < h-1 && filled[idx+w]) {
				frontier = append(frontier, idx)
			}
		}
	}

	for iter := 0; iter < iterations && len(frontier) > 0; iter++ {
		nextFrontier := make([]int, 0, len(frontier)*2)
		newVals := make([]float32, len(frontier))

		for i, idx := range frontier {
			x := idx % w
			y := idx / w
			var sum float32
			var count int
			if x > 0 && filled[idx-1] {
				sum += ext.Data[idx-1]
				count++
			}
			if x < w-1 && filled[idx+1] {
				sum += ext.Data[idx+1]
				count++
			}
			if y > 0 && filled[idx-w] {
				sum += ext.Data[idx-w]
				count++
			}
			if y < h-1 && filled[idx+w] {
				sum += ext.Data[idx+w]
				count++
			}
			if count > 0 {
				newVals[i] = sum / float32(count)
			}
		}

		for i, idx := range frontier {
			ext.Data[idx] = newVals[i]
			filled[idx] = true
		}

		// Collect next frontier
		for _, idx := range frontier {
			x := idx % w
			y := idx / w
			nbrs := [4]int{-1, 1, -w, w}
			conds := [4]bool{x > 0, x < w-1, y > 0, y < h-1}
			for k := 0; k < 4; k++ {
				if conds[k] {
					nIdx := idx + nbrs[k]
					if !filled[nIdx] {
						filled[nIdx] = true // Mark to avoid duplicate additions
						nextFrontier = append(nextFrontier, nIdx)
					}
				}
			}
		}

		for _, idx := range nextFrontier {
			filled[idx] = false
		}
		frontier = nextFrontier
	}

	return ext
}

// MultiscaleFrangiVesselness calculates fast Frangi vesselness filter using separable derivatives,
// background boundary extension, distance-transform boundary suppression, and parallelized Hessian eigenvalue extraction.
func MultiscaleFrangiVesselness(src *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, distMap *imageutil.FloatMatrix, opts FrangiOptions) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	maxResponse := imageutil.NewFloatMatrix(w, h)
	srcFloat := src.ToFloat()

	if distMap == nil && mask != nil {
		distMap = segmentation.ChamferDistanceTransform(mask)
	}

	// 1. Extend skin border into background so Gaussian blur doesn't see a 12°C cliff at the skin-air border
	paddedFloat := extendSkinBorder(srcFloat, mask, 16)

	twoBeta2 := 2.0 * opts.Beta * opts.Beta
	twoC2 := 2.0 * opts.C * opts.C
	edgeMargin := opts.EdgeMarginPx
	if edgeMargin <= 0 {
		edgeMargin = 14.0
	}
	edgeRamp := opts.EdgeRampPx
	if edgeRamp <= 0 {
		edgeRamp = 8.0
	}

	for _, sigma := range opts.Scales {
		// 1. Separable Gaussian smoothing on border-extended image (AVX2 FMA accelerated)
		smoothed := gaussianBlurSeparable(paddedFloat, sigma)

		// 2. Compute 2nd derivatives using finite differences in parallel
		sig2 := sigma * sigma

		var wg sync.WaitGroup
		workers := 8
		chunk := (h - 2 + workers - 1) / workers

		for wid := 0; wid < workers; wid++ {
			r0 := 1 + wid*chunk
			r1 := r0 + chunk
			if r1 > h-1 {
				r1 = h - 1
			}
			if r0 >= r1 {
				continue
			}
			wg.Add(1)
			go func(start, end int) {
				defer wg.Done()
				for y := start; y < end; y++ {
					rowPrev := (y - 1) * w
					rowCurr := y * w
					rowNext := (y + 1) * w

					for x := 1; x < w-1; x++ {
						idx := rowCurr + x
						if mask != nil && mask.Data[idx] == 0 {
							continue
						}

						// Distance attenuation factor from skin border
						var edgeWeight float32 = 1.0
						if distMap != nil {
							d := distMap.Data[idx]
							if d <= edgeMargin {
								// Strictly discard skin-air interface border artifacts
								continue
							} else if d < edgeMargin+edgeRamp {
								edgeWeight = (d - edgeMargin) / edgeRamp
							}
						}

						// 2nd derivatives scaled by sigma^2
						dxx := (smoothed.Data[idx-1] - 2.0*smoothed.Data[idx] + smoothed.Data[idx+1]) * sig2
						dyy := (smoothed.Data[rowPrev+x] - 2.0*smoothed.Data[idx] + smoothed.Data[rowNext+x]) * sig2
						dxy := (smoothed.Data[rowNext+x+1] - smoothed.Data[rowNext+x-1] - smoothed.Data[rowPrev+x+1] + smoothed.Data[rowPrev+x-1]) * 0.25 * sig2

						// Hessian eigenvalues:
						trace := dxx + dyy
						diff := dxx - dyy
						disc := float32(math.Sqrt(float64(diff*diff + 4.0*dxy*dxy)))

						lam1 := (trace - disc) * 0.5
						lam2 := (trace + disc) * 0.5

						if math.Abs(float64(lam1)) > math.Abs(float64(lam2)) {
							lam1, lam2 = lam2, lam1
						}

						rb := float32(math.Abs(float64(lam1))) / (float32(math.Abs(float64(lam2))) + 1e-6)
						s2 := lam1*lam1 + lam2*lam2

						blobnessExp := float32(math.Exp(float64(-rb * rb / twoBeta2)))
						structureExp := 1.0 - float32(math.Exp(float64(-s2/twoC2)))
						vBase := blobnessExp * structureExp

						var v float32
						if lam2 < 0 {
							// Warm superficial vessel (ridge)
							v = vBase
						} else if opts.DetectCoolVeins && lam2 > 0 {
							// Cool superficial vessel (valley)
							v = vBase * 0.85
						} else {
							continue
						}

						v *= edgeWeight
						if v > maxResponse.Data[idx] {
							maxResponse.Data[idx] = v
						}
					}
				}
			}(r0, r1)
		}
		wg.Wait()
	}

	// Robust percentile normalization:
	// Compute 99.5th percentile of non-zero vesselness responses inside tissue to prevent single-pixel clipping
	var hist [1000]int
	var nonZeroCount int
	for i, v := range maxResponse.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		if v > 0 {
			bin := int(v * 999.0)
			if bin < 0 {
				bin = 0
			} else if bin > 999 {
				bin = 999
			}
			hist[bin]++
			nonZeroCount++
		}
	}

	var normCeil float32 = 0.5
	if nonZeroCount > 100 {
		targetCount := int(float64(nonZeroCount) * 0.995)
		cum := 0
		for b := 0; b < 1000; b++ {
			cum += hist[b]
			if cum >= targetCount {
				normCeil = float32(b+1) / 1000.0
				break
			}
		}
	}
	if normCeil < 0.15 {
		normCeil = 0.15
	}

	gm := imageutil.NewGrayMatrix(w, h)
	for i, v := range maxResponse.Data {
		if mask != nil && mask.Data[i] == 0 || v <= 0 {
			gm.Data[i] = 0
			continue
		}
		norm := v / normCeil
		if norm > 1.0 {
			norm = 1.0
		}
		gm.Data[i] = uint8(math.Round(float64(norm * 255.0)))
	}

	return gm
}
