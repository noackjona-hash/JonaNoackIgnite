package reconstruction3d

import (
	"math"
	"runtime"
	"sync"

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
		AngleCompensationK: 1.2,
		DistanceFalloffK:   0.0,
		MaxCorrectionUnits: 12.0,
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

	workers := runtime.GOMAXPROCS(0)
	if workers > 8 {
		workers = 8
	}
	if workers < 1 || h < 16 {
		workers = 1
	}

	// 2. Anatomical Poisson/Ellipsoidal Surface Inflation: Z(x, y) (Parallelized)
	var wg sync.WaitGroup
	for wk := 0; wk < workers; wk++ {
		y0 := wk * h / workers
		y1 := (wk + 1) * h / workers
		if y0 >= y1 {
			continue
		}
		wg.Add(1)
		go func(yStart, yEnd int) {
			defer wg.Done()
			for y := yStart; y < yEnd; y++ {
				rowOff := y * w
				for x := 0; x < w; x++ {
					idx := rowOff + x
					if bodyMask.Data[idx] == 0 {
						depthMap.Data[idx] = 0
						cosThetaMap.Data[idx] = 1.0
						continue
					}

					var d float64
					if distMap != nil {
						d = float64(distMap.Data[idx])
					}
					u := d / maxD
					if u < 0 {
						u = 0
					} else if u > 1 {
						u = 1
					}

					// Biomechanical blended curvature profile
					oneMinusU := 1.0 - u
					curv1 := math.Sin(u * (math.Pi / 2.0))
					sqArg := 1.0 - oneMinusU*oneMinusU
					if sqArg < 0 {
						sqArg = 0
					}
					curv2 := math.Sqrt(sqArg)
					normZ := 0.5*curv1 + 0.5*curv2
					normZ = math.Pow(normZ, cfg.CurvatureExponent)

					depthMap.Data[idx] = float32(normZ * maxDepth)
				}
			}
		}(y0, y1)
	}
	wg.Wait()

	// 3. Multi-pass Poisson Laplacian Relaxation (removes sharp ridge creases for organic smoothness)
	tempDepth := imageutil.NewFloatMatrix(w, h)
	copy(tempDepth.Data, depthMap.Data)
	for iter := 0; iter < 3; iter++ {
		for wk := 0; wk < workers; wk++ {
			y0 := 1 + wk*(h-2)/workers
			y1 := 1 + (wk+1)*(h-2)/workers
			if y0 >= y1 {
				continue
			}
			wg.Add(1)
			go func(yStart, yEnd int) {
				defer wg.Done()
				for y := yStart; y < yEnd; y++ {
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
			}(y0, y1)
		}
		wg.Wait()
		copy(tempDepth.Data, depthMap.Data)
	}

	// 4. Compute 3D surface normal vector n(x, y), incidence angle, and Curvature Tensor (Parallelized)
	const nTissue = 1.34 // Refractive index of stratum corneum / skin in LWIR 8-14 µm
	const eps0 = 0.98    // Normal skin emissivity
	_ = eps0
	r0 := ((nTissue - 1.0) / (nTissue + 1.0))
	r0 *= r0
	invOneMinusR0 := 1.0 / (1.0 - r0)
	invTwoPitch := 1.0 / (2.0 * pitch)
	invPitchSq := 1.0 / (pitch * pitch)
	invFourPitchSq := 1.0 / (4.0 * pitch * pitch)
	angleScale := cfg.AngleCompensationK / 2.5
	radToDeg := 180.0 / math.Pi

	minDim := w
	if h < minDim {
		minDim = h
	}
	frameGuard := minDim / 20
	if frameGuard > 12 {
		frameGuard = 12
	}
	if frameGuard < 1 {
		frameGuard = 1
	}

	type workerStats struct {
		maxAngleDeg    float64
		edgeDeltaSum   float64
		edgeDeltaCount int
		compCount      int
		totalMeanCurv  float64
		totalGaussCurv float64
		curvPixelCount int
	}
	statsPerWorker := make([]workerStats, workers)

	for wk := 0; wk < workers; wk++ {
		y0 := wk * h / workers
		y1 := (wk + 1) * h / workers
		if y0 >= y1 {
			continue
		}
		wg.Add(1)
		go func(workerIdx, yStart, yEnd int) {
			defer wg.Done()
			var ws workerStats
			for y := yStart; y < yEnd; y++ {
				rowOff := y * w
				for x := 0; x < w; x++ {
					idx := rowOff + x
					if bodyMask.Data[idx] == 0 {
						cosThetaMap.Data[idx] = 1.0
						continue
					}

					zC := float64(depthMap.Data[idx])
					zLeft, zRight, zUp, zDown := zC, zC, zC, zC
					if x > 0 {
						zLeft = float64(depthMap.Data[idx-1])
					}
					if x < w-1 {
						zRight = float64(depthMap.Data[idx+1])
					}
					if y > 0 {
						zUp = float64(depthMap.Data[idx-w])
					}
					if y < h-1 {
						zDown = float64(depthMap.Data[idx+w])
					}

					dzdx := (zRight - zLeft) * invTwoPitch
					dzdy := (zDown - zUp) * invTwoPitch

					slopeSq := dzdx*dzdx + dzdy*dzdy
					onePlusSlopeSq := 1.0 + slopeSq
					sqrtOnePlusSlope := math.Sqrt(onePlusSlopeSq)
					cosTheta := 1.0 / sqrtOnePlusSlope
					if cosTheta < 0.15 {
						cosTheta = 0.15
					} else if cosTheta > 1.0 {
						cosTheta = 1.0
					}
					cosThetaMap.Data[idx] = float32(cosTheta)

					angleDeg := math.Acos(cosTheta) * radToDeg
					if angleDeg > ws.maxAngleDeg {
						ws.maxAngleDeg = angleDeg
					}

					// Second order spatial derivatives for Curvature Tensor
					dzdxx := (zRight - 2.0*zC + zLeft) * invPitchSq
					dzdyy := (zDown - 2.0*zC + zUp) * invPitchSq
					zDR, zUL, zDL, zUR := zC, zC, zC, zC
					if x < w-1 && y < h-1 {
						zDR = float64(depthMap.Data[idx+w+1])
					}
					if x > 0 && y > 0 {
						zUL = float64(depthMap.Data[idx-w-1])
					}
					if x > 0 && y < h-1 {
						zDL = float64(depthMap.Data[idx+w-1])
					}
					if x < w-1 && y > 0 {
						zUR = float64(depthMap.Data[idx-w+1])
					}
					dzdxy := (zDR + zUL - zDL - zUR) * invFourPitchSq

					denomK := onePlusSlopeSq * onePlusSlopeSq
					gaussK := (dzdxx*dzdyy - dzdxy*dzdxy) / denomK
					meanH := ((1.0+dzdx*dzdx)*dzdyy - 2.0*dzdx*dzdy*dzdxy + (1.0+dzdy*dzdy)*dzdxx) / (2.0 * onePlusSlopeSq * sqrtOnePlusSlope)
					meanCurvMap.Data[idx] = float32(meanH)
					gaussCurvMap.Data[idx] = float32(gaussK)

					if meanH < 0 {
						ws.totalMeanCurv -= meanH
					} else {
						ws.totalMeanCurv += meanH
					}
					if gaussK < 0 {
						ws.totalGaussCurv -= gaussK
					} else {
						ws.totalGaussCurv += gaussK
					}
					ws.curvPixelCount++

					// 5. Rigorous Fresnel LWIR Radiometric Skin Model relative to normal incidence:
					sinThetaSq := 1.0 - cosTheta*cosTheta
					if sinThetaSq < 0 {
						sinThetaSq = 0
					}
					sinThetaT := math.Sqrt(sinThetaSq) / nTissue
					cosSqT := 1.0 - sinThetaT*sinThetaT
					if cosSqT < 0 {
						cosSqT = 0
					}
					cosThetaT := math.Sqrt(cosSqT)
					rPar := (nTissue*cosTheta - cosThetaT) / (nTissue*cosTheta + cosThetaT)
					rPerp := (cosTheta - nTissue*cosThetaT) / (cosTheta + nTissue*cosThetaT)
					fresnelReflect := 0.5 * (rPar*rPar + rPerp*rPerp)
					emissivityRatio := (1.0 - fresnelReflect) * invOneMinusR0
					if emissivityRatio < 0.1 {
						emissivityRatio = 0.1
					} else if emissivityRatio > 1.0 {
						emissivityRatio = 1.0
					}

					origVal := float64(src.Data[idx])
					tAppK := 293.15 + (origVal-cfg.AmbientRaw)*0.1
					invSqrtEmiss := 1.0 / math.Sqrt(math.Sqrt(emissivityRatio))
					fresnelDeltaK := angleScale * tAppK * (invSqrtEmiss - 1.0)
					if fresnelDeltaK < 0 {
						fresnelDeltaK = 0
					}

					normZ := float64(depthMap.Data[idx]) / maxDepth
					if normZ < 0 {
						normZ = 0
					} else if normZ > 1 {
						normZ = 1
					}
					oneMinusNormZ := 1.0 - normZ
					distCompK := cfg.DistanceFalloffK * oneMinusNormZ * oneMinusNormZ
					totalDeltaK := fresnelDeltaK + distCompK

					// Guard against image-frame crop edges (cropped trousers/limbs aren't organic edges)
					edgeDist := x
					if d := w - 1 - x; d < edgeDist {
						edgeDist = d
					}
					if y < edgeDist {
						edgeDist = y
					}
					if d := h - 1 - y; d < edgeDist {
						edgeDist = d
					}
					if edgeDist < frameGuard {
						totalDeltaK *= float64(edgeDist) / float64(frameGuard)
					}

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
							ws.compCount++
						}

						// Measure edge correction for outer margin (< 15 px from border)
						if distMap != nil && distMap.Data[idx] < 15.0 {
							ws.edgeDeltaSum += totalDeltaK
							ws.edgeDeltaCount++
						}
					}
				}
			}
			statsPerWorker[workerIdx] = ws
		}(wk, y0, y1)
	}
	wg.Wait()

	var maxAngleDeg float64
	var edgeDeltaSum float64
	var edgeDeltaCount int
	var compCount int
	var totalMeanCurv float64
	var totalGaussCurv float64
	var curvPixelCount int
	for _, ws := range statsPerWorker {
		if ws.maxAngleDeg > maxAngleDeg {
			maxAngleDeg = ws.maxAngleDeg
		}
		edgeDeltaSum += ws.edgeDeltaSum
		edgeDeltaCount += ws.edgeDeltaCount
		compCount += ws.compCount
		totalMeanCurv += ws.totalMeanCurv
		totalGaussCurv += ws.totalGaussCurv
		curvPixelCount += ws.curvPixelCount
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
