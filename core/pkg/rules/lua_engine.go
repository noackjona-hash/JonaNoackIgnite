package rules

import (
	"fmt"
	"os"

	"github.com/yuin/gopher-lua"
	"ignite-core/pkg/statistics"
)

// ClinicalAssessment represents the clinical evaluation returned from the Lua script.
type ClinicalAssessment struct {
	RiskLevel      string  `json:"risk_level"`     // "CRITICAL", "MODERATE", "LOW", "BENIGN"
	Recommendation string  `json:"recommendation"` // Clinical text
	Score          float64 `json:"score"`          // Quantitative score (e.g. 0 to 10)
	DiagnosisType  string  `json:"diagnosis_type"` // "INFLAMMATION", "PRESSURE_POINT", "INFLAMED_PRESSURE_POINT", "BENIGN"
}

// LuaRuleEngine manages embedded Lua script execution for medical decisions.
type LuaRuleEngine struct {
	L *lua.LState
}

// NewLuaRuleEngine creates an initialized Lua state.
func NewLuaRuleEngine() *LuaRuleEngine {
	L := lua.NewState()
	return &LuaRuleEngine{L: L}
}

// Close closes the Lua state.
func (e *LuaRuleEngine) Close() {
	if e.L != nil {
		e.L.Close()
	}
}

// LoadScriptFromFile loads a .lua file into the state.
func (e *LuaRuleEngine) LoadScriptFromFile(path string) error {
	content, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("failed to read lua script %s: %w", path, err)
	}
	return e.LoadScriptFromString(string(content))
}

// LoadScriptFromString executes Lua source code.
func (e *LuaRuleEngine) LoadScriptFromString(code string) error {
	if err := e.L.DoString(code); err != nil {
		return fmt.Errorf("lua execution error: %w", err)
	}
	return nil
}

// EvaluateHotspot runs the Lua function "evaluate_hotspot(hotspot, stats)"
func (e *LuaRuleEngine) EvaluateHotspot(h statistics.HotspotRegion, stats statistics.OutlierStats) (ClinicalAssessment, error) {
	luaFunc := e.L.GetGlobal("evaluate_hotspot")
	if luaFunc.Type() != lua.LTFunction {
		// Fallback default rule if no function defined
		return ClinicalAssessment{
			RiskLevel:      "UNASSESSED",
			Recommendation: "Keine Lua-Auswerteregel ('evaluate_hotspot') geladen.",
			DiagnosisType:  h.DiagnosisType,
		}, nil
	}

	// Prepare hotspot table
	htable := e.L.NewTable()
	htable.RawSetString("id", lua.LNumber(h.ID))
	htable.RawSetString("area_pixels", lua.LNumber(h.AreaPixels))
	htable.RawSetString("area_percent", lua.LNumber(h.AreaPercent))
	htable.RawSetString("circularity", lua.LNumber(h.Circularity))
	htable.RawSetString("max_val", lua.LNumber(h.MaxVal))
	htable.RawSetString("mean_val", lua.LNumber(h.MeanVal))
	htable.RawSetString("edge_gradient", lua.LNumber(h.EdgeGradient))
	htable.RawSetString("thermal_laplacian", lua.LNumber(h.ThermalLaplacian))
	htable.RawSetString("halo_delta", lua.LNumber(h.HaloDelta))
	htable.RawSetString("peak_to_mean", lua.LNumber(h.PeakToMean))
	htable.RawSetString("local_prominence", lua.LNumber(h.LocalProminence))
	htable.RawSetString("local_surround_med", lua.LNumber(h.LocalSurroundMed))
	htable.RawSetString("contra_delta", lua.LNumber(h.ContraDelta))
	htable.RawSetString("diagnosis_type", lua.LString(h.DiagnosisType))
	htable.RawSetString("confidence_score", lua.LNumber(h.ConfidenceScore))

	// Prepare stats table
	stable := e.L.NewTable()
	stable.RawSetString("median", lua.LNumber(stats.Median))
	stable.RawSetString("orig_median", lua.LNumber(stats.OrigMedian))
	stable.RawSetString("mad", lua.LNumber(stats.MAD))
	stable.RawSetString("mean", lua.LNumber(stats.Mean))
	stable.RawSetString("std_dev", lua.LNumber(stats.StdDev))
	stable.RawSetString("threshold", lua.LNumber(stats.Threshold))

	if err := e.L.CallByParam(lua.P{
		Fn:      luaFunc,
		NRet:    1,
		Protect: true,
	}, htable, stable); err != nil {
		return ClinicalAssessment{}, fmt.Errorf("error calling evaluate_hotspot: %w", err)
	}

	ret := e.L.Get(-1)
	e.L.Pop(1)

	assess := ClinicalAssessment{
		RiskLevel:      "BENIGN",
		Recommendation: "Kein Handlungsbedarf",
		DiagnosisType:  h.DiagnosisType,
	}

	if tbl, ok := ret.(*lua.LTable); ok {
		if v := tbl.RawGetString("risk_level"); v.Type() == lua.LTString {
			assess.RiskLevel = v.String()
		}
		if v := tbl.RawGetString("recommendation"); v.Type() == lua.LTString {
			assess.Recommendation = v.String()
		}
		if v := tbl.RawGetString("score"); v.Type() == lua.LTNumber {
			assess.Score = float64(v.(lua.LNumber))
		}
		if v := tbl.RawGetString("diagnosis_type"); v.Type() == lua.LTString {
			assess.DiagnosisType = v.String()
		}
	}

	return assess, nil
}
