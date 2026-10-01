package pipeline

import (
	"time"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
	"ignite-core/pkg/perfusion"
	"ignite-core/pkg/rules"
	"ignite-core/pkg/segmentation"
	"ignite-core/pkg/statistics"
	"ignite-core/pkg/vascular"
)

// PipelineConfig contains all tuning parameters for an analysis run.
type PipelineConfig struct {
	KernelFactor     float64 `json:"kernel_factor"`      // default 0.05
	MarginFactor     float32 `json:"margin_factor"`      // default 0.05
	KFactor          float64 `json:"k_factor"`           // default 2.5
	ThresholdMode    string  `json:"threshold_mode"`     // "MAD" or "GAUSSIAN"
	MinAreaFraction  float64 `json:"min_area_fraction"`  // default 0.0005
	MinCircularity   float64 `json:"min_circularity"`   // default 0.08
	RunVascularMap   bool    `json:"run_vascular_map"`   // enable Frangi filter
	RunPerfusion     bool    `json:"run_perfusion"`      // enable longitudinal gradient
	LuaScriptPath    string  `json:"lua_script_path"`    // optional path to custom Lua rule
}

// DefaultPipelineConfig returns standard research parameters.
func DefaultPipelineConfig() PipelineConfig {
	return PipelineConfig{
		KernelFactor:    0.05,
		MarginFactor:    0.05,
		KFactor:         2.5,
		ThresholdMode:   "MAD",
		MinAreaFraction: 0.0005,
		MinCircularity:  0.08,
		RunVascularMap:  true,
		RunPerfusion:    true,
	}
}

// StageTiming measures benchmark time in milliseconds.
type StageTiming struct {
	BodyMaskMs   float64 `json:"body_mask_ms"`
	TopHatMs     float64 `json:"tophat_ms"`
	ThresholdMs  float64 `json:"threshold_ms"`
	GeometryMs   float64 `json:"geometry_ms"`
	VascularMs   float64 `json:"vascular_ms,omitempty"`
	PerfusionMs  float64 `json:"perfusion_ms,omitempty"`
	LuaEvalMs    float64 `json:"lua_eval_ms"`
	TotalMs      float64 `json:"total_ms"`
}

// AnalysisResult encapsulates all outputs of the multi-stage analysis.
type AnalysisResult struct {
	Hotspots         []HotspotSummary          `json:"hotspots"`
	Stats            statistics.OutlierStats   `json:"stats"`
	Timing           StageTiming               `json:"timing"`
	Perfusion        *perfusion.PerfusionProfile `json:"perfusion,omitempty"`
	TissuePixelCount int                       `json:"tissue_pixel_count"`
	TotalHotspots    int                       `json:"total_hotspots"`
	HighestRisk      string                    `json:"highest_risk"`
	
	// Binary/Grayscale matrices (kept for image export/GUI rendering)
	BodyMask     *imageutil.GrayMatrix `json:"-"`
	TopHatDiff   *imageutil.GrayMatrix `json:"-"`
	HotspotMask  *imageutil.GrayMatrix `json:"-"`
	VascularMask *imageutil.GrayMatrix `json:"-"`
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

	// 1. Body mask & distance erosion
	t0 := time.Now()
	rawMask := segmentation.SegmentBodyMask(src)
	bodyMask := segmentation.ErodeBodyMask(rawMask, cfg.MarginFactor)
	timing.BodyMaskMs = float64(time.Since(t0).Microseconds()) / 1000.0

	var tissuePixels int
	for _, v := range bodyMask.Data {
		if v > 0 {
			tissuePixels++
		}
	}

	// 2. Top-Hat morphology (AVX2-accelerated)
	t0 = time.Now()
	radius := morphology.DynamicKernelRadius(src.Width, src.Height, cfg.KernelFactor)
	topHatDiff := morphology.TopHat(src, radius)
	timing.TopHatMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 3. Statistical outlier thresholding
	t0 = time.Now()
	var stats statistics.OutlierStats
	if cfg.ThresholdMode == "GAUSSIAN" {
		stats = statistics.CalculateGaussianThreshold(topHatDiff, bodyMask, cfg.KFactor)
	} else {
		stats = statistics.CalculateMADThreshold(topHatDiff, bodyMask, cfg.KFactor)
	}
	binaryHotspots := statistics.ApplyThreshold(topHatDiff, bodyMask, stats.Threshold)
	timing.ThresholdMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 4. Connected components & geometric circularity filter
	t0 = time.Now()
	fOpts := statistics.FilterOptions{
		MinAreaFraction: cfg.MinAreaFraction,
		MinCircularity:  cfg.MinCircularity,
	}
	regions, filteredMask := statistics.ExtractHotspots(binaryHotspots, src, tissuePixels, fOpts)
	timing.GeometryMs = float64(time.Since(t0).Microseconds()) / 1000.0

	// 5. Optional: Vascular mapping (Frangi vesselness)
	var vascularMask *imageutil.GrayMatrix
	if cfg.RunVascularMap {
		t0 = time.Now()
		vascularMask = vascular.MultiscaleFrangiVesselness(src, bodyMask, vascular.DefaultFrangiOptions())
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
		// Embedded default clinical rule:
		_ = luaEngine.LoadScriptFromString(`
		function evaluate_hotspot(hotspot, stats)
			local delta = hotspot.max_val - stats.median
			if delta >= 25 and hotspot.circularity >= 0.12 then
				return {
					risk_level = "CRITICAL",
					recommendation = "Pathologischer Entzündungsherd (ΔT hoch). Druckentlastung und fachärztliche Abklärung.",
					score = 9.0
				}
			elseif delta >= 15 then
				return {
					risk_level = "MODERATE",
					recommendation = "Lokale Hyperthermie. Kontrolle in 48 Stunden.",
					score = 5.5
				}
			else
				return {
					risk_level = "BENIGN",
					recommendation = "Physiologische Variation / unkritische Erwärmung.",
					score = 1.0
				}
			end
		end
		`)
	}

	highestRisk := "BENIGN"
	var summaries []HotspotSummary
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
		summaries = append(summaries, HotspotSummary{
			Region:     r,
			Assessment: assess,
		})
	}
	timing.LuaEvalMs = float64(time.Since(t0).Microseconds()) / 1000.0
	timing.TotalMs = float64(time.Since(startTotal).Microseconds()) / 1000.0

	return AnalysisResult{
		Hotspots:         summaries,
		Stats:            stats,
		Timing:           timing,
		Perfusion:        perfusionProfile,
		TissuePixelCount: tissuePixels,
		TotalHotspots:    len(summaries),
		HighestRisk:      highestRisk,
		BodyMask:         bodyMask,
		TopHatDiff:       topHatDiff,
		HotspotMask:      filteredMask,
		VascularMask:     vascularMask,
	}
}
