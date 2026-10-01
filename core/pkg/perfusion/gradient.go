package perfusion

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// PerfusionProfile represents the longitudinal thermal profile along the extremity axis.
type PerfusionProfile struct {
	AxisValues      []float32 `json:"axis_values"`      // Row or column index
	MeanTemperatures []float32 `json:"mean_temperatures"` // Average intensity/temp along axis
	Gradients       []float32 `json:"gradients"`        // dT/ds (rate of temperature change)
	MaxGradientDrop float32   `json:"max_gradient_drop"` // Maximum localized drop (ishemia marker)
	Status          string    `json:"status"`            // "NORMAL", "MILD_DROP", "CRITICAL_ISCHEMIA"
	Description     string    `json:"description"`
}

// ComputeLongitudinalProfile calculates the thermal gradient from proximal to distal (top to bottom).
func ComputeLongitudinalProfile(src *imageutil.GrayMatrix, mask *imageutil.GrayMatrix) PerfusionProfile {
	w, h := src.Width, src.Height
	profile := PerfusionProfile{
		AxisValues:       make([]float32, h),
		MeanTemperatures: make([]float32, h),
		Gradients:        make([]float32, h),
	}

	for y := 0; y < h; y++ {
		profile.AxisValues[y] = float32(y)
		var sum float64
		var count int
		rowOffset := y * w

		for x := 0; x < w; x++ {
			if mask != nil && mask.Data[rowOffset+x] == 0 {
				continue
			}
			sum += float64(src.Data[rowOffset+x])
			count++
		}

		if count > 0 {
			profile.MeanTemperatures[y] = float32(sum / float64(count))
		} else if y > 0 {
			profile.MeanTemperatures[y] = profile.MeanTemperatures[y-1]
		}
	}

	// Smooth profile with 5-point moving average to suppress sensor noise
	smoothed := make([]float32, h)
	for y := 0; y < h; y++ {
		var sum float32
		var cnt float32
		for k := -2; k <= 2; k++ {
			py := y + k
			if py >= 0 && py < h {
				sum += profile.MeanTemperatures[py]
				cnt++
			}
		}
		smoothed[y] = sum / cnt
	}
	profile.MeanTemperatures = smoothed

	// Compute gradients: dT/dy (finite difference)
	var maxDrop float32
	for y := 1; y < h-1; y++ {
		grad := (profile.MeanTemperatures[y+1] - profile.MeanTemperatures[y-1]) * 0.5
		profile.Gradients[y] = grad
		if -grad > maxDrop { // Drop towards distal end
			maxDrop = -grad
		}
	}
	profile.MaxGradientDrop = maxDrop

	// Clinical classification
	if maxDrop > 4.5 {
		profile.Status = "CRITICAL_ISCHEMIA"
		profile.Description = "Starker distaler Temperaturabfall detektiert. Verdacht auf signifikante Durchblutungsstörung (pAVK/Mikroangiopathie)."
	} else if maxDrop > 2.0 {
		profile.Status = "MILD_DROP"
		profile.Description = "Mäßiger Temperaturabfall im distalen Bereich. Regelmäßige Verlaufskontrolle empfohlen."
	} else {
		profile.Status = "NORMAL"
		profile.Description = "Physiologischer, homogener Temperaturverlauf ohne abrupte Durchblutungsabbrüche."
	}

	return profile
}

// ThermalRecoveryResult holds the wash-in rate between two timepoints.
type ThermalRecoveryResult struct {
	MeanWashInRate  float32 `json:"mean_wash_in_rate"` // Average delta T / dt
	HypoPerfusedArea float32 `json:"hypo_perfused_area"` // Percentage of tissue with 0 recovery
	Status          string  `json:"status"`
}

// ComputeDynamicRecovery evaluates re-warming between a baseline post-cooling image and a re-warmed image.
func ComputeDynamicRecovery(imgPre, imgPost *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, durationSec float32) ThermalRecoveryResult {
	if durationSec <= 0 {
		durationSec = 60.0
	}

	var sumWashIn float64
	var totalPixels int
	var zeroRecoveryPixels int

	for i := range imgPre.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		totalPixels++
		delta := float64(imgPost.Data[i]) - float64(imgPre.Data[i])
		rate := delta / float64(durationSec)
		sumWashIn += rate

		if delta <= 0 {
			zeroRecoveryPixels++
		}
	}

	if totalPixels == 0 {
		return ThermalRecoveryResult{Status: "NO_TISSUE_DETECTED"}
	}

	meanRate := float32(sumWashIn / float64(totalPixels))
	hypoFrac := float32(zeroRecoveryPixels) / float32(totalPixels) * 100.0

	res := ThermalRecoveryResult{
		MeanWashInRate:   meanRate,
		HypoPerfusedArea: float32(math.Round(float64(hypoFrac)*10) / 10),
	}

	if hypoFrac > 25.0 {
		res.Status = "DELAYED_RECOVERY_CRITICAL"
	} else if hypoFrac > 10.0 {
		res.Status = "DELAYED_RECOVERY_MILD"
	} else {
		res.Status = "RAPID_PHYSIOLOGICAL_RECOVERY"
	}

	return res
}
