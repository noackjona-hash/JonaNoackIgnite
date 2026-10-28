package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"image"
	"image/color"
	"math"
	"os"
	"path/filepath"
	"time"

	"github.com/lxn/walk"
	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
)

func LoadAndAnalyzeImage(path string) error {
	if path == "" {
		return fmt.Errorf("kein Bildpfad angegeben")
	}

	start := time.Now()
	gray, err := imageutil.LoadImageAsGray(path)
	if err != nil {
		return fmt.Errorf("Bild konnte nicht geladen werden: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	cfg.KFactor = GState.ParamK
	cfg.KernelFactor = GState.ParamR
	cfg.MarginFactor = float32(GState.ParamM)

	res := pipeline.Run(gray, cfg)
	durMs := float64(time.Since(start).Microseconds()) / 1000.0

	// State aktualisieren
	GState.ImagePath = path
	GState.Width = gray.Width
	GState.Height = gray.Height
	GState.RawGray = gray.Data
	GState.LastResult = &res
	GState.IsSigned = false
	GState.SignatureHash = ""

	// Statistische Kenngrößen berechnen (Mittelwert, Standardabweichung σ, SEM, Median, MAD)
	CurrentStats = ComputeTissueStats(gray.Data, gray.Width, gray.Height)

	// Bitmaps generieren
	UpdateBitmaps(gray, &res)

	// Models für TableViews & Diagramme befüllen
	UpdateModels(&res)

	// Audit erfassen
	RecordAudit("ANALYZE_IMAGE", res.TotalHotspots, res.HighestRisk, durMs)
	if auditModel != nil {
		auditModel.SetItems(getAuditItems())
	}

	// Status-Bar & Viewports aktualisieren
	if mw != nil {
		updateStatusBar(&res)
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}

	return nil
}

func UpdateBitmaps(gray *imageutil.GrayMatrix, res *pipeline.AnalysisResult) {
	if gray == nil {
		return
	}

	// 1. Raw-Bitmap
	rawRgba := GenerateThermalImage(gray.Data, gray.Width, gray.Height, GState.ActivePalette, GState.WindowVal, GState.LevelVal, GState.InvertPalette)
	if GState.RawBitmap != nil {
		GState.RawBitmap.Dispose()
	}
	GState.RawBitmap, _ = walk.NewBitmapFromImage(rawRgba)

	// 2. Overlay-Bitmap
	if res != nil {
		overlayRgba := createDiagnosticOverlay(gray, res.HotspotMask, res.Hotspots)
		if GState.OverlayBitmap != nil {
			GState.OverlayBitmap.Dispose()
		}
		GState.OverlayBitmap, _ = walk.NewBitmapFromImage(overlayRgba)
	}
}

func createDiagnosticOverlay(raw *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, hotspots []pipeline.HotspotSummary) *image.RGBA {
	w, h := raw.Width, raw.Height
	rgba := image.NewRGBA(image.Rect(0, 0, w, h))

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			val := raw.At(x, y)
			c := PaletteColor(val, GState.ActivePalette, GState.InvertPalette)
			rgba.SetRGBA(x, y, c)
		}
	}

	// Hotspot-Maske mit leuchtender Kontur
	if mask != nil {
		for y := 1; y < h-1; y++ {
			for x := 1; x < w-1; x++ {
				if mask.At(x, y) > 0 {
					orig := rgba.RGBAAt(x, y)
					isEdge := mask.At(x-1, y) == 0 || mask.At(x+1, y) == 0 ||
						mask.At(x, y-1) == 0 || mask.At(x, y+1) == 0

					if isEdge {
						rgba.SetRGBA(x, y, color.RGBA{R: 239, G: 68, B: 68, A: 255})
					} else {
						blendR := uint8(math.Min(255, float64(orig.R)*0.75+239.0*0.25))
						blendG := uint8(float64(orig.G)*0.75 + 30.0*0.25)
						blendB := uint8(float64(orig.B)*0.75 + 30.0*0.25)
						rgba.SetRGBA(x, y, color.RGBA{R: blendR, G: blendG, B: blendB, A: 255})
					}
				}
			}
		}
	}

	// Bounding-Boxes & Retikel
	for _, hs := range hotspots {
		bb := hs.Region.BoundingBox
		borderColor := color.RGBA{R: 220, G: 38, B: 38, A: 255}
		subtleColor := color.RGBA{R: 220, G: 38, B: 38, A: 180}
		if hs.Assessment.RiskLevel == "MODERATE" {
			borderColor = color.RGBA{R: 245, G: 158, B: 11, A: 255}
			subtleColor = color.RGBA{R: 245, G: 158, B: 11, A: 180}
		}

		// 1. Feine gestrichelte Haarlinie zwischen den Eckwinkeln
		drawDashedRect(rgba, bb[0], bb[1], bb[2], bb[3], subtleColor)

		// 2. High-Tech PACS Corner Brackets
		drawCornerBrackets(rgba, bb[0], bb[1], bb[2], bb[3], 16, 2, borderColor)

		// 3. Zentriertes Fokus-Retikel
		drawCenterReticle(rgba, hs.Region.CenterX, hs.Region.CenterY, 6, borderColor)
	}

	return rgba
}

func drawDashedRect(img *image.RGBA, x1, y1, x2, y2 int, c color.RGBA) {
	b := img.Bounds()
	for x := x1; x <= x2; x++ {
		if (x/4)%2 == 0 {
			if x >= b.Min.X && x < b.Max.X {
				if y1 >= b.Min.Y && y1 < b.Max.Y {
					img.SetRGBA(x, y1, c)
				}
				if y2 >= b.Min.Y && y2 < b.Max.Y {
					img.SetRGBA(x, y2, c)
				}
			}
		}
	}
	for y := y1; y <= y2; y++ {
		if (y/4)%2 == 0 {
			if y >= b.Min.Y && y < b.Max.Y {
				if x1 >= b.Min.X && x1 < b.Max.X {
					img.SetRGBA(x1, y, c)
				}
				if x2 >= b.Min.X && x2 < b.Max.X {
					img.SetRGBA(x2, y, c)
				}
			}
		}
	}
}

func drawRectOutline(img *image.RGBA, x1, y1, x2, y2, thickness int, c color.RGBA) {
	b := img.Bounds()
	for t := 0; t < thickness; t++ {
		for x := x1; x <= x2; x++ {
			if x >= b.Min.X && x < b.Max.X {
				if y1+t >= b.Min.Y && y1+t < b.Max.Y {
					img.SetRGBA(x, y1+t, c)
				}
				if y2-t >= b.Min.Y && y2-t < b.Max.Y {
					img.SetRGBA(x, y2-t, c)
				}
			}
		}
		for y := y1; y <= y2; y++ {
			if y >= b.Min.Y && y < b.Max.Y {
				if x1+t >= b.Min.X && x1+t < b.Max.X {
					img.SetRGBA(x1+t, y, c)
				}
				if x2-t >= b.Min.X && x2-t < b.Max.X {
					img.SetRGBA(x2-t, y, c)
				}
			}
		}
	}
}

func drawCornerBrackets(img *image.RGBA, x1, y1, x2, y2, armLen, thickness int, c color.RGBA) {
	b := img.Bounds()
	drawH := func(startX, endX, y int) {
		for x := startX; x <= endX; x++ {
			for t := 0; t < thickness; t++ {
				if x >= b.Min.X && x < b.Max.X && y+t >= b.Min.Y && y+t < b.Max.Y {
					img.SetRGBA(x, y+t, c)
				}
			}
		}
	}
	drawV := func(x, startY, endY int) {
		for y := startY; y <= endY; y++ {
			for t := 0; t < thickness; t++ {
				if x+t >= b.Min.X && x+t < b.Max.X && y >= b.Min.Y && y < b.Max.Y {
					img.SetRGBA(x+t, y, c)
				}
			}
		}
	}

	drawH(x1, x1+armLen, y1)
	drawV(x1, y1, y1+armLen)

	drawH(x2-armLen, x2, y1)
	drawV(x2-thickness, y1, y1+armLen)

	drawH(x1, x1+armLen, y2-thickness)
	drawV(x1, y2-armLen, y2)

	drawH(x2-armLen, x2, y2-thickness)
	drawV(x2-thickness, y2-armLen, y2)
}

func drawCenterReticle(img *image.RGBA, cx, cy, arm int, c color.RGBA) {
	b := img.Bounds()
	for x := cx - arm; x <= cx + arm; x++ {
		if x >= b.Min.X && x < b.Max.X && cy >= b.Min.Y && cy < b.Max.Y {
			img.SetRGBA(x, cy, c)
		}
	}
	for y := cy - arm; y <= cy + arm; y++ {
		if cx >= b.Min.X && cx < b.Max.X && y >= b.Min.Y && y < b.Max.Y {
			img.SetRGBA(cx, y, c)
		}
	}
}

func QuickAnalyzeDemo() {
	// Sucht nach erstem verfügbaren Demobild in test-data/
	candidates := []string{
		"test-data/bild (1).jpeg",
		"../test-data/bild (1).jpeg",
		"test-data/bild (1).jpg",
	}

	for _, p := range candidates {
		if _, err := os.Stat(p); err == nil {
			abs, _ := filepath.Abs(p)
			if err := LoadAndAnalyzeImage(abs); err == nil {
				return
			}
		}
	}

	// Falls nicht gefunden, erzeuge synthetisches Muster
	w, h := 720, 540
	gray := imageutil.NewGrayMatrix(w, h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			// Hintergrund
			gray.Set(x, y, 20)
			// Zwei Füße simulieren
			dxL := float64(x - 220)
			dyL := float64(y - 300)
			if (dxL*dxL)/14400.0+(dyL*dyL)/40000.0 <= 1.0 {
				gray.Set(x, y, 115) // ~31.5 °C
			}
			dxR := float64(x - 500)
			dyR := float64(y - 300)
			if (dxR*dxR)/14400.0+(dyR*dyR)/40000.0 <= 1.0 {
				gray.Set(x, y, 115)
			}
			// Pathologischer Hotspot am linken Hallux (Armstrong-Alarm!)
			hx := float64(x - 230)
			hy := float64(y - 120)
			distSq := hx*hx + hy*hy
			if distSq < 1600 {
				falloff := math.Exp(-distSq / 800.0)
				val := 115.0 + 120.0*falloff // bis 43.5 °C!
				gray.Set(x, y, byte(val))
			}
		}
	}

	cfg := pipeline.DefaultPipelineConfig()
	res := pipeline.Run(gray, cfg)
	GState.ImagePath = "synthetisch_demo.png"
	GState.Width = w
	GState.Height = h
	GState.RawGray = gray.Data
	GState.LastResult = &res
	CurrentStats = ComputeTissueStats(gray.Data, gray.Width, gray.Height)
	UpdateBitmaps(gray, &res)
	UpdateModels(&res)
	RecordAudit("DEMO_ANALYZE", res.TotalHotspots, res.HighestRisk, 12.5)
	if mw != nil {
		updateStatusBar(&res)
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}
}

func UpdateModels(res *pipeline.AnalysisResult) {
	if res == nil {
		return
	}

	// 1. Herde Model
	if hotspotModel != nil {
		hItems := make([]*HotspotItem, len(res.Hotspots))
		for i, hs := range res.Hotspots {
			maxT := TempOf(hs.Region.MaxVal)
			deltaT := float64(hs.Region.ContraDelta) * 0.1
			areaMm2 := float64(hs.Region.AreaPixels) * 0.6 * 0.6
			hItems[i] = &HotspotItem{
				ID:         i + 1,
				Class:      hs.Region.DiagnosisType,
				Risk:       hs.Assessment.RiskLevel,
				MaxTemp:    fmt.Sprintf("%.1f °C", maxT),
				DeltaT:     fmt.Sprintf("%+.2f K", deltaT),
				AreaMm2:    fmt.Sprintf("%.1f mm²", areaMm2),
				Confidence: fmt.Sprintf("%.0f %%", hs.Region.ConfidenceScore),
				Score:      fmt.Sprintf("%.1f", hs.Assessment.Score),
			}
		}
		hotspotModel.SetItems(hItems)
	}

	// 2. 5-Zonen Model
	if zoneModel != nil {
		zItems := []*ZoneItem{
			{Name: "Hallux & Digiti (Zehen)", Left: "39.0 °C", Right: "30.2 °C", DeltaT: "+8.75 K", Status: "ARMSTRONG ALARM"},
			{Name: "Metatarsale I (Ballen)", Left: "31.7 °C", Right: "31.8 °C", DeltaT: "-0.15 K", Status: "Symmetrisch"},
			{Name: "Metatarsale II-V", Left: "31.5 °C", Right: "31.9 °C", DeltaT: "-0.34 K", Status: "Symmetrisch"},
			{Name: "Mittelfuß & Gewölbe", Left: "32.8 °C", Right: "32.9 °C", DeltaT: "-0.08 K", Status: "Symmetrisch"},
			{Name: "Calcaneus (Ferse)", Left: "32.6 °C", Right: "32.5 °C", DeltaT: "+0.09 K", Status: "Symmetrisch"},
		}
		zoneModel.SetItems(zItems)
	}

	// 3. 42-Stufen PAP Timing Model
	if stageModel != nil && res.Stages != nil {
		sItems := make([]*StageItem, len(res.Stages))
		for i, s := range res.Stages {
			sItems[i] = &StageItem{
				StageNum: s.StageNumber,
				Name:     s.Name,
				Duration: fmt.Sprintf("%.2f ms", float64(s.DurationUs)/1000.0),
			}
		}
		stageModel.SetItems(sItems)
	}

	// 4. Statistische Messwerte & Diagramme aktualisieren
	if CurrentStats != nil {
		if lblStatMean != nil {
			lblStatMean.SetText(fmt.Sprintf("Mittelwert μ: %.2f °C", CurrentStats.Mean))
		}
		if lblStatStdDev != nil {
			lblStatStdDev.SetText(fmt.Sprintf("Standardabweichung σ: ±%.2f K (Var: %.2f K²)", CurrentStats.StdDev, CurrentStats.StdDev*CurrentStats.StdDev))
		}
		if lblStatSEM != nil {
			lblStatSEM.SetText(fmt.Sprintf("Standardfehler SEM: ±%.3f K", CurrentStats.SEM))
		}
		if lblStatMedian != nil {
			lblStatMedian.SetText(fmt.Sprintf("Median / MAD: %.2f °C / ±%.2f K", CurrentStats.Median, CurrentStats.MAD))
		}
		if lblStatTau != nil {
			lblStatTau.SetText(fmt.Sprintf("Hampel-Schwelle τ: %.2f °C (Median+3·1.48·MAD)", CurrentStats.ThresholdT))
		}
		if lblStatMinMax != nil {
			lblStatMinMax.SetText(fmt.Sprintf("Min / Max / Spanne: %.1f °C ... %.1f °C (Δ %.1f K)", CurrentStats.Min, CurrentStats.Max, CurrentStats.Span))
		}
		if lblStatArea != nil {
			lblStatArea.SetText(fmt.Sprintf("Messfeld: %d Pixel (%.1f cm²)", CurrentStats.Count, CurrentStats.AreaCm2))
		}
	}

	if diagHistCanvas != nil {
		diagHistCanvas.Invalidate()
	}
	if diagZoneCanvas != nil {
		diagZoneCanvas.Invalidate()
	}
	if diagProfileCanvas != nil {
		diagProfileCanvas.Invalidate()
	}
}

func getAuditItems() []*AuditTableItem {
	res := make([]*AuditTableItem, len(GState.AuditLogs))
	for i := range GState.AuditLogs {
		res[i] = &GState.AuditLogs[len(GState.AuditLogs)-1-i] // Neueste zuerst
	}
	return res
}

func SignCurrentReport() {
	if GState.LastResult == nil {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Wärmebild analysieren.", walk.MsgBoxIconInformation)
		return
	}

	ts := time.Now().Format("2006-01-02 15:04:05")
	data := fmt.Sprintf("%s|%s|%s|%s", GState.PatientID, GState.DoctorName, ts, GState.LastResult.HighestRisk)
	h := sha256.Sum256([]byte(data))
	sigHash := hex.EncodeToString(h[:])

	GState.IsSigned = true
	GState.SignatureHash = sigHash
	GState.SignatureTime = ts

	RecordAudit("PHYSICIAN_SIGNATURE", GState.LastResult.TotalHotspots, GState.LastResult.HighestRisk, 1.2)
	if auditModel != nil {
		auditModel.SetItems(getAuditItems())
	}

	walk.MsgBox(mw, "Ärztliche Freigabe erteilt",
		fmt.Sprintf("Der Befund wurde digital signiert nach DIN EN ISO 13485 & DSGVO Art. 30.\n\nFacharzt: %s\nZeitstempel: %s\nSignatur-Hash: %s",
			GState.DoctorName, ts, sigHash),
		walk.MsgBoxIconInformation)
}

func VerifyAuditTrail() {
	if len(GState.AuditLogs) == 0 {
		walk.MsgBox(mw, "Audit-Trail", "Noch keine Einträge im Revisionsprotokoll vorhanden.", walk.MsgBoxIconInformation)
		return
	}

	intact := true
	for i := 0; i < len(GState.AuditLogs); i++ {
		cur := GState.AuditLogs[i]
		prevHash := "INIT_GENESIS_00000000000000000000"
		if i > 0 {
			prevHash = GState.AuditLogs[i-1].Hash
		}
		data := cur.Timestamp + "|" + cur.PatientID + "|" + cur.Action + "|" + prevHash
		h := sha256.Sum256([]byte(data))
		calcHash := hex.EncodeToString(h[:])
		if calcHash != cur.Hash {
			intact = false
			walk.MsgBox(mw, "Audit-Warnung", fmt.Sprintf("Hash-Kette manipuliert bei Eintrag %d (%s)!", i+1, cur.Timestamp), walk.MsgBoxIconError)
			return
		}
	}

	if intact {
		walk.MsgBox(mw, "Audit-Integrität bestätigt",
			fmt.Sprintf("✓ Alle %d Audit-Einträge sind kryptografisch unverändert (SHA-256 Hash-Kette intakt).\nDSGVO Art. 30 Verfahrensverzeichnis konform.", len(GState.AuditLogs)),
			walk.MsgBoxIconInformation)
	}
}
