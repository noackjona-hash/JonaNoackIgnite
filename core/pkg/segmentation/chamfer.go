package segmentation

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// ChamferDistanceTransform computes a 2-pass distance transform on a binary mask.
// Foreground (255) pixels get their distance to the nearest background (0) pixel.
func ChamferDistanceTransform(mask *imageutil.GrayMatrix) *imageutil.FloatMatrix {
	w, h := mask.Width, mask.Height
	dist := imageutil.NewFloatMatrix(w, h)
	const inf = 1e7

	// Initialize: 0 for background, inf for foreground
	for i, v := range mask.Data {
		if v == 0 {
			dist.Data[i] = 0
		} else {
			dist.Data[i] = inf
		}
	}

	// Forward pass: top-left to bottom-right (3-4 chamfer weights)
	d1 := float32(1.0)
	d2 := float32(1.4142)

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := y*w + x
			cur := dist.Data[idx]
			if cur == 0 {
				continue
			}

			// Left
			if x > 0 {
				if v := dist.Data[idx-1] + d1; v < cur {
					cur = v
				}
			}
			// Top
			if y > 0 {
				if v := dist.Data[idx-w] + d1; v < cur {
					cur = v
				}
			}
			// Top-Left
			if x > 0 && y > 0 {
				if v := dist.Data[idx-w-1] + d2; v < cur {
					cur = v
				}
			}
			// Top-Right
			if x < w-1 && y > 0 {
				if v := dist.Data[idx-w+1] + d2; v < cur {
					cur = v
				}
			}
			dist.Data[idx] = cur
		}
	}

	// Backward pass: bottom-right to top-left
	for y := h - 1; y >= 0; y-- {
		for x := w - 1; x >= 0; x-- {
			idx := y*w + x
			cur := dist.Data[idx]
			if cur == 0 {
				continue
			}

			// Right
			if x < w-1 {
				if v := dist.Data[idx+1] + d1; v < cur {
					cur = v
				}
			}
			// Bottom
			if y < h-1 {
				if v := dist.Data[idx+w] + d1; v < cur {
					cur = v
				}
			}
			// Bottom-Right
			if x < w-1 && y < h-1 {
				if v := dist.Data[idx+w+1] + d2; v < cur {
					cur = v
				}
			}
			// Bottom-Left
			if x > 0 && y < h-1 {
				if v := dist.Data[idx+w-1] + d2; v < cur {
					cur = v
				}
			}
			dist.Data[idx] = cur
		}
	}

	return dist
}

// ErodeBodyMask removes tissue border pixels using the distance transform.
// marginFactor (e.g. 0.05) removes the outer 5% distance margin.
func ErodeBodyMask(mask *imageutil.GrayMatrix, marginFactor float32) *imageutil.GrayMatrix {
	w, h := mask.Width, mask.Height
	dist := ChamferDistanceTransform(mask)
	_, maxDist := dist.MinMax()

	threshold := maxDist * marginFactor
	eroded := imageutil.NewGrayMatrix(w, h)

	for i, d := range dist.Data {
		if mask.Data[i] > 0 && d >= threshold && !math.IsInf(float64(d), 0) {
			eroded.Data[i] = 255
		} else {
			eroded.Data[i] = 0
		}
	}
	return eroded
}
