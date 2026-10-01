package symmetry

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// SymmetryZone represents an anatomical zone with bilateral comparison metrics.
type SymmetryZone struct {
	Name         string  `json:"name"`
	LeftMean     float32 `json:"left_mean"`
	RightMean    float32 `json:"right_mean"`
	DeltaT       float32 `json:"delta_t"` // |Left - Right|
	Status       string  `json:"status"`  // "NORMAL", "BORDERLINE", "CRITICAL_INFLAMMATION"
	IsPathologic bool    `json:"is_pathologic"`
}

// BilateralResult contains the full bilateral symmetry analysis.
type BilateralResult struct {
	DifferenceMap *imageutil.GrayMatrix `json:"-"`
	MaxDeltaT     float32               `json:"max_delta_t"`
	MeanDeltaT    float32               `json:"mean_delta_t"`
	Zones         []SymmetryZone        `json:"zones"`
	OverallStatus string                `json:"overall_status"`
	ClinicalAssessment string           `json:"clinical_assessment"`
}

// MirrorHorizontal flips an image horizontally (useful for contralateral limb alignment).
func MirrorHorizontal(src *imageutil.GrayMatrix) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewGrayMatrix(w, h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			dst.Set(w-1-x, y, src.At(x, y))
		}
	}
	return dst
}

// AnalyzeBilateralSymmetry compares left and right limbs (either two separate images or left/right halves).
// deltaTThreshold (e.g. 2.2 K in real radiometric units or ~15-20 in 8-bit scale).
func AnalyzeBilateralSymmetry(leftImg, rightImg *imageutil.GrayMatrix, leftMask, rightMask *imageutil.GrayMatrix, thresholdDeltaT float32) BilateralResult {
	w, h := leftImg.Width, leftImg.Height
	rightMirrored := MirrorHorizontal(rightImg)
	var rightMaskMirrored *imageutil.GrayMatrix
	if rightMask != nil {
		rightMaskMirrored = MirrorHorizontal(rightMask)
	}

	diffMap := imageutil.NewGrayMatrix(w, h)
	var sumDelta float64
	var maxDelta float32
	var validPixels int

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := y*w + x
			if leftMask != nil && leftMask.Data[idx] == 0 {
				continue
			}
			if rightMaskMirrored != nil && rightMaskMirrored.Data[idx] == 0 {
				continue
			}

			valL := float32(leftImg.Data[idx])
			valR := float32(rightMirrored.Data[idx])
			diff := float32(math.Abs(float64(valL - valR)))

			if diff > maxDelta {
				maxDelta = diff
			}
			sumDelta += float64(diff)
			validPixels++

			// Scale diff into 8-bit display map
			scaled := uint8(math.Min(255, float64(diff*3.0)))
			diffMap.Data[idx] = scaled
		}
	}

	meanDelta := float32(0)
	if validPixels > 0 {
		meanDelta = float32(sumDelta / float64(validPixels))
	}

	// Anatomical zonal analysis (Heel: 0-25% height, Midfoot: 25-60%, Forefoot/Toes: 60-100%)
	zoneDefs := []struct {
		name string
		y0   float64
		y1   float64
	}{
		{"Ferse (Kalkaneus)", 0.0, 0.25},
		{"Mittelfuß & Fußgewölbe", 0.25, 0.60},
		{"Vorfuß & Mittelfußköpfchen", 0.60, 0.85},
		{"Zehen & Hallux", 0.85, 1.0},
	}

	zones := make([]SymmetryZone, 0, len(zoneDefs))
	var hasCriticalZone bool

	for _, zd := range zoneDefs {
		r0 := int(float64(h) * zd.y0)
		r1 := int(float64(h) * zd.y1)
		if r1 > h {
			r1 = h
		}

		var sumL, sumR float64
		var cntL, cntR int

		for y := r0; y < r1; y++ {
			for x := 0; x < w; x++ {
				idx := y*w + x
				if leftMask == nil || leftMask.Data[idx] > 0 {
					sumL += float64(leftImg.Data[idx])
					cntL++
				}
				if rightMaskMirrored == nil || rightMaskMirrored.Data[idx] > 0 {
					sumR += float64(rightMirrored.Data[idx])
					cntR++
				}
			}
		}

		meanL := float32(0)
		if cntL > 0 {
			meanL = float32(sumL / float64(cntL))
		}
		meanR := float32(0)
		if cntR > 0 {
			meanR = float32(sumR / float64(cntR))
		}

		zoneDelta := float32(math.Abs(float64(meanL - meanR)))
		status := "NORMAL"
		isPath := false

		if zoneDelta >= thresholdDeltaT {
			status = "CRITICAL_INFLAMMATION"
			isPath = true
			hasCriticalZone = true
		} else if zoneDelta >= thresholdDeltaT*0.6 {
			status = "BORDERLINE"
		}

		zones = append(zones, SymmetryZone{
			Name:         zd.name,
			LeftMean:     meanL,
			RightMean:    meanR,
			DeltaT:       zoneDelta,
			Status:       status,
			IsPathologic: isPath,
		})
	}

	result := BilateralResult{
		DifferenceMap: diffMap,
		MaxDeltaT:     maxDelta,
		MeanDeltaT:    meanDelta,
		Zones:         zones,
	}

	if hasCriticalZone || maxDelta >= thresholdDeltaT*1.5 {
		result.OverallStatus = "PATHOLOGICAL_ASYMMETRY"
		result.ClinicalAssessment = "Fokale thermische Asymmetrie (ΔT >= 2.2 K). Signifikanter Verdacht auf unilaterale Entzündung / Vorstufe diabetisches Fußulkus nach Armstrong-Kriterien."
	} else if maxDelta >= thresholdDeltaT*0.8 {
		result.OverallStatus = "MILD_ASYMMETRY"
		result.ClinicalAssessment = "Leichte Asymmetrie nachgewiesen. Kontrolle nach 48 Stunden empfohlen."
	} else {
		result.OverallStatus = "SYMMETRIC_BENIGN"
		result.ClinicalAssessment = "Beidseitig symmetrischer Befund. Etwaige Erwärmungen sind physiologisch / mechanisch bedingt (z. B. Belastung oder Socken) und stellen keine fokale Entzündung dar."
	}

	return result
}
