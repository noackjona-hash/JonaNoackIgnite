using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Ignite.Desktop.Models
{
    public class HotspotRegion
    {
        [JsonPropertyName("id")]
        public int Id { get; set; }

        [JsonPropertyName("area_pixels")]
        public int AreaPixels { get; set; }

        [JsonPropertyName("area_percent")]
        public double AreaPercent { get; set; }

        [JsonPropertyName("perimeter")]
        public double Perimeter { get; set; }

        [JsonPropertyName("circularity")]
        public double Circularity { get; set; }

        [JsonPropertyName("center_x")]
        public int CenterX { get; set; }

        [JsonPropertyName("center_y")]
        public int CenterY { get; set; }

        [JsonPropertyName("max_val")]
        public byte MaxVal { get; set; }

        [JsonPropertyName("mean_val")]
        public double MeanVal { get; set; }

        [JsonPropertyName("bounding_box")]
        public int[] BoundingBox { get; set; } = new int[4];

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;
    }

    public class ClinicalAssessment
    {
        [JsonPropertyName("risk_level")]
        public string RiskLevel { get; set; } = string.Empty;

        [JsonPropertyName("recommendation")]
        public string Recommendation { get; set; } = string.Empty;

        [JsonPropertyName("score")]
        public double Score { get; set; }
    }

    public class HotspotSummary
    {
        [JsonPropertyName("region")]
        public HotspotRegion Region { get; set; } = new();

        [JsonPropertyName("assessment")]
        public ClinicalAssessment Assessment { get; set; } = new();
    }

    public class OutlierStats
    {
        [JsonPropertyName("mean")]
        public double Mean { get; set; }

        [JsonPropertyName("std_dev")]
        public double StdDev { get; set; }

        [JsonPropertyName("median")]
        public double Median { get; set; }

        [JsonPropertyName("mad")]
        public double Mad { get; set; }

        [JsonPropertyName("threshold")]
        public byte Threshold { get; set; }

        [JsonPropertyName("mode")]
        public string Mode { get; set; } = string.Empty;

        [JsonPropertyName("orig_median")]
        public double OrigMedian { get; set; }
    }

    public class StageTiming
    {
        [JsonPropertyName("body_mask_ms")]
        public double BodyMaskMs { get; set; }

        [JsonPropertyName("tophat_ms")]
        public double TopHatMs { get; set; }

        [JsonPropertyName("threshold_ms")]
        public double ThresholdMs { get; set; }

        [JsonPropertyName("geometry_ms")]
        public double GeometryMs { get; set; }

        [JsonPropertyName("vascular_ms")]
        public double VascularMs { get; set; }

        [JsonPropertyName("perfusion_ms")]
        public double PerfusionMs { get; set; }

        [JsonPropertyName("lua_eval_ms")]
        public double LuaEvalMs { get; set; }

        [JsonPropertyName("total_ms")]
        public double TotalMs { get; set; }
    }

    public class PerfusionProfile
    {
        [JsonPropertyName("axis_values")]
        public List<float> AxisValues { get; set; } = new();

        [JsonPropertyName("mean_temperatures")]
        public List<float> MeanTemperatures { get; set; } = new();

        [JsonPropertyName("gradients")]
        public List<float> Gradients { get; set; } = new();

        [JsonPropertyName("max_gradient_drop")]
        public float MaxGradientDrop { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("description")]
        public string Description { get; set; } = string.Empty;
    }

    public class AnalysisResult
    {
        [JsonPropertyName("hotspots")]
        public List<HotspotSummary> Hotspots { get; set; } = new();

        [JsonPropertyName("stats")]
        public OutlierStats Stats { get; set; } = new();

        [JsonPropertyName("timing")]
        public StageTiming Timing { get; set; } = new();

        [JsonPropertyName("perfusion")]
        public PerfusionProfile? Perfusion { get; set; }

        [JsonPropertyName("tissue_pixel_count")]
        public int TissuePixelCount { get; set; }

        [JsonPropertyName("total_hotspots")]
        public int TotalHotspots { get; set; }

        [JsonPropertyName("highest_risk")]
        public string HighestRisk { get; set; } = string.Empty;
    }

    public class SymmetryZone
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("left_mean")]
        public float LeftMean { get; set; }

        [JsonPropertyName("right_mean")]
        public float RightMean { get; set; }

        [JsonPropertyName("delta_t")]
        public float DeltaT { get; set; }

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("is_pathologic")]
        public bool IsPathologic { get; set; }
    }

    public class BilateralResult
    {
        [JsonPropertyName("max_delta_t")]
        public float MaxDeltaT { get; set; }

        [JsonPropertyName("mean_delta_t")]
        public float MeanDeltaT { get; set; }

        [JsonPropertyName("zones")]
        public List<SymmetryZone> Zones { get; set; } = new();

        [JsonPropertyName("overall_status")]
        public string OverallStatus { get; set; } = string.Empty;

        [JsonPropertyName("clinical_assessment")]
        public string ClinicalAssessment { get; set; } = string.Empty;
    }
}
