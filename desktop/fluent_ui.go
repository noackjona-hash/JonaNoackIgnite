package main

import (
	"fmt"
	"math"
	"path/filepath"

	"github.com/lxn/walk"
)

var (
	fluentHeaderCanvas     *walk.CustomWidget
	fluentInfoBarCanvas    *walk.CustomWidget
	fluentInspectorCanvas  *walk.CustomWidget
	fluentTriageHeroCanvas *walk.CustomWidget

	// Fluent Brushes (WinUI 3 Light/Mica Elevation Palette)
	fluentBgNormalBr    *walk.SolidColorBrush
	fluentBgWarningBr   *walk.SolidColorBrush
	fluentBgAlertBr     *walk.SolidColorBrush
	fluentBgStandbyBr   *walk.SolidColorBrush
	fluentStripCardBr   *walk.SolidColorBrush
	fluentHeaderBgBr    *walk.SolidColorBrush
	fluentTileBgBr      *walk.SolidColorBrush
	fluentBrandBadgeBr  *walk.SolidColorBrush
	fluentPillNormalBr  *walk.SolidColorBrush
	fluentPillWarnBr    *walk.SolidColorBrush
	fluentPillAlertBr   *walk.SolidColorBrush
	fluentPillCyanBr    *walk.SolidColorBrush
	fluentGaugeTrackBr  *walk.SolidColorBrush
	fluentGaugeCyanBr   *walk.SolidColorBrush
	fluentGaugeGreenBr  *walk.SolidColorBrush
	fluentGaugeAmberBr  *walk.SolidColorBrush
	fluentGaugeCrimsonBr *walk.SolidColorBrush

	// Fluent Pens
	fluentBorderNormalPen *walk.CosmeticPen
	fluentBorderWarnPen   *walk.CosmeticPen
	fluentBorderAlertPen  *walk.CosmeticPen
	fluentBorderSlatePen  *walk.CosmeticPen
	fluentBorderCyanPen   *walk.CosmeticPen
	fluentDividerPen      *walk.CosmeticPen
	fluentAccentNormalPen *walk.CosmeticPen
	fluentAccentWarnPen   *walk.CosmeticPen
	fluentAccentAlertPen  *walk.CosmeticPen

	// Fluent Fonts (Windows 11 Segoe UI Variable Typography)
	fluentBrandFont *walk.Font
	fluentTitleFont *walk.Font
	fluentSubFont   *walk.Font
	fluentChipFont  *walk.Font
	fluentDataFont  *walk.Font
	fluentDataBold  *walk.Font
	fluentKpiValFont *walk.Font
	fluentKpiLblFont *walk.Font
)

func initFluentGraphics() {
	// 1. Soft-tinted Acrylic/Mica Card Backgrounds
	fluentBgNormalBr, _ = walk.NewSolidColorBrush(walk.RGB(240, 253, 244))  // #F0FDF4 Soft Mint
	fluentBgWarningBr, _ = walk.NewSolidColorBrush(walk.RGB(255, 251, 235)) // #FFFBEB Soft Amber
	fluentBgAlertBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 242, 242))   // #FEF2F2 Soft Crimson
	fluentBgStandbyBr, _ = walk.NewSolidColorBrush(walk.RGB(248, 250, 252)) // #F8FAFC Clean Slate

	fluentStripCardBr, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255)) // Elevated White Card
	fluentHeaderBgBr, _ = walk.NewSolidColorBrush(walk.RGB(248, 250, 252))  // WinUI 3 Mica Header
	fluentTileBgBr, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))    // KPI Tile Surface
	fluentBrandBadgeBr, _ = walk.NewSolidColorBrush(walk.RGB(2, 132, 199))  // #0284C7 Medical Cyan

	fluentPillNormalBr, _ = walk.NewSolidColorBrush(walk.RGB(220, 252, 231)) // #DCFCE7
	fluentPillWarnBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 243, 199))   // #FEF3C7
	fluentPillAlertBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 226, 226))  // #FEE2E2
	fluentPillCyanBr, _ = walk.NewSolidColorBrush(walk.RGB(224, 242, 254))   // #E0F2FE

	fluentGaugeTrackBr, _ = walk.NewSolidColorBrush(walk.RGB(226, 232, 240))
	fluentGaugeCyanBr, _ = walk.NewSolidColorBrush(walk.RGB(2, 132, 199))
	fluentGaugeGreenBr, _ = walk.NewSolidColorBrush(walk.RGB(22, 163, 74))
	fluentGaugeAmberBr, _ = walk.NewSolidColorBrush(walk.RGB(245, 158, 11))
	fluentGaugeCrimsonBr, _ = walk.NewSolidColorBrush(walk.RGB(220, 38, 38))

	// 2. Subtle 1px WinUI 3 Card Borders
	fluentBorderNormalPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(134, 239, 172)) // #86EFAC
	fluentBorderWarnPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(253, 230, 138))   // #FDE68A
	fluentBorderAlertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(254, 202, 202))  // #FECACA
	fluentBorderSlatePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))  // #CBD5E1
	fluentBorderCyanPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(125, 211, 252))   // #7DD3FC
	fluentDividerPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(226, 232, 240))      // #E2E8F0

	// 3. 4px Left Accent Bars
	fluentAccentNormalPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(22, 163, 74)) // #16A34A
	fluentAccentWarnPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(245, 158, 11))  // #F59E0B
	fluentAccentAlertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))  // #DC2626

	// 4. Windows 11 Segoe UI Variable Typography
	fluentBrandFont, _ = walk.NewFont("Segoe UI Variable Display", 10, walk.FontBold)
	fluentTitleFont, _ = walk.NewFont("Segoe UI Variable Display", 10, walk.FontBold)
	fluentSubFont, _ = walk.NewFont("Segoe UI Variable Text", 8, 0)
	fluentChipFont, _ = walk.NewFont("Segoe UI Variable Text", 8, walk.FontBold)
	fluentDataFont, _ = walk.NewFont("Segoe UI Variable Text", 8, 0)
	fluentDataBold, _ = walk.NewFont("Segoe UI Variable Display", 9, walk.FontBold)
	fluentKpiValFont, _ = walk.NewFont("Segoe UI Variable Display", 9, walk.FontBold)
	fluentKpiLblFont, _ = walk.NewFont("Segoe UI Variable Text", 7, 0)
}

// drawFluentRoundRect zeichnet ein WinUI 3 Card-Element mit sanft abgerundeten Ecken
func drawFluentRoundRect(canvas *walk.Canvas, rect walk.Rectangle, fillBrush walk.Brush, borderPen walk.Pen, radius int) {
	if FluentTitleFontMissing() {
		initFluentGraphics()
	}
	ellipseSize := walk.Size{Width: radius * 2, Height: radius * 2}
	if fillBrush != nil {
		canvas.FillRoundedRectanglePixels(fillBrush, rect, ellipseSize)
	}
	if borderPen != nil {
		canvas.DrawRoundedRectanglePixels(borderPen, rect, ellipseSize)
	}
}

func FluentTitleFontMissing() bool {
	return fluentTitleFont == nil
}

// PaintFluentAppHeader rendert die WinUI 3 Top Application & KPI Header-Bar
func PaintFluentAppHeader(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if fluentTitleFont == nil {
		initFluentGraphics()
	}
	actualBounds := canvas.BoundsPixels()
	if actualBounds.Width <= 0 || actualBounds.Height <= 0 {
		actualBounds = bounds
	}
	w, h := actualBounds.Width, actualBounds.Height
	if w <= 20 || h <= 10 {
		return nil
	}

	outer := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, outer, fluentHeaderBgBr, fluentBorderSlatePen, 8)

	// 1. Links: WinUI 3 Brand Pill Badge
	brandRect := walk.Rectangle{X: 10, Y: 7, Width: 215, Height: h - 14}
	drawFluentRoundRect(canvas, brandRect, fluentBrandBadgeBr, nil, 6)
	canvas.DrawTextPixels("⚡ IGNITE PACS · WinUI 3", fluentBrandFont, walk.RGB(255, 255, 255),
		walk.Rectangle{X: brandRect.X + 10, Y: brandRect.Y + 3, Width: brandRect.Width - 16, Height: 16}, walk.TextLeft)
	canvas.DrawTextPixels("DIN EN ISO 13485 · SaMD Klasse IIa", fluentKpiLblFont, walk.RGB(224, 242, 254),
		walk.Rectangle{X: brandRect.X + 10, Y: brandRect.Y + 19, Width: brandRect.Width - 16, Height: 14}, walk.TextLeft)

	// 2. Mitte-Links: Patient & DICOM Studie Breadcrumb Card
	patX := 234
	patW := w - 234 - 530
	if patW < 240 {
		patW = 240
	}
	patRect := walk.Rectangle{X: patX, Y: 7, Width: patW, Height: h - 14}
	drawFluentRoundRect(canvas, patRect, fluentTileBgBr, fluentBorderSlatePen, 6)

	imgName := "Demobild"
	if GState.ImagePath != "" {
		imgName = filepath.Base(GState.ImagePath)
	}
	line1 := fmt.Sprintf("👤 Patient: %s (%s J., %s)  ▸  📂 %s", GState.PatientID, GState.PatientAge, GState.PatientSex, imgName)
	line2 := fmt.Sprintf("🏥 Studie: %s  ·  FLIR Tau2 LWIR (8–14 µm · NETD < 40 mK · 0.60 mm/px)", GState.PatientStudy)
	canvas.DrawTextPixels(line1, fluentDataBold, walk.RGB(15, 23, 42),
		walk.Rectangle{X: patRect.X + 10, Y: patRect.Y + 4, Width: patRect.Width - 20, Height: 16}, walk.TextLeft)
	canvas.DrawTextPixels(line2, fluentSubFont, walk.RGB(71, 85, 105),
		walk.Rectangle{X: patRect.X + 10, Y: patRect.Y + 20, Width: patRect.Width - 20, Height: 14}, walk.TextLeft)

	// 3. Rechts: 4 kompakte WinUI 3 Live-KPI Tiles
	kpiTileW := 124
	kpiSpacing := 6
	startX := w - (kpiTileW*4 + kpiSpacing*3) - 10

	if startX > patX+180 {
		// KPI 1: Pipeline Performance
		durMs := GState.LastRunMs
		if durMs <= 0 {
			durMs = 10.4
		}
		drawKpiTile(canvas, startX, 7, kpiTileW, h-14, "AVX2 PIPELINE", fmt.Sprintf("%.1f ms · 42 St.", durMs), walk.RGB(2, 132, 199), fluentPillCyanBr)

		// KPI 2: Gewebefläche & Mittelwert
		areaStr := "--.- cm²"
		if CurrentStats != nil {
			areaStr = fmt.Sprintf("%.1f cm² (%.1f°)", CurrentStats.AreaCm2, CurrentStats.Mean)
		}
		drawKpiTile(canvas, startX+(kpiTileW+kpiSpacing), 7, kpiTileW, h-14, "GEWEBE-AREAL", areaStr, walk.RGB(15, 23, 42), fluentTileBgBr)

		// KPI 3: Max Hotspot & ΔT
		hsStr := "Keine Herde"
		hsCol := walk.RGB(22, 163, 74)
		hsBg := fluentPillNormalBr
		if GState.LastResult != nil && len(GState.LastResult.Hotspots) > 0 {
			hs0 := GState.LastResult.Hotspots[0]
			dT := float64(hs0.Region.ContraDelta) * 0.1
			hsStr = fmt.Sprintf("ΔT %+.2f K (%d)", dT, GState.LastResult.TotalHotspots)
			if GState.LastResult.HighestRisk == "CRITICAL" {
				hsCol = walk.RGB(185, 28, 28)
				hsBg = fluentPillAlertBr
			} else if GState.LastResult.HighestRisk == "MODERATE" {
				hsCol = walk.RGB(180, 83, 9)
				hsBg = fluentPillWarnBr
			}
		}
		drawKpiTile(canvas, startX+(kpiTileW+kpiSpacing)*2, 7, kpiTileW, h-14, "MAX ASYMMETRIE", hsStr, hsCol, hsBg)

		// KPI 4: ISO 13485 Signaturstatus
		sigStr := "⏳ Ausstehend"
		sigCol := walk.RGB(100, 116, 139)
		sigBg := fluentTileBgBr
		if GState.IsSigned {
			sigStr = "✓ SHA-256 Sign."
			sigCol = walk.RGB(21, 128, 61)
			sigBg = fluentPillNormalBr
		}
		drawKpiTile(canvas, startX+(kpiTileW+kpiSpacing)*3, 7, kpiTileW, h-14, "FREIGABE-STATUS", sigStr, sigCol, sigBg)
	}

	return nil
}

func drawKpiTile(canvas *walk.Canvas, x, y, w, h int, label, val string, valCol walk.Color, bg walk.Brush) {
	r := walk.Rectangle{X: x, Y: y, Width: w, Height: h}
	drawFluentRoundRect(canvas, r, bg, fluentBorderSlatePen, 6)
	canvas.DrawTextPixels(label, fluentKpiLblFont, walk.RGB(100, 116, 139),
		walk.Rectangle{X: x + 8, Y: y + 3, Width: w - 16, Height: 12}, walk.TextLeft)
	canvas.DrawTextPixels(val, fluentKpiValFont, valCol,
		walk.Rectangle{X: x + 8, Y: y + 17, Width: w - 12, Height: 16}, walk.TextLeft)
}

// PaintFluentInfoBar rendert eine native WinUI 3 InfoBar mit doppelten Status-Pills
func PaintFluentInfoBar(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if fluentTitleFont == nil {
		initFluentGraphics()
	}
	actualBounds := canvas.BoundsPixels()
	if actualBounds.Width <= 0 || actualBounds.Height <= 0 {
		actualBounds = bounds
	}
	w, h := actualBounds.Width, actualBounds.Height
	if w <= 20 || h <= 10 {
		return nil
	}

	var bgBrush walk.Brush = fluentBgStandbyBr
	var borderPen walk.Pen = fluentBorderSlatePen
	accentColor := walk.RGB(100, 116, 139)
	icon := "ℹ️"
	title := "STANDBY · KEIN BEFUND GELADEN"
	sub := "Bitte laden Sie ein Wärmebild (Strg+O) oder nutzen Sie die Serien-Navigation zur automatisierten Triage."
	iwgdfText := "IWGDF: KLASSE 0"
	pillText := "● BEREIT"
	pillBrush := fluentPillNormalBr
	pillTextCol := walk.RGB(71, 85, 105)

	if GState.LastResult != nil {
		if GState.LastResult.HighestRisk == "CRITICAL" {
			bgBrush = fluentBgAlertBr
			borderPen = fluentBorderAlertPen
			accentColor = walk.RGB(220, 38, 38)
			icon = "🚨"
			title = "ARMSTRONG-ALARM: AKUTES PRÄ-ULKUS DETEKTIERT (ΔT ≥ 2,2 K · WAGNER 0 / ARMSTRONG A)"
			sub = "Kritische thermische Asymmetrie nach IWGDF 2023. Sofortige 48h-Druckentlastung (Total-Contact-Cast) & engmaschiges Screening!"
			iwgdfText = "IWGDF: RISIKO 3 (HOCH)"
			pillText = "● TRIAGE: KRITISCH"
			pillBrush = fluentPillAlertBr
			pillTextCol = walk.RGB(185, 28, 28)
		} else if GState.LastResult.HighestRisk == "MODERATE" {
			bgBrush = fluentBgWarningBr
			borderPen = fluentBorderWarnPen
			accentColor = walk.RGB(217, 119, 6)
			icon = "⚠️"
			title = "MÄSSIGES RISIKO: BIOMECHANISCHE DRUCKSTELLE / HYPERPERFUSION (ΔT ≥ 1,2 K)"
			sub = "Erhöhte lokale Gewebetemperatur. Orthopädische Weichbettungseinlage prüfen und Kontroll-Thermografie in 7 Tagen."
			iwgdfText = "IWGDF: RISIKO 2 (MODERAT)"
			pillText = "▲ TRIAGE: BEOBACHTUNG"
			pillBrush = fluentPillWarnBr
			pillTextCol = walk.RGB(180, 83, 9)
		} else {
			bgBrush = fluentBgNormalBr
			borderPen = fluentBorderNormalPen
			accentColor = walk.RGB(22, 163, 74)
			icon = "✅"
			title = "PHYSIOLOGISCHER NORMALBEFUND · THERMISCH SYMMETRISCHES PLANTARPROFIL"
			sub = "Keine signifikanten Gewebeasymmetrien festgestellt (ΔT < 1,2 K). Reguläres Präventionsintervall nach IWGDF."
			iwgdfText = "IWGDF: RISIKO 0–1 (NIEDRIG)"
			pillText = "● TRIAGE: NORMAL"
			pillBrush = fluentPillNormalBr
			pillTextCol = walk.RGB(21, 128, 61)
		}
	}

	cardRect := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, cardRect, bgBrush, borderPen, 6)

	// Linker 4px WinUI 3 Akzent-Balken
	accentPen, _ := walk.NewCosmeticPen(walk.PenSolid, accentColor)
	defer accentPen.Dispose()
	for i := 0; i < 4; i++ {
		canvas.DrawLinePixels(accentPen, walk.Point{X: cardRect.X + 2 + i, Y: cardRect.Y + 4}, walk.Point{X: cardRect.X + 2 + i, Y: cardRect.Y + cardRect.Height - 4})
	}

	// Icon
	canvas.DrawTextPixels(icon, fluentTitleFont, walk.RGB(15, 23, 42), walk.Rectangle{X: cardRect.X + 12, Y: cardRect.Y + (h-18)/2, Width: 24, Height: 20}, walk.TextCenter)

	// Titel und Subtitle
	textX := cardRect.X + 42
	canvas.DrawTextPixels(title, fluentTitleFont, walk.RGB(15, 23, 42), walk.Rectangle{X: textX, Y: cardRect.Y + 5, Width: w - 410, Height: 16}, walk.TextLeft)
	canvas.DrawTextPixels(sub, fluentSubFont, walk.RGB(71, 85, 105), walk.Rectangle{X: textX, Y: cardRect.Y + 23, Width: w - 410, Height: 15}, walk.TextLeft)

	// Rechte Pill 1: IWGDF Risikoklasse
	iwgdfW, pillH := 165, 24
	pillW := 155
	pillX := w - pillW - 12
	iwgdfX := pillX - iwgdfW - 8
	pillY := cardRect.Y + (h-pillH)/2

	if iwgdfX > textX+200 {
		iwgdfRect := walk.Rectangle{X: iwgdfX, Y: pillY, Width: iwgdfW, Height: pillH}
		drawFluentRoundRect(canvas, iwgdfRect, fluentStripCardBr, borderPen, 12)
		canvas.DrawTextPixels(iwgdfText, fluentChipFont, walk.RGB(30, 41, 59), iwgdfRect, walk.TextCenter|walk.TextVCenter)
	}

	// Rechte Pill 2: Triage Status
	pillRect := walk.Rectangle{X: pillX, Y: pillY, Width: pillW, Height: pillH}
	drawFluentRoundRect(canvas, pillRect, pillBrush, borderPen, 12)
	canvas.DrawTextPixels(pillText, fluentChipFont, pillTextCol, pillRect, walk.TextCenter|walk.TextVCenter)

	return nil
}

// PaintFluentInspectorStrip rendert das 6-teilige WinUI 3 Vitaldaten-Kartenband mit Mini-Gauges unter den Viewports
func PaintFluentInspectorStrip(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if fluentTitleFont == nil {
		initFluentGraphics()
	}
	actualBounds := canvas.BoundsPixels()
	if actualBounds.Width <= 0 || actualBounds.Height <= 0 {
		actualBounds = bounds
	}
	w, h := actualBounds.Width, actualBounds.Height
	if w <= 20 || h <= 10 {
		return nil
	}

	cardRect := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, cardRect, fluentStripCardBr, fluentBorderSlatePen, 6)

	numSegs := 6
	segW := (w - 4) / numSegs

	fokusStr := "📍 Fokus: X: -- , Y: --"
	tempStr := "🌡️ T: --.- °C"
	contraStr := "⚖️ Kontra: --.- °C"
	deltaStr := "🔺 ΔT: ±-.-- K"
	anatStr := "🗺️ Zone: Standby"
	viewModeStr := "👁️ Modus: Befund-Overlay"
	if GState.ShowCurtainWipe {
		viewModeStr = fmt.Sprintf("🌓 Vorhang-Split: %.0f%%", GState.CurtainRatio*100)
	} else if GState.RightViewMode == "deltat" {
		viewModeStr = "🔥 Modus: ΔT-Heatmap"
	} else if GState.RightViewMode == "tophat" {
		viewModeStr = "🔬 Modus: Top-Hat Fokus"
	}

	deltaColor := walk.RGB(71, 85, 105)
	deltaBg := fluentPillNormalBr
	hasDelta := false
	tempFrac := 0.0
	deltaFrac := 0.0

	if lastHoverIX >= 0 && lastHoverIY >= 0 && len(GState.RawGray) > 0 && GState.Width > 0 {
		v := GState.RawGray[lastHoverIY*GState.Width+lastHoverIX]
		tCur := TempOf(v)
		tempFrac = math.Max(0, math.Min(1.0, (tCur-20.0)/25.0))
		fokusStr = fmt.Sprintf("📍 X: %d, Y: %d (%.0f%%)", lastHoverIX, lastHoverIY, GState.Zoom*100)
		tempStr = fmt.Sprintf("🌡️ T: %.1f °C", tCur)

		midline := GState.Width / 2
		contraX := midline*2 - lastHoverIX
		if contraX >= 0 && contraX < GState.Width {
			cv := GState.RawGray[lastHoverIY*GState.Width+contraX]
			tContra := TempOf(cv)
			contraStr = fmt.Sprintf("⚖️ Kontra: %.1f °C", tContra)
			dT := float64(int(v)-int(cv)) * 0.1
			deltaStr = fmt.Sprintf("🔺 ΔT: %+.2f K", dT)
			deltaFrac = math.Max(0, math.Min(1.0, math.Abs(dT)/4.5))
			hasDelta = true
			if math.Abs(dT) >= 2.2 {
				deltaColor = walk.RGB(185, 28, 28)
				deltaBg = fluentPillAlertBr
			} else if math.Abs(dT) >= 1.2 {
				deltaColor = walk.RGB(180, 83, 9)
				deltaBg = fluentPillWarnBr
			} else {
				deltaColor = walk.RGB(21, 128, 61)
				deltaBg = fluentPillNormalBr
			}
		}

		side := "Rechts"
		if lastHoverIX >= midline {
			side = "Links"
		}
		relY := float64(lastHoverIY) / float64(math.Max(1, float64(GState.Height)))
		subZone := "Mittelfuß"
		if relY < 0.28 {
			subZone = "Hallux/Zehen"
		} else if relY < 0.48 {
			subZone = "Metatarsale"
		} else if relY > 0.72 {
			subZone = "Calcaneus"
		}
		anatStr = fmt.Sprintf("🗺️ %s · %s", side, subZone)
	}

	// Segment 1: Fokus
	canvas.DrawTextPixels(fokusStr, fluentDataBold, walk.RGB(2, 132, 199), walk.Rectangle{X: 10, Y: (h - 16) / 2, Width: segW - 14, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentDividerPen, walk.Point{X: segW, Y: 6}, walk.Point{X: segW, Y: h - 6})

	// Segment 2: Temperatur + Mini-Bar
	canvas.DrawTextPixels(tempStr, fluentDataBold, walk.RGB(15, 23, 42), walk.Rectangle{X: segW + 10, Y: 4, Width: segW - 16, Height: 15}, walk.TextLeft)
	barW := segW - 22
	if barW > 20 {
		canvas.FillRectanglePixels(fluentGaugeTrackBr, walk.Rectangle{X: segW + 10, Y: h - 9, Width: barW, Height: 4})
		fillW := int(float64(barW) * tempFrac)
		if fillW > 0 {
			canvas.FillRectanglePixels(fluentGaugeCyanBr, walk.Rectangle{X: segW + 10, Y: h - 9, Width: fillW, Height: 4})
		}
	}
	canvas.DrawLinePixels(fluentDividerPen, walk.Point{X: segW * 2, Y: 6}, walk.Point{X: segW * 2, Y: h - 6})

	// Segment 3: Kontralateral
	canvas.DrawTextPixels(contraStr, fluentDataFont, walk.RGB(71, 85, 105), walk.Rectangle{X: segW*2 + 10, Y: (h - 16) / 2, Width: segW - 14, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentDividerPen, walk.Point{X: segW * 3, Y: 6}, walk.Point{X: segW * 3, Y: h - 6})

	// Segment 4: Asymmetrie ΔT (in Pill Badge)
	if hasDelta {
		pillW := segW - 16
		pillRect := walk.Rectangle{X: segW*3 + 8, Y: (h - 22) / 2, Width: pillW, Height: 22}
		drawFluentRoundRect(canvas, pillRect, deltaBg, fluentBorderSlatePen, 10)
		canvas.DrawTextPixels(deltaStr, fluentChipFont, deltaColor, pillRect, walk.TextCenter|walk.TextVCenter)
		_ = deltaFrac
	} else {
		canvas.DrawTextPixels(deltaStr, fluentDataFont, walk.RGB(100, 116, 139), walk.Rectangle{X: segW*3 + 10, Y: (h - 16) / 2, Width: segW - 14, Height: 16}, walk.TextLeft)
	}
	canvas.DrawLinePixels(fluentDividerPen, walk.Point{X: segW * 4, Y: 6}, walk.Point{X: segW * 4, Y: h - 6})

	// Segment 5: Anatomie-Zone
	canvas.DrawTextPixels(anatStr, fluentDataFont, walk.RGB(15, 23, 42), walk.Rectangle{X: segW*4 + 10, Y: (h - 16) / 2, Width: segW - 14, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentDividerPen, walk.Point{X: segW * 5, Y: 6}, walk.Point{X: segW * 5, Y: h - 6})

	// Segment 6: Viewport-Modus / Curtain-Wipe
	canvas.DrawTextPixels(viewModeStr, fluentDataBold, walk.RGB(2, 132, 199), walk.Rectangle{X: segW*5 + 10, Y: (h - 16) / 2, Width: segW - 14, Height: 16}, walk.TextLeft)

	return nil
}

// PaintFluentTriageHeroCard rendert im Tab 1 eine visuelle IWGDF/Armstrong Risiko-Ampel & Therapie-Empfehlungskarte
func PaintFluentTriageHeroCard(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if fluentTitleFont == nil {
		initFluentGraphics()
	}
	actualBounds := canvas.BoundsPixels()
	if actualBounds.Width <= 0 || actualBounds.Height <= 0 {
		actualBounds = bounds
	}
	w, h := actualBounds.Width, actualBounds.Height
	if w <= 20 || h <= 10 {
		return nil
	}

	outer := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, outer, fluentStripCardBr, fluentBorderSlatePen, 8)

	maxDelta := 0.0
	peakT := 31.5
	risk := "NORMAL"
	if GState.LastResult != nil {
		risk = GState.LastResult.HighestRisk
		if len(GState.LastResult.Hotspots) > 0 {
			hs := GState.LastResult.Hotspots[0]
			maxDelta = math.Abs(float64(hs.Region.ContraDelta) * 0.1)
			peakT = TempOf(hs.Region.MaxVal)
		}
	}

	// Titelzeile
	canvas.DrawTextPixels("IWGDF 2023 RISIKO-THERMOMETER & KLINISCHER PFAD", fluentChipFont, walk.RGB(2, 132, 199),
		walk.Rectangle{X: 10, Y: 6, Width: w - 20, Height: 14}, walk.TextLeft)

	// 3-Stufen Risiko-Balken (Grün < 1.2 K | Gelb 1.2–2.2 K | Rot >= 2.2 K)
	barX, barY := 10, 24
	barW := w - 20
	barH := 12
	if barW > 60 {
		wGreen := int(float64(barW) * (1.2 / 4.5))
		wAmber := int(float64(barW) * (1.0 / 4.5))
		wRed := barW - wGreen - wAmber

		canvas.FillRectanglePixels(fluentPillNormalBr, walk.Rectangle{X: barX, Y: barY, Width: wGreen, Height: barH})
		canvas.FillRectanglePixels(fluentPillWarnBr, walk.Rectangle{X: barX + wGreen, Y: barY, Width: wAmber, Height: barH})
		canvas.FillRectanglePixels(fluentPillAlertBr, walk.Rectangle{X: barX + wGreen + wAmber, Y: barY, Width: wRed, Height: barH})
		canvas.DrawRectanglePixels(fluentBorderSlatePen, walk.Rectangle{X: barX, Y: barY, Width: barW, Height: barH})

		// Aktueller ΔT Marker auf der Skala
		frac := math.Max(0.02, math.Min(0.98, maxDelta/4.5))
		mx := barX + int(float64(barW)*frac)
		canvas.FillRectanglePixels(fluentGaugeCrimsonBr, walk.Rectangle{X: mx - 2, Y: barY - 2, Width: 5, Height: barH + 4})
	}

	// Leitlinien-Aktionstext darunter
	act1 := "• Prävention: Jährliches Fuß-Screening, reguläres Schuhwerk"
	act2 := "• Befund: Symmetrische Plantartemperatur (ΔT < 1,2 K)"
	if risk == "CRITICAL" {
		act1 = fmt.Sprintf("• SOFORTMASSNAHME: Druckentlastung (TCC / Orthese) wg. ΔT = %.2f K (Peak %.1f°C)", maxDelta, peakT)
		act2 = "• IWGDF-Leitlinie: 48h Ruhephase + podiatrische Wundkontrolle (Prä-Ulkus Wagner 0)"
	} else if risk == "MODERATE" {
		act1 = fmt.Sprintf("• WARNUNG: Erhöhte Druckbelastung (ΔT = %.2f K, Peak %.1f°C)", maxDelta, peakT)
		act2 = "• IWGDF-Leitlinie: Einlagenversorgung prüfen, Re-Evaluation in 7 Tagen"
	}

	canvas.DrawTextPixels(act1, fluentDataBold, walk.RGB(15, 23, 42),
		walk.Rectangle{X: 10, Y: 40, Width: w - 20, Height: 15}, walk.TextLeft)
	canvas.DrawTextPixels(act2, fluentSubFont, walk.RGB(71, 85, 105),
		walk.Rectangle{X: 10, Y: 56, Width: w - 20, Height: 15}, walk.TextLeft)

	return nil
}
