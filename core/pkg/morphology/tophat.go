package morphology

import (
	"ignite-core/pkg/imageutil"
)

// Morphological opening = Dilation of Erosion.
// Top-Hat = Input - Opening(Input).

// Erode1DHorizontal computes 1D horizontal erosion along image rows with radius r using AVX2 SIMD MinVector.
func Erode1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := src.Clone()
	for k := 1; k <= r; k++ {
		for y := 0; y < h; y++ {
			row := y * w
			MinVector(src.Data[row+k:row+w], dst.Data[row:row+w-k])
			MinVector(src.Data[row:row+w-k], dst.Data[row+k:row+w])
		}
	}
	return dst
}

// Erode1DVertical computes 1D vertical erosion along image columns with radius r using AVX2 SIMD MinVector.
func Erode1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := src.Clone()
	for k := 1; k <= r; k++ {
		for y := 0; y < h-k; y++ {
			MinVector(src.Data[(y+k)*w:(y+k+1)*w], dst.Data[y*w:(y+1)*w])
			MinVector(src.Data[y*w:(y+1)*w], dst.Data[(y+k)*w:(y+k+1)*w])
		}
	}
	return dst
}

// Dilate1DHorizontal computes 1D horizontal dilation along image rows with radius r using AVX2 SIMD MaxVector.
func Dilate1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := src.Clone()
	for k := 1; k <= r; k++ {
		for y := 0; y < h; y++ {
			row := y * w
			MaxVector(src.Data[row+k:row+w], dst.Data[row:row+w-k])
			MaxVector(src.Data[row:row+w-k], dst.Data[row+k:row+w])
		}
	}
	return dst
}

// Dilate1DVertical computes 1D vertical dilation along image columns with radius r using AVX2 SIMD MaxVector.
func Dilate1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := src.Clone()
	for k := 1; k <= r; k++ {
		for y := 0; y < h-k; y++ {
			MaxVector(src.Data[(y+k)*w:(y+k+1)*w], dst.Data[y*w:(y+1)*w])
			MaxVector(src.Data[y*w:(y+1)*w], dst.Data[(y+k)*w:(y+k+1)*w])
		}
	}
	return dst
}

// Opening computes separable morphological opening with radius r.
func Opening(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	erodedH := Erode1DHorizontal(src, r)
	eroded := Erode1DVertical(erodedH, r)
	dilatedH := Dilate1DHorizontal(eroded, r)
	opened := Dilate1DVertical(dilatedH, r)
	return opened
}

// TopHat computes the morphological Top-Hat transform: src - Opening(src).
// Subtraction uses AVX2 SIMD acceleration.
func TopHat(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	opened := Opening(src, r)
	dst := imageutil.NewGrayMatrix(src.Width, src.Height)
	SubVector(src.Data, opened.Data, dst.Data)
	return dst
}

// DynamicKernelRadius computes kernel radius based on image resolution (e.g. 5% of min dimension).
func DynamicKernelRadius(width, height int, factor float64) int {
	minDim := width
	if height < minDim {
		minDim = height
	}
	raw := int(float64(minDim) * factor)
	if raw < 1 {
		raw = 1
	}
	return raw
}
