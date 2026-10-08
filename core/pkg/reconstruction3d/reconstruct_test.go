package reconstruction3d

import (
	"testing"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/segmentation"
)

func Test3DReconstructionAndEdgeCompensation(t *testing.T) {
	w, h := 100, 100
	src := imageutil.NewGrayMatrix(w, h)
	mask := imageutil.NewGrayMatrix(w, h)

	// Create a synthetic round body part (e.g. heel or foot cross-section)
	cx, cy, r := 50, 50, 40
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dx := x - cx
			dy := y - cy
			if dx*dx+dy*dy <= r*r {
				mask.Set(x, y, 255)
				// Uniform tissue temperature 120 (approx 32°C)
				src.Set(x, y, 120)
			}
		}
	}

	distMap := segmentation.ChamferDistanceTransform(mask)
	cfg := DefaultReconstructionConfig()
	cfg.AngleCompensationK = 2.5
	cfg.DistanceFalloffK = 0.5

	res := Reconstruct3DAndCompensate(src, mask, distMap, cfg)

	// 1. Verify apex/center: maximum depth and cos(theta) close to 1.0 (perpendicular)
	centerIdx := cy*w + cx
	if res.DepthMapMm.Data[centerIdx] < float32(cfg.MaxDepthMm*0.8) {
		t.Fatalf("expected central depth to approach max depth (%f mm), got %f mm", cfg.MaxDepthMm, res.DepthMapMm.Data[centerIdx])
	}
	if res.CosThetaMap.Data[centerIdx] < 0.95 {
		t.Fatalf("expected central cos(theta) near 1.0, got %f", res.CosThetaMap.Data[centerIdx])
	}

	// 2. Central compensation should be virtually 0 (less than 2 raw units)
	centerRawDiff := int(res.CorrectedImage.Data[centerIdx]) - int(src.Data[centerIdx])
	if centerRawDiff > 2 {
		t.Fatalf("expected center compensation <= 2 units, got %d", centerRawDiff)
	}

	// 3. Edge pixel (e.g. at radius 38, 2 px from border)
	edgeX, edgeY := cx+38, cy
	edgeIdx := edgeY*w + edgeX
	edgeRawDiff := int(res.CorrectedImage.Data[edgeIdx]) - int(src.Data[edgeIdx])
	if edgeRawDiff < 10 { // At least 1.0 K (10 raw units) added to compensate grazing angle!
		t.Fatalf("expected edge compensation >= 10 raw units (+1.0 K), got %d", edgeRawDiff)
	}

	if res.MeanEdgeCorrectionK <= 0.5 {
		t.Fatalf("expected mean edge correction > 0.5 K, got %f", res.MeanEdgeCorrectionK)
	}

	t.Logf("Success: 3D Apex Depth: %.1f mm, Max Angle: %.1f deg, Edge Correction: +%.2f K",
		res.MaxDepthMm, res.MaxIncidenceAngleDeg, res.MeanEdgeCorrectionK)
}
