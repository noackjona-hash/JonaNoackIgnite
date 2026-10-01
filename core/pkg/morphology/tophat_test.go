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
