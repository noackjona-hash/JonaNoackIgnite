//go:build !amd64

package morphology

// MinVector scalar fallback for non-x86_64 architectures.
func MinVector(src, dst []uint8) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		if src[i] < dst[i] {
			dst[i] = src[i]
		}
	}
}

// MaxVector scalar fallback for non-x86_64 architectures.
func MaxVector(src, dst []uint8) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		if src[i] > dst[i] {
			dst[i] = src[i]
		}
	}
}

// SubVector scalar fallback for non-x86_64 architectures.
func SubVector(a, b, dst []uint8) {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		if a[i] > b[i] {
			dst[i] = a[i] - b[i]
		} else {
			dst[i] = 0
		}
	}
}

// AbsDiffVector scalar fallback
func AbsDiffVector(a, b, dst []uint8) {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		if a[i] > b[i] {
			dst[i] = a[i] - b[i]
		} else {
			dst[i] = b[i] - a[i]
		}
	}
}

// FMAVectorFloat32 scalar fallback
func FMAVectorFloat32(src, dst []float32, factor float32) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		dst[i] += factor * src[i]
	}
}

// MulScalarFloat32 scalar fallback
func MulScalarFloat32(src, dst []float32, factor float32) {
	n := len(src)
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		dst[i] = factor * src[i]
	}
}

// ThresholdMaskAVX2 scalar fallback
func ThresholdMaskAVX2(diff, orig, mask, dst []uint8, threshold, origMedian uint8) {
	n := len(diff)
	if len(dst) < n {
		n = len(dst)
	}
	for i := 0; i < n; i++ {
		if mask != nil && mask[i] == 0 {
			dst[i] = 0
			continue
		}
		if diff[i] >= threshold && (orig == nil || orig[i] >= origMedian) {
			dst[i] = 255
		} else {
			dst[i] = 0
		}
	}
}

// DotProductFloat32 scalar fallback
func DotProductFloat32(a, b []float32) float32 {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	var res float32
	for i := 0; i < n; i++ {
		res += a[i] * b[i]
	}
	return res
}

// AddVectorFloat32 scalar fallback
func AddVectorFloat32(a, b, dst []float32) {
	n := len(a)
	if len(b) < n { n = len(b) }
	if len(dst) < n { n = len(dst) }
	for i := 0; i < n; i++ {
		dst[i] = a[i] + b[i]
	}
}

// ScaleOffsetFloat32 scalar fallback
func ScaleOffsetFloat32(src, dst []float32, scale, offset float32) {
	n := len(src)
	if len(dst) < n { n = len(dst) }
	for i := 0; i < n; i++ {
		dst[i] = src[i]*scale + offset
	}
}

// Laplacian2DVectorFloat32 scalar fallback
func Laplacian2DVectorFloat32(center, left, right, up, down, dst []float32) {
	n := len(center)
	if len(left) < n { n = len(left) }
	if len(right) < n { n = len(right) }
	if len(up) < n { n = len(up) }
	if len(down) < n { n = len(down) }
	if len(dst) < n { n = len(dst) }
	for i := 0; i < n; i++ {
		dst[i] = left[i] + right[i] + up[i] + down[i] - 4.0*center[i]
	}
}

// SumAndSumSqUint8 scalar fallback
func SumAndSumSqUint8(src, mask []uint8) (sum uint64, sumSq uint64, validCount uint64) {
	n := len(src)
	for i := 0; i < n; i++ {
		if mask != nil && mask[i] == 0 {
			continue
		}
		v := uint64(src[i])
		sum += v
		sumSq += v * v
		validCount++
	}
	return sum, sumSq, validCount
}

