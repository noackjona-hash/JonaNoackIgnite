package vascular

import (
	"testing"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/segmentation"
)

func TestMultiscaleFrangiVesselness_BorderSuppression(t *testing.T) {
	w, h := 120, 120
	src := imageutil.NewGrayMatrix(w, h)
	rawMask := imageutil.NewGrayMatrix(w, h)

	// Create a synthetic warm body (intensity 180) on a cold background (intensity 20)
	// Body covers [20..100, 20..100]
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			if x >= 20 && x <= 100 && y >= 20 && y <= 100 {
				src.Set(x, y, 180)
				rawMask.Set(x, y, 255)
			} else {
				src.Set(x, y, 20)
				rawMask.Set(x, y, 0)
			}
		}
	}

	// Add a warm tubular vein (intensity 200, width ~3px) inside the tissue at y=60, x in [40..80]
	for x := 40; x <= 80; x++ {
		src.Set(x, 59, 195)
		src.Set(x, 60, 200)
		src.Set(x, 61, 195)
	}

	distMap := segmentation.ChamferDistanceTransform(rawMask)
	opts := DefaultFrangiOptions()
	opts.Scales = []float32{1.5, 2.5}
	opts.EdgeMarginPx = 8.0
	opts.EdgeRampPx = 6.0

	res := MultiscaleFrangiVesselness(src, rawMask, distMap, opts)

	// 1. The vein center must have strong vesselness
	veinVal := res.At(60, 60)
	if veinVal < 50 {
		t.Errorf("Expected significant vesselness at vein center (60, 60), got %d", veinVal)
	}

	// 2. The border pixels (where distance to background <= 8) MUST have zero vesselness
	for x := 20; x <= 100; x++ {
		topVal := res.At(x, 21)
		botVal := res.At(x, 99)
		if topVal != 0 {
			t.Errorf("Expected 0 vesselness at top border (%d, 21), got %d", x, topVal)
		}
		if botVal != 0 {
			t.Errorf("Expected 0 vesselness at bottom border (%d, 99), got %d", x, botVal)
		}
	}

	for y := 20; y <= 100; y++ {
		leftVal := res.At(21, y)
		rightVal := res.At(99, y)
		if leftVal != 0 {
			t.Errorf("Expected 0 vesselness at left border (21, %d), got %d", y, leftVal)
		}
		if rightVal != 0 {
			t.Errorf("Expected 0 vesselness at right border (99, %d), got %d", y, rightVal)
		}
	}
}
