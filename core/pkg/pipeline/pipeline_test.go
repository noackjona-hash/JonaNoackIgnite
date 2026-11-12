package pipeline_test

import (
	"fmt"
	"path/filepath"
	"testing"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
	"ignite-core/pkg/pipeline"
	"ignite-core/pkg/segmentation"
)

func TestBild1HotspotAssessments(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	if res.TotalHotspots == 0 {
		t.Fatalf("Expected hotspots to be detected on Bild 1, got 0")
	}

	primary := res.Hotspots[0]
	// Assert that primary hotspot is within the inflamed toe ground truth area (X: 450..600, Y: 300..450)
	if primary.Region.CenterX < 450 || primary.Region.CenterX > 600 || primary.Region.CenterY < 300 || primary.Region.CenterY > 450 {
		t.Errorf("Expected primary hotspot on the inflamed toe (X:450..600, Y:300..450), got center (%d, %d)",
			primary.Region.CenterX, primary.Region.CenterY)
	}

	t.Logf("Total confirmed hotspots: %d, OrigMedian: %.1f", len(res.Hotspots), res.Stats.OrigMedian)
	for i, h := range res.Hotspots {
		t.Logf("Spot %d: Center=(%d,%d), Area=%d, MaxVal=%d, ContraDelta=%.1f, Prominence=%.1f, EdgeGrad=%.1f, HaloDelta=%.1f, Risk=%s, Score=%.1f",
			i, h.Region.CenterX, h.Region.CenterY, h.Region.AreaPixels, h.Region.MaxVal, h.Region.ContraDelta, h.Region.LocalProminence,
			h.Region.EdgeGradient, h.Region.HaloDelta, h.Assessment.RiskLevel, h.Assessment.Score)
	}

	if res.TotalStages != 42 {
		t.Errorf("Expected TotalStages to be 42, got %d", res.TotalStages)
	}
	if len(res.Stages) != 42 {
		t.Errorf("Expected 42 stages in Stages slice, got %d", len(res.Stages))
	}

	criticalCount := 0
	for _, h := range res.Hotspots {
		if h.Assessment.RiskLevel == "CRITICAL" {
			criticalCount++
		}
	}
	if criticalCount != 1 {
		t.Errorf("Expected EXACTLY 1 critical hotspot (inflamed toe), got %d critical hotspots", criticalCount)
	}

	if primary.Assessment.RiskLevel != "CRITICAL" {
		t.Errorf("Expected primary hotspot risk to be CRITICAL, got %s", primary.Assessment.RiskLevel)
	}
}

func Test42PipelineStagesIntegrity(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	if len(res.Stages) != 42 {
		t.Fatalf("Expected 42 stages, got %d", len(res.Stages))
	}

	phaseCounts := make(map[int]int)
	for i, s := range res.Stages {
		if s.StageNumber != i+1 {
			t.Errorf("Stage index mismatch: expected stage %d, got %d", i+1, s.StageNumber)
		}
		phaseCounts[s.PhaseNumber]++
		t.Logf("[%02d/42] Phase %d: %s -> %s (%d µs)",
			s.StageNumber, s.PhaseNumber, s.Name, s.Status, s.DurationUs)
	}

	for p := 1; p <= 7; p++ {
		if phaseCounts[p] != 6 {
			t.Errorf("Phase %d expected 6 stages, got %d", p, phaseCounts[p])
		}
	}
}

func TestInspectLocalNeighborhood(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	for i, h := range res.Hotspots {
		bb := h.Region.BoundingBox
		x0 := bb[0] - 25
		if x0 < 0 { x0 = 0 }
		y0 := bb[1] - 25
		if y0 < 0 { y0 = 0 }
		x1 := bb[2] + 25
		if x1 >= gray.Width { x1 = gray.Width - 1 }
		y1 := bb[3] + 25
		if y1 >= gray.Height { y1 = gray.Height - 1 }

		var vals []int
		for y := y0; y <= y1; y++ {
			for x := x0; x <= x1; x++ {
				if x >= bb[0] && x <= bb[2] && y >= bb[1] && y <= bb[3] {
					continue
				}
				if res.BodyMask.At(x, y) > 0 {
					vals = append(vals, int(gray.At(x, y)))
				}
			}
		}

		surroundMed := 0
		if len(vals) > 0 {
			// calculate median
			for a := 0; a < len(vals)-1; a++ {
				for b := a + 1; b < len(vals); b++ {
					if vals[a] > vals[b] {
						vals[a], vals[b] = vals[b], vals[a]
					}
				}
			}
			surroundMed = vals[len(vals)/2]
		}
		prom := int(h.Region.MaxVal) - surroundMed
		thVal := res.TopHatDiff.At(h.Region.CenterX, h.Region.CenterY)
		t.Logf("Spot %d: Center=(%d, %d), Area=%d, MaxVal=%d, TopHatVal=%d, SurroundMed=%d, Prominence=%d, BBox=%v",
			i, h.Region.CenterX, h.Region.CenterY, h.Region.AreaPixels, h.Region.MaxVal, thVal, surroundMed, prom, bb)
	}
}

func TestPrintAsciiThermal(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}
	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	// Sample grid across image: 15 rows x 20 cols
	stepX := gray.Width / 20
	stepY := gray.Height / 15
	t.Logf("--- 2D Thermal Sampling (Values/10) ---")
	for row := 0; row < 15; row++ {
		line := ""
		for col := 0; col < 20; col++ {
			x := col * stepX
			y := row * stepY
			v := gray.At(x, y)
			isMask := res.BodyMask.At(x, y) > 0
			if !isMask {
				line += " . "
			} else {
				line += fmt.Sprintf("%2d ", v/10)
			}
		}
		t.Logf("Y=%4d: %s", row*stepY, line)
	}
}

func TestGeodesicMaskedTopHat(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	// Separable boundary-clamped Top-Hat test
	clamped := gray.Clone()
	w, h := gray.Width, gray.Height
	mask := res.BodyMask

	// Horizontal row clamp
	for y := 0; y < h; y++ {
		row := y * w
		firstX, lastX := -1, -1
		for x := 0; x < w; x++ {
			if mask.Data[row+x] > 0 {
				if firstX == -1 {
					firstX = x
				}
				lastX = x
			}
		}
		if firstX != -1 {
			firstVal := gray.Data[row+firstX]
			lastVal := gray.Data[row+lastX]
			for x := 0; x < firstX; x++ {
				clamped.Data[row+x] = firstVal
			}
			for x := lastX + 1; x < w; x++ {
				clamped.Data[row+x] = lastVal
			}
		}
	}

	radius := 54
	thClamped := morphology.TopHat(clamped, radius)
	t.Logf("Clamped Top-Hat at Toe (520, 367): %d", thClamped.At(520, 367))
	t.Logf("Clamped Top-Hat at Calf (210, 820): %d", thClamped.At(210, 820))
	t.Logf("Clamped Top-Hat at Calf (1209, 808): %d", thClamped.At(1209, 808))
}

func TestInspectDistMap(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	rawMask := segmentation.SegmentBodyMask(gray)
	distMap := segmentation.ChamferDistanceTransform(rawMask)

	for i, h := range res.Hotspots {
		cx, cy := h.Region.CenterX, h.Region.CenterY
		distCenter := distMap.At(cx, cy)
		t.Logf("Spot %d: Center=(%d,%d), Area=%d, MaxVal=%d, LocalProm=%.1f, LocalMed=%.1f, Dist=%.1f, EdgeGrad=%.1f, HaloDelta=%.1f, Risk=%s, Score=%.1f",
			i, cx, cy, h.Region.AreaPixels, h.Region.MaxVal, h.Region.LocalProminence, h.Region.LocalSurroundMed,
			distCenter, h.Region.EdgeGradient, h.Region.HaloDelta, h.Assessment.RiskLevel, h.Assessment.Score)
	}
}

func TestEvaluateAllImages(t *testing.T) {
	for i := 1; i <= 21; i++ {
		imgPath := filepath.Join("..", "..", "..", "test-data", fmt.Sprintf("bild (%d).jpeg", i))
		gray, err := imageutil.LoadImageAsGray(imgPath)
		if err != nil {
			t.Logf("Skip bild (%d): %v", i, err)
			continue
		}
		cfg := pipeline.DefaultPipelineConfig()
		res := pipeline.Run(gray, cfg)
		t.Logf("=== BILD %d (%dx%d, Med=%.1f) -> Hotspots: %d ===", i, gray.Width, gray.Height, res.Stats.OrigMedian, len(res.Hotspots))
		for j, h := range res.Hotspots {
			r := h.Region
			a := h.Assessment
			t.Logf("  [%d] Box=[%d,%d..%d,%d] Center=(%d,%d) Max=%d ContraDelta=%.1f Prom=%.1f EdgeGrad=%.1f Area=%d Risk=%s Label=%s",
				j, r.BoundingBox[0], r.BoundingBox[1], r.BoundingBox[2], r.BoundingBox[3],
				r.CenterX, r.CenterY, r.MaxVal, r.ContraDelta, r.LocalProminence, r.EdgeGradient, r.AreaPixels,
				a.RiskLevel, a.DiagnosisType)
		}
	}
}

func TestInspectBild20(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (20).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load bild (20): %v", err)
	}
	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	t.Logf("Bild 20 Result: %d hotspots, stats: origMedian=%.1f",
		len(res.Hotspots), res.Stats.OrigMedian)

	// Find X bounding range of bodyMask
	minX, maxX, minY, maxY := 1440, 0, 1080, 0
	for y := 0; y < gray.Height; y++ {
		for x := 0; x < gray.Width; x++ {
			if res.BodyMask.At(x, y) > 0 {
				if x < minX { minX = x }
				if x > maxX { maxX = x }
				if y < minY { minY = y }
				if y > maxY { maxY = y }
			}
		}
	}
	t.Logf("Total BodyMask bounding box: [%d, %d .. %d, %d]", minX, minY, maxX, maxY)

	// Sample column sums every 50 pixels
	var colSummary string
	for x := 0; x < gray.Width; x += 100 {
		sum := 0
		for y := 0; y < gray.Height; y++ {
			if res.BodyMask.At(x, y) > 0 {
				sum++
			}
		}
		colSummary += fmt.Sprintf("X%d:%d ", x, sum)
	}
	t.Logf("Col density: %s", colSummary)



	for j, h := range res.Hotspots {
		r := h.Region
		a := h.Assessment
		t.Logf("Spot %d: Box=%v Center=(%d,%d) Max=%d ContraDelta=%.1f Prom=%.1f EdgeGrad=%.1f Area=%d Status=%s Risk=%s Label=%s",
			j, r.BoundingBox, r.CenterX, r.CenterY, r.MaxVal, r.ContraDelta, r.LocalProminence, r.EdgeGradient, r.AreaPixels,
			r.Status, a.RiskLevel, a.DiagnosisType)

		// Check what is at mirrored coordinates
		contraX := gray.Width - 1 - r.CenterX
		contraY := r.CenterY
		maskVal := uint8(0)
		rawVal := uint8(0)
		if res.BodyMask != nil && contraX >= 0 && contraX < gray.Width && contraY >= 0 && contraY < gray.Height {
			maskVal = res.BodyMask.At(contraX, contraY)
			rawVal = gray.At(contraX, contraY)
		}
		t.Logf("  Mirrored coords across W/2: (%d,%d), MaskVal=%d, RawVal=%d",
			contraX, contraY, maskVal, rawVal)
	}
}

func TestGroundTruthValidation(t *testing.T) {
	gtIndices := []int{1, 10, 11, 12, 13, 14, 15, 16, 17}
	var sumDice, sumIoU, sumSens, sumPrec, sumMs float64
	var validCount int

	for _, idx := range gtIndices {
		imgPath := filepath.Join("..", "..", "..", "test-data", fmt.Sprintf("bild (%d).jpeg", idx))
		gtPath := filepath.Join("..", "..", "..", "test-data", "ground_truth", fmt.Sprintf("bild (%d).png", idx))

		gray, err := imageutil.LoadImageAsGray(imgPath)
		if err != nil {
			t.Fatalf("Failed to load image %d: %v", idx, err)
		}
		gt, err := imageutil.LoadImageAsGray(gtPath)
		if err != nil {
			t.Fatalf("Failed to load gt %d: %v", idx, err)
		}

		cfg := pipeline.DefaultPipelineConfig()
		res := pipeline.Run(gray, cfg)

		var tp, fp, fn int
		var fnNoBodyMask, fnCoolOrig, fnBboxCap int
		n := len(res.HotspotMask.Data)
		for i := 0; i < n; i++ {
			pred := res.HotspotMask.Data[i] > 127
			truth := gt.Data[i] > 127
			if pred && truth {
				tp++
			} else if pred && !truth {
				fp++
			} else if !pred && truth {
				fn++
				if res.BodyMask.Data[i] == 0 {
					fnNoBodyMask++
				} else if gray.Data[i] < 180 {
					fnCoolOrig++
				} else {
					fnBboxCap++
				}
			}
		}

		dice := 0.0
		if 2*tp+fp+fn > 0 {
			dice = float64(2*tp) / float64(2*tp+fp+fn)
		}
		iou := 0.0
		if tp+fp+fn > 0 {
			iou = float64(tp) / float64(tp+fp+fn)
		}
		sens := 0.0
		if tp+fn > 0 {
			sens = float64(tp) / float64(tp+fn)
		}
		prec := 0.0
		if tp+fp > 0 {
			prec = float64(tp) / float64(tp+fp)
		}

		sumDice += dice
		sumIoU += iou
		sumSens += sens
		sumPrec += prec
		sumMs += res.Timing.TotalMs
		validCount++

		var spot0Info string
		if len(res.Hotspots) > 0 {
			r0 := res.Hotspots[0].Region
			spot0Info = fmt.Sprintf("Max=%d SurMed=%.1f Prom=%.1f Lap=%.1f Edge=%.1f", r0.MaxVal, r0.LocalSurroundMed, r0.LocalProminence, r0.ThermalLaplacian, r0.EdgeGradient)
		}
		t.Logf("BILD %2d | Spots=%d | Dice=%.4f | IoU=%.4f | Sens=%.4f | Prec=%.4f | TP=%d FP=%d FN=%d (noMask=%d cool=%d cap=%d) | %s | %.1f ms",
			idx, res.TotalHotspots, dice, iou, sens, prec, tp, fp, fn, fnNoBodyMask, fnCoolOrig, fnBboxCap, spot0Info, res.Timing.TotalMs)
		for hsIdx, hs := range res.Hotspots {
			if hsIdx > 0 {
				rN := hs.Region
				t.Logf("   extra[%d] Center=(%d,%d) Area=%d Max=%d SurMed=%.1f Prom=%.1f Lap=%.1f Edge=%.1f Contra=%.1f",
					hsIdx, rN.CenterX, rN.CenterY, rN.AreaPixels, rN.MaxVal, rN.LocalSurroundMed, rN.LocalProminence, rN.ThermalLaplacian, rN.EdgeGradient, rN.ContraDelta)
			}
		}
		if res.TotalHotspots != 1 {
			t.Errorf("BILD %d: expected 1 confirmed clinical hotspot, got %d", idx, res.TotalHotspots)
		}
	}

	meanDice := sumDice / float64(validCount)
	t.Logf("SUMMARY (n=%d) | MeanDice=%.4f | MeanIoU=%.4f | MeanSens=%.4f | MeanPrec=%.4f | MeanTime=%.1f ms",
		validCount, meanDice, sumIoU/float64(validCount), sumSens/float64(validCount), sumPrec/float64(validCount), sumMs/float64(validCount))
	if meanDice < 0.48 {
		t.Errorf("MeanDice regression: got %.4f, want >= 0.48", meanDice)
	}
}




