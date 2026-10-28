//go:build wails

package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
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
	lastRes    *pipeline.AnalysisResult
	lastGray   *imageutil.GrayMatrix
	audit      []AuditItemDto
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
	DepthBase64      string                    `json:"depth_base64,omitempty"`
	MaxDepthMm       float64                   `json:"max_depth_mm"`
	CorrectedBase64  string                    `json:"corrected_base64,omitempty"`
	BioheatMean      float64                   `json:"bioheat_mean"`
	BioheatHyperPct  float64                   `json:"bioheat_hyper_pct"`
	EdgeCorrectionK  float64                   `json:"edge_correction_k"`
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
	Hash        string  `json:"hash"`
	PrevHash    string  `json:"prev_hash"`
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
	if res.DepthMap3D != nil {
		dto.DepthBase64 = grayMatrixToBase64(res.DepthMap3D.ToGrayMasked(res.BodyMask))
	}
	if res.Corrected3DImage != nil {
		dto.CorrectedBase64 = grayMatrixToBase64(res.Corrected3DImage)
	}
	if res.Reconstruction3D != nil {
		dto.MaxDepthMm = res.Reconstruction3D.MaxDepthMm
		dto.EdgeCorrectionK = res.Reconstruction3D.MeanEdgeCorrectionK
	}
	if res.BioheatPerfusion != nil {
		dto.BioheatMean = res.BioheatPerfusion.MeanPerfusion
		dto.BioheatHyperPct = res.BioheatPerfusion.HyperaemicArea
	}
	a.lastResult = dto
	a.lastRes = &res
	a.lastGray = gray

	maxDelta := 0.0
	for _, hs := range res.Hotspots {
		if d := hs.Region.ContraDelta * 0.1; d > maxDelta {
			maxDelta = d
		}
	}
	a.recordAudit("DIAGNOSTIC_ANALYSIS_42_STAGES", imagePath, len(res.Hotspots), res.HighestRisk, maxDelta, totalDur)
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

// recordAudit appends a hash-chained entry (SHA-256) to the in-memory GDPR Art. 30 audit trail.
func (a *App) recordAudit(action, source string, hotspots int, risk string, maxDelta, durMs float64) {
	sum := sha256.Sum256([]byte(source))
	prev := "GENESIS"
	if n := len(a.audit); n > 0 {
		prev = a.audit[n-1].Hash
	}
	e := AuditItemDto{
		Timestamp:   time.Now().Format("2006-01-02 15:04:05"),
		PatientHash: "ANON-" + hex.EncodeToString(sum[:])[:12],
		Action:      action,
		Hotspots:    hotspots,
		HighestRisk: risk,
		MaxDeltaT:   maxDelta,
		DurationMs:  durMs,
		PrevHash:    prev,
	}
	e.Hash = auditHash(e)
	a.audit = append(a.audit, e)
}

func auditHash(e AuditItemDto) string {
	s := fmt.Sprintf("%s|%s|%s|%d|%s|%.3f|%.3f|%s", e.Timestamp, e.PatientHash, e.Action, e.Hotspots, e.HighestRisk, e.MaxDeltaT, e.DurationMs, e.PrevHash)
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])
}

// GetAuditLogs returns the revision-safe hash-chained audit records (GDPR Art. 30).
func (a *App) GetAuditLogs() ([]AuditItemDto, error) {
	return a.audit, nil
}

// VerifyAuditChain recomputes all SHA-256 links; returns index of first broken link or -1.
func (a *App) VerifyAuditChain() int {
	prev := "GENESIS"
	for i, e := range a.audit {
		if e.PrevHash != prev || auditHash(e) != e.Hash {
			return i
		}
		prev = e.Hash
	}
	return -1
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

// Helper: Render Ironbow / High-Contrast Heatmap with Hotspot Contours & Clinical Callout Overlays
func createDiagnosticOverlayBase64(raw *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, hotspots []pipeline.HotspotSummary) string {
	w, h := raw.Width, raw.Height
	rgba := image.NewRGBA(image.Rect(0, 0, w, h))

	// 1. Hintergrund: Ironbow Farbpalette
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			val := raw.At(x, y)
			c := ironbowColor(val)
			rgba.SetRGBA(x, y, c)
		}
	}

	// 2. Bestätigte Hotspots mit leuchtender Kontur und transluzentem Entzündungs-Glow hervorheben
	if mask != nil {
		for y := 1; y < h-1; y++ {
			for x := 1; x < w-1; x++ {
				if mask.At(x, y) > 0 {
					orig := rgba.RGBAAt(x, y)
					// Prüfen ob Kantenpixel
					isEdge := mask.At(x-1, y) == 0 || mask.At(x+1, y) == 0 ||
						mask.At(x, y-1) == 0 || mask.At(x, y+1) == 0

					if isEdge {
						// Leuchtende Kontur
						rgba.SetRGBA(x, y, color.RGBA{R: 239, G: 68, B: 68, A: 255})
					} else {
						// Sanfte Transluzenz zur Erhaltung der thermischen Tiefenstruktur
						blendR := uint8(math.Min(255, float64(orig.R)*0.75+239.0*0.25))
						blendG := uint8(float64(orig.G)*0.75 + 30.0*0.25)
						blendB := uint8(float64(orig.B)*0.75 + 30.0*0.25)
						rgba.SetRGBA(x, y, color.RGBA{R: blendR, G: blendG, B: blendB, A: 255})
					}
				}
			}
		}
	}

	// 3. Klinische Bounding-Boxes, Fadenkreuze und Callouts der bestätigten Herde einzeichnen
	for idx, hs := range hotspots {
		bb := hs.Region.BoundingBox
		borderColor := color.RGBA{R: 220, G: 38, B: 38, A: 255} // Critical Red
		if hs.Assessment.RiskLevel == "MODERATE" {
			borderColor = color.RGBA{R: 245, G: 158, B: 11, A: 255} // Warning Amber
		}

		// Rechteck-Umriss
		drawRectOutline(rgba, bb[0], bb[1], bb[2], bb[3], 2, borderColor)

		// Eck-Klammern für professionellen PACS-Look
		drawCornerBrackets(rgba, bb[0], bb[1], bb[2], bb[3], 14, 3, borderColor)

		// Zentrales Zielkreuz am Herd-Zentrum
		drawCrosshair(rgba, hs.Region.CenterX, hs.Region.CenterY, 6, borderColor)

		// Dunkler Callout-Badge am oberen Rand des Herdes
		badgeY := bb[1] - 18
		if badgeY < 6 {
			badgeY = bb[3] + 6
		}
		drawBadgeBar(rgba, bb[0], badgeY, 130, 14, borderColor, idx+1)
	}

	var buf bytes.Buffer
	if err := png.Encode(&buf, rgba); err != nil {
		return ""
	}
	return "data:image/png;base64," + base64.StdEncoding.EncodeToString(buf.Bytes())
}

func drawCornerBrackets(img *image.RGBA, x1, y1, x2, y2, length, thickness int, c color.RGBA) {
	b := img.Bounds()
	drawH := func(xStart, xEnd, y int) {
		for t := 0; t < thickness; t++ {
			yy := y + t
			if yy < b.Min.Y || yy >= b.Max.Y {
				continue
			}
			for xx := xStart; xx <= xEnd; xx++ {
				if xx >= b.Min.X && xx < b.Max.X {
					img.SetRGBA(xx, yy, c)
				}
			}
		}
	}
	drawV := func(x, yStart, yEnd int) {
		for t := 0; t < thickness; t++ {
			xx := x + t
			if xx < b.Min.X || xx >= b.Max.X {
				continue
			}
			for yy := yStart; yy <= yEnd; yy++ {
				if yy >= b.Min.Y && yy < b.Max.Y {
					img.SetRGBA(xx, yy, c)
				}
			}
		}
	}

	// Top-Left
	drawH(x1, x1+length, y1)
	drawV(x1, y1, y1+length)
	// Top-Right
	drawH(x2-length, x2, y1)
	drawV(x2-thickness+1, y1, y1+length)
	// Bottom-Left
	drawH(x1, x1+length, y2-thickness+1)
	drawV(x1, y2-length, y2)
	// Bottom-Right
	drawH(x2-length, x2, y2-thickness+1)
	drawV(x2-thickness+1, y2-length, y2)
}

func drawCrosshair(img *image.RGBA, cx, cy, r int, c color.RGBA) {
	b := img.Bounds()
	for d := -r; d <= r; d++ {
		if cx+d >= b.Min.X && cx+d < b.Max.X && cy >= b.Min.Y && cy < b.Max.Y {
			img.SetRGBA(cx+d, cy, c)
		}
		if cx >= b.Min.X && cx < b.Max.X && cy+d >= b.Min.Y && cy+d < b.Max.Y {
			img.SetRGBA(cx, cy+d, c)
		}
	}
}

func drawBadgeBar(img *image.RGBA, x, y, w, h int, c color.RGBA, id int) {
	b := img.Bounds()
	bg := color.RGBA{R: 11, G: 15, B: 25, A: 230} // Dark Slate
	for by := y; by < y+h; by++ {
		if by < b.Min.Y || by >= b.Max.Y {
			continue
		}
		for bx := x; bx < x+w; bx++ {
			if bx < b.Min.X || bx >= b.Max.X {
				continue
			}
			if by == y || by == y+h-1 || bx == x || bx == x+w-1 {
				img.SetRGBA(bx, by, c)
			} else {
				img.SetRGBA(bx, by, bg)
			}
		}
	}
	// Marker-Punkt links im Badge
	for dy := -2; dy <= 2; dy++ {
		for dx := -2; dx <= 2; dx++ {
			px, py := x + 7 + dx, y + h/2 + dy
			if px >= b.Min.X && px < b.Max.X && py >= b.Min.Y && py < b.Max.Y {
				img.SetRGBA(px, py, c)
			}
		}
	}
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
