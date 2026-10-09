package pipeline_test

import (
	"path/filepath"
	"testing"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
)

func TestBild1HotspotAssessments(t *testing.T) {
	imgPath := filepath.Join("..", "..", "..", "test-data", "bild (1).jpeg")
	gray, err := imageutil.LoadImageAsGray(imgPath)
	if err != nil {
		t.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)

	if res.TotalHotspots == 0 {
		t.Fatalf("Expected hotspots to be detected on Bild 1, got 0")
	}

	primary := res.Hotspots[0]
	// Assert that primary hotspot is within the inflamed toe ground truth area (X: 450..600, Y: 300..450)
	if primary.Region.CenterX < 450 || primary.Region.CenterX > 600 || primary.Region.CenterY < 300 || primary.Region.CenterY > 450 {
		t.Errorf("Expected primary hotspot on the inflamed toe (X:450..600, Y:300..450), got center (%d, %d)",
			primary.Region.CenterX, primary.Region.CenterY)
	}

	if primary.Assessment.RiskLevel != "CRITICAL" {
		t.Errorf("Expected primary hotspot risk to be CRITICAL, got %s", primary.Assessment.RiskLevel)
	}
}
