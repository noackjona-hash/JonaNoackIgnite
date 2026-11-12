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

func TestAVX2DotProductFloat32(t *testing.T) {
	n := 67 // Non-multiple of 8 to test both AVX2 loop and scalar tail
	a := make([]float32, n)
	b := make([]float32, n)
	var expected float32
	for i := 0; i < n; i++ {
		a[i] = float32(i + 1)
		b[i] = float32(i%5 + 1)
		expected += a[i] * b[i]
	}

	got := DotProductFloat32(a, b)
	diff := got - expected
	if diff < 0 { diff = -diff }
	if diff > 1e-3 {
		t.Fatalf("DotProductFloat32 mismatch: expected %f, got %f (diff %f)", expected, got, diff)
	}
}

func TestAVX2AddVectorFloat32(t *testing.T) {
	n := 35
	a := make([]float32, n)
	b := make([]float32, n)
	dst := make([]float32, n)
	for i := 0; i < n; i++ {
		a[i] = float32(i * 2)
		b[i] = float32(100 - i)
	}

	AddVectorFloat32(a, b, dst)

	for i := 0; i < n; i++ {
		exp := a[i] + b[i]
		if dst[i] != exp {
			t.Fatalf("AddVectorFloat32 mismatch at %d: expected %f, got %f", i, exp, dst[i])
		}
	}
}

func TestAVX2ScaleOffsetFloat32(t *testing.T) {
	n := 37
	src := make([]float32, n)
	dst := make([]float32, n)
	for i := 0; i < n; i++ {
		src[i] = float32(i)
	}

	ScaleOffsetFloat32(src, dst, 0.5, 20.0)

	for i := 0; i < n; i++ {
		exp := float32(i)*0.5 + 20.0
		if dst[i] != exp {
			t.Fatalf("ScaleOffsetFloat32 mismatch at %d: expected %f, got %f", i, exp, dst[i])
		}
	}
}

func TestAVX2Laplacian2DVectorFloat32(t *testing.T) {
	n := 25
	c := make([]float32, n)
	l := make([]float32, n)
	r := make([]float32, n)
	u := make([]float32, n)
	d := make([]float32, n)
	dst := make([]float32, n)

	for i := 0; i < n; i++ {
		c[i] = float32(30 + i)
		l[i] = float32(28 + i)
		r[i] = float32(32 + i)
		u[i] = float32(29 + i)
		d[i] = float32(31 + i)
	}

	Laplacian2DVectorFloat32(c, l, r, u, d, dst)

	for i := 0; i < n; i++ {
		exp := l[i] + r[i] + u[i] + d[i] - 4.0*c[i]
		diff := dst[i] - exp
		if diff < 0 { diff = -diff }
		if diff > 1e-4 {
			t.Fatalf("Laplacian2DVectorFloat32 mismatch at %d: expected %f, got %f", i, exp, dst[i])
		}
	}
}

func TestAVX2SumAndSumSqUint8(t *testing.T) {
	n := 128
	src := make([]uint8, n)
	mask := make([]uint8, n)
	var expSum uint64
	var expSumSq uint64
	var expCount uint64

	for i := 0; i < n; i++ {
		src[i] = uint8(i + 10)
		if i%3 == 0 {
			mask[i] = 0 // Masked out
		} else {
			mask[i] = 255
			expSum += uint64(src[i])
			expSumSq += uint64(src[i]) * uint64(src[i])
			expCount++
		}
	}

	sum, sumSq, count := SumAndSumSqUint8(src, mask)

	if sum != expSum || sumSq != expSumSq || count != expCount {
		t.Fatalf("SumAndSumSqUint8 mismatch: expected sum=%d, sumSq=%d, count=%d; got sum=%d, sumSq=%d, count=%d",
			expSum, expSumSq, expCount, sum, sumSq, count)
	}
}

func TestVHGWExactnessAndMaskedOpening(t *testing.T) {
	w, h, r := 73, 59, 11
	mat := imageutil.NewGrayMatrix(w, h)
	mask := imageutil.NewGrayMatrix(w, h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			v := uint8((x*7 + y*13) % 200)
			if x >= 15 && x <= 58 && y >= 10 && y <= 48 {
				mask.Set(x, y, 255)
				mat.Set(x, y, 140+(v%60))
			} else {
				// Cold air background (should NOT bleed into TopHatMasked)
				mat.Set(x, y, 30)
			}
		}
	}

	// Verify unmasked Erode1DHorizontal matches exact naive window min
	gotH := Erode1DHorizontal(mat, r)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			exp := uint8(255)
			for dx := -r; dx <= r; dx++ {
				nx := x + dx
				if nx >= 0 && nx < w {
					if val := mat.At(nx, y); val < exp {
						exp = val
					}
				}
			}
			if gotH.At(x, y) != exp {
				t.Fatalf("vhgw Erode1DHorizontal mismatch at (%d,%d): expected %d, got %d", x, y, exp, gotH.At(x, y))
			}
		}
	}

	// Verify unmasked Dilate1DVertical matches exact naive window max
	gotV := Dilate1DVertical(mat, r)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			exp := uint8(0)
			for dy := -r; dy <= r; dy++ {
				ny := y + dy
				if ny >= 0 && ny < h {
					if val := mat.At(x, ny); val > exp {
						exp = val
					}
				}
			}
			if gotV.At(x, y) != exp {
				t.Fatalf("vhgw Dilate1DVertical mismatch at (%d,%d): expected %d, got %d", x, y, exp, gotV.At(x, y))
			}
		}
	}

	// Verify TopHatMasked blocks cold background (30) from bleeding into skin boundary (>=140)
	// On a flat warm tissue plateau at 160 inside mask, masked TopHat must be 0 even right at border!
	flatTissue := imageutil.NewGrayMatrix(w, h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			if mask.At(x, y) > 0 {
				flatTissue.Set(x, y, 160)
			} else {
				flatTissue.Set(x, y, 30)
			}
		}
	}
	thMasked := TopHatMasked(flatTissue, mask, r)
	if thMasked.At(15, 10) != 0 || thMasked.At(58, 48) != 0 {
		t.Fatalf("expected 0 border artifact in TopHatMasked, got (%d, %d)", thMasked.At(15, 10), thMasked.At(58, 48))
	}

	// Verify CloseBinaryMasked bridges a 2px dark crease inside a hotspot
	bin := imageutil.NewGrayMatrix(30, 30)
	binMask := imageutil.NewGrayMatrix(30, 30)
	for y := 5; y < 25; y++ {
		for x := 5; x < 25; x++ {
			binMask.Set(x, y, 255)
			if x >= 10 && x <= 19 && y >= 10 && y <= 19 && x != 14 && x != 15 {
				bin.Set(x, y, 255)
			}
		}
	}
	closed := CloseBinaryMasked(bin, binMask, 2)
	if closed.At(14, 15) != 255 || closed.At(15, 15) != 255 {
		t.Fatalf("CloseBinaryMasked failed to bridge 2px crease: got (%d, %d)", closed.At(14, 15), closed.At(15, 15))
	}
	if closed.At(7, 15) != 0 {
		t.Fatalf("CloseBinaryMasked leaked beyond radius: got %d at (7,15)", closed.At(7, 15))
	}
}


