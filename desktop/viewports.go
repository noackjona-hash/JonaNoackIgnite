package main

import (
	"fmt"
	"image"
	"math"

	"github.com/lxn/walk"
)

var (
	bgBrush          *walk.SolidColorBrush
	hudFont          *walk.Font
	hudBoldFont      *walk.Font
	anatFont         *walk.Font
	reticlePen       *walk.CosmeticPen
	reticleRedPen    *walk.CosmeticPen
	hairlinePen      *walk.CosmeticPen
	scalePen         *walk.CosmeticPen
	badgeBrush       *walk.SolidColorBrush
	badgeAlarmBr     *walk.SolidColorBrush
	cardBrush        *walk.SolidColorBrush
	cardBorderPen    *walk.CosmeticPen
	framePen         *walk.CosmeticPen
	barBorderPen     *walk.CosmeticPen
	colorbarBitmap   *walk.Bitmap
	colorbarPalette  string
	colorbarInvert   bool
	colorbarHeight   int
)

func initViewportGraphics() {
	bgBrush, _ = walk.NewSolidColorBrush(walk.RGB(241, 245, 249))       // Helles klinisches Slate-100
	hudFont, _ = walk.NewFont("Segoe UI", 8, 0)
	hudBoldFont, _ = walk.NewFont("Segoe UI", 8, walk.FontBold)
	anatFont, _ = walk.NewFont("Segoe UI", 8, walk.FontBold)
	reticlePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))     // Klinisches Saphirblau
	reticleRedPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))   // Alarm-Rot
	hairlinePen, _ = walk.NewCosmeticPen(walk.PenDash, walk.RGB(148, 163, 184))   // Feines Slate Fadenkreuz
	scalePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(100, 116, 139))     // Skalenstift
	badgeBrush, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))     // Weiße HUD-Karte
	badgeAlarmBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 242, 242))   // Helles Alarm-Rot
	cardBrush, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))
	cardBorderPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	framePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	barBorderPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(148, 163, 184))
}

func updateColorbarBitmap(barH int) {
	if barH <= 10 {
		barH = 200
	}
	if colorbarBitmap != nil && colorbarPalette == GState.ActivePalette && colorbarInvert == GState.InvertPalette && colorbarHeight == barH {
		return
	}
	if colorbarBitmap != nil {
		colorbarBitmap.Dispose()
		colorbarBitmap = nil
	}
	img := image.NewRGBA(image.Rect(0, 0, 12, barH))
	for y := 0; y < barH; y++ {
		norm := 1.0 - float64(y)/float64(barH)
		val := byte(norm * 255.0)
		c := PaletteColor(val, GState.ActivePalette, GState.InvertPalette)
		for x := 0; x < 12; x++ {
			img.SetRGBA(x, y, c)
		}
	}
	colorbarBitmap, _ = walk.NewBitmapFromImage(img)
	colorbarPalette = GState.ActivePalette
	colorbarInvert = GState.InvertPalette
	colorbarHeight = barH
}

func GetImageDestRect(canvasBounds walk.Rectangle, imgW, imgH int, zoom float64, panX, panY int) walk.Rectangle {
	if imgW <= 0 || imgH <= 0 {
		return walk.Rectangle{}
	}
	// Zentrieren & Zoom
	scale := math.Min(float64(canvasBounds.Width)/float64(imgW), float64(canvasBounds.Height)/float64(imgH)) * 0.95 * zoom
	dw := int(float64(imgW) * scale)
	dh := int(float64(imgH) * scale)
	dx := (canvasBounds.Width-dw)/2 + panX
	dy := (canvasBounds.Height-dh)/2 + panY
	return walk.Rectangle{X: dx, Y: dy, Width: dw, Height: dh}
}

// ── Left Viewport: Roh-Thermogramm (LWIR 8-14 µm) ───────────────────────────
func PaintLeftViewport(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if bgBrush == nil {
		initViewportGraphics()
	}
	actualBounds := bounds
	if vpLeft != nil {
		cb := vpLeft.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(bgBrush, actualBounds)

	if GState.RawBitmap == nil {
		text := "Kein Wärmebild geladen.\nKlicken Sie auf „Schnelltest“ oder Datei ▸ „Bild öffnen...“"
		canvas.DrawTextPixels(text, hudFont, walk.RGB(100, 116, 139), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	dest := GetImageDestRect(actualBounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)
	canvas.DrawBitmapWithOpacityPixels(GState.RawBitmap, dest, 255)

	// Klinischer Bildrahmen
	framePen, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	canvas.DrawRectanglePixels(framePen, walk.Rectangle{X: dest.X - 1, Y: dest.Y - 1, Width: dest.Width + 2, Height: dest.Height + 2})
	framePen.Dispose()

	// DICOM HUD Corner Overlays
	if GState.ShowHUD {
		drawDicomHUD(canvas, actualBounds, false)
	}

	// Anatomische Orientierungs-Marken
	drawAnatomicalTags(canvas, dest)

	// Fadenkreuz & Retikel
	if GState.ShowCrosshair && GState.HasHover {
		drawReticle(canvas, actualBounds, dest)
	}

	return nil
}

// ── Right Viewport: Diagnostisches Befund-Overlay ───────────────────────────
func PaintRightViewport(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if bgBrush == nil {
		initViewportGraphics()
	}
	actualBounds := bounds
	if vpRight != nil {
		cb := vpRight.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(bgBrush, actualBounds)

	if GState.OverlayBitmap == nil && GState.RawBitmap == nil {
		text := "Diagnostik-Befundung (Standby)\nArmstrong-Kriterien (ΔT ≥ 2,2 K) & 42-Stufen-Pipeline"
		canvas.DrawTextPixels(text, hudFont, walk.RGB(100, 116, 139), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	dest := GetImageDestRect(actualBounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)

	// Zeichne Befund-Overlay oder Rohbild
	if GState.ShowFindings && GState.OverlayBitmap != nil {
		canvas.DrawBitmapWithOpacityPixels(GState.OverlayBitmap, dest, 255)
	} else if GState.RawBitmap != nil {
		canvas.DrawBitmapWithOpacityPixels(GState.RawBitmap, dest, 255)
	}

	// Klinischer Bildrahmen
	framePen, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	canvas.DrawRectanglePixels(framePen, walk.Rectangle{X: dest.X - 1, Y: dest.Y - 1, Width: dest.Width + 2, Height: dest.Height + 2})
	framePen.Dispose()

	// DICOM HUD Corner Overlays (Rechts: Befund-Daten)
	if GState.ShowHUD {
		drawDicomHUD(canvas, actualBounds, true)
	}

	// Anatomische Orientierungs-Marken
	drawAnatomicalTags(canvas, dest)

	// Fadenkreuz & Retikel
	if GState.ShowCrosshair && GState.HasHover {
		drawReticle(canvas, actualBounds, dest)
	}

	// Vertikaler radiometrischer Farbbalken am rechten Rand
	drawColorbar(canvas, actualBounds)

	return nil
}

func drawDicomHUD(canvas *walk.Canvas, b walk.Rectangle, isResult bool) {
	pad := 10

	// Top-Left Card
	tlCard := walk.Rectangle{X: b.X + pad, Y: b.Y + pad, Width: 260, Height: 52}
	canvas.FillRectanglePixels(cardBrush, tlCard)
	canvas.DrawRectanglePixels(cardBorderPen, tlCard)

	if !isResult {
		canvas.DrawTextPixels(fmt.Sprintf("%s · (%s/%s J.)", GState.PatientID, GState.PatientSex, GState.PatientAge), hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 6, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		canvas.DrawTextPixels("PID: #904218-DFS · STATIONÄR", hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 20, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		canvas.DrawTextPixels("MODALITÄT: LWIR 8–14 µm · 0.60 mm/px", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 34, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
	} else {
		canvas.DrawTextPixels(fmt.Sprintf("%s · BEFUND-DIAGNOSTIK", GState.PatientID), hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 6, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		status := "ARMSTRONG: ΔT ≥ 2,2 K (ALARM)"
		col := walk.RGB(220, 38, 38)
		if GState.LastResult != nil && GState.LastResult.HighestRisk != "CRITICAL" {
			status = "ARMSTRONG: PHYSIOLOGISCH"
			col = walk.RGB(22, 163, 74)
		}
		canvas.DrawTextPixels(status, hudBoldFont, col, walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 20, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		canvas.DrawTextPixels("IWGDF 2023 LEITLINIEN-PROTOKOLL", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 34, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
	}

	// Top-Right Card
	trCard := walk.Rectangle{X: b.Width - 270, Y: b.Y + pad, Width: 260, Height: 52}
	canvas.FillRectanglePixels(cardBrush, trCard)
	canvas.DrawRectanglePixels(cardBorderPen, trCard)

	if !isResult {
		canvas.DrawTextPixels("UNIVERSITÄTSKLINIKUM", hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 6, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
		canvas.DrawTextPixels("DIABETISCHE FUSSAMBULANZ", hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 20, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
		canvas.DrawTextPixels(fmt.Sprintf("%d × %d · NETD < 40 mK", GState.Width, GState.Height), hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 34, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
	} else {
		canvas.DrawTextPixels("42-STUFIGE GO-PIPELINE", hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 6, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
		nHot := 0
		if GState.LastResult != nil {
			nHot = GState.LastResult.TotalHotspots
		}
		canvas.DrawTextPixels(fmt.Sprintf("HOTSPOTS: %d DETEKTIERT", nHot), hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 20, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
		canvas.DrawTextPixels("AVX2 HARDWARE-VEKTORISIERT", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: trCard.X + 8, Y: trCard.Y + 34, Width: trCard.Width - 16, Height: 14}, walk.TextRight)
	}

	// Bottom-Left Card
	blCard := walk.Rectangle{X: b.X + pad, Y: b.Height - 50, Width: 230, Height: 40}
	canvas.FillRectanglePixels(cardBrush, blCard)
	canvas.DrawRectanglePixels(cardBorderPen, blCard)
	canvas.DrawTextPixels(fmt.Sprintf("W: %d · L: %d (%.1f °C)", GState.WindowVal, GState.LevelVal, TempOf(byte(GState.LevelVal))), hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: blCard.X + 8, Y: blCard.Y + 4, Width: blCard.Width - 16, Height: 14}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("ZOOM: %d%% · %s", int(GState.Zoom*100), GState.ActivePalette), hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: blCard.X + 8, Y: blCard.Y + 20, Width: blCard.Width - 16, Height: 14}, walk.TextLeft)

	// Bottom-Right Card
	brCard := walk.Rectangle{X: b.Width - 240, Y: b.Height - 50, Width: 230, Height: 40}
	canvas.FillRectanglePixels(cardBrush, brCard)
	canvas.DrawRectanglePixels(cardBorderPen, brCard)
	canvas.DrawTextPixels("DIN EN ISO 13485 · MDR SaMD IIa", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: brCard.X + 8, Y: brCard.Y + 4, Width: brCard.Width - 16, Height: 14}, walk.TextRight)
	canvas.DrawTextPixels("NUC KALIBRIERT · ε = 0.98", hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: brCard.X + 8, Y: brCard.Y + 20, Width: brCard.Width - 16, Height: 14}, walk.TextRight)
}

func drawAnatomicalTags(canvas *walk.Canvas, dest walk.Rectangle) {
	if dest.Width <= 0 || dest.Height <= 0 {
		return
	}
	tagColor := walk.RGB(2, 132, 199)

	// D (Distal) - oben mit dezentem Badge-Hintergrund
	dBadge := walk.Rectangle{X: dest.X + dest.Width/2 - 45, Y: dest.Y + 6, Width: 90, Height: 18}
	canvas.FillRectanglePixels(badgeBrush, dBadge)
	canvas.DrawRectanglePixels(cardBorderPen, dBadge)
	canvas.DrawTextPixels("D (DISTAL)", anatFont, tagColor, dBadge, walk.TextCenter|walk.TextVCenter)

	// P (Proximal) - unten am Fersenrand, ausreichend breit damit kein Abschneiden erfolgt
	pBadge := walk.Rectangle{X: dest.X + dest.Width/2 - 55, Y: dest.Y + dest.Height - 24, Width: 110, Height: 18}
	canvas.FillRectanglePixels(badgeBrush, pBadge)
	canvas.DrawRectanglePixels(cardBorderPen, pBadge)
	canvas.DrawTextPixels("P (PROXIMAL)", anatFont, tagColor, pBadge, walk.TextCenter|walk.TextVCenter)

	// R (Rechts) / L (Links)
	rBadge := walk.Rectangle{X: dest.X + 8, Y: dest.Y + dest.Height/2 - 10, Width: 22, Height: 20}
	canvas.FillRectanglePixels(badgeBrush, rBadge)
	canvas.DrawRectanglePixels(cardBorderPen, rBadge)
	canvas.DrawTextPixels("R", anatFont, tagColor, rBadge, walk.TextCenter|walk.TextVCenter)

	lBadge := walk.Rectangle{X: dest.X + dest.Width - 30, Y: dest.Y + dest.Height/2 - 10, Width: 22, Height: 20}
	canvas.FillRectanglePixels(badgeBrush, lBadge)
	canvas.DrawRectanglePixels(cardBorderPen, lBadge)
	canvas.DrawTextPixels("L", anatFont, tagColor, lBadge, walk.TextCenter|walk.TextVCenter)

	// Calibrated Metric Scale (50 mm)
	scalePx := int(50.0 / 0.6 * (float64(dest.Width) / float64(GState.Width)))
	if scalePx > 10 && scalePx < dest.Width/2 {
		sx := dest.X + dest.Width/2 - scalePx/2
		sy := dest.Y + dest.Height - 34
		canvas.DrawLinePixels(scalePen, walk.Point{X: sx, Y: sy}, walk.Point{X: sx + scalePx, Y: sy})
		canvas.DrawLinePixels(scalePen, walk.Point{X: sx, Y: sy - 4}, walk.Point{X: sx, Y: sy + 4})
		canvas.DrawLinePixels(scalePen, walk.Point{X: sx + scalePx, Y: sy - 4}, walk.Point{X: sx + scalePx, Y: sy + 4})
		sRect := walk.Rectangle{X: sx, Y: sy - 14, Width: scalePx, Height: 14}
		canvas.DrawTextPixels("50 mm", hudFont, tagColor, sRect, walk.TextCenter)
	}
}

func drawReticle(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	// Screen coords
	cx := GState.HoverX
	cy := GState.HoverY
	if cx < bounds.X || cx >= bounds.X+bounds.Width || cy < bounds.Y || cy >= bounds.Y+bounds.Height {
		return
	}

	// 1. Feine Ausrichtungsachsen
	canvas.DrawLinePixels(hairlinePen, walk.Point{X: bounds.X, Y: cy}, walk.Point{X: bounds.X + bounds.Width, Y: cy})
	canvas.DrawLinePixels(hairlinePen, walk.Point{X: cx, Y: bounds.Y}, walk.Point{X: cx, Y: bounds.Y + bounds.Height})

	// 2. Zielkreis (15-mm Messretikel)
	rOuter := 14
	rInner := 3

	// Prüfe Armstrong-Alarm am Fokuspunkt
	isArmAlarm := false
	var tempCur, deltaT float64
	if dest.Width > 0 && dest.Height > 0 && GState.RawGray != nil {
		ix := int(float64(cx-dest.X) / float64(dest.Width) * float64(GState.Width))
		iy := int(float64(cy-dest.Y) / float64(dest.Height) * float64(GState.Height))
		if ix >= 0 && iy >= 0 && ix < GState.Width && iy < GState.Height {
			v := GState.RawGray[iy*GState.Width+ix]
			tempCur = TempOf(v)
			midline := GState.Width / 2
			contraX := midline*2 - ix
			if contraX >= 0 && contraX < GState.Width {
				cv := GState.RawGray[iy*GState.Width+contraX]
				deltaT = float64(int(v)-int(cv)) * 0.1
				if math.Abs(deltaT) >= 2.2 {
					isArmAlarm = true
				}
			}
		}
	}

	pen := reticlePen
	if isArmAlarm {
		pen = reticleRedPen
	}

	canvas.DrawEllipsePixels(pen, walk.Rectangle{X: cx - rOuter, Y: cy - rOuter, Width: 2 * rOuter, Height: 2 * rOuter})
	canvas.DrawEllipsePixels(pen, walk.Rectangle{X: cx - rInner, Y: cy - rInner, Width: 2 * rInner, Height: 2 * rInner})

	// 3. Schwebendes klinisches Mess-HUD am Cursor (Großzügig dimensioniert, damit kein Text abschneidet)
	badgeW := 185
	badgeH := 42
	bx := cx + rOuter + 8
	by := cy - rOuter - 6
	if bx+badgeW > bounds.X+bounds.Width {
		bx = cx - rOuter - 8 - badgeW
	}
	if by < bounds.Y {
		by = cy + rOuter + 6
	}

	badgeRect := walk.Rectangle{X: bx, Y: by, Width: badgeW, Height: badgeH}
	br := badgeBrush
	if isArmAlarm {
		br = badgeAlarmBr
	}
	canvas.FillRectanglePixels(br, badgeRect)
	canvas.DrawRectanglePixels(pen, badgeRect)

	line1 := fmt.Sprintf("%.1f °C  ·  ΔT %+.2f K", tempCur, deltaT)
	textColor := walk.RGB(2, 132, 199)
	if isArmAlarm {
		textColor = walk.RGB(220, 38, 38)
	}
	canvas.DrawTextPixels(line1, hudBoldFont, textColor, walk.Rectangle{X: bx + 8, Y: by + 5, Width: badgeW - 16, Height: 15}, walk.TextLeft)
	canvas.DrawTextPixels("Fokus: Plantar Pedis", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: bx + 8, Y: by + 21, Width: badgeW - 16, Height: 15}, walk.TextLeft)
}

func drawColorbar(canvas *walk.Canvas, b walk.Rectangle) {
	cbW := 54
	cbH := int(float64(b.Height) * 0.75)
	cbX := b.Width - cbW - 10
	cbY := (b.Height - cbH) / 2

	cbBox := walk.Rectangle{X: cbX, Y: cbY, Width: cbW, Height: cbH}
	canvas.FillRectanglePixels(badgeBrush, cbBox)
	canvas.DrawRectanglePixels(cardBorderPen, cbBox)

	// Header: TEMP [°C]
	canvas.DrawTextPixels("°C", hudBoldFont, walk.RGB(30, 41, 59), walk.Rectangle{X: cbX, Y: cbY + 4, Width: cbW, Height: 14}, walk.TextCenter)

	// Farbbalken
	barX := cbX + 24
	barY := cbY + 22
	barW := 12
	barH := cbH - 42

	// Vorkomponierte 1-Pass Bitmap zeichnen (Null GDI Brush Allocation Overhead!)
	updateColorbarBitmap(barH)
	if colorbarBitmap != nil {
		canvas.DrawBitmapWithOpacityPixels(colorbarBitmap, walk.Rectangle{X: barX, Y: barY, Width: barW, Height: barH}, 255)
	}
	canvas.DrawRectanglePixels(barBorderPen, walk.Rectangle{X: barX, Y: barY, Width: barW, Height: barH})

	// Ticks (45°, 40°, 35°, 30°, 25°, 20°)
	ticks := []struct {
		temp float64
		text string
		crit bool
	}{
		{45.0, "45°", false},
		{40.0, "40°", false},
		{35.0, "35°", false},
		{34.0, "⚠ 34°", true},
		{30.0, "30°", false},
		{25.0, "25°", false},
		{20.0, "20°", false},
	}

	for _, t := range ticks {
		py := barY + int((45.0-t.temp)/(45.0-20.0)*float64(barH))
		tCol := walk.RGB(71, 85, 105)
		if t.crit {
			tCol = walk.RGB(220, 38, 38)
		}
		canvas.DrawTextPixels(t.text, hudFont, tCol, walk.Rectangle{X: cbX + 2, Y: py - 6, Width: 20, Height: 12}, walk.TextRight)
	}

	// Armstrong Gefahren-Klammer (> 34°C)
	armY := barY + int((45.0-34.0)/(45.0-20.0)*float64(barH))
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 2, Y: barY}, walk.Point{X: barX + barW + 5, Y: barY})
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 5, Y: barY}, walk.Point{X: barX + barW + 5, Y: armY})
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 2, Y: armY}, walk.Point{X: barX + barW + 5, Y: armY})
}
