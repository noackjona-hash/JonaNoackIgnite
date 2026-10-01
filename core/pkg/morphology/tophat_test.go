package morphology

import (
	"testing"

	"ignite-core/pkg/imageutil"
)

func TestAVX2SubVector(t *testing.T) {
	a := make([]uint8, 64)
	b := make([]uint8, 64)
	dst := make([]uint8, 64)

	for i := 0; i < 64; i++ {
		a[i] = uint8(100 + i)
		b[i] = uint8(50)
	}

	SubVector(a, b, dst)

	for i := 0; i < 64; i++ {
		expected := uint8(50 + i)
		if dst[i] != expected {
			t.Fatalf("at index %d: expected %d, got %d", i, expected, dst[i])
		}
	}
}

func TestTopHatSimple(t *testing.T) {
	w, h := 50, 50
	mat := imageutil.NewGrayMatrix(w, h)

	// Set smooth background: 100
	for i := range mat.Data {
		mat.Data[i] = 100
	}
	// Place a localized hotspot in the center: 220
	mat.Set(25, 25, 220)
	mat.Set(25, 26, 220)
	mat.Set(26, 25, 220)

	th := TopHat(mat, 5)

	// Smooth background should be 0 in Top-Hat
	if th.At(5, 5) != 0 {
		t.Fatalf("expected flat background to be 0, got %d", th.At(5, 5))
	}
	// Hotspot center should stand out
	if th.At(25, 25) < 100 {
		t.Fatalf("expected hotspot to have high value, got %d", th.At(25, 25))
	}
}

func TestAVX2MinMax(t *testing.T) {
	src := make([]uint8, 64)
	dstMin := make([]uint8, 64)
	dstMax := make([]uint8, 64)

	for i := 0; i < 64; i++ {
		src[i] = uint8(i * 3)
		dstMin[i] = 100
		dstMax[i] = 100
	}

	MinVector(src, dstMin)
	MaxVector(src, dstMax)

	for i := 0; i < 64; i++ {
		expectedMin := uint8(100)
		if src[i] < 100 {
			expectedMin = src[i]
		}
		if dstMin[i] != expectedMin {
			t.Fatalf("MinVector mismatch at %d: expected %d, got %d", i, expectedMin, dstMin[i])
		}

		expectedMax := uint8(100)
		if src[i] > 100 {
			expectedMax = src[i]
		}
		if dstMax[i] != expectedMax {
			t.Fatalf("MaxVector mismatch at %d: expected %d, got %d", i, expectedMax, dstMax[i])
		}
	}
}

func TestAVX2AbsDiff(t *testing.T) {
	a := make([]uint8, 64)
	b := make([]uint8, 64)
	dst := make([]uint8, 64)

	for i := 0; i < 64; i++ {
		a[i] = uint8(200)
		b[i] = uint8(i * 4)
	}

	AbsDiffVector(a, b, dst)

	for i := 0; i < 64; i++ {
		diff := int(a[i]) - int(b[i])
		if diff < 0 {
			diff = -diff
		}
		if dst[i] != uint8(diff) {
			t.Fatalf("AbsDiffVector mismatch at %d: expected %d, got %d", i, diff, dst[i])
		}
	}
}

func TestAVX2ThresholdMask(t *testing.T) {
	n := 64
	diff := make([]uint8, n)
	orig := make([]uint8, n)
	mask := make([]uint8, n)
	dst := make([]uint8, n)

	for i := 0; i < n; i++ {
		diff[i] = uint8(i * 4) // 0 to 252
		orig[i] = uint8(150)
		mask[i] = 255
	}
	// Make some fail mask
	mask[0] = 0
	mask[10] = 0

	ThresholdMaskAVX2(diff, orig, mask, dst, 100, 140)

	for i := 0; i < n; i++ {
		expected := uint8(0)
		if diff[i] >= 100 && orig[i] >= 140 && mask[i] > 0 {
			expected = 255
		}
		if dst[i] != expected {
			t.Fatalf("ThresholdMaskAVX2 mismatch at %d: expected %d, got %d", i, expected, dst[i])
		}
	}
}

func TestAVX2FMAFloat32(t *testing.T) {
	n := 32
	src := make([]float32, n)
	dst := make([]float32, n)

	for i := 0; i < n; i++ {
		src[i] = float32(i + 1)
		dst[i] = 10.0
	}

	FMAVectorFloat32(src, dst, 2.5)

	for i := 0; i < n; i++ {
		expected := 10.0 + 2.5*float32(i+1)
		if dst[i] != expected {
			t.Fatalf("FMAVectorFloat32 mismatch at %d: expected %f, got %f", i, expected, dst[i])
		}
	}
}
