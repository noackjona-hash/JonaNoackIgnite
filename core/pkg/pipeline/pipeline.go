package pipeline

import (
	"math"
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
	KernelFactor            float64 `json:"kernel_factor"`             // default 0.05
	MarginFactor            float32 `json:"margin_factor"`             // default 0.05
	KFactor                 float64 `json:"k_factor"`                  // default 3.0
	ThresholdMode           string  `json:"threshold_mode"`            // "MAD" or "GAUSSIAN"
	MinAreaFraction         float64 `json:"min_area_fraction"`         // default 0.0005
	MinCircularity          float64 `json:"min_circularity"`          // default 0.08
	RunVascularMap          bool    `json:"run_vascular_map"`          // enable Frangi filter
	RunPerfusion            bool    `json:"run_perfusion"`             // enable longitudinal gradient
	Enable3DReconstruction  bool    `json:"enable_3d_reconstruction"`  // 3D anatomical surface inflation & angle compensation
	LuaScriptPath           string  `json:"lua_script_path"`           // optional path to custom Lua rule
	ROI                     [4]int  `json:"roi"`                       // [minX, minY, maxX, maxY], if [0,0,0,0] full image
	AutoBilateral           bool    `json:"auto_bilateral"`            // auto-split into left & right limb
}

// DefaultPipelineConfig returns standard research parameters.
func DefaultPipelineConfig() PipelineConfig {
	return PipelineConfig{
		KernelFactor:           0.05,
		MarginFactor:           0.05,
		KFactor:                3.0, // Calibrated standard
		ThresholdMode:          "MAD",
		MinAreaFraction:        0.0005,
		MinCircularity:         0.08,
		RunVascularMap:         false, // Off by default for instant speed, enabled on demand
		RunPerfusion:           true,
		Enable3DReconstruction: true,  // Automatically eliminate edge-cooling artifacts
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

// AnalysisResult encapsulates all outputs of the multi-stage analysis.
type AnalysisResult struct {
	Hotspots         []HotspotSummary                             `json:"hotspots"`
	Stats            statistics.OutlierStats                      `json:"stats"`
	Timing           StageTiming                                  `json:"timing"`
	Perfusion        *perfusion.PerfusionProfile                  `json:"perfusion,omitempty"`
	Reconstruction3D *reconstruction3d.ReconstructionResult        `json:"reconstruction_3d,omitempty"`
	TissuePixelCount int                                          `json:"tissue_pixel_count"`
	TotalHotspots    int                                          `json:"total_hotspots"`
	HighestRisk      string                                       `json:"highest_risk"`
	
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

// Run executes the complete multi-stage medical imaging pipeline.
func Run(src *imageutil.GrayMatrix, cfg PipelineConfig) AnalysisResult {
	startTotal := time.Now()
	var timing StageTiming

	// 1. Body mask & distance field
	t0 := time.Now()
	rawMask := segmentation.SegmentBodyMask(src)
	distMap := segmentation.ChamferDistanceTransform(rawMask)
	bodyMask := segmentation.ErodeBodyMask(rawMask, cfg.MarginFactor)

	// If ROI is specified, mask out everything outside ROI
	if cfg.ROI[2] > cfg.ROI[0] && cfg.ROI[3] > cfg.ROI[1] {
		for y := 0; y < src.Height; y++ {
			for x := 0; x < src.Width; x++ {
				if x < cfg.ROI[0] || x > cfg.ROI[2] || y < cfg.ROI[1] || y > cfg.ROI[3] {
					bodyMask.Set(x, y, 0)
				}
			}
		}
	}

	timing.BodyMaskMs = float64(time.Since(t0).Microseconds()) / 1000.0

	var tissuePixels int
	for _, v := range bodyMask.Data {
		if v > 0 {
			tissuePixels++
		}
	}

	// 1.5 3D Anatomical Surface Inflation & Lambertian Angle Compensation
	var reconRes *reconstruction3d.ReconstructionResult
	imgToAnalyze := src

	if cfg.Enable3DReconstruction {
		t3d := time.Now()
		r3dCfg := reconstruction3d.DefaultReconstructionConfig()
		res3D := reconstruction3d.Reconstruct3DAndCompensate(src, bodyMask, distMap, r3dCfg)
		reconRes = &res3D
		imgToAnalyze = res3D.CorrectedImage // Use angle-compensated true temperature matrix!
		timing.Reconstruction3DMs = float64(time.Since(t3d).Microseconds()) / 1000.0
	}

	// 2. Top-Hat morphology (AVX2-accelerated)
	t0 = time.Now()
	radius := morphology.DynamicKernelRadius(imgToAnalyze.Width, imgToAnalyze.Height, cfg.KernelFactor)
	topHatDiff := morphology.TopHat(imgToAnalyze, radius)
	timing.TopHatMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 3. Statistical outlier thresholding (with tissue median hyperthermia check!)
	t0 = time.Now()
	var stats statistics.OutlierStats
	if cfg.ThresholdMode == "GAUSSIAN" {
		stats = statistics.CalculateGaussianThreshold(topHatDiff, imgToAnalyze, bodyMask, cfg.KFactor)
	} else {
		stats = statistics.CalculateMADThreshold(topHatDiff, imgToAnalyze, bodyMask, cfg.KFactor)
	}
	binaryHotspots := statistics.ApplyThreshold(topHatDiff, imgToAnalyze, bodyMask, stats.Threshold, uint8(math.Round(stats.OrigMedian)))
	timing.ThresholdMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 4. Connected components & boundary/geometric circularity filter
	t0 = time.Now()
	fOpts := statistics.FilterOptions{
		MinAreaFraction:   cfg.MinAreaFraction,
		MinCircularity:    cfg.MinCircularity,
		BorderMarginPx:    15,
		MinDistFromBorder: 8.0,
		AnatomicalCutoffY: 0.65,
		OrigMedian:        stats.OrigMedian,
	}
	regions, filteredMask := statistics.ExtractHotspots(binaryHotspots, src, distMap, tissuePixels, fOpts)
	timing.GeometryMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 5. Optional: Vascular mapping (Fast Separable Frangi vesselness)
	var vascularMask *imageutil.GrayMatrix
	if cfg.RunVascularMap {
		t0 = time.Now()
		bodyDist := segmentation.ChamferDistanceTransform(bodyMask)
		vascularMask = vascular.MultiscaleFrangiVesselness(src, bodyMask, bodyDist, vascular.DefaultFrangiOptions())
		timing.VascularMs = float64(time.Since(t0).Microseconds()) / 1000.0
	}

	// 6. Optional: Longitudinal perfusion gradient
	var perfusionProfile *perfusion.PerfusionProfile
	if cfg.RunPerfusion {
		t0 = time.Now()
		p := perfusion.ComputeLongitudinalProfile(src, bodyMask)
		perfusionProfile = &p
		timing.PerfusionMs = float64(time.Since(t0).Microseconds()) / 1000.0
	}

	// 7. Clinical Lua Rule Evaluation
	t0 = time.Now()
	luaEngine := rules.NewLuaRuleEngine()
	defer luaEngine.Close()

	if cfg.LuaScriptPath != "" {
		_ = luaEngine.LoadScriptFromFile(cfg.LuaScriptPath)
	} else {
		_ = luaEngine.LoadScriptFromString(`
		function evaluate_hotspot(hotspot, stats)
			local baseline = stats.orig_median or stats.median or 120.0
			local delta = hotspot.max_val - baseline
			local is_sharp = (hotspot.edge_gradient or 0) >= 3.0
			local has_halo = (hotspot.halo_delta or 0) >= 5.0
			local is_metabolic = (hotspot.thermal_laplacian or 0) <= -3.5 or (hotspot.peak_to_mean or 1.0) >= 1.25

			if delta >= 22 then
				if is_sharp and not has_halo then
					return {
						risk_level = "CRITICAL",
						diagnosis_type = "INFLAMED_PRESSURE_POINT",
						recommendation = "AKUT GEFÄHRDET: Entzündete Druckstelle / Prä-Ulkus unter Hyperkeratose (Delta T >= 2.2 K). Hohes Ulzerationsrisiko! Sofortige Entlastung und Debridement.",
						score = 9.8
					}
				else
					return {
						risk_level = "CRITICAL",
						diagnosis_type = "INFLAMMATION",
						recommendation = "Pathologischer Entzündungsherd (Armstrong Delta T >= 2.2 K, Diffusionshalo). Verdacht auf floride Weichteilinfektion.",
						score = 9.5
					}
				end
			elseif delta >= 10 then
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
						recommendation = "Subklinische Weichteilentzündung (1.0 K <= Delta T < 2.2 K). Verlaufskontrolle in 48 Stunden.",
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
				if is_sharp then
					return {
						risk_level = "LOW",
						diagnosis_type = "PRESSURE_POINT",
						recommendation = "Oberflächliche Verhornung / milde Druckstelle.",
						score = 2.0
					}
				else
					return {
						risk_level = "BENIGN",
						diagnosis_type = "BENIGN",
						recommendation = "Physiologische Normaltemperatur / unkritischer Befund.",
						score = 1.0
					}
				end
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
	timing.LuaEvalMs = float64(time.Since(t0).Microseconds()) / 1000.0
	timing.TotalMs = float64(time.Since(startTotal).Microseconds()) / 1000.0

	var depth3D *imageutil.FloatMatrix
	var corrected3D *imageutil.GrayMatrix
	if reconRes != nil {
		depth3D = reconRes.DepthMapMm
		corrected3D = reconRes.CorrectedImage
	}

	return AnalysisResult{
		Hotspots:         summaries,
		Stats:            stats,
		Timing:           timing,
		Perfusion:        perfusionProfile,
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
