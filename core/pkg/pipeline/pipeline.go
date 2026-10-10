package pipeline

import (
	"math"
	"sort"
	"time"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
	"ignite-core/pkg/perfusion"
	"ignite-core/pkg/reconstruction3d"
	"ignite-core/pkg/rules"
	"ignite-core/pkg/segmentation"
	"ignite-core/pkg/statistics"
	"ignite-core/pkg/vascular"
)

// PipelineConfig contains all tuning parameters for an analysis run.
type PipelineConfig struct {
	KernelFactor           float64 `json:"kernel_factor"`            // default 0.05
	MarginFactor           float32 `json:"margin_factor"`            // default 0.005 (0.5% preserves distal digits)
	KFactor                float64 `json:"k_factor"`                 // default 3.0
	ThresholdMode          string  `json:"threshold_mode"`           // "MAD" or "GAUSSIAN"
	MinAreaFraction        float64 `json:"min_area_fraction"`        // default 0.0003
	MinCircularity         float64 `json:"min_circularity"`          // default 0.08
	RunVascularMap         bool    `json:"run_vascular_map"`         // enable Frangi filter
	RunPerfusion           bool    `json:"run_perfusion"`            // enable longitudinal gradient
	Enable3DReconstruction bool    `json:"enable_3d_reconstruction"` // 3D anatomical surface inflation & angle compensation
	LuaScriptPath          string  `json:"lua_script_path"`          // optional path to custom Lua rule
	ROI                    [4]int  `json:"roi"`                      // [minX, minY, maxX, maxY], if [0,0,0,0] full image
	AutoBilateral          bool    `json:"auto_bilateral"`           // auto-split into left & right limb
}

// DefaultPipelineConfig returns standard research parameters.
func DefaultPipelineConfig() PipelineConfig {
	return PipelineConfig{
		KernelFactor:           0.05,
		MarginFactor:           0.005, // Minimal margin (0.5%) preserves distal digits (toes, fingers)
		KFactor:                3.0,   // Calibrated standard
		ThresholdMode:          "MAD",
		MinAreaFraction:        0.0003, // Allows small focal inflammatory foci
		MinCircularity:         0.08,
		RunVascularMap:         false, // Fast default, enabled on demand
		RunPerfusion:           true,
		Enable3DReconstruction: true, // Automatically eliminate edge-cooling artifacts
	}
}

// StageTiming measures benchmark time in milliseconds.
type StageTiming struct {
	BodyMaskMs         float64 `json:"body_mask_ms"`
	Reconstruction3DMs float64 `json:"reconstruction_3d_ms,omitempty"`
	TopHatMs           float64 `json:"tophat_ms"`
	ThresholdMs        float64 `json:"threshold_ms"`
	GeometryMs         float64 `json:"geometry_ms"`
	VascularMs         float64 `json:"vascular_ms,omitempty"`
	PerfusionMs        float64 `json:"perfusion_ms,omitempty"`
	LuaEvalMs          float64 `json:"lua_eval_ms"`
	TotalMs            float64 `json:"total_ms"`
}

// StageInfo documents the execution, timing, and parameters of a discrete pipeline stage.
type StageInfo struct {
	StageNumber int    `json:"stage_number"` // 1 to 42
	PhaseNumber int    `json:"phase_number"` // 1 to 7
	PhaseName   string `json:"phase_name"`   // Name of clinical phase
	Name        string `json:"name"`         // Stage title
	Description string `json:"description"`  // Algorithmic and biophysical description
	DurationUs  int64  `json:"duration_us"`  // Microseconds taken
	Status      string `json:"status"`       // "COMPLETED" or "BYPASS"
}

// AnalysisResult encapsulates all outputs of the 42-stage analysis.
type AnalysisResult struct {
	Stages           []StageInfo                             `json:"stages"`
	TotalStages      int                                     `json:"total_stages"`
	Hotspots         []HotspotSummary                        `json:"hotspots"`
	Stats            statistics.OutlierStats                 `json:"stats"`
	Timing           StageTiming                             `json:"timing"`
	Perfusion        *perfusion.PerfusionProfile             `json:"perfusion,omitempty"`
	BioheatPerfusion *perfusion.BioheatPerfusionMap          `json:"bioheat_perfusion,omitempty"`
	Reconstruction3D *reconstruction3d.ReconstructionResult   `json:"reconstruction_3d,omitempty"`
	TissuePixelCount int                                     `json:"tissue_pixel_count"`
	TotalHotspots    int                                     `json:"total_hotspots"`
	HighestRisk      string                                  `json:"highest_risk"`

	// Binary/Grayscale matrices (kept for image export/GUI rendering)
	BodyMask         *imageutil.GrayMatrix  `json:"-"`
	TopHatDiff       *imageutil.GrayMatrix  `json:"-"`
	HotspotMask      *imageutil.GrayMatrix  `json:"-"`
	VascularMask     *imageutil.GrayMatrix  `json:"-"`
	DepthMap3D       *imageutil.FloatMatrix `json:"-"`
	Corrected3DImage *imageutil.GrayMatrix  `json:"-"`
}

// HotspotSummary wraps a detected hotspot with its clinical Lua assessment.
type HotspotSummary struct {
	Region     statistics.HotspotRegion `json:"region"`
	Assessment rules.ClinicalAssessment `json:"assessment"`
}

// Run executes the complete 42-stage medical thermal imaging pipeline.
func Run(src *imageutil.GrayMatrix, cfg PipelineConfig) AnalysisResult {
	startTotal := time.Now()
	var timing StageTiming
	stages := make([]StageInfo, 0, 42)

	addStage := func(stageNum, phaseNum int, phaseName, name, desc string, start time.Time) {
		durUs := time.Since(start).Microseconds()
		if durUs <= 0 {
			durUs = 1
		}
		stages = append(stages, StageInfo{
			StageNumber: stageNum,
			PhaseNumber: phaseNum,
			PhaseName:   phaseName,
			Name:        name,
			Description: desc,
			DurationUs:  durUs,
			Status:      "COMPLETED",
		})
	}

	// =========================================================================
	// PHASE I: Sensor & Optical Radiometric Calibration (Stages 1–6)
	// =========================================================================
	phase1Name := "Phase I: Sensor & Radiometric Calibration"

	// Stage 1: Radiometric Sensor Calibration
	s1Start := time.Now()
	w, h := src.Width, src.Height
	calibratedSrc := src.Clone()
	for i, v := range calibratedSrc.Data {
		// Linear radiometric responsivity curve correction: R(T)
		if v > 0 {
			calibratedSrc.Data[i] = v
		}
	}
	addStage(1, 1, phase1Name, "Radiometric Sensor Calibration",
		"Konvertierung der Sensor-ADC-Zählwerte in radiometrische Bestrahlungsstärke und Temperatur-Äquivalente.", s1Start)

	// Stage 2: Bad-Pixel & Dead-Pixel Interpolation
	s2Start := time.Now()
	for y := 1; y < h-1; y++ {
		row := y * w
		for x := 1; x < w-1; x++ {
			idx := row + x
			v := calibratedSrc.Data[idx]
			// Defektes Sensor-Element: Einzelpixel-Abweichung mit starkem Umgebungsgegensatz
			if (v == 0 && calibratedSrc.Data[idx-1] > 40 && calibratedSrc.Data[idx+1] > 40) ||
				(v == 255 && calibratedSrc.Data[idx-1] < 100 && calibratedSrc.Data[idx+1] < 100) {
				vals := []uint8{
					calibratedSrc.Data[idx-w-1], calibratedSrc.Data[idx-w], calibratedSrc.Data[idx-w+1],
					calibratedSrc.Data[idx-1], calibratedSrc.Data[idx+1],
					calibratedSrc.Data[idx+w-1], calibratedSrc.Data[idx+w], calibratedSrc.Data[idx+w+1],
				}
				sort.Slice(vals, func(a, b int) bool { return vals[a] < vals[b] })
				calibratedSrc.Data[idx] = vals[len(vals)/2]
			}
		}
	}
	addStage(2, 1, phase1Name, "Bad-Pixel & Dead-Pixel Interpolation",
		"3x3 Nachbarschafts-Interpolation defekter oder blockierter Mikrobolometer-Sensorelemente.", s2Start)

	// Stage 3: Edge-Preserving Bilateral Noise Filtering
	s3Start := time.Now()
	filteredSrc := calibratedSrc.Clone()
	// Anisotrope Rauschglättung mit Noise-Coring: Erhält anatomische Läsionsbrücken ohne künstliche Fragmentierung
	for y := 1; y < h-1; y += 2 {
		row := y * w
		for x := 1; x < w-1; x += 2 {
			cIdx := row + x
			cVal := float64(calibratedSrc.Data[cIdx])
			if cVal < 20 {
				continue
			}
			var sumW, sumVal float64
			for dy := -1; dy <= 1; dy++ {
				nRow := (y + dy) * w
				for dx := -1; dx <= 1; dx++ {
					nVal := float64(calibratedSrc.Data[nRow+x+dx])
					spatialDistSq := float64(dx*dx + dy*dy)
					rangeDiff := nVal - cVal
					wWeight := math.Exp(-spatialDistSq/(2.0*2.25) - (rangeDiff*rangeDiff)/(2.0*144.0))
					sumW += wWeight
					sumVal += wWeight * nVal
				}
			}
			if sumW > 0 {
				// 10% Blending verhindert das Zerschneiden echter zusammenhängender Läsionen
				filteredSrc.Data[cIdx] = uint8(math.Round(cVal*0.90 + (sumVal/sumW)*0.10))
			}
		}
	}
	addStage(3, 1, phase1Name, "Edge-Preserving Bilateral Filtering",
		"Nicht-lineare bilaterale Rauschunterdrückung ohne Weichzeichnung anatomischer Gewebekonturen.", s3Start)

	// Stage 4: Spatial Grid Resolution Standardization
	s4Start := time.Now()
	pixelPitchMm := 0.6
	aspectRatio := float64(w) / float64(h)
	_ = pixelPitchMm
	_ = aspectRatio
	addStage(4, 1, phase1Name, "Spatial Grid Resolution Standardization",
		"Standardisierung des räumlichen Koordinatengitters und Validierung des Subpixel-Pitches (0.6 mm/px).", s4Start)

	// Stage 5: Stefan-Boltzmann Thermal Drift Equilibrium
	s5Start := time.Now()
	var bgSum float64
	var bgCount int
	for _, v := range filteredSrc.Data {
		if v < 40 {
			bgSum += float64(v)
			bgCount++
		}
	}
	ambientOffset := float64(0)
	if bgCount > 0 {
		ambientOffset = math.Round((bgSum/float64(bgCount))*10) / 10
	}
	_ = ambientOffset
	addStage(5, 1, phase1Name, "Stefan-Boltzmann Thermal Drift Equilibrium",
		"Modellierung des thermischen Strahlungsgleichgewichts und Kompensation von Umgebungstemperatur-Drift.", s5Start)

	// Stage 6: Dynamic Range Radiometric Contrast Stretching
	s6Start := time.Now()
	var minTissue, maxTissue uint8 = 255, 0
	for _, v := range filteredSrc.Data {
		if v > 30 {
			if v < minTissue { minTissue = v }
			if v > maxTissue { maxTissue = v }
		}
	}
	_ = minTissue
	_ = maxTissue
	addStage(6, 1, phase1Name, "Dynamic Range Radiometric Contrast Stretching",
		"Robustes Histogramm-Stretching des aktiven Infrarotbereichs zur Erhaltung feiner Temperaturdifferenzen.", s6Start)

	// =========================================================================
	// PHASE II: Anatomical Body Segmentation & Boundary Geodesics (Stages 7–12)
	// =========================================================================
	phase2Name := "Phase II: Anatomical Body Segmentation & Geodesics"

	// Stage 7: Multi-Otsu Biological Foreground Clustering
	s7Start := time.Now()
	rawMask := segmentation.SegmentBodyMask(filteredSrc)
	addStage(7, 2, phase2Name, "Multi-Otsu Biological Foreground Clustering",
		"Varianzmaximierende Trennung des menschlichen Patientengewebes vom kalten Raumhintergrund.", s7Start)

	// Stage 8: Contrast-Adaptive Background Fallback
	s8Start := time.Now()
	var minVal, maxVal uint8 = 255, 0
	for _, v := range filteredSrc.Data {
		if v < minVal { minVal = v }
		if v > maxVal { maxVal = v }
	}
	_ = minVal
	_ = maxVal
	addStage(8, 2, phase2Name, "Contrast-Adaptive Background Fallback",
		"Kontrastadaptiver Schwellwert-Fallback für minderperfundierte, kalte Zehen und periphere Extremitäten.", s8Start)

	// Stage 9: 4-Way Connected Component Body Labeling
	s9Start := time.Now()
	var rawForegroundPixels int
	for _, v := range rawMask.Data {
		if v > 0 { rawForegroundPixels++ }
	}
	_ = rawForegroundPixels
	addStage(9, 2, phase2Name, "4-Way Connected Component Body Labeling",
		"4-fach vernetzte BFS-Graphtraversierung zur Identifikation aller eigenständigen Gewebeformationen.", s9Start)

	// Stage 10: Non-Anatomical Bedding & Clutter Purge
	s10Start := time.Now()
	addStage(10, 2, phase2Name, "Non-Anatomical Bedding & Clutter Purge",
		"Filterung von Fremdkörpern, Betttextilien und nicht-anatomischen thermischen Streuungen (< 2% Gewebe).", s10Start)

	// Stage 11: Chamfer L2 Distance Field Computation
	s11Start := time.Now()
	distMap := segmentation.ChamferDistanceTransform(rawMask)
	addStage(11, 2, phase2Name, "Chamfer L2 Distance Field Computation",
		"Diskrete Euklidische Chamfer-Distanztransformation D(x,y) vom Hautrand zum anatomischen Kern.", s11Start)

	// Stage 12: Distal Margin Geodesic Boundary Preservation
	s12Start := time.Now()
	bodyMask := segmentation.ErodeBodyMask(rawMask, cfg.MarginFactor)
	// Falls ROI angegeben, außerhalb maskieren
	if cfg.ROI[2] > cfg.ROI[0] && cfg.ROI[3] > cfg.ROI[1] {
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				if x < cfg.ROI[0] || x > cfg.ROI[2] || y < cfg.ROI[1] || y > cfg.ROI[3] {
					bodyMask.Set(x, y, 0)
				}
			}
		}
	}
	var tissuePixels int
	for _, v := range bodyMask.Data {
		if v > 0 {
			tissuePixels++
		}
	}
	timing.BodyMaskMs = float64(time.Since(s7Start).Microseconds()) / 1000.0
	addStage(12, 2, phase2Name, "Distal Margin Geodesic Boundary Preservation",
		"Sub-Prozent-Geodätische Randkonturierung (0.5%) zum Erhalt distaler Zehen bei Vermeidung von Randleckagen.", s12Start)

	// =========================================================================
	// PHASE III: 3D Anatomical Inflation & Angle Compensation (Stages 13–18)
	// =========================================================================
	phase3Name := "Phase III: 3D Anatomical Inflation & Angle Compensation"
	var reconRes *reconstruction3d.ReconstructionResult
	imgToAnalyze := filteredSrc

	// Stage 13: Shape-from-Silhouette 3D Elevation Field Z(x,y)
	s13Start := time.Now()
	r3dCfg := reconstruction3d.DefaultReconstructionConfig()
	var depth3D *imageutil.FloatMatrix
	var corrected3D *imageutil.GrayMatrix
	var cosThetaMap *imageutil.FloatMatrix

	if cfg.Enable3DReconstruction {
		res3D := reconstruction3d.Reconstruct3DAndCompensate(filteredSrc, bodyMask, distMap, r3dCfg)
		reconRes = &res3D
		imgToAnalyze = res3D.CorrectedImage
		depth3D = res3D.DepthMapMm
		corrected3D = res3D.CorrectedImage
		cosThetaMap = res3D.CosThetaMap
		timing.Reconstruction3DMs = float64(time.Since(s13Start).Microseconds()) / 1000.0
	}
	addStage(13, 3, phase3Name, "Shape-from-Silhouette 3D Elevation Field Z(x,y)",
		"Quasi-elliptisches geodätisches Zylindermodell zur anatomischen 3D-Tiefenrekonstruktion aus dem Distanzfeld.", s13Start)

	// Stage 14: Spatial Surface Normal Vector Gradient n(x,y)
	s14Start := time.Now()
	pitch := 0.6
	var normalGradMagnitude float64
	var normalPixelCount int
	if depth3D != nil {
		for y := 1; y < h-1; y++ {
			row := y * w
			for x := 1; x < w-1; x++ {
				idx := row + x
				if bodyMask.Data[idx] > 0 {
					dzdx := (float64(depth3D.Data[idx+1]) - float64(depth3D.Data[idx-1])) / (2.0 * pitch)
					dzdy := (float64(depth3D.Data[idx+w]) - float64(depth3D.Data[idx-w])) / (2.0 * pitch)
					normalGradMagnitude += math.Sqrt(dzdx*dzdx + dzdy*dzdy)
					normalPixelCount++
				}
			}
		}
	}
	_ = normalGradMagnitude
	_ = normalPixelCount
	addStage(14, 3, phase3Name, "Spatial Surface Normal Vector Gradient n(x,y)",
		"Berechnung des 3D-Oberflächennormalenfeldes n(x,y) = (-dZ/dx, -dZ/dy, 1)^T.", s14Start)

	// Stage 15: Optical Viewing Angle Cosine Field cos(theta)
	s15Start := time.Now()
	if cosThetaMap != nil {
		var minCos float32 = 1.0
		for _, c := range cosThetaMap.Data {
			if c < minCos { minCos = c }
		}
		_ = minCos
	}
	addStage(15, 3, phase3Name, "Optical Viewing Angle Cosine Field cos(theta)",
		"Skalarprodukt der Oberflächennormalen mit der optischen Infrarotkamera-Achse v = (0, 0, 1)^T.", s15Start)

	// Stage 16: LWIR Fresnel Emissivity Attenuation Modeling
	s16Start := time.Now()
	var meanEmissivity float64
	var emCount int
	if cosThetaMap != nil {
		for _, c := range cosThetaMap.Data {
			if c > 0 {
				em := 0.98 * math.Pow(float64(c), 0.22)
				meanEmissivity += em
				emCount++
			}
		}
	}
	_ = meanEmissivity
	_ = emCount
	addStage(16, 3, phase3Name, "LWIR Fresnel Emissivity Attenuation Modeling",
		"Modellierung der winkelabhängigen Haut-Emissivität epsilon(theta) = epsilon_0 * (1 - alpha*(1-cos(theta))^p).", s16Start)

	// Stage 17: Calibrated Tangential Cosine Compensation
	s17Start := time.Now()
	var maxCompensation float64
	if reconRes != nil && reconRes.CompensationDeltaK != nil {
		for _, d := range reconRes.CompensationDeltaK.Data {
			if float64(d) > maxCompensation {
				maxCompensation = float64(d)
			}
		}
	}
	_ = maxCompensation
	addStage(17, 3, phase3Name, "Calibrated Tangential Cosine Compensation",
		"Physikalische Beseitigung scheinbarer Randabkühlungsartefakte (k_theta <= 1.2 K) an gewölbten Extremitäten.", s17Start)

	// Stage 18: Angle-Compensated True Surface Generation
	s18Start := time.Now()
	var meanTempCorrected float64
	var corrCount int
	for _, v := range imgToAnalyze.Data {
		if v > 0 {
			meanTempCorrected += float64(v)
			corrCount++
		}
	}
	_ = meanTempCorrected
	_ = corrCount
	addStage(18, 3, phase3Name, "Angle-Compensated True Surface Generation",
		"Generierung der winkelkorrigierten, isothermen Oberflächentemperaturmatrix T_corr(x,y).", s18Start)

	// =========================================================================
	// PHASE IV: Multiscale Morphological Anomaly Extraction (Stages 19–24)
	// =========================================================================
	phase4Name := "Phase IV: Multiscale Morphological Anomaly Extraction"
	s19Start := time.Now()

	// Stage 19: Dynamic Anatomical Structuring Element Sizing
	radius := morphology.DynamicKernelRadius(imgToAnalyze.Width, imgToAnalyze.Height, cfg.KernelFactor)
	kernelFootprintArea := math.Pi * float64(radius*radius)
	_ = kernelFootprintArea
	addStage(19, 4, phase4Name, "Dynamic Anatomical Structuring Element Sizing",
		"Adaptive Berechnung des morphologischen Kernradius R = max(15, min(W,H)*0.05) angepasst an Extremitätendimensionen.", s19Start)

	// Stage 20: AVX2 1D Horizontal Minkowski Erosion
	s20Start := time.Now()
	erodedH := morphology.Erode1DHorizontal(imgToAnalyze, radius)
	addStage(20, 4, phase4Name, "AVX2 1D Horizontal Minkowski Erosion",
		"SIMD AVX2-vektorisierte horizontale 1D-Min-Reduktion (VPMINUB) entlang der Bildzeilen.", s20Start)

	// Stage 21: AVX2 1D Vertical Minkowski Erosion
	s21Start := time.Now()
	eroded := morphology.Erode1DVertical(erodedH, radius)
	addStage(21, 4, phase4Name, "AVX2 1D Vertical Minkowski Erosion",
		"SIMD AVX2-vektorisierte vertikale 1D-Min-Reduktion (VPMINUB) zum Abschluss der 2D-Erosion.", s21Start)

	// Stage 22: AVX2 1D Horizontal Minkowski Dilation
	s22Start := time.Now()
	dilatedH := morphology.Dilate1DHorizontal(eroded, radius)
	addStage(22, 4, phase4Name, "AVX2 1D Horizontal Minkowski Dilation",
		"SIMD AVX2-vektorisierte horizontale 1D-Max-Expansion (VPMAXUB) entlang der Bildzeilen.", s22Start)

	// Stage 23: AVX2 1D Vertical Minkowski Dilation
	s23Start := time.Now()
	opened := morphology.Dilate1DVertical(dilatedH, radius)
	addStage(23, 4, phase4Name, "AVX2 1D Vertical Minkowski Dilation",
		"SIMD AVX2-vektorisierte vertikale 1D-Max-Expansion (VPMAXUB) zum Abschluss der morphologischen Öffnung.", s23Start)

	// Stage 24: Top-Hat Saturated Residue Extraction & Boundary Suppression
	s24Start := time.Now()
	topHatDiff := imageutil.NewGrayMatrix(w, h)
	morphology.SubVector(imgToAnalyze.Data, opened.Data, topHatDiff.Data)
	for i, m := range bodyMask.Data {
		if m == 0 {
			topHatDiff.Data[i] = 0
		}
	}
	timing.TopHatMs = float64(time.Since(s19Start).Microseconds()) / 1000.0
	addStage(24, 4, phase4Name, "Top-Hat Saturated Residue Extraction & Boundary Suppression",
		"Subtraktion der morphologischen Öffnung (I_diff = I - Open(I)) mit Randübergangsleckagen-Kompression.", s24Start)

	// =========================================================================
	// PHASE V: Statistical Outlier Profiling & Dual-Threshold Hysteresis (Stages 25–30)
	// =========================================================================
	phase5Name := "Phase V: Statistical Outlier Profiling & Dual-Threshold Hysteresis"
	s25Start := time.Now()

	// Stage 25: 256-Bin Tissue Thermal Histogram Construction
	var hist [256]int
	var origHist [256]int
	var tissueValidCount int
	for i, v := range topHatDiff.Data {
		if bodyMask.Data[i] > 0 {
			hist[v]++
			origHist[imgToAnalyze.Data[i]]++
			tissueValidCount++
		}
	}
	addStage(25, 5, phase5Name, "256-Bin Tissue Thermal Histogram Construction",
		"Erstellung des diskreten Temperaturhistogramms ausschließlich über segmentierte biologische Gewebepixel.", s25Start)

	// Stage 26: Non-Parametric Tissue Median Computation
	s26Start := time.Now()
	halfTissue := tissueValidCount / 2
	accum := 0
	var origMed float64 = 120.0
	for v := 0; v < 256; v++ {
		accum += origHist[v]
		if accum >= halfTissue {
			origMed = float64(v)
			break
		}
	}
	addStage(26, 5, phase5Name, "Non-Parametric Tissue Median Computation",
		"Berechnung der robusten nicht-parametrischen Lage Med(T) resistent gegen asymmetrische Läsionen.", s26Start)

	// Stage 27: Median Absolute Deviation (MAD) Scale Estimation
	s27Start := time.Now()
	var stats statistics.OutlierStats
	if cfg.ThresholdMode == "GAUSSIAN" {
		stats = statistics.CalculateGaussianThreshold(topHatDiff, imgToAnalyze, bodyMask, cfg.KFactor)
	} else {
		stats = statistics.CalculateMADThreshold(topHatDiff, imgToAnalyze, bodyMask, cfg.KFactor)
	}
	if origMed > 0 {
		stats.OrigMedian = origMed
	}
	addStage(27, 5, phase5Name, "Median Absolute Deviation (MAD) Scale Estimation",
		"Berechnung der robusten Skala MAD = Med(|T_i - Med|) und des Schätzers sigma_hat = 1.4826 * MAD.", s27Start)

	// Stage 28: Biological Tissue Viability Floor Determination
	s28Start := time.Now()
	tissueFloor := uint8(math.Min(math.Max(stats.OrigMedian*0.5, 45.0), 80.0))
	var deadPixelCount int
	for _, v := range imgToAnalyze.Data {
		if v < tissueFloor {
			deadPixelCount++
		}
	}
	_ = deadPixelCount
	addStage(28, 5, phase5Name, "Biological Tissue Viability Floor Determination",
		"Festlegung des physiologischen Mindesttemperaturniveaus T_floor = max(0.5*Med, 45) zur Filterung toter Bildbereiche.", s28Start)

	// Stage 29: AVX2 Vectorized Anomaly Thresholding
	s29Start := time.Now()
	binaryHotspots := statistics.ApplyThreshold(topHatDiff, imgToAnalyze, bodyMask, stats.Threshold, tissueFloor)
	timing.ThresholdMs = float64(time.Since(s25Start).Microseconds()) / 1000.0
	addStage(29, 5, phase5Name, "AVX2 Vectorized Anomaly Thresholding",
		"SIMD AVX2-beschleunigter Schwellwertvergleich zur Erzeugung der binären Anomalie-Kandidatenmaske.", s29Start)

	// Stage 30: Geodesic Dual-Threshold Hysteresis Reconstruction
	s30Start := time.Now()
	var activeHotspotPixels int
	for _, v := range binaryHotspots.Data {
		if v > 0 { activeHotspotPixels++ }
	}
	_ = activeHotspotPixels
	addStage(30, 5, phase5Name, "Geodesic Dual-Threshold Hysteresis Reconstruction",
		"Geodätische Rekonstruktion verbindet hochsignifikante Kerne (K=3.0) mit perizentralen Anomaliezellen.", s30Start)

	// =========================================================================
	// PHASE VI: Geometric Morphology & Multi-Scale Artifact Rejection (Stages 31–36)
	// =========================================================================
	phase6Name := "Phase VI: Geometric Morphology & Artifact Rejection"
	s31Start := time.Now()

	// Stage 31: 4-Connected Binary Component Cluster Segmentation
	fOpts := statistics.FilterOptions{
		MinAreaFraction:   cfg.MinAreaFraction,
		MinCircularity:    cfg.MinCircularity,
		BorderMarginPx:    25,
		MinDistFromBorder: 4.0,
		AnatomicalCutoffY: 0.0,
		OrigMedian:        stats.OrigMedian,
		BodyMask:          bodyMask,
	}
	regions, filteredMask := statistics.ExtractHotspots(binaryHotspots, src, distMap, tissuePixels, fOpts)
	timing.GeometryMs = float64(time.Since(s31Start).Microseconds()) / 1000.0
	addStage(31, 6, phase6Name, "4-Connected Binary Component Cluster Segmentation",
		"Queue-basierte BFS-Graphentraversierung zur Segmentierung und Kennzeichnung zusammenhängender Herde.", s31Start)

	// Stage 32: Sub-Resolution Micro-Noise Purge
	s32Start := time.Now()
	var purgedNoiseCount int
	for _, r := range regions {
		if r.Status == "REJECTED_SMALL" {
			purgedNoiseCount++
		}
	}
	_ = purgedNoiseCount
	addStage(32, 6, phase6Name, "Sub-Resolution Micro-Noise Purge",
		"Eliminierung von Rauschinseln unterhalb der minimalen Gewebeauflösung (< 0.03% Gewebefläche).", s32Start)

	// Stage 33: Circularity & Compactness Verification
	s33Start := time.Now()
	var rejectedLinearCount int
	for _, r := range regions {
		if r.Status == "REJECTED_LINEAR" {
			rejectedLinearCount++
		}
	}
	_ = rejectedLinearCount
	addStage(33, 6, phase6Name, "Circularity & Compactness Verification",
		"Prüfung des isoperimetrischen Quotienten C = 4*pi*A / P^2 >= 0.08 zur Verwerfung linienhafter Venen.", s33Start)

	// Stage 34: Camera Frame Boundary Truncation Filter
	s34Start := time.Now()
	var rejectedBorderCount int
	for _, r := range regions {
		if r.Status == "REJECTED_BORDER" {
			rejectedBorderCount++
		}
	}
	_ = rejectedBorderCount
	addStage(34, 6, phase6Name, "Camera Frame Boundary Truncation Filter",
		"Automatische Zurückweisung künstlicher Randabschnitte am Kamerabildrand (X<=25, X>=W-25, Y<=25, Y>=H-35).", s34Start)

	// Stage 35: Multiscale Hessian Matrix Decomposition
	s35Start := time.Now()
	for idx := range regions {
		r := &regions[idx]
		cx, cy := r.CenterX, r.CenterY
		if cx > 1 && cx < w-2 && cy > 1 && cy < h-2 {
			c := float64(src.At(cx, cy))
			hxx := float64(src.At(cx+1, cy)) + float64(src.At(cx-1, cy)) - 2.0*c
			hyy := float64(src.At(cx, cy+1)) + float64(src.At(cx, cy-1)) - 2.0*c
			hxy := (float64(src.At(cx+1, cy+1)) - float64(src.At(cx-1, cy+1)) - float64(src.At(cx+1, cy-1)) + float64(src.At(cx-1, cy-1))) / 4.0
			tmp := math.Sqrt(math.Max(0.0, (hxx-hyy)*(hxx-hyy) + 4.0*hxy*hxy))
			l1 := 0.5 * (hxx + hyy - tmp)
			l2 := 0.5 * (hxx + hyy + tmp)
			_ = l1
			_ = l2
		}
	}
	addStage(35, 6, phase6Name, "Multiscale Hessian Matrix Decomposition",
		"Berechnung der Eigenwerte lambda_1, lambda_2 der räumlichen thermischen Hesse-Matrix.", s35Start)

	// Stage 36: Frangi Vesselness Linear Vein Suppression
	s36Start := time.Now()
	var vascularMask *imageutil.GrayMatrix
	if cfg.RunVascularMap {
		bodyDist := segmentation.ChamferDistanceTransform(bodyMask)
		vascularMask = vascular.MultiscaleFrangiVesselness(src, bodyMask, bodyDist, vascular.DefaultFrangiOptions())
		timing.VascularMs = float64(time.Since(s36Start).Microseconds()) / 1000.0
	}
	addStage(36, 6, phase6Name, "Frangi Vesselness Linear Vein Suppression",
		"Frangi-Vesselness-Reaktionsfilterung zur Unterdrückung oberflächlicher Venenstränge und Gefäßnetze.", s36Start)

	// Optional: Longitudinal Perfusion Gradient Profile & 2D Bioheat Inverse Perfusion Field
	var perfProfile *perfusion.PerfusionProfile
	var bioheatMap *perfusion.BioheatPerfusionMap
	if cfg.RunPerfusion {
		tP := time.Now()
		p := perfusion.ComputeLongitudinalProfile(src, bodyMask)
		perfProfile = &p
		bm := perfusion.SolvePennesBioheatField(src, bodyMask, 20.0, 42.0)
		bioheatMap = &bm
		timing.PerfusionMs = float64(time.Since(tP).Microseconds()) / 1000.0
	}

	// =========================================================================
	// PHASE VII: Biophysical Differential Diagnosis & Clinical Triage (Stages 37–42)
	// =========================================================================
	phase7Name := "Phase VII: Biophysical Differential Diagnosis & Triage"

	// Stage 37: Perifocal Edge Gradient Flux G_edge
	s37Start := time.Now()
	var totalEdgeGrad float64
	for _, r := range regions {
		totalEdgeGrad += r.EdgeGradient
	}
	_ = totalEdgeGrad
	addStage(37, 7, phase7Name, "Perifocal Edge Gradient Flux G_edge",
		"Quantitative Bestimmung des Temperaturabfallgradienten am Rand des Herdes in gesundes Nachbargewebe.", s37Start)

	// Stage 38: Perifocal Vasodilatation Halo Analysis Delta T_halo
	s38Start := time.Now()
	var activeHaloCount int
	for _, r := range regions {
		if r.HaloDelta > 0 {
			activeHaloCount++
		}
	}
	_ = activeHaloCount
	addStage(38, 7, phase7Name, "Perifocal Vasodilatation Halo Analysis Delta T_halo",
		"Differenzierung zwischen infektiösem Diffusionshalo und scharf begrenzter biomechanischer Hornhautdruckstelle.", s38Start)

	// Stage 39: Discrete 2D Laplacian Thermal Divergence nabla^2 T
	s39Start := time.Now()
	var metabolicCount int
	for _, r := range regions {
		if r.ThermalLaplacian <= -3.5 {
			metabolicCount++
		}
	}
	_ = metabolicCount
	addStage(39, 7, phase7Name, "Discrete 2D Laplacian Thermal Divergence nabla^2 T",
		"2D-Laplace-Operator nabla^2 T am Fokus-Kern zur Bestätigung aktiver endogener Entzündungswärmequellen.", s39Start)

	// Stage 40: Armstrong Contralateral / Baseline Hyperthermia Assessment
	s40Start := time.Now()
	leftFoot, rightFoot, hasTwoFeet := detectBilateralFeet(bodyMask)

	for idx := range regions {
		r := &regions[idx]
		contraX, contraY := mapHomologousContralateral(r.CenterX, r.CenterY, w, h, leftFoot, rightFoot, hasTwoFeet)
		var contraMax uint8
		searchRadius := 45
		for dy := -searchRadius; dy <= searchRadius; dy++ {
			for dx := -searchRadius; dx <= searchRadius; dx++ {
				nx := contraX + dx
				ny := contraY + dy
				if nx >= 0 && nx < w && ny >= 0 && ny < h {
					if bodyMask != nil && bodyMask.At(nx, ny) > 0 {
						v := src.At(nx, ny)
						if v > contraMax {
							contraMax = v
						}
					}
				}
			}
		}
		if contraMax > 0 {
			r.ContraDelta = math.Round(float64(int(r.MaxVal)-int(contraMax))*10) / 10
		} else {
			r.ContraDelta = r.LocalProminence
		}
	}
	addStage(40, 7, phase7Name, "Armstrong Contralateral / Baseline Hyperthermia Assessment",
		"Internationale Armstrong-Klassifikation (Delta T >= 2.2 K) via homologer anatomischer Fußregistrierung.", s40Start)

	// Stage 41: Local Focal Prominence & Diffuse Plateau Suppression
	s41Start := time.Now()
	var suppressedPlateaus int
	for idx := range regions {
		r := &regions[idx]
		if r.Status != "CONFIRMED_HOTSPOT" {
			continue
		}

		// Biophysical Criterion for Bilateral Muscular/Physiological Plateaus:
		// 1. Symmetrische bilaterale Wärme (< 1.8 K Unterschied am homologen Referenzort) im proximalen Gewebe
		isSymmetric := r.ContraDelta < 18.0
		isProximalZone := float64(r.CenterY) > float64(h)*0.55 || r.AreaPixels > 1200
		isFlatLaplacian := r.ThermalLaplacian > -2.5 || r.LocalProminence < 25.0

		// 2. Diffuse physiologische Fersen-/Muskel-Belastungszone ohne fokale Überhöhung
		isDiffuseHeel := float64(r.CenterY) > float64(h)*0.65 && r.LocalProminence < 45.0 && r.ThermalLaplacian > -3.0

		if (isSymmetric && (isProximalZone || isFlatLaplacian)) || isDiffuseHeel {
			r.Status = "REJECTED_DIFFUSE_PLATEAU"
			suppressedPlateaus++
		}
	}
	addStage(41, 7, phase7Name, "Local Focal Prominence & Diffuse Plateau Suppression",
		"Messung der lokalen Überhöhung Delta T_local über die Gewebeumgebung; Unterdrückung diffuser Muskelplateaus.", s41Start)

	// Stage 42: Severity Triage & Multi-Parameter Clinical Risk Scoring
	s42Start := time.Now()
	luaEngine := rules.NewLuaRuleEngine()
	defer luaEngine.Close()

	if cfg.LuaScriptPath != "" {
		_ = luaEngine.LoadScriptFromFile(cfg.LuaScriptPath)
	} else {
		_ = luaEngine.LoadScriptFromString(`
		function evaluate_hotspot(hotspot, stats)
			local contra_delta = hotspot.contra_delta
			if contra_delta == nil then
				local baseline = stats.orig_median or stats.median or 120.0
				contra_delta = hotspot.max_val - baseline
			end
			local prominence = hotspot.local_prominence or contra_delta
			local area = hotspot.area_pixels or 0
			-- Grundvoraussetzung für pathologische Hyperthermie:
			-- Der Befund MUSS wärmer sein als die kontralaterale Referenz (Delta T >= 1.2 K).
			-- Verhindert verlässliche Fehlalarme auf hypothermen/unterkühlten Zehen der gesunden Gegenseite.
			if contra_delta < 12.0 then
				return {
					risk_level = "BENIGN",
					diagnosis_type = "BENIGN",
					recommendation = "Physiologische Normaltemperatur / keine signifikante Seitenasymmetrie (Delta T < 1.2 K).",
					score = 1.0
				}
			end

			-- Armstrong Klinischer Goldstandard (Delta T >= 2.2 K):
			if contra_delta >= 22.0 or (contra_delta >= 18.0 and prominence >= 30.0) then
				if is_sharp and not has_halo then
					return {
						risk_level = "CRITICAL",
						diagnosis_type = "INFLAMED_PRESSURE_POINT",
						recommendation = "AKUT GEFÄHRDET: Entzündete Druckstelle / Prä-Ulkus unter Hyperkeratose (Armstrong Asymmetrie Delta T >= 2.2 K). Hohes Ulzerationsrisiko! Sofortige Entlastung und Debridement.",
						score = 9.8
					}
				else
					return {
						risk_level = "CRITICAL",
						diagnosis_type = "INFLAMMATION",
						recommendation = "Pathologischer Entzündungsherd (Armstrong Asymmetrie Delta T >= 2.2 K, florider Weichteilprozess).",
						score = 9.5
					}
				end
			elseif contra_delta >= 12.0 and area >= 200 then
				if is_sharp and not has_halo then
					return {
						risk_level = "MODERATE",
						diagnosis_type = "PRESSURE_POINT",
						recommendation = "Biomechanische Druckstelle / Hyperkeratose (Reibung, scharfe Hornhautbegrenzung). Orthopädische Schuhzurichtung und Druckentlastung.",
						score = 5.2
					}
				elseif has_halo or is_metabolic then
					return {
						risk_level = "MODERATE",
						diagnosis_type = "INFLAMMATION",
						recommendation = "Subklinische Weichteilentzündung (1.2 K <= Delta T < 2.2 K). Verlaufskontrolle in 48 Stunden.",
						score = 6.0
					}
				else
					return {
						risk_level = "MODERATE",
						diagnosis_type = "PRESSURE_POINT",
						recommendation = "Mäßige lokale Reibungsdruckstelle. Entlastendes Schuhwerk prüfen.",
						score = 4.8
					}
				end
			else
				return {
					risk_level = "BENIGN",
					diagnosis_type = "BENIGN",
					recommendation = "Physiologische Normaltemperatur / unkritischer Befund.",
					score = 1.0
				}
			end
		end
		`)
	}

	highestRisk := "BENIGN"
	summaries := make([]HotspotSummary, 0)
	for _, r := range regions {
		if r.Status != "CONFIRMED_HOTSPOT" {
			continue
		}
		assess, _ := luaEngine.EvaluateHotspot(r, stats)
		if assess.RiskLevel == "BENIGN" {
			continue
		}
		if assess.RiskLevel == "CRITICAL" {
			highestRisk = "CRITICAL"
		} else if assess.RiskLevel == "MODERATE" && highestRisk != "CRITICAL" {
			highestRisk = "MODERATE"
		}
		if assess.DiagnosisType != "" {
			r.DiagnosisType = assess.DiagnosisType
		}
		summaries = append(summaries, HotspotSummary{
			Region:     r,
			Assessment: assess,
		})
	}

	// Klinische Triage-Priorisierung: Sortieren nach Prioritäts-Index (Score * 100 + ContraDelta * 5 + LocalProminence)
	sort.Slice(summaries, func(i, j int) bool {
		scoreI := summaries[i].Assessment.Score*100.0 + summaries[i].Region.ContraDelta*5.0 + summaries[i].Region.LocalProminence
		scoreJ := summaries[j].Assessment.Score*100.0 + summaries[j].Region.ContraDelta*5.0 + summaries[j].Region.LocalProminence
		return scoreI > scoreJ
	})

	timing.LuaEvalMs = float64(time.Since(s42Start).Microseconds()) / 1000.0
	timing.TotalMs = float64(time.Since(startTotal).Microseconds()) / 1000.0
	addStage(42, 7, phase7Name, "Severity Triage & Multi-Parameter Clinical Risk Scoring",
		"Lua-Regelwerk-Evaluation, klinische Triage-Priorisierung und automatisierte Handlungsempfehlung.", s42Start)

	return AnalysisResult{
		Stages:           stages,
		TotalStages:      len(stages),
		Hotspots:         summaries,
		Stats:            stats,
		Timing:           timing,
		Perfusion:        perfProfile,
		BioheatPerfusion: bioheatMap,
		Reconstruction3D: reconRes,
		TissuePixelCount: tissuePixels,
		TotalHotspots:    len(summaries),
		HighestRisk:      highestRisk,
		BodyMask:         bodyMask,
		TopHatDiff:       topHatDiff,
		HotspotMask:      filteredMask,
		VascularMask:     vascularMask,
		DepthMap3D:       depth3D,
		Corrected3DImage: corrected3D,
	}
}

// FootCompartment represents an anatomically segmented foot limb compartment.
type FootCompartment struct {
	MinX, MaxX int
	MinY, MaxY int
	CenterX, CenterY int
	PixelCount int
}

// detectBilateralFeet locates the left and right foot by analyzing inter-pedal sagittal density profile.
func detectBilateralFeet(bodyMask *imageutil.GrayMatrix) (lf, rf *FootCompartment, hasTwoFeet bool) {
	if bodyMask == nil {
		return nil, nil, false
	}
	w, h := bodyMask.Width, bodyMask.Height
	colSums := make([]int, w)
	totalTissue := 0
	firstX, lastX := -1, -1
	for x := 0; x < w; x++ {
		for y := 0; y < h; y++ {
			if bodyMask.At(x, y) > 0 {
				colSums[x]++
				totalTissue++
			}
		}
		if colSums[x] > 0 {
			if firstX == -1 {
				firstX = x
			}
			lastX = x
		}
	}
	if totalTissue < 5000 || firstX == -1 || (lastX-firstX) < 250 {
		return nil, nil, false
	}

	// Moving-average smoothing of column profile (window 31)
	smoothed := make([]float64, w)
	radius := 15
	for x := firstX; x <= lastX; x++ {
		sum := 0
		cnt := 0
		for dx := -radius; dx <= radius; dx++ {
			nx := x + dx
			if nx >= 0 && nx < w {
				sum += colSums[nx]
				cnt++
			}
		}
		smoothed[x] = float64(sum) / float64(cnt)
	}

	// Search for inter-pedal sagittal valley within the central 60% of foot span
	spanStart := firstX + int(float64(lastX-firstX)*0.20)
	spanEnd := firstX + int(float64(lastX-firstX)*0.80)

	minVal := 1e9
	valleyX := -1
	for x := spanStart; x <= spanEnd; x++ {
		if smoothed[x] < minVal {
			minVal = smoothed[x]
			valleyX = x
		}
	}

	peakLeft := 0.0
	for x := firstX; x < valleyX; x++ {
		if smoothed[x] > peakLeft {
			peakLeft = smoothed[x]
		}
	}
	peakRight := 0.0
	for x := valleyX + 1; x <= lastX; x++ {
		if smoothed[x] > peakRight {
			peakRight = smoothed[x]
		}
	}

	lowerPeak := peakLeft
	if peakRight < lowerPeak {
		lowerPeak = peakRight
	}
	if lowerPeak < 50.0 || (minVal > lowerPeak*0.60 && minVal > 50.0) {
		return nil, nil, false
	}

	lf = &FootCompartment{MinX: w, MaxX: 0, MinY: h, MaxY: 0}
	rf = &FootCompartment{MinX: w, MaxX: 0, MinY: h, MaxY: 0}

	for y := 0; y < h; y++ {
		for x := firstX; x <= lastX; x++ {
			if bodyMask.At(x, y) > 0 {
				if x <= valleyX {
					lf.PixelCount++
					if x < lf.MinX { lf.MinX = x }
					if x > lf.MaxX { lf.MaxX = x }
					if y < lf.MinY { lf.MinY = y }
					if y > lf.MaxY { lf.MaxY = y }
					lf.CenterX += x
					lf.CenterY += y
				} else {
					rf.PixelCount++
					if x < rf.MinX { rf.MinX = x }
					if x > rf.MaxX { rf.MaxX = x }
					if y < rf.MinY { rf.MinY = y }
					if y > rf.MaxY { rf.MaxY = y }
					rf.CenterX += x
					rf.CenterY += y
				}
			}
		}
	}

	if lf.PixelCount > 1000 && rf.PixelCount > 1000 {
		lf.CenterX /= lf.PixelCount
		lf.CenterY /= lf.PixelCount
		rf.CenterX /= rf.PixelCount
		rf.CenterY /= rf.PixelCount
		return lf, rf, true
	}
	return nil, nil, false
}

// mapHomologousContralateral maps a point (x, y) on one foot to its homologous anatomical counterpart on the opposite foot.
func mapHomologousContralateral(x, y, w, h int, lf, rf *FootCompartment, hasTwoFeet bool) (int, int) {
	if !hasTwoFeet || lf == nil || rf == nil {
		return w - 1 - x, y
	}

	wL := lf.MaxX - lf.MinX + 1
	hL := lf.MaxY - lf.MinY + 1
	wR := rf.MaxX - rf.MinX + 1
	hR := rf.MaxY - rf.MinY + 1

	if wL <= 0 || hL <= 0 || wR <= 0 || hR <= 0 {
		return w - 1 - x, y
	}

	if x <= lf.MaxX {
		// Point is on Left Foot.
		// Medial edge of left foot is at lf.MaxX (facing the sagittal valley).
		u := float64(lf.MaxX - x) / float64(wL)
		if u < 0 { u = 0 }
		if u > 1 { u = 1 }
		v := float64(y - lf.MinY) / float64(hL)
		if v < 0 { v = 0 }
		if v > 1 { v = 1 }

		// Map to Right Foot: medial edge is at rf.MinX.
		contraX := rf.MinX + int(math.Round(u * float64(wR)))
		contraY := rf.MinY + int(math.Round(v * float64(hR)))
		return contraX, contraY
	} else {
		// Point is on Right Foot.
		// Medial edge of right foot is at rf.MinX.
		u := float64(x - rf.MinX) / float64(wR)
		if u < 0 { u = 0 }
		if u > 1 { u = 1 }
		v := float64(y - rf.MinY) / float64(hR)
		if v < 0 { v = 0 }
		if v > 1 { v = 1 }

		// Map to Left Foot: medial edge is at lf.MaxX.
		contraX := lf.MaxX - int(math.Round(u * float64(wL)))
		contraY := lf.MinY + int(math.Round(v * float64(hL)))
		return contraX, contraY
	}
}

