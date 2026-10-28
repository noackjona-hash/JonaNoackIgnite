package main

import (
	"fmt"
	"math"

	"github.com/lxn/walk"
)

var (
	fluentInfoBarCanvas   *walk.CustomWidget
	fluentInspectorCanvas *walk.CustomWidget

	// Fluent Brushes
	fluentBgNormalBr   *walk.SolidColorBrush
	fluentBgWarningBr  *walk.SolidColorBrush
	fluentBgAlertBr    *walk.SolidColorBrush
	fluentBgStandbyBr  *walk.SolidColorBrush
	fluentStripCardBr  *walk.SolidColorBrush
	fluentPillNormalBr *walk.SolidColorBrush
	fluentPillWarnBr   *walk.SolidColorBrush
	fluentPillAlertBr  *walk.SolidColorBrush

	// Fluent Pens
	fluentBorderNormalPen *walk.CosmeticPen
	fluentBorderWarnPen   *walk.CosmeticPen
	fluentBorderAlertPen  *walk.CosmeticPen
	fluentBorderSlatePen  *walk.CosmeticPen
	fluentDividerPen      *walk.CosmeticPen
	fluentAccentNormalPen *walk.CosmeticPen
	fluentAccentWarnPen   *walk.CosmeticPen
	fluentAccentAlertPen  *walk.CosmeticPen

	// Fluent Fonts
	fluentTitleFont *walk.Font
	fluentSubFont   *walk.Font
	fluentChipFont  *walk.Font
	fluentDataFont  *walk.Font
	fluentDataBold  *walk.Font
)

func initFluentGraphics() {
	// 1. Soft-tinted Acrylic/Mica Card Backgrounds
	fluentBgNormalBr, _ = walk.NewSolidColorBrush(walk.RGB(240, 253, 244))  // #F0FDF4 Soft Mint
	fluentBgWarningBr, _ = walk.NewSolidColorBrush(walk.RGB(255, 251, 235)) // #FFFBEB Soft Amber
	fluentBgAlertBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 242, 242))   // #FEF2F2 Soft Crimson
	fluentBgStandbyBr, _ = walk.NewSolidColorBrush(walk.RGB(248, 250, 252)) // #F8FAFC Clean Slate

	fluentStripCardBr, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255)) // White Card

	fluentPillNormalBr, _ = walk.NewSolidColorBrush(walk.RGB(220, 252, 231)) // #DCFCE7
	fluentPillWarnBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 243, 199))   // #FEF3C7
	fluentPillAlertBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 226, 226))  // #FEE2E2

	// 2. Subtle 1px Borders
	fluentBorderNormalPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(134, 239, 172)) // #86EFAC
	fluentBorderWarnPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(253, 230, 138))   // #FDE68A
	fluentBorderAlertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(254, 202, 202))  // #FECACA
	fluentBorderSlatePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(226, 232, 240))  // #E2E8F0
	fluentDividerPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(241, 245, 249))      // #F1F5F9

	// 3. 4px Left Accent Bars
	fluentAccentNormalPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(22, 163, 74))  // #16A34A
	fluentAccentWarnPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(245, 158, 11))   // #F59E0B
	fluentAccentAlertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))   // #DC2626

	// 4. Windows 11 Segoe UI Variable Typography
	fluentTitleFont, _ = walk.NewFont("Segoe UI Variable Display", 10, walk.FontBold)
	fluentSubFont, _ = walk.NewFont("Segoe UI Variable Text", 8, 0)
	fluentChipFont, _ = walk.NewFont("Segoe UI Variable Text", 8, walk.FontBold)
	fluentDataFont, _ = walk.NewFont("Segoe UI Variable Text", 8, 0)
	fluentDataBold, _ = walk.NewFont("Segoe UI Variable Display", 9, walk.FontBold)
}

// drawFluentRoundRect zeichnet ein WinUI 3 Card-Element mit sanft abgerundeten Ecken
func drawFluentRoundRect(canvas *walk.Canvas, rect walk.Rectangle, fillBrush walk.Brush, borderPen walk.Pen, radius int) {
	ellipseSize := walk.Size{Width: radius * 2, Height: radius * 2}
	if fillBrush != nil {
		canvas.FillRoundedRectanglePixels(fillBrush, rect, ellipseSize)
	}
	if borderPen != nil {
		canvas.DrawRoundedRectanglePixels(borderPen, rect, ellipseSize)
	}
}

// PaintFluentInfoBar rendert eine native WinUI 3 InfoBar
func PaintFluentInfoBar(canvas *walk.Canvas, bounds walk.Rectangle) error {
	actualBounds := canvas.BoundsPixels()
	if actualBounds.Width <= 0 || actualBounds.Height <= 0 {
		actualBounds = bounds
	}
	w, h := actualBounds.Width, actualBounds.Height
	if w <= 20 || h <= 10 {
		return nil
	}

	// Standard: Standby
	var bgBrush walk.Brush = fluentBgStandbyBr
	var borderPen walk.Pen = fluentBorderSlatePen
	accentColor := walk.RGB(100, 116, 139)
	icon := "ℹ️"
	title := "STANDBY · KEIN BEFUND GELADEN"
	sub := "Bitte laden Sie ein Wärmebild (Strg+O) oder starten Sie den Schnelltest zur automatisierten Triage."
	pillText := "● BEREIT"
	pillBrush := fluentPillNormalBr
	pillTextCol := walk.RGB(71, 85, 105)

	if GState.LastResult != nil {
		if GState.LastResult.HighestRisk == "CRITICAL" {
			bgBrush = fluentBgAlertBr
			borderPen = fluentBorderAlertPen
			accentColor = walk.RGB(220, 38, 38)
			icon = "🚨"
			title = "ARMSTRONG-ALARM: AKUTES PRÄ-ULKUS DETEKTIERT (ΔT ≥ 2,2 K)"
			sub = "Kritische thermische Asymmetrie nach IWGDF 2023. Sofortige Druckentlastung (Total-Contact-Cast) indiziert."
			pillText = "● TRIAGE: KRITISCH"
			pillBrush = fluentPillAlertBr
			pillTextCol = walk.RGB(185, 28, 28)
		} else if GState.LastResult.HighestRisk == "MODERATE" {
			bgBrush = fluentBgWarningBr
			borderPen = fluentBorderWarnPen
			accentColor = walk.RGB(217, 119, 6)
			icon = "⚠️"
			title = "MÄSSIGES RISIKO: BIOMECHANISCHE DRUCKSTELLE (ΔT ≥ 1,2 K)"
			sub = "Erhöhte lokale Perfusion. Schuhzurichtung prüfen und podiatrisches Verlaufs-Screening anberaumen."
			pillText = "▲ TRIAGE: BEOBACHTUNG"
			pillBrush = fluentPillWarnBr
			pillTextCol = walk.RGB(180, 83, 9)
		} else {
			bgBrush = fluentBgNormalBr
			borderPen = fluentBorderNormalPen
			accentColor = walk.RGB(22, 163, 74)
			icon = "✅"
			title = "PHYSIOLOGISCHER NORMALBEFUND · THERMISCH SYMMETRISCH"
			sub = "Keine signifikanten Gewebeasymmetrien festgestellt (ΔT < 1,2 K). Normale Schichtbelastung toleriert."
			pillText = "● TRIAGE: NORMAL"
			pillBrush = fluentPillNormalBr
			pillTextCol = walk.RGB(21, 128, 61)
		}
	}

	cardRect := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, cardRect, bgBrush, borderPen, 6)

	// Linker 4px Akzent-Balken
	accentPen, _ := walk.NewCosmeticPen(walk.PenSolid, accentColor)
	defer accentPen.Dispose()
	for i := 0; i < 4; i++ {
		canvas.DrawLinePixels(accentPen, walk.Point{X: cardRect.X + 2 + i, Y: cardRect.Y + 4}, walk.Point{X: cardRect.X + 2 + i, Y: cardRect.Y + cardRect.Height - 4})
	}

	// Icon
	canvas.DrawTextPixels(icon, fluentTitleFont, walk.RGB(15, 23, 42), walk.Rectangle{X: cardRect.X + 12, Y: cardRect.Y + (h-18)/2, Width: 24, Height: 20}, walk.TextCenter)

	// Titel und Subtitle
	textX := cardRect.X + 42
	canvas.DrawTextPixels(title, fluentTitleFont, walk.RGB(15, 23, 42), walk.Rectangle{X: textX, Y: cardRect.Y + 6, Width: w - 230, Height: 16}, walk.TextLeft)
	canvas.DrawTextPixels(sub, fluentSubFont, walk.RGB(71, 85, 105), walk.Rectangle{X: textX, Y: cardRect.Y + 23, Width: w - 230, Height: 15}, walk.TextLeft)

	// Status-Pill rechts
	pillW, pillH := 165, 24
	pillX := w - pillW - 14
	pillY := cardRect.Y + (h-pillH)/2
	pillRect := walk.Rectangle{X: pillX, Y: pillY, Width: pillW, Height: pillH}
	drawFluentRoundRect(canvas, pillRect, pillBrush, borderPen, 12)
	canvas.DrawTextPixels(pillText, fluentChipFont, pillTextCol, pillRect, walk.TextCenter|walk.TextVCenter)

	return nil
}

// PaintFluentInspectorStrip rendert das moderne WinUI 3 Vitaldaten-Kartenband unter den Viewports
func PaintFluentInspectorStrip(canvas *walk.Canvas, bounds walk.Rectangle) error {
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

	// 5 Segmente berechnen
	numSegs := 5
	segW := (w - 4) / numSegs

	// Berechne aktuelle Hover-Werte
	fokusStr := "📍 Fokus: X: -- , Y: --"
	tempStr := "🌡️ T: --.- °C"
	contraStr := "⚖️ Kontra: --.- °C"
	deltaStr := "🔺 ΔT: ±-.-- K"
	anatStr := "🗺️ Zone: Standby"

	deltaColor := walk.RGB(71, 85, 105)
	deltaBg := fluentPillNormalBr
	hasDelta := false

	if lastHoverIX >= 0 && lastHoverIY >= 0 && len(GState.RawGray) > 0 && GState.Width > 0 {
		v := GState.RawGray[lastHoverIY*GState.Width+lastHoverIX]
		tCur := TempOf(v)
		fokusStr = fmt.Sprintf("📍 Fokus: X: %d, Y: %d", lastHoverIX, lastHoverIY)
		tempStr = fmt.Sprintf("🌡️ T: %.1f °C", tCur)

		midline := GState.Width / 2
		contraX := midline*2 - lastHoverIX
		if contraX >= 0 && contraX < GState.Width {
			cv := GState.RawGray[lastHoverIY*GState.Width+contraX]
			tContra := TempOf(cv)
			contraStr = fmt.Sprintf("⚖️ Kontra: %.1f °C", tContra)
			dT := float64(int(v)-int(cv)) * 0.1
			deltaStr = fmt.Sprintf("🔺 ΔT: %+.2f K", dT)
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

		if lastHoverIX >= midline {
			anatStr = "🗺️ Linker Fuß (Plantar)"
		} else {
			anatStr = "🗺️ Rechter Fuß (Plantar)"
		}
	}

	// 1. Fokus
	canvas.DrawTextPixels(fokusStr, fluentDataBold, walk.RGB(2, 132, 199), walk.Rectangle{X: 12, Y: (h - 16) / 2, Width: segW - 16, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentBorderSlatePen, walk.Point{X: segW, Y: 6}, walk.Point{X: segW, Y: h - 6})

	// 2. Temperatur
	canvas.DrawTextPixels(tempStr, fluentDataBold, walk.RGB(15, 23, 42), walk.Rectangle{X: segW + 12, Y: (h - 16) / 2, Width: segW - 16, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentBorderSlatePen, walk.Point{X: segW * 2, Y: 6}, walk.Point{X: segW * 2, Y: h - 6})

	// 3. Kontralateral
	canvas.DrawTextPixels(contraStr, fluentDataFont, walk.RGB(71, 85, 105), walk.Rectangle{X: segW*2 + 12, Y: (h - 16) / 2, Width: segW - 16, Height: 16}, walk.TextLeft)
	canvas.DrawLinePixels(fluentBorderSlatePen, walk.Point{X: segW * 3, Y: 6}, walk.Point{X: segW * 3, Y: h - 6})

	// 4. Asymmetrie ΔT (in Pill Badge)
	if hasDelta {
		pillW := segW - 20
		pillRect := walk.Rectangle{X: segW*3 + 10, Y: (h - 22) / 2, Width: pillW, Height: 22}
		drawFluentRoundRect(canvas, pillRect, deltaBg, fluentBorderSlatePen, 10)
		canvas.DrawTextPixels(deltaStr, fluentChipFont, deltaColor, pillRect, walk.TextCenter|walk.TextVCenter)
	} else {
		canvas.DrawTextPixels(deltaStr, fluentDataFont, walk.RGB(100, 116, 139), walk.Rectangle{X: segW*3 + 12, Y: (h - 16) / 2, Width: segW - 16, Height: 16}, walk.TextLeft)
	}
	canvas.DrawLinePixels(fluentBorderSlatePen, walk.Point{X: segW * 4, Y: 6}, walk.Point{X: segW * 4, Y: h - 6})

	// 5. Anatomie
	canvas.DrawTextPixels(anatStr, fluentDataFont, walk.RGB(15, 23, 42), walk.Rectangle{X: segW*4 + 12, Y: (h - 16) / 2, Width: segW - 16, Height: 16}, walk.TextLeft)

	return nil
}
