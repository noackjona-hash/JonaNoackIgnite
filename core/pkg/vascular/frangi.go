package vascular

import (
	"math"
	"sync"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
)

// FrangiOptions defines parameters for multiscale vesselness filtering.
type FrangiOptions struct {
	Scales []float32 // e.g. [1.5, 3.0]
	Beta   float32   // Blobness sensitivity (default 0.5)
	C      float32   // Contrast sensitivity (default 15.0)
}

// DefaultFrangiOptions returns standard parameters for thermal vascular mapping.
func DefaultFrangiOptions() FrangiOptions {
	return FrangiOptions{
		Scales: []float32{1.5, 3.0},
		Beta:   0.5,
		C:      15.0,
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

// MultiscaleFrangiVesselness calculates fast Frangi vesselness filter using separable derivatives.
func MultiscaleFrangiVesselness(src *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, opts FrangiOptions) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	maxResponse := imageutil.NewFloatMatrix(w, h)
	srcFloat := src.ToFloat()

	twoBeta2 := 2.0 * opts.Beta * opts.Beta
	twoC2 := 2.0 * opts.C * opts.C

	for _, sigma := range opts.Scales {
		// 1. Separable Gaussian smoothing
		smoothed := gaussianBlurSeparable(srcFloat, sigma)

		// 2. Compute 2nd derivatives using Sobel / finite differences
		sig2 := sigma * sigma

		for y := 1; y < h-1; y++ {
			rowPrev := (y - 1) * w
			rowCurr := y * w
			rowNext := (y + 1) * w

			for x := 1; x < w-1; x++ {
				idx := rowCurr + x
				if mask != nil && mask.Data[idx] == 0 {
					continue
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

				// Warm superficial veins: principal cross-curvature lam2 must be negative
				if lam2 >= 0 {
					continue
				}

				rb := float32(math.Abs(float64(lam1))) / float32(math.Abs(float64(lam2)))
				s2 := lam1*lam1 + lam2*lam2

				blobnessExp := float32(math.Exp(float64(-rb * rb / twoBeta2)))
				structureExp := 1.0 - float32(math.Exp(float64(-s2/twoC2)))

				v := blobnessExp * structureExp
				if v > maxResponse.Data[idx] {
					maxResponse.Data[idx] = v
				}
			}
		}
	}

	return maxResponse.ToGray()
}
