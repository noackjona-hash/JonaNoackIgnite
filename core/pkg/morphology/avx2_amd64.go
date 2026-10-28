//go:build amd64

package morphology

// Declarations of the x86_64 AVX2 assembly kernels in avx2_amd64.s
//
//go:noescape
func minVectorAVX2(src, dst *byte, count int)

//go:noescape
func maxVectorAVX2(src, dst *byte, count int)

//go:noescape
func subVectorAVX2(a, b, dst *byte, count int)

//go:noescape
func absDiffVectorAVX2(a, b, dst *byte, count int)

//go:noescape
func fmaVectorFloat32AVX2(src, dst *float32, factor float32, count int)

//go:noescape
func mulScalarFloat32AVX2(src, dst *float32, factor float32, count int)

//go:noescape
func thresholdMaskAVX2(diff, orig, mask, dst *byte, count int, threshold, origMedian byte)

//go:noescape
func dotProductFloat32AVX2(a, b *float32, res *float32, count int)

//go:noescape
func addVectorFloat32AVX2(a, b, dst *float32, count int)

//go:noescape
func scaleOffsetFloat32AVX2(src, dst *float32, scale, offset float32, count int)

//go:noescape
func laplacian2DVectorFloat32AVX2(center, left, right, up, down, dst *float32, count int)

//go:noescape
func sumAndSumSqUint8AVX2(src, mask *byte, count int, sum, sumSq, validCount *uint64)

// MinVector applies dst[i] = min(dst[i], src[i])
func MinVector(src, dst []uint8) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	minVectorAVX2(&src[0], &dst[0], n)
}

// MaxVector applies dst[i] = max(dst[i], src[i])
func MaxVector(src, dst []uint8) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	maxVectorAVX2(&src[0], &dst[0], n)
}

// SubVector applies dst[i] = max(0, a[i] - b[i])
func SubVector(a, b, dst []uint8) {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	subVectorAVX2(&a[0], &b[0], &dst[0], n)
}

// AbsDiffVector applies dst[i] = |a[i] - b[i]| using AVX2 SIMD
func AbsDiffVector(a, b, dst []uint8) {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	absDiffVectorAVX2(&a[0], &b[0], &dst[0], n)
}

// FMAVectorFloat32 computes dst[i] += factor * src[i] using 256-bit AVX2
func FMAVectorFloat32(src, dst []float32, factor float32) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	fmaVectorFloat32AVX2(&src[0], &dst[0], factor, n)
}

// MulScalarFloat32 computes dst[i] = factor * src[i] using 256-bit AVX2
func MulScalarFloat32(src, dst []float32, factor float32) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	mulScalarFloat32AVX2(&src[0], &dst[0], factor, n)
}

// ThresholdMaskAVX2 performs fast multi-condition binarization using AVX2:
// dst[i] = (diff[i] >= threshold && (orig == nil || orig[i] >= origMedian) && (mask == nil || mask[i] > 0)) ? 255 : 0
func ThresholdMaskAVX2(diff, orig, mask, dst []uint8, threshold, origMedian uint8) {
	n := len(diff)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	var origPtr, maskPtr *byte
	if orig != nil && len(orig) >= n {
		origPtr = &orig[0]
	}
	if mask != nil && len(mask) >= n {
		maskPtr = &mask[0]
	}
	thresholdMaskAVX2(&diff[0], origPtr, maskPtr, &dst[0], n, threshold, origMedian)
}

// DotProductFloat32 computes the dot product of two float32 slices using 256-bit AVX2.
func DotProductFloat32(a, b []float32) float32 {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if n == 0 {
		return 0
	}
	var res float32
	dotProductFloat32AVX2(&a[0], &b[0], &res, n)
	return res
}

// AddVectorFloat32 computes dst[i] = a[i] + b[i] using 256-bit AVX2.
func AddVectorFloat32(a, b, dst []float32) {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	addVectorFloat32AVX2(&a[0], &b[0], &dst[0], n)
}

// ScaleOffsetFloat32 computes dst[i] = src[i] * scale + offset using 256-bit AVX2.
func ScaleOffsetFloat32(src, dst []float32, scale, offset float32) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	if n == 0 {
		return
	}
	scaleOffsetFloat32AVX2(&src[0], &dst[0], scale, offset, n)
}

// Laplacian2DVectorFloat32 computes dst[i] = left[i] + right[i] + up[i] + down[i] - 4*center[i] using 256-bit AVX2.
func Laplacian2DVectorFloat32(center, left, right, up, down, dst []float32) {
	n := len(center)
	if len(left) < n { n = len(left) }
	if len(right) < n { n = len(right) }
	if len(up) < n { n = len(up) }
	if len(down) < n { n = len(down) }
	if len(dst) < n { n = len(dst) }
	if n == 0 {
		return
	}
	laplacian2DVectorFloat32AVX2(&center[0], &left[0], &right[0], &up[0], &down[0], &dst[0], n)
}

// SumAndSumSqUint8 computes sum, sum of squares, and valid pixel count in parallel using AVX2.
func SumAndSumSqUint8(src, mask []uint8) (sum uint64, sumSq uint64, validCount uint64) {
	n := len(src)
	if n == 0 {
		return 0, 0, 0
	}
	var maskPtr *byte
	if mask != nil && len(mask) >= n {
		maskPtr = &mask[0]
	}
	sumAndSumSqUint8AVX2(&src[0], maskPtr, n, &sum, &sumSq, &validCount)
	return sum, sumSq, validCount
}

