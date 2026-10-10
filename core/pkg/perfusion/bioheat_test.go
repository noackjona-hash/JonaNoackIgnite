package perfusion_test

import (
	"testing"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/perfusion"
)

func TestPennesBioheatSolver(t *testing.T) {
	w, h := 100, 100
	src := imageutil.NewGrayMatrix(w, h)
	mask := imageutil.NewGrayMatrix(w, h)

	// Simulate a synthetic foot tissue disk (radius 40 px)
	cx, cy := 50, 50
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dx := float64(x - cx)
			dy := float64(y - cy)
			r := dx*dx + dy*dy
			if r <= 40*40 {
				mask.Set(x, y, 255)
				// Baseline skin temp: ~30°C (raw val ~115 for 20-42°C range)
				val := uint8(115)
				// Introduce focal inflammatory hotspot at center (r <= 8): ~37°C (raw val ~197)
				if r <= 8*8 {
					val = 197
				}
				src.Set(x, y, val)
			}
		}
	}

	res := perfusion.SolvePennesBioheatField(src, mask, 20.0, 42.0)

	if res.Width != w || res.Height != h {
		t.Errorf("Expected dimensions %dx%d, got %dx%d", w, h, res.Width, res.Height)
	}

	t.Logf("Bioheat result: Mean=%.2f, Max=%.2f, Min=%.2f, HyperaemicArea=%.1f%%, Status=%s",
		res.MeanPerfusion, res.MaxPerfusion, res.MinPerfusion, res.HyperaemicArea, res.PerfusionStatus)

	if res.MaxPerfusion <= 0 {
		t.Errorf("Expected positive max perfusion rate, got %.2f", res.MaxPerfusion)
	}

	if res.HyperaemicArea <= 0 {
		t.Errorf("Expected detected hyperaemic area around the focal inflammatory center")
	}

	if res.PerfusionStatus != "ACUTE_HYPERAEMIA" {
		t.Errorf("Expected ACUTE_HYPERAEMIA status for inflammatory focus, got %s", res.PerfusionStatus)
	}
}
