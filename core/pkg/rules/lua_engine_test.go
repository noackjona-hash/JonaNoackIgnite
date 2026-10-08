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

func TestDifferentialPressurePointAndInflammation(t *testing.T) {
	engine := NewLuaRuleEngine()
	defer engine.Close()

	if err := engine.LoadScriptFromFile("../../../rules/armstrong_criteria.lua"); err != nil {
		t.Fatalf("failed to load armstrong_criteria.lua: %v", err)
	}

	stats := statistics.OutlierStats{
		OrigMedian: 120,
		Median:     120,
	}

	// 1. Druckstelle: Mäßige Erwärmung (Delta T = 1.5 K / 15 Einheiten), scharfer Randgradient, kein Diffusionshalo
	pressureSpot := statistics.HotspotRegion{
		ID:           1,
		MaxVal:       135, // Delta = 15
		EdgeGradient: 4.2, // Scharfe Kante (Hornhautplatte)
		HaloDelta:    1.2, // Kein perifokaler Halo
	}

	resPressure, err := engine.EvaluateHotspot(pressureSpot, stats)
	if err != nil {
		t.Fatalf("pressure eval error: %v", err)
	}
	if resPressure.DiagnosisType != "PRESSURE_POINT" {
		t.Fatalf("expected PRESSURE_POINT, got %s", resPressure.DiagnosisType)
	}

	// 2. Floride Entzündung: Hohe Hitze (Delta T = 2.5 K / 25 Einheiten), weicher Rand, starker Diffusionshalo
	inflamSpot := statistics.HotspotRegion{
		ID:               2,
		MaxVal:           145,  // Delta = 25 (Armstrong >= 2.2 K)
		Circularity:      0.45, // Ausgeprägt rund/fokal
		EdgeGradient:     1.8,  // Weicher Übergang ins Gewebe
		HaloDelta:        7.5,  // Reaktive perifokale Hyperämie
		ThermalLaplacian: -5.2, // Stark zentrierte metabolische Wärmequelle
	}

	resInflam, err := engine.EvaluateHotspot(inflamSpot, stats)
	if err != nil {
		t.Fatalf("inflammation eval error: %v", err)
	}
	if resInflam.DiagnosisType != "INFLAMMATION" {
		t.Fatalf("expected INFLAMMATION, got %s", resInflam.DiagnosisType)
	}
	if resInflam.RiskLevel != "CRITICAL" {
		t.Fatalf("expected CRITICAL for severe inflammation, got %s", resInflam.RiskLevel)
	}

	// 3. Entzündete Druckstelle / Prä-Ulkus: Delta T = 2.6 K unter scharfkantiger Hornhautplatte
	inflamedPressureSpot := statistics.HotspotRegion{
		ID:           3,
		MaxVal:       146, // Delta = 26
		EdgeGradient: 4.8, // Scharfe Hornhautbegrenzung
		HaloDelta:    2.0, // Keine weite Ausbreitung durch isolierende Keratose
	}

	resInflamedPressure, err := engine.EvaluateHotspot(inflamedPressureSpot, stats)
	if err != nil {
		t.Fatalf("inflamed pressure eval error: %v", err)
	}
	if resInflamedPressure.DiagnosisType != "INFLAMED_PRESSURE_POINT" {
		t.Fatalf("expected INFLAMED_PRESSURE_POINT, got %s", resInflamedPressure.DiagnosisType)
	}
}
