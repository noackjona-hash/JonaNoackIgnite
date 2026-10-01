package vascular

import (
	"math"
	"sync"

	"ignite-core/pkg/imageutil"
)

// FrangiOptions defines parameters for multiscale vesselness filtering.
type FrangiOptions struct {
	Scales []float32 // e.g. [1.0, 2.0, 3.0, 4.0]
	Beta   float32   // Blobness sensitivity (default 0.5)
	C      float32   // Contrast sensitivity (default 15.0)
}

// DefaultFrangiOptions returns standard parameters for thermal vascular mapping.
func DefaultFrangiOptions() FrangiOptions {
	return FrangiOptions{
		Scales: []float32{1.0, 2.0, 3.0},
		Beta:   0.5,
		C:      15.0,
	}
}

// GaussianKernel2D generates 2nd-order derivative kernels for Hessian calculation.
func gaussian2ndDerivatives(sigma float32) (kxx, kxy, kyy [][]float32, radius int) {
	radius = int(math.Ceil(float64(3.0 * sigma)))
	size := 2*radius + 1
	kxx = make([][]float32, size)
	kxy = make([][]float32, size)
	kyy = make([][]float32, size)
	for i := range kxx {
		kxx[i] = make([]float32, size)
		kxy[i] = make([]float32, size)
		kyy[i] = make([]float32, size)
	}

	sig2 := sigma * sigma
	sig4 := sig2 * sig2
	const twoPi = float32(2.0 * math.Pi)

	for y := -radius; y <= radius; y++ {
		for x := -radius; x <= radius; x++ {
			r2 := float32(x*x + y*y)
			g := float32(math.Exp(float64(-r2 / (2.0 * sig2)))) / (twoPi * sig2)

			// Gxx = (x^2 / sig4 - 1 / sig2) * G
			kxx[y+radius][x+radius] = (float32(x*x)/sig4 - 1.0/sig2) * g * sig2 // Scale-normalized (Lindeberg)
			// Gxy = (x*y / sig4) * G
			kxy[y+radius][x+radius] = (float32(x*y) / sig4) * g * sig2
			// Gyy = (y^2 / sig4 - 1 / sig2) * G
			kyy[y+radius][x+radius] = (float32(y*y)/sig4 - 1.0/sig2) * g * sig2
		}
	}
	return
}

// Convolve2D performs spatial 2D convolution with border clamping.
func convolve2D(src *imageutil.FloatMatrix, kernel [][]float32, radius int) *imageutil.FloatMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewFloatMatrix(w, h)

	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		startRow := wid * chunk
		endRow := startRow + chunk
		if endRow > h {
			endRow = h
		}
		if startRow >= endRow {
			continue
		}

		wg.Add(1)
		go func(r0, r1 int) {
			defer wg.Done()
			for y := r0; y < r1; y++ {
				for x := 0; x < w; x++ {
					var sum float32
					for ky := -radius; ky <= radius; ky++ {
						py := y + ky
						if py < 0 {
							py = 0
						} else if py >= h {
							py = h - 1
						}
						kRow := kernel[ky+radius]
						for kx := -radius; kx <= radius; kx++ {
							px := x + kx
							if px < 0 {
								px = 0
							} else if px >= w {
								px = w - 1
							}
							sum += src.Data[py*w+px] * kRow[kx+radius]
						}
					}
					dst.Data[y*w+x] = sum
				}
			}
		}(startRow, endRow)
	}
	wg.Wait()
	return dst
}

// ComputeVesselness calculates the Frangi vesselness filter at a single scale sigma.
func computeVesselnessSingleScale(src *imageutil.FloatMatrix, mask *imageutil.GrayMatrix, sigma float32, beta, c float32) *imageutil.FloatMatrix {
	w, h := src.Width, src.Height
	kxx, kxy, kyy, radius := gaussian2ndDerivatives(sigma)

	ixx := convolve2D(src, kxx, radius)
	ixy := convolve2D(src, kxy, radius)
	iyy := convolve2D(src, kyy, radius)

	vesselness := imageutil.NewFloatMatrix(w, h)
	twoBeta2 := 2.0 * beta * beta
	twoC2 := 2.0 * c * c

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := y*w + x
			if mask != nil && mask.Data[idx] == 0 {
				continue
			}

			a := ixx.Data[idx]
			b := ixy.Data[idx]
			d := iyy.Data[idx]

			// Hessian eigenvalues:
			trace := a + d
			diff := a - d
			disc := float32(math.Sqrt(float64(diff*diff + 4.0*b*b)))

			lam1 := (trace - disc) * 0.5
			lam2 := (trace + disc) * 0.5

			// Sort so that |lam1| <= |lam2|
			if math.Abs(float64(lam1)) > math.Abs(float64(lam2)) {
				lam1, lam2 = lam2, lam1
			}

			// In thermal imaging, warm veins are brighter than surrounding tissue:
			// For bright tubular structures on 2D, the principal curvature across the vessel
			// lam2 must be negative (convex downward peak).
			if lam2 >= 0 {
				vesselness.Data[idx] = 0
				continue
			}

			rb := float32(math.Abs(float64(lam1))) / float32(math.Abs(float64(lam2)))
			s2 := lam1*lam1 + lam2*lam2

			blobnessExp := float32(math.Exp(float64(-rb * rb / twoBeta2)))
			structureExp := 1.0 - float32(math.Exp(float64(-s2/twoC2)))

			vesselness.Data[idx] = blobnessExp * structureExp
		}
	}
	return vesselness
}

// MultiscaleFrangiVesselness extracts superficial veins and vascular structures
// across multiple spatial scales, returning a normalized [0, 255] grayscale vein map.
func MultiscaleFrangiVesselness(src *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, opts FrangiOptions) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	maxResponse := imageutil.NewFloatMatrix(w, h)
	srcFloat := src.ToFloat()

	for _, sigma := range opts.Scales {
		vSingle := computeVesselnessSingleScale(srcFloat, mask, sigma, opts.Beta, opts.C)
		for i, v := range vSingle.Data {
			if v > maxResponse.Data[i] {
				maxResponse.Data[i] = v
			}
		}
	}

	// Normalize response into [0, 255]
	return maxResponse.ToGray()
}
