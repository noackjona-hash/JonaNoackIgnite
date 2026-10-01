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
