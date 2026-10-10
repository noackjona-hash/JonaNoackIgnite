package perfusion

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// BioheatPerfusionMap encapsulates the quantitative microvascular perfusion rate field
// calculated via inverse solution of the 2D Pennes Bioheat Partial Differential Equation.
type BioheatPerfusionMap struct {
	Width          int                    `json:"width"`
	Height         int                    `json:"height"`
	MeanPerfusion  float64                `json:"mean_perfusion"`     // in ml / (100g * min)
	MaxPerfusion   float64                `json:"max_perfusion"`      // in ml / (100g * min)
	MinPerfusion   float64                `json:"min_perfusion"`      // in ml / (100g * min)
	HyperaemicArea float64                `json:"hyperaemic_area_pct"`// % of tissue with acute inflammatory hyperaemia (> 8.0)
	IschaemicArea  float64                `json:"ischaemic_area_pct"` // % of tissue with critical microvascular ischemia (< 1.5)
	PerfusionStatus string                `json:"perfusion_status"`   // "PHYSIOLOGICAL", "ACUTE_HYPERAEMIA", "CRITICAL_ISCHEMIA"
	Description    string                 `json:"description"`
	PerfusionField *imageutil.FloatMatrix `json:"-"`
}

// SolvePennesBioheatField solves the steady-state Pennes Bioheat Equation in 2D
// to reconstruct underlying capillary blood perfusion omega_b(x, y).
//
// Formulation:
//   k * nabla^2 T(x, y) - omega_b * rho_b * c_b * (T(x, y) - T_core) + q_metabolic - q_loss / d = 0
//
// Solving for omega_b(x, y):
//   omega_b(x, y) = [ q_loss / d - q_metabolic - k * nabla^2 T(x, y) ] / [ rho_b * c_b * (T_core - T(x, y)) ]
func SolvePennesBioheatField(src *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, tMin, tMax float64) BioheatPerfusionMap {
	w, h := src.Width, src.Height
	if tMin <= 0 {
		tMin = 20.0
	}
	if tMax <= tMin {
		tMax = 42.0
	}

	// Biophysical constants (Human dermal & subcutaneous microvasculature):
	const (
		kThermal   = 0.45       // Thermal conductivity of tissue [W / (m * K)]
		rhoBlood   = 1060.0     // Density of whole blood [kg / m^3]
		cBlood     = 3640.0     // Specific heat capacity of blood [J / (kg * K)]
		tCore      = 37.0       // Internal arterial core body temperature [°C]
		qMetabolic = 368.0      // Basal metabolic heat production [W / m^3]
		hConv      = 5.0        // Natural convective heat transfer coefficient [W / (m^2 * K)]
		tAmb       = 22.0       // Ambient examination room temperature [°C]
		emissivity = 0.98       // Dermal infrared emissivity
		sigmaSB    = 5.67037e-8 // Stefan-Boltzmann constant [W / (m^2 * K^4)]
		dSkin      = 0.002      // Effective cutaneous perfusion depth [m] (2 mm)
		pixelPitch = 0.0006     // Spatial physical pitch [m/pixel] (0.6 mm/px)
	)

	// Step 1: Convert 8-bit sensor intensity to absolute temperature matrix T(x, y) [°C]
	tempMatrix := imageutil.NewFloatMatrix(w, h)
	rangeT := tMax - tMin
	for y := 0; y < h; y++ {
		row := y * w
		for x := 0; x < w; x++ {
			rawVal := float64(src.Data[row+x])
			tempMatrix.Data[row+x] = float32(tMin + (rawVal/255.0)*rangeT)
		}
	}

	// Step 2: Compute discrete 2D Laplacian nabla^2 T in physical SI units [K / m^2]
	// nabla^2 T = [ T(x+1, y) + T(x-1, y) + T(x, y+1) + T(x, y-1) - 4*T(x,y) ] / dx^2
	dx2 := pixelPitch * pixelPitch
	perfField := imageutil.NewFloatMatrix(w, h)

	var (
		sumPerf        float64
		tissueCount    int
		hyperaemicCnt  int
		ischaemicCnt   int
		maxPerf        = -1e9
		minPerf        = 1e9
	)

	for y := 1; y < h-1; y++ {
		row := y * w
		for x := 1; x < w; x++ {
			p := row + x
			if bodyMask != nil && bodyMask.Data[p] == 0 {
				continue
			}

			tc := float64(tempMatrix.Data[p])
			if tc <= tMin+1.0 {
				continue
			}

			// 2D discrete Laplacian (4-neighbor stencil)
			tL := float64(tempMatrix.Data[row+x-1])
			tR := float64(tempMatrix.Data[row+x+1])
			tT := float64(tempMatrix.Data[(y-1)*w+x])
			tB := float64(tempMatrix.Data[(y+1)*w+x])
			laplacianSI := (tL + tR + tT + tB - 4.0*tc) / dx2

			// Surface thermal losses: Convective + Stefan-Boltzmann radiative
			tKelvin := tc + 273.15
			tAmbKelvin := tAmb + 273.15
			qConv := hConv * (tc - tAmb)
			qRad := emissivity * sigmaSB * (math.Pow(tKelvin, 4) - math.Pow(tAmbKelvin, 4))
			qLossTotal := (qConv + qRad) / dSkin // Volumetric equivalent [W / m^3]

			// Driving temperature gradient from core to skin:
			deltaTCore := tCore - tc
			if deltaTCore < 0.5 {
				deltaTCore = 0.5 // Clamp near body core
			}

			// Solve for capillary perfusion rate omega_b [1 / s]:
			// omega_b = (qLossTotal - qMetabolic - kThermal * laplacianSI) / (rhoBlood * cBlood * deltaTCore)
			numerator := qLossTotal - qMetabolic - (kThermal * laplacianSI)
			denominator := rhoBlood * cBlood * deltaTCore
			omegaSI := numerator / denominator
			if omegaSI < 0.0 {
				omegaSI = 0.0
			}

			// Convert SI [1/s] to clinical medicine standard: [ml / (100g * min)]
			// omega_clinical = omega_SI * (100 g / rho_tissue) * 60 s * 1000 ml/kg
			// With rho_tissue ~ 1000 kg/m^3: factor is approx. 6000.0
			omegaClinical := omegaSI * 6000.0
			if omegaClinical > 50.0 {
				omegaClinical = 50.0 // Biophysical upper limit of cutaneous vasodilation
			}

			perfField.Data[p] = float32(omegaClinical)
			sumPerf += omegaClinical
			tissueCount++

			if omegaClinical > maxPerf {
				maxPerf = omegaClinical
			}
			if omegaClinical < minPerf {
				minPerf = omegaClinical
			}

			if omegaClinical >= 8.0 {
				hyperaemicCnt++
			} else if omegaClinical < 1.5 {
				ischaemicCnt++
			}
		}
	}

	result := BioheatPerfusionMap{
		Width:          w,
		Height:         h,
		PerfusionField: perfField,
	}

	if tissueCount > 0 {
		mean := sumPerf / float64(tissueCount)
		result.MeanPerfusion = math.Round(mean*100) / 100
		result.MaxPerfusion = math.Round(maxPerf*100) / 100
		result.MinPerfusion = math.Round(minPerf*100) / 100
		result.HyperaemicArea = math.Round((float64(hyperaemicCnt)/float64(tissueCount))*1000) / 10
		result.IschaemicArea = math.Round((float64(ischaemicCnt)/float64(tissueCount))*1000) / 10

		if result.HyperaemicArea > 5.0 {
			result.PerfusionStatus = "ACUTE_HYPERAEMIA"
			result.Description = "Signifikante mikrovaskuläre Hyperämie (akute entzündliche Perfusionserhöhung im Angiosom)."
		} else if result.IschaemicArea > 20.0 {
			result.PerfusionStatus = "CRITICAL_ISCHEMIA"
			result.Description = "Kritische distale Hypoperfusion. V.a. schwere mikrozirkulatorische Minderdurchblutung (pAVK/Mönckeberg)."
		} else {
			result.PerfusionStatus = "PHYSIOLOGICAL"
			result.Description = "Physiologisches dermales Perfusionsmuster im Normbereich (1.5 - 6.0 ml/100g/min)."
		}
	} else {
		result.PerfusionStatus = "NO_TISSUE"
		result.Description = "Keine vitalen Gewebepixel segmentiert."
	}

	return result
}
