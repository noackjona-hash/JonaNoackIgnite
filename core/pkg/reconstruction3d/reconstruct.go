package reconstruction3d

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// ReconstructionConfig sets tuning parameters for 3D surface inflation and radiometric angle compensation.
type ReconstructionConfig struct {
	MaxDepthMm         float64 // Estimated anatomical depth / curvature radius in mm (default 35.0 mm)
	CurvatureExponent  float64 // Profile curvature exponent (default 0.65 for organic inflation)
	EmissivityAlpha    float64 // Directional skin emissivity exponent (default 0.22, Ring & Ammer model)
	AngleCompensationK float64 // Max temperature compensation at grazing edges in Kelvin (default 2.5 K)
	DistanceFalloffK   float64 // Distance falloff compensation in Kelvin (default 0.5 K)
	MaxCorrectionUnits float64 // Max raw byte correction clamp (default 35 units = 3.5 K)
	AmbientRaw         float64 // Background room temperature in raw units (default 60 = 20.0°C)
	PixelPitchMm       float64 // Spatial sensor resolution in mm/pixel (default 0.6 mm)
}

// DefaultReconstructionConfig returns clinical standard parameters.
func DefaultReconstructionConfig() ReconstructionConfig {
	return ReconstructionConfig{
		MaxDepthMm:         35.0,
		CurvatureExponent:  0.65,
		EmissivityAlpha:    0.22,
		AngleCompensationK: 2.5,
		DistanceFalloffK:   0.5,
		MaxCorrectionUnits: 35.0,
		AmbientRaw:         60.0,
		PixelPitchMm:       0.6,
	}
}

// ReconstructionResult encapsulates the 3D surface geometry, curvature metrics, and angle-compensated thermography.
type ReconstructionResult struct {
	DepthMapMm            *imageutil.FloatMatrix `json:"-"`
	CosThetaMap           *imageutil.FloatMatrix `json:"-"`
	CorrectedImage        *imageutil.GrayMatrix  `json:"-"`
	CompensationDeltaK    *imageutil.FloatMatrix `json:"-"`
	MeanCurvatureMap      *imageutil.FloatMatrix `json:"-"`
	GaussianCurvatureMap  *imageutil.FloatMatrix `json:"-"`
	MaxDepthMm            float64                `json:"max_depth_mm"`
	MeanEdgeCorrectionK   float64                `json:"mean_edge_correction_k"`
	MaxIncidenceAngleDeg  float64                `json:"max_incidence_angle_deg"`
	CompensatedPixelCount int                    `json:"compensated_pixel_count"`
	MeanCurvatureMm       float64                `json:"mean_curvature_mm,omitempty"`
	GaussianCurvatureMm2  float64                `json:"gaussian_curvature_mm2,omitempty"`
}

// Reconstruct3DAndCompensate performs anatomical 3D surface reconstruction and eliminates edge-cooling artifacts.
func Reconstruct3DAndCompensate(src *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, distMap *imageutil.FloatMatrix, cfg ReconstructionConfig) ReconstructionResult {
	w, h := src.Width, src.Height
	depthMap := imageutil.NewFloatMatrix(w, h)
	cosThetaMap := imageutil.NewFloatMatrix(w, h)
	deltaKMap := imageutil.NewFloatMatrix(w, h)
	meanCurvMap := imageutil.NewFloatMatrix(w, h)
	gaussCurvMap := imageutil.NewFloatMatrix(w, h)
	corrected := imageutil.NewGrayMatrix(w, h)

	// Copy baseline
	copy(corrected.Data, src.Data)

	// 1. Find maximum Euclidean distance inside tissue to establish anatomical core ridge
	var maxDist float32
	if distMap != nil {
		for i, d := range distMap.Data {
			if bodyMask.Data[i] > 0 && d > maxDist {
				maxDist = d
			}
		}
	}
	if maxDist < 1.0 {
		maxDist = 1.0
	}

	maxD := float64(maxDist)
	maxDepth := cfg.MaxDepthMm
	pitch := cfg.PixelPitchMm
	if pitch <= 0 {
		pitch = 0.6
	}

	// 2. Anatomical Poisson/Ellipsoidal Surface Inflation: Z(x, y)
	for y := 0; y < h; y++ {
		rowOff := y * w
		for x := 0; x < w; x++ {
			idx := rowOff + x
			if bodyMask.Data[idx] == 0 {
				depthMap.Data[idx] = 0
				cosThetaMap.Data[idx] = 1.0
				continue
			}

			d := float64(0)
			if distMap != nil {
				d = float64(distMap.Data[idx])
			}
			u := math.Min(1.0, math.Max(0.0, d/maxD))

			// Biomechanical blended curvature profile
			curv1 := math.Sin(u * (math.Pi / 2.0))
			curv2 := math.Sqrt(math.Max(0.0, 1.0-math.Pow(1.0-u, 2.0)))
			normZ := 0.5*curv1 + 0.5*curv2
			normZ = math.Pow(normZ, cfg.CurvatureExponent)

			zMm := float32(normZ * maxDepth)
			depthMap.Data[idx] = zMm
		}
	}

	// 3. Multi-pass Poisson Laplacian Relaxation (removes sharp ridge creases for organic smoothness)
	tempDepth := imageutil.NewFloatMatrix(w, h)
	copy(tempDepth.Data, depthMap.Data)
	for iter := 0; iter < 3; iter++ {
		for y := 1; y < h-1; y++ {
			rowOff := y * w
			for x := 1; x < w-1; x++ {
				idx := rowOff + x
				if bodyMask.Data[idx] == 0 {
					continue
				}
				var zL, zR, zU, zD float32
				if bodyMask.Data[idx-1] > 0 {
					zL = tempDepth.Data[idx-1]
				}
				if bodyMask.Data[idx+1] > 0 {
					zR = tempDepth.Data[idx+1]
				}
				if bodyMask.Data[idx-w] > 0 {
					zU = tempDepth.Data[idx-w]
				}
				if bodyMask.Data[idx+w] > 0 {
					zD = tempDepth.Data[idx+w]
				}

				lap := 0.25*(zL+zR+zU+zD) - tempDepth.Data[idx]
				depthMap.Data[idx] = tempDepth.Data[idx] + 0.3*lap
			}
		}
		copy(tempDepth.Data, depthMap.Data)
	}

	// 4. Compute 3D surface normal vector n(x, y), incidence angle, and Curvature Tensor
	var maxAngleDeg float64
	var edgeDeltaSum float64
	var edgeDeltaCount int
	var compCount int
	var totalMeanCurv float64
	var totalGaussCurv float64
	var curvPixelCount int

	const nTissue = 1.34 // Refractive index of stratum corneum / skin in LWIR 8-14 µm
	const eps0 = 0.98    // Normal skin emissivity

	for y := 0; y < h; y++ {
		rowOff := y * w
		for x := 0; x < w; x++ {
			idx := rowOff + x
			if bodyMask.Data[idx] == 0 {
				cosThetaMap.Data[idx] = 1.0
				continue
			}

			// Spatial central differences for dZ/dx and dZ/dy
			var zLeft, zRight, zUp, zDown float64
			if x > 0 {
				zLeft = float64(depthMap.Data[idx-1])
			} else {
				zLeft = float64(depthMap.Data[idx])
			}
			if x < w-1 {
				zRight = float64(depthMap.Data[idx+1])
			} else {
				zRight = float64(depthMap.Data[idx])
			}
			if y > 0 {
				zUp = float64(depthMap.Data[idx-w])
			} else {
				zUp = float64(depthMap.Data[idx])
			}
			if y < h-1 {
				zDown = float64(depthMap.Data[idx+w])
			} else {
				zDown = float64(depthMap.Data[idx])
			}

			dzdx := (zRight - zLeft) / (2.0 * pitch)
			dzdy := (zDown - zUp) / (2.0 * pitch)

			// Normal vector: n = (-dzdx, -dzdy, 1) / sqrt(dzdx^2 + dzdy^2 + 1)
			slopeSq := dzdx*dzdx + dzdy*dzdy
			cosTheta := 1.0 / math.Sqrt(1.0+slopeSq)

			// Physical clamp [0.15, 1.0]
			cosTheta = math.Max(0.15, math.Min(1.0, cosTheta))
			cosThetaMap.Data[idx] = float32(cosTheta)

			angleDeg := math.Acos(cosTheta) * (180.0 / math.Pi)
			if angleDeg > maxAngleDeg {
				maxAngleDeg = angleDeg
			}

			// Second order spatial derivatives for Curvature Tensor
			dzdxx := (zRight - 2.0*float64(depthMap.Data[idx]) + zLeft) / (pitch * pitch)
			dzdyy := (zDown - 2.0*float64(depthMap.Data[idx]) + zUp) / (pitch * pitch)
			var zDR, zUL, zDL, zUR float64
			if x < w-1 && y < h-1 {
				zDR = float64(depthMap.Data[idx+w+1])
			} else {
				zDR = float64(depthMap.Data[idx])
			}
			if x > 0 && y > 0 {
				zUL = float64(depthMap.Data[idx-w-1])
			} else {
				zUL = float64(depthMap.Data[idx])
			}
			if x > 0 && y < h-1 {
				zDL = float64(depthMap.Data[idx+w-1])
			} else {
				zDL = float64(depthMap.Data[idx])
			}
			if x < w-1 && y > 0 {
				zUR = float64(depthMap.Data[idx-w+1])
			} else {
				zUR = float64(depthMap.Data[idx])
			}
			dzdxy := (zDR + zUL - zDL - zUR) / (4.0 * pitch * pitch)

			denomK := math.Pow(1.0+slopeSq, 2.0)
			gaussK := (dzdxx*dzdyy - dzdxy*dzdxy) / denomK
			meanH := ((1.0+dzdx*dzdx)*dzdyy - 2.0*dzdx*dzdy*dzdxy + (1.0+dzdy*dzdy)*dzdxx) / (2.0 * math.Pow(1.0+slopeSq, 1.5))
			meanCurvMap.Data[idx] = float32(meanH)
			gaussCurvMap.Data[idx] = float32(gaussK)

			totalMeanCurv += math.Abs(meanH)
			totalGaussCurv += math.Abs(gaussK)
			curvPixelCount++

			// 5. Rigorous Fresnel LWIR Radiometric Skin Model relative to normal incidence:
			sinThetaSq := math.Max(0.0, 1.0-cosTheta*cosTheta)
			sinThetaT := math.Sqrt(sinThetaSq) / nTissue
			cosThetaT := math.Sqrt(math.Max(0.0, 1.0-sinThetaT*sinThetaT))
			rPar := (nTissue*cosTheta - cosThetaT) / (nTissue*cosTheta + cosThetaT)
			rPerp := (cosTheta - nTissue*cosThetaT) / (cosTheta + nTissue*cosThetaT)
			fresnelReflect := 0.5 * (rPar*rPar + rPerp*rPerp)
			r0 := math.Pow((nTissue-1.0)/(nTissue+1.0), 2.0)
			emissivityRatio := math.Max(0.1, (1.0-fresnelReflect)/(1.0-r0))
			if emissivityRatio > 1.0 {
				emissivityRatio = 1.0
			}

			origVal := float64(src.Data[idx])
			tAppK := 293.15 + (origVal-cfg.AmbientRaw)*0.1
			fresnelDeltaK := (cfg.AngleCompensationK / 2.5) * tAppK * (math.Pow(1.0/emissivityRatio, 0.25) - 1.0)
			if fresnelDeltaK < 0 {
				fresnelDeltaK = 0
			}

			normZ := math.Min(1.0, math.Max(0.0, float64(depthMap.Data[idx])/maxDepth))
			distCompK := cfg.DistanceFalloffK * math.Pow(1.0-normZ, 2.0)
			totalDeltaK := fresnelDeltaK + distCompK

			deltaKMap.Data[idx] = float32(totalDeltaK)

			// 1 K corresponds to ~10 raw intensity units in standard medical FLIR scaling
			rawDelta := totalDeltaK * 10.0
			if rawDelta > cfg.MaxCorrectionUnits {
				rawDelta = cfg.MaxCorrectionUnits
			}

			if origVal > 20 { // only active on tissue
				newVal := origVal + rawDelta
				if newVal > 255.0 {
					newVal = 255.0
				}
				corrected.Data[idx] = uint8(math.Round(newVal))

				if rawDelta > 1.0 {
					compCount++
				}

				// Measure edge correction for outer margin (< 15 px from border)
				if distMap != nil && distMap.Data[idx] < 15.0 {
					edgeDeltaSum += totalDeltaK
					edgeDeltaCount++
				}
			}
		}
	}

	meanEdgeK := float64(0)
	if edgeDeltaCount > 0 {
		meanEdgeK = math.Round((edgeDeltaSum/float64(edgeDeltaCount))*100) / 100
	}

	meanCurvAvg := float64(0)
	gaussCurvAvg := float64(0)
	if curvPixelCount > 0 {
		meanCurvAvg = math.Round((totalMeanCurv/float64(curvPixelCount))*1000) / 1000
		gaussCurvAvg = math.Round((totalGaussCurv/float64(curvPixelCount))*10000) / 10000
	}

	return ReconstructionResult{
		DepthMapMm:            depthMap,
		CosThetaMap:           cosThetaMap,
		CorrectedImage:        corrected,
		CompensationDeltaK:    deltaKMap,
		MeanCurvatureMap:      meanCurvMap,
		GaussianCurvatureMap:  gaussCurvMap,
		MaxDepthMm:            maxDepth,
		MeanEdgeCorrectionK:   meanEdgeK,
		MaxIncidenceAngleDeg:  math.Round(maxAngleDeg*10) / 10,
		CompensatedPixelCount: compCount,
		MeanCurvatureMm:       meanCurvAvg,
		GaussianCurvatureMm2:  gaussCurvAvg,
	}
}
