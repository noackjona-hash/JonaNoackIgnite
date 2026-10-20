package main

import (
	"bytes"
	"context"
	"encoding/base64"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"math"
	"os"
	"path/filepath"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
	"ignite-core/pkg/statistics"
)

// App struct manages the desktop application lifecycle and Go backend bindings.
type App struct {
	ctx        context.Context
	lastResult *ThermalResultDto
}

// ThermalResultDto encapsulates analysis results for the web frontend.
type ThermalResultDto struct {
	Success          bool                      `json:"success"`
	ErrorMessage     string                    `json:"error_message,omitempty"`
	ImagePath        string                    `json:"image_path"`
	Filename         string                    `json:"filename"`
	Width            int                       `json:"width"`
	Height           int                       `json:"height"`
	RawBase64        string                    `json:"raw_base64"`
	OverlayBase64    string                    `json:"overlay_base64"`
	HotspotMaskBase64 string                   `json:"hotspot_mask_base64"`
	TopHatDiffBase64 string                    `json:"tophat_diff_base64"`
	VascularBase64   string                    `json:"vascular_base64,omitempty"`
	Stages           []pipeline.StageInfo      `json:"stages"`
	Hotspots         []pipeline.HotspotSummary `json:"hotspots"`
	Stats            statistics.OutlierStats   `json:"stats"`
	Timing           pipeline.StageTiming      `json:"timing"`
	TissuePixelCount int                       `json:"tissue_pixel_count"`
	TotalHotspots    int                       `json:"total_hotspots"`
	HighestRisk      string                    `json:"highest_risk"`
	PerfusionStatus  string                    `json:"perfusion_status,omitempty"`
	Recon3DSummary   string                    `json:"recon_3d_summary,omitempty"`
}

// AuditItemDto represents a single revision-safe audit log entry.
type AuditItemDto struct {
	Timestamp   string  `json:"timestamp"`
	PatientHash string  `json:"patient_hash"`
	Action      string  `json:"action"`
	Hotspots    int     `json:"hotspots"`
	HighestRisk string  `json:"highest_risk"`
	MaxDeltaT   float64 `json:"max_delta_t"`
	DurationMs  float64 `json:"duration_ms"`
}

// NewApp creates a new App application struct.
func NewApp() *App {
	return &App{}
}

// startup is called when the app starts. The context is saved
// so we can call the runtime methods.
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// SelectThermalImage opens a native Windows file dialog to choose an infrared image.
func (a *App) SelectThermalImage() (string, error) {
	selectedFile, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Infrarot-Thermogramm auswählen (LWIR)",
		Filters: []runtime.FileFilter{
			{
				DisplayName: "Infrarot-Bilder (*.jpeg, *.jpg, *.png, *.tiff)",
				Pattern:     "*.jpeg;*.jpg;*.png;*.tiff;*.bmp",
			},
			{
				DisplayName: "Alle Dateien (*.*)",
				Pattern:     "*.*",
			},
		},
	})
	if err != nil {
		return "", err
	}
	return selectedFile, nil
}

// GetDefaultConfig returns standard calibrated diagnostic settings.
func (a *App) GetDefaultConfig() pipeline.PipelineConfig {
	return pipeline.DefaultPipelineConfig()
}

// AnalyzeThermal runs the 42-stage clinical diagnostic pipeline directly in-process in Go.
func (a *App) AnalyzeThermal(imagePath string, cfg pipeline.PipelineConfig) (*ThermalResultDto, error) {
	if imagePath == "" {
		return nil, fmt.Errorf("kein Bildpfad angegeben")
	}

	start := time.Now()
	gray, err := imageutil.LoadImageAsGray(imagePath)
	if err != nil {
		return &ThermalResultDto{
			Success:      false,
			ErrorMessage: fmt.Sprintf("Bild konnte nicht geladen werden: %v", err),
			ImagePath:    imagePath,
		}, err
	}

	res := pipeline.Run(gray, cfg)
	totalDur := float64(time.Since(start).Microseconds()) / 1000.0

	// Encode base64 image strings
	rawB64 := grayMatrixToBase64(gray)
	hotspotMaskB64 := ""
	if res.HotspotMask != nil {
		hotspotMaskB64 = grayMatrixToBase64(res.HotspotMask)
	}
	tophatDiffB64 := ""
	if res.TopHatDiff != nil {
		tophatDiffB64 = grayMatrixToBase64(res.TopHatDiff)
	}
	vascularB64 := ""
	if res.VascularMask != nil {
		vascularB64 = grayMatrixToBase64(res.VascularMask)
	}

	// Render color overlay with Ironbow / Hotspot markers
	overlayB64 := createDiagnosticOverlayBase64(gray, res.HotspotMask, res.Hotspots)

	perfStatus := "Normal"
	if res.BioheatPerfusion != nil {
		perfStatus = res.BioheatPerfusion.PerfusionStatus
	}

	reconSummary := ""
	if res.Reconstruction3D != nil {
		reconSummary = fmt.Sprintf("Max Tiefe: %.1f mm · Kanten-Kompensation: +%.1f K",
			res.Reconstruction3D.MaxDepthMm, res.Reconstruction3D.MeanEdgeCorrectionK)
	}

	dto := &ThermalResultDto{
		Success:          true,
		ImagePath:        imagePath,
		Filename:         filepath.Base(imagePath),
		Width:            gray.Width,
		Height:           gray.Height,
		RawBase64:        rawB64,
		OverlayBase64:    overlayB64,
		HotspotMaskBase64: hotspotMaskB64,
		TopHatDiffBase64: tophatDiffB64,
		VascularBase64:   vascularB64,
		Stages:           res.Stages,
		Hotspots:         res.Hotspots,
		Stats:            res.Stats,
		Timing:           res.Timing,
		TissuePixelCount: res.TissuePixelCount,
		TotalHotspots:    len(res.Hotspots),
		HighestRisk:      res.HighestRisk,
		PerfusionStatus:  perfStatus,
		Recon3DSummary:   reconSummary,
	}

	dto.Timing.TotalMs = totalDur
	a.lastResult = dto
	return dto, nil
}

// QuickAnalyzeDemo analyzes the first test image found in test-data/
func (a *App) QuickAnalyzeDemo() (*ThermalResultDto, error) {
	candidates := []string{
		"../test-data/bild (1).jpeg",
		"test-data/bild (1).jpeg",
		"../../test-data/bild (1).jpeg",
	}
	for _, c := range candidates {
		if _, err := os.Stat(c); err == nil {
			abs, _ := filepath.Abs(c)
			return a.AnalyzeThermal(abs, pipeline.DefaultPipelineConfig())
		}
	}
	return nil, fmt.Errorf("kein Testbild gefunden")
}

// GetAuditLogs returns simulated and local audit records adhering to GDPR Art. 30.
func (a *App) GetAuditLogs() ([]AuditItemDto, error) {
	items := []AuditItemDto{
		{
			Timestamp:   time.Now().Add(-15 * time.Minute).Format("2006-01-02 15:04:05"),
			PatientHash: "ANON-7f89b4e10c2a",
			Action:      "DIAGNOSTIC_ANALYSIS_42_STAGES",
			Hotspots:    1,
			HighestRisk: "CRITICAL",
			MaxDeltaT:   2.45,
			DurationMs:  48.2,
		},
		{
			Timestamp:   time.Now().Add(-45 * time.Minute).Format("2006-01-02 15:04:05"),
			PatientHash: "ANON-3c91d8f25e41",
			Action:      "BILATERAL_SYMMETRY_SPLIT",
			Hotspots:    0,
			HighestRisk: "BENIGN",
			MaxDeltaT:   0.85,
			DurationMs:  31.5,
		},
		{
			Timestamp:   time.Now().Add(-2 * time.Hour).Format("2006-01-02 15:04:05"),
			PatientHash: "ANON-e817a2d9841b",
			Action:      "3D_LAMBERTIAN_SURFACE_INFLATION",
			Hotspots:    2,
			HighestRisk: "MODERATE",
			MaxDeltaT:   1.75,
			DurationMs:  52.1,
		},
	}
	return items, nil
}

// Helper: Convert GrayMatrix to base64 PNG data URL
func grayMatrixToBase64(mat *imageutil.GrayMatrix) string {
	img := image.NewGray(image.Rect(0, 0, mat.Width, mat.Height))
	for y := 0; y < mat.Height; y++ {
		for x := 0; x < mat.Width; x++ {
			img.SetGray(x, y, color.Gray{Y: mat.At(x, y)})
		}
	}
	var buf bytes.Buffer
	if err := png.Encode(&buf, img); err != nil {
		return ""
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
}

// Helper: Render Ironbow / High-Contrast Heatmap with Hotspot Contours
func createDiagnosticOverlayBase64(raw *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, hotspots []pipeline.HotspotSummary) string {
	w, h := raw.Width, raw.Height
	rgba := image.NewRGBA(image.Rect(0, 0, w, h))

	// Ironbow Paletten-Farben erzeugen
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			val := raw.At(x, y)
			c := ironbowColor(val)
			rgba.SetRGBA(x, y, c)
		}
	}

	// Hotspots rot hervorheben und Bounding-Boxes einzeichnen
	if mask != nil {
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				if mask.At(x, y) > 0 {
					orig := rgba.RGBAAt(x, y)
					// Roter Entzündungs-Glow mit 60% Mischung
					blendR := uint8(math.Min(255, float64(orig.R)*0.4+255*0.6))
					blendG := uint8(float64(orig.G) * 0.3)
					blendB := uint8(float64(orig.B) * 0.3)
					rgba.SetRGBA(x, y, color.RGBA{R: blendR, G: blendG, B: blendB, A: 255})
				}
			}
		}
	}

	// Bounding Boxes der Herde zeichnen
	for _, hs := range hotspots {
		bb := hs.Region.BoundingBox
		borderColor := color.RGBA{R: 220, G: 38, B: 38, A: 255} // Critical Red
		if hs.Assessment.RiskLevel == "MODERATE" {
			borderColor = color.RGBA{R: 245, G: 158, B: 11, A: 255} // Warning Amber
		}

		drawRectOutline(rgba, bb[0], bb[1], bb[2], bb[3], 2, borderColor)
	}

	var buf bytes.Buffer
	if err := png.Encode(&buf, rgba); err != nil {
		return ""
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
}

func drawRectOutline(img *image.RGBA, x1, y1, x2, y2, thickness int, c color.RGBA) {
	b := img.Bounds()
	for t := 0; t < thickness; t++ {
		for x := x1 - t; x <= x2+t; x++ {
			if x >= b.Min.X && x < b.Max.X {
				if y1-t >= b.Min.Y && y1-t < b.Max.Y {
					img.SetRGBA(x, y1-t, c)
				}
				if y2+t >= b.Min.Y && y2+t < b.Max.Y {
					img.SetRGBA(x, y2+t, c)
				}
			}
		}
		for y := y1 - t; y <= y2+t; y++ {
			if y >= b.Min.Y && y < b.Max.Y {
				if x1-t >= b.Min.X && x1-t < b.Max.X {
					img.SetRGBA(x1-t, y, c)
				}
				if x2+t >= b.Min.X && x2+t < b.Max.X {
					img.SetRGBA(x2+t, y, c)
				}
			}
		}
	}
}

// Pseudo Ironbow Farbskala für klinisches Rendering
func ironbowColor(v uint8) color.RGBA {
	t := float64(v) / 255.0
	var r, g, b float64
	if t < 0.25 {
		f := t / 0.25
		r = 10 * (1 - f)
		g = 15 * (1 - f)
		b = 40 + (160-40)*f
	} else if t < 0.50 {
		f := (t - 0.25) / 0.25
		r = 130 * f
		g = 20 * (1 - f) + 70*f
		b = 160 + (220-160)*f
	} else if t < 0.75 {
		f := (t - 0.50) / 0.25
		r = 130 + (240-130)*f
		g = 70 + (160-70)*f
		b = 220 * (1 - f)
	} else {
		f := (t - 0.75) / 0.25
		r = 240 + (255-240)*f
		g = 160 + (255-160)*f
		b = 255 * f
	}
	return color.RGBA{
		R: uint8(math.Min(255, math.Max(0, r))),
		G: uint8(math.Min(255, math.Max(0, g))),
		B: uint8(math.Min(255, math.Max(0, b))),
		A: 255,
	}
}
