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
