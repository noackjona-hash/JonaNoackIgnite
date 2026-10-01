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
