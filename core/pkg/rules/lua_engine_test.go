package rules

import (
	"testing"

	"ignite-core/pkg/statistics"
)

func TestLuaHotspotEvaluation(t *testing.T) {
	engine := NewLuaRuleEngine()
	defer engine.Close()

	script := `
	function evaluate_hotspot(hotspot, stats)
		local delta = hotspot.max_val - stats.median
		if delta > 30 and hotspot.circularity > 0.1 then
			return {
				risk_level = "CRITICAL",
				recommendation = "Druckentlastung und aerztliche Inspektion",
				score = 9.5
			}
		else
			return {
				risk_level = "BENIGN",
				recommendation = "Regulaere Routinekontrolle",
				score = 1.0
			}
		end
	end
	`

	if err := engine.LoadScriptFromString(script); err != nil {
		t.Fatalf("failed to load lua script: %v", err)
	}

	h := statistics.HotspotRegion{
		ID:          1,
		AreaPixels:  150,
		Circularity: 0.45,
		MaxVal:      200,
	}
	stats := statistics.OutlierStats{
		Median: 120,
	}

	res, err := engine.EvaluateHotspot(h, stats)
	if err != nil {
		t.Fatalf("evaluation failed: %v", err)
	}

	if res.RiskLevel != "CRITICAL" {
		t.Fatalf("expected CRITICAL, got %s", res.RiskLevel)
	}
	if res.Score != 9.5 {
		t.Fatalf("expected score 9.5, got %f", res.Score)
	}
}
