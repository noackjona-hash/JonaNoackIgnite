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
	hudTinyFont      *walk.Font
	anatFont         *walk.Font
	reticlePen       *walk.CosmeticPen
	reticleRedPen    *walk.CosmeticPen
	hairlinePen      *walk.CosmeticPen
	scalePen         *walk.CosmeticPen
	badgeBrush       *walk.SolidColorBrush
	badgeAlarmBr     *walk.SolidColorBrush
	badgeCyanBr      *walk.SolidColorBrush
	cardBrush        *walk.SolidColorBrush
	cardBorderPen    *walk.CosmeticPen
	framePen         *walk.CosmeticPen
	barBorderPen     *walk.CosmeticPen
	colorbarBitmap   *walk.Bitmap
	colorbarPalette  string
	colorbarInvert   bool
	colorbarHeight   int

	measurePen       *walk.CosmeticPen
	measureGreenPen  *walk.CosmeticPen
	measureAmberPen  *walk.CosmeticPen
	measureDashPen   *walk.CosmeticPen
	measureGreenDash *walk.CosmeticPen
	angiosomePen     *walk.CosmeticPen
	curtainPen       *walk.CosmeticPen
	isoPen30         *walk.CosmeticPen
	isoPen32         *walk.CosmeticPen
	isoPen34         *walk.CosmeticPen
)

func initViewportGraphics() {
	bgBrush, _ = walk.NewSolidColorBrush(walk.RGB(241, 245, 249)) // Helles klinisches Slate-100
	hudFont, _ = walk.NewFont("Segoe UI Variable Text", 8, 0)
	hudBoldFont, _ = walk.NewFont("Segoe UI Variable Display", 8, walk.FontBold)
	hudTinyFont, _ = walk.NewFont("Segoe UI Variable Text", 7, 0)
	anatFont, _ = walk.NewFont("Segoe UI Variable Display", 8, walk.FontBold)
	reticlePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))     // Klinisches Saphirblau
	reticleRedPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))  // Alarm-Rot
	hairlinePen, _ = walk.NewCosmeticPen(walk.PenDash, walk.RGB(148, 163, 184))   // Feines Slate Fadenkreuz
	scalePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(100, 116, 139))     // Skalenstift
	badgeBrush, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))              // Weiße HUD-Karte
	badgeAlarmBr, _ = walk.NewSolidColorBrush(walk.RGB(254, 242, 242))            // Helles Alarm-Rot
	badgeCyanBr, _ = walk.NewSolidColorBrush(walk.RGB(224, 242, 254))             // WinUI 3 Cyan Pill
	cardBrush, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))
	cardBorderPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	framePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	barBorderPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(148, 163, 184))

	measurePen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))
	measureGreenPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(16, 185, 129))
	measureAmberPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(217, 119, 6))
	measureDashPen, _ = walk.NewCosmeticPen(walk.PenDash, walk.RGB(2, 132, 199))
	measureGreenDash, _ = walk.NewCosmeticPen(walk.PenDash, walk.RGB(16, 185, 129))
	angiosomePen, _ = walk.NewCosmeticPen(walk.PenDot, walk.RGB(14, 165, 233))
	curtainPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))

	isoPen30, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(56, 189, 248))  // 30°C Cyan
	isoPen32, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(251, 191, 36))  // 32°C Amber
	isoPen34, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(244, 63, 94))   // 34°C Crimson
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
	scale := math.Min(float64(canvasBounds.Width)/float64(imgW), float64(canvasBounds.Height)/float64(imgH)) * 0.94 * zoom
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
		text := "Kein Wärmebild geladen.\nKlicken Sie auf „⚡ Schnelltest“ oder Datei ▸ „Bild öffnen...“"
		canvas.DrawTextPixels(text, hudFont, walk.RGB(100, 116, 139), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	dest := GetImageDestRect(actualBounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)
	canvas.DrawBitmapWithOpacityPixels(GState.RawBitmap, dest, 255)

	// Klinischer Bildrahmen
	canvas.DrawRectanglePixels(framePen, walk.Rectangle{X: dest.X - 1, Y: dest.Y - 1, Width: dest.Width + 2, Height: dest.Height + 2})

	// Optionale Topografie-Höhenlinien (Iso-Contours)
	if GState.ShowIsoContours {
		drawIsoContours(canvas, dest)
	}

	// Optionales Taylor & Palmer Angiosom-Gitter
	if GState.ShowAngiosomeGrid {
		drawAngiosomeOverlay(canvas, dest)
	}

	// DICOM HUD Corner Overlays
	if GState.ShowHUD {
		drawDicomHUD(canvas, actualBounds, false)
	}

	// Anatomische Orientierungs-Marken
	drawAnatomicalTags(canvas, dest)

	// Messungen, Pins & aktive Zeichen-Tools
	drawMeasurements(canvas, actualBounds, dest)
	drawThermalPins(canvas, actualBounds, dest)
	drawActiveDrawing(canvas, actualBounds, dest)

	// Mini-Navigator bei Zoom
	if GState.Zoom > 1.08 {
		drawMiniNavigator(canvas, actualBounds, dest)
	}

	// Fadenkreuz & Retikel
	if GState.ShowCrosshair && GState.HasHover && GState.ActiveTool == ToolReticle {
		drawReticle(canvas, actualBounds, dest)
	}

	// Radiometrische Präzisions-Lupe
	if (GState.ShowMagnifier || GState.ActiveTool == ToolMagnifier) && GState.HasHover {
		drawMagnifierLoupe(canvas, actualBounds, dest)
	}

	return nil
}

// getRightTargetBitmap wählt das aktive Diagnostik-Bitmap für den rechten Viewport
func getRightTargetBitmap() *walk.Bitmap {
	switch GState.RightViewMode {
	case "deltat":
		if GState.DeltaTBitmap != nil {
			return GState.DeltaTBitmap
		}
	case "tophat":
		if GState.TopHatBitmap != nil {
			return GState.TopHatBitmap
		}
	}
	if GState.ShowFindings && GState.OverlayBitmap != nil {
		return GState.OverlayBitmap
	}
	return GState.RawBitmap
}

// ── Right Viewport: Diagnostisches Befund-Overlay & Curtain-Wipe ────────────
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
	rightBmp := getRightTargetBitmap()

	// Zeichne entweder Curtain-Wipe (Vorhang-Vergleich) oder Vollbild
	if GState.ShowCurtainWipe && GState.RawBitmap != nil && rightBmp != nil && dest.Width > 10 && GState.Width > 10 {
		ratio := math.Max(0.05, math.Min(0.95, GState.CurtainRatio))
		splitScreenW := int(float64(dest.Width) * ratio)
		splitImgW := int(float64(GState.Width) * ratio)

		// Links vom Vorhang: Rohbild
		dstLeft := walk.Rectangle{X: dest.X, Y: dest.Y, Width: splitScreenW, Height: dest.Height}
		srcLeft := walk.Rectangle{X: 0, Y: 0, Width: splitImgW, Height: GState.Height}
		canvas.DrawBitmapPartWithOpacityPixels(GState.RawBitmap, dstLeft, srcLeft, 255)

		// Rechts vom Vorhang: Diagnostik-Overlay / ΔT-Heatmap
		dstRight := walk.Rectangle{X: dest.X + splitScreenW, Y: dest.Y, Width: dest.Width - splitScreenW, Height: dest.Height}
		srcRight := walk.Rectangle{X: splitImgW, Y: 0, Width: GState.Width - splitImgW, Height: GState.Height}
		canvas.DrawBitmapPartWithOpacityPixels(rightBmp, dstRight, srcRight, 255)

		// Vorhang-Trennlinie + WinUI 3 Grip Handle
		curtainX := dest.X + splitScreenW
		for dx := -1; dx <= 1; dx++ {
			canvas.DrawLinePixels(curtainPen, walk.Point{X: curtainX + dx, Y: dest.Y}, walk.Point{X: curtainX + dx, Y: dest.Y + dest.Height})
		}

		// Mittiger Griff-Kreis (◄|►)
		gripY := dest.Y + dest.Height/2
		gripRect := walk.Rectangle{X: curtainX - 18, Y: gripY - 14, Width: 36, Height: 28}
		drawFluentRoundRect(canvas, gripRect, badgeCyanBr, curtainPen, 12)
		canvas.DrawTextPixels("◄|►", hudBoldFont, walk.RGB(2, 132, 199), gripRect, walk.TextCenter|walk.TextVCenter)

		// Vorhang-Header-Badges
		lblL := walk.Rectangle{X: curtainX - 96, Y: dest.Y + 30, Width: 90, Height: 20}
		if lblL.X >= dest.X+4 {
			drawFluentRoundRect(canvas, lblL, badgeBrush, cardBorderPen, 6)
			canvas.DrawTextPixels("◀ ROH-LWIR", hudBoldFont, walk.RGB(71, 85, 105), lblL, walk.TextCenter|walk.TextVCenter)
		}
		lblR := walk.Rectangle{X: curtainX + 6, Y: dest.Y + 30, Width: 105, Height: 20}
		if lblR.X+lblR.Width <= dest.X+dest.Width-4 {
			drawFluentRoundRect(canvas, lblR, badgeCyanBr, curtainPen, 6)
			canvas.DrawTextPixels("BEFUND-KI ▶", hudBoldFont, walk.RGB(2, 132, 199), lblR, walk.TextCenter|walk.TextVCenter)
		}
	} else if rightBmp != nil {
		canvas.DrawBitmapWithOpacityPixels(rightBmp, dest, 255)
	}

	// Klinischer Bildrahmen
	canvas.DrawRectanglePixels(framePen, walk.Rectangle{X: dest.X - 1, Y: dest.Y - 1, Width: dest.Width + 2, Height: dest.Height + 2})

	// Optionale Topografie-Höhenlinien (Iso-Contours)
	if GState.ShowIsoContours {
		drawIsoContours(canvas, dest)
	}

	// Optionales Taylor & Palmer Angiosom-Gitter
	if GState.ShowAngiosomeGrid {
		drawAngiosomeOverlay(canvas, dest)
	}

	// DICOM HUD Corner Overlays (Rechts: Befund-Daten)
	if GState.ShowHUD {
		drawDicomHUD(canvas, actualBounds, true)
	}

	// Anatomische Orientierungs-Marken
	drawAnatomicalTags(canvas, dest)

	// Messungen, Pins & aktive Zeichen-Tools
	drawMeasurements(canvas, actualBounds, dest)
	drawThermalPins(canvas, actualBounds, dest)
	drawActiveDrawing(canvas, actualBounds, dest)
	drawActiveCrosshair(canvas, actualBounds, dest)

	// Mini-Navigator bei Zoom
	if GState.Zoom > 1.08 {
		drawMiniNavigator(canvas, actualBounds, dest)
	}

	// Fadenkreuz & Retikel
	if GState.ShowCrosshair && GState.HasHover && GState.ActiveTool == ToolReticle {
		drawReticle(canvas, actualBounds, dest)
	}

	// Radiometrische Präzisions-Lupe
	if (GState.ShowMagnifier || GState.ActiveTool == ToolMagnifier) && GState.HasHover {
		drawMagnifierLoupe(canvas, actualBounds, dest)
	}

	// Vertikaler radiometrischer Farbbalken am rechten Rand
	drawColorbar(canvas, actualBounds)

	return nil
}

// drawIsoContours zeichnet thermische Topografie-Höhenlinien (30°C, 32°C, 34°C)
func drawIsoContours(canvas *walk.Canvas, dest walk.Rectangle) {
	if len(GState.RawGray) == 0 || GState.Width <= 4 || GState.Height <= 4 || dest.Width <= 20 {
		return
	}
	w, h := GState.Width, GState.Height
	raw30 := RawOf(30.0)
	raw32 := RawOf(32.0)
	raw34 := RawOf(34.0)

	step := 3
	for y := step; y < h-step; y += step {
		rowOff := y * w
		for x := step; x < w-step; x += step {
			v := GState.RawGray[rowOff+x]
			if v <= 30 {
				continue
			}
			vr := GState.RawGray[rowOff+x+step]
			vb := GState.RawGray[(y+step)*w+x]

			checkCross := func(thresh byte, pen *walk.CosmeticPen) {
				if (v >= thresh && vr < thresh) || (v < thresh && vr >= thresh) ||
					(v >= thresh && vb < thresh) || (v < thresh && vb >= thresh) {
					s1 := ImgToScreen(image.Pt(x, y), dest, w, h)
					s2 := ImgToScreen(image.Pt(x+step, y+step), dest, w, h)
					canvas.DrawLinePixels(pen, s1, s2)
				}
			}

			checkCross(raw30, isoPen30)
			checkCross(raw32, isoPen32)
			checkCross(raw34, isoPen34)
		}
	}
}

// drawAngiosomeOverlay zeichnet die plantaren Taylor & Palmer Gefäßversorgungsgebiete (Angiosome)
func drawAngiosomeOverlay(canvas *walk.Canvas, dest walk.Rectangle) {
	if dest.Width <= 40 || dest.Height <= 40 {
		return
	}
	midX := dest.X + dest.Width/2
	// Mittellinie L / R
	canvas.DrawLinePixels(angiosomePen, walk.Point{X: midX, Y: dest.Y + 24}, walk.Point{X: midX, Y: dest.Y + dest.Height - 28})

	// Horizontale anatomische Zonengrenzen (Zehen/Hallux 28%, Metatarsale 48%, Mittelfuß 72%)
	yFore := dest.Y + int(float64(dest.Height)*0.28)
	yMeta := dest.Y + int(float64(dest.Height)*0.48)
	yCalc := dest.Y + int(float64(dest.Height)*0.72)

	canvas.DrawLinePixels(angiosomePen, walk.Point{X: dest.X + 15, Y: yFore}, walk.Point{X: dest.X + dest.Width - 15, Y: yFore})
	canvas.DrawLinePixels(angiosomePen, walk.Point{X: dest.X + 15, Y: yMeta}, walk.Point{X: dest.X + dest.Width - 15, Y: yMeta})
	canvas.DrawLinePixels(angiosomePen, walk.Point{X: dest.X + 15, Y: yCalc}, walk.Point{X: dest.X + dest.Width - 15, Y: yCalc})

	// Angiosom-Badges (Taylor & Palmer)
	drawAngioTag := func(rx, ry int, code, sub string) {
		r := walk.Rectangle{X: rx - 46, Y: ry - 10, Width: 92, Height: 20}
		drawFluentRoundRect(canvas, r, badgeCyanBr, angiosomePen, 5)
		canvas.DrawTextPixels(code+" · "+sub, hudTinyFont, walk.RGB(3, 105, 161), r, walk.TextCenter|walk.TextVCenter)
	}

	qLeft := dest.X + dest.Width*3/4
	qRight := dest.X + dest.Width/4

	drawAngioTag(qRight, dest.Y+int(float64(dest.Height)*0.19), "ADP/APM", "Hallux R")
	drawAngioTag(qLeft, dest.Y+int(float64(dest.Height)*0.19), "ADP/APM", "Hallux L")
	drawAngioTag(qRight, dest.Y+int(float64(dest.Height)*0.38), "APM", "Plant. med.")
	drawAngioTag(qLeft, dest.Y+int(float64(dest.Height)*0.38), "APM", "Plant. med.")
	drawAngioTag(qRight, dest.Y+int(float64(dest.Height)*0.60), "APL", "Plant. lat.")
	drawAngioTag(qLeft, dest.Y+int(float64(dest.Height)*0.60), "APL", "Plant. lat.")
	drawAngioTag(qRight, dest.Y+int(float64(dest.Height)*0.81), "RC", "Calcaneus")
	drawAngioTag(qLeft, dest.Y+int(float64(dest.Height)*0.81), "RC", "Calcaneus")
}

// drawMagnifierLoupe rendert eine schwebende 4x WinUI 3 Radiometrie-Lupe mit Subpixel-Temperaturmatrix
func drawMagnifierLoupe(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if dest.Width <= 0 || dest.Height <= 0 || GState.RawBitmap == nil || len(GState.RawGray) == 0 {
		return
	}
	cx, cy := GState.HoverX, GState.HoverY
	pt := ScreenToImg(cx, cy, dest, GState.Width, GState.Height)
	if pt.X <= 0 || pt.Y <= 0 || pt.X >= GState.Width-1 || pt.Y >= GState.Height-1 {
		return
	}

	loupeW, loupeH := 186, 152
	lx := cx + 22
	ly := cy + 22
	if lx+loupeW > bounds.X+bounds.Width-10 {
		lx = cx - loupeW - 22
	}
	if ly+loupeH > bounds.Y+bounds.Height-10 {
		ly = cy - loupeH - 22
	}

	loupeCard := walk.Rectangle{X: lx, Y: ly, Width: loupeW, Height: loupeH}
	drawFluentRoundRect(canvas, loupeCard, badgeBrush, reticlePen, 8)

	// Header
	tCenter := TempOf(GState.RawGray[pt.Y*GState.Width+pt.X])
	canvas.DrawTextPixels(fmt.Sprintf("🔍 4× LUPE @ (%d,%d) · %.1f°C", pt.X, pt.Y, tCenter),
		hudBoldFont, walk.RGB(2, 132, 199),
		walk.Rectangle{X: lx + 8, Y: ly + 4, Width: loupeW - 16, Height: 14}, walk.TextLeft)

	// Links in der Lupe: Gezoomter Bildausschnitt (88x88 px)
	patchRadius := 14
	srcX := int(math.Max(0, float64(pt.X-patchRadius)))
	srcY := int(math.Max(0, float64(pt.Y-patchRadius)))
	srcW := int(math.Min(float64(GState.Width-srcX), float64(patchRadius*2)))
	srcH := int(math.Min(float64(GState.Height-srcY), float64(patchRadius*2)))

	patchDst := walk.Rectangle{X: lx + 8, Y: ly + 22, Width: 82, Height: 82}
	if srcW > 2 && srcH > 2 {
		canvas.DrawBitmapPartWithOpacityPixels(GState.RawBitmap, patchDst, walk.Rectangle{X: srcX, Y: srcY, Width: srcW, Height: srcH}, 255)
	}
	canvas.DrawRectanglePixels(reticlePen, patchDst)
	// Fadenkreuz im Lupenbild
	pMidX := patchDst.X + patchDst.Width/2
	pMidY := patchDst.Y + patchDst.Height/2
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: pMidX - 8, Y: pMidY}, walk.Point{X: pMidX + 8, Y: pMidY})
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: pMidX, Y: pMidY - 8}, walk.Point{X: pMidX, Y: pMidY + 8})

	// Rechts in der Lupe: 3x3 Subpixel-Zahlenraster (°C)
	mat := GetSubpixelMatrix(GState.RawGray, GState.Width, GState.Height, pt.X, pt.Y)
	gridX := lx + 96
	gridY := ly + 22
	cellW, cellH := 27, 27
	for ry := 0; ry < 3; ry++ {
		for rx := 0; rx < 3; rx++ {
			valT := mat[ry+1][rx+1]
			cellRect := walk.Rectangle{X: gridX + rx*cellW, Y: gridY + ry*cellH, Width: cellW - 1, Height: cellH - 1}
			cellBg := badgeBrush
			tCol := walk.RGB(51, 65, 85)
			fnt := hudTinyFont
			if rx == 1 && ry == 1 {
				cellBg = badgeCyanBr
				tCol = walk.RGB(220, 38, 38)
				fnt = hudBoldFont
			}
			canvas.FillRectanglePixels(cellBg, cellRect)
			canvas.DrawRectanglePixels(cardBorderPen, cellRect)
			canvas.DrawTextPixels(fmt.Sprintf("%.1f", valT), fnt, tCol, cellRect, walk.TextCenter|walk.TextVCenter)
		}
	}

	// Footer: Lokale Statistik im 5x5 Fenster
	min5, max5, sum5 := 100.0, -100.0, 0.0
	for ry := 0; ry < 5; ry++ {
		for rx := 0; rx < 5; rx++ {
			v := mat[ry][rx]
			sum5 += v
			if v < min5 {
				min5 = v
			}
			if v > max5 {
				max5 = v
			}
		}
	}
	mean5 := sum5 / 25.0
	canvas.DrawTextPixels(fmt.Sprintf("5×5 Ø: %.1f°C · Spanne: %.1f..%.1f°C", mean5, min5, max5),
		hudTinyFont, walk.RGB(71, 85, 105),
		walk.Rectangle{X: lx + 8, Y: ly + 108, Width: loupeW - 16, Height: 14}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("Lokale Streuung ΔT_lokal: %.2f K", max5-min5),
		hudBoldFont, walk.RGB(2, 132, 199),
		walk.Rectangle{X: lx + 8, Y: ly + 124, Width: loupeW - 16, Height: 14}, walk.TextLeft)
}

// drawMiniNavigator zeichnet eine Picture-in-Picture Übersichtskarte bei aktivem Zoom
func drawMiniNavigator(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if GState.RawBitmap == nil || GState.Width <= 0 || GState.Height <= 0 {
		return
	}
	navW, navH := 110, 84
	nx := bounds.X + 12
	ny := bounds.Height - 54 - navH - 6
	if ny < bounds.Y+70 {
		return
	}
	navRect := walk.Rectangle{X: nx, Y: ny, Width: navW, Height: navH}
	drawFluentRoundRect(canvas, navRect, badgeBrush, reticlePen, 6)

	imgBox := walk.Rectangle{X: nx + 4, Y: ny + 16, Width: navW - 8, Height: navH - 20}
	canvas.DrawBitmapWithOpacityPixels(GState.RawBitmap, imgBox, 235)
	canvas.DrawTextPixels(fmt.Sprintf("NAVIGATOR (%.0f%%)", GState.Zoom*100), hudTinyFont, walk.RGB(2, 132, 199),
		walk.Rectangle{X: nx + 6, Y: ny + 2, Width: navW - 12, Height: 12}, walk.TextLeft)

	// Berechne sichtbares Fenster relativ zum Bild
	visW := int(float64(imgBox.Width) / GState.Zoom)
	visH := int(float64(imgBox.Height) / GState.Zoom)
	visX := imgBox.X + (imgBox.Width-visW)/2 - int(float64(GState.PanX)/float64(dest.Width)*float64(imgBox.Width))
	visY := imgBox.Y + (imgBox.Height-visH)/2 - int(float64(GState.PanY)/float64(dest.Height)*float64(imgBox.Height))
	canvas.DrawRectanglePixels(reticleRedPen, walk.Rectangle{X: visX, Y: visY, Width: visW, Height: visH})
}

func drawDicomHUD(canvas *walk.Canvas, b walk.Rectangle, isResult bool) {
	pad := 10

	// Top-Left Card
	tlCard := walk.Rectangle{X: b.X + pad, Y: b.Y + pad, Width: 265, Height: 52}
	drawFluentRoundRect(canvas, tlCard, cardBrush, cardBorderPen, 6)

	if !isResult {
		canvas.DrawTextPixels(fmt.Sprintf("%s · (%s/%s J.)", GState.PatientID, GState.PatientSex, GState.PatientAge), hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 6, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		canvas.DrawTextPixels("PID: #904218-DFS · STATIONÄR", hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 20, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
		canvas.DrawTextPixels("MODALITÄT: LWIR 8–14 µm · 0.60 mm/px", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 34, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
	} else {
		modeTitle := "BEFUND-DIAGNOSTIK"
		if GState.RightViewMode == "deltat" {
			modeTitle = "KONTRALATERALE ΔT-KARTE"
		} else if GState.RightViewMode == "tophat" {
			modeTitle = "WHITE TOP-HAT ISOLATION"
		}
		canvas.DrawTextPixels(fmt.Sprintf("%s · %s", GState.PatientID, modeTitle), hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: tlCard.X + 8, Y: tlCard.Y + 6, Width: tlCard.Width - 16, Height: 14}, walk.TextLeft)
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
	drawFluentRoundRect(canvas, trCard, cardBrush, cardBorderPen, 6)

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
	blCard := walk.Rectangle{X: b.X + pad, Y: b.Height - 50, Width: 235, Height: 40}
	drawFluentRoundRect(canvas, blCard, cardBrush, cardBorderPen, 6)
	canvas.DrawTextPixels(fmt.Sprintf("W: %d · L: %d (%.1f °C)", GState.WindowVal, GState.LevelVal, TempOf(byte(GState.LevelVal))), hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: blCard.X + 8, Y: blCard.Y + 4, Width: blCard.Width - 16, Height: 14}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("ZOOM: %d%% · %s", int(GState.Zoom*100), GState.ActivePalette), hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: blCard.X + 8, Y: blCard.Y + 20, Width: blCard.Width - 16, Height: 14}, walk.TextLeft)

	// Bottom-Right Card
	brCard := walk.Rectangle{X: b.Width - 240, Y: b.Height - 50, Width: 230, Height: 40}
	drawFluentRoundRect(canvas, brCard, cardBrush, cardBorderPen, 6)
	canvas.DrawTextPixels("DIN EN ISO 13485 · MDR SaMD IIa", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: brCard.X + 8, Y: brCard.Y + 4, Width: brCard.Width - 16, Height: 14}, walk.TextRight)
	canvas.DrawTextPixels("NUC KALIBRIERT · ε = 0.98", hudBoldFont, walk.RGB(2, 132, 199), walk.Rectangle{X: brCard.X + 8, Y: brCard.Y + 20, Width: brCard.Width - 16, Height: 14}, walk.TextRight)
}

func drawAnatomicalTags(canvas *walk.Canvas, dest walk.Rectangle) {
	if dest.Width <= 0 || dest.Height <= 0 {
		return
	}
	tagColor := walk.RGB(2, 132, 199)

	dBadge := walk.Rectangle{X: dest.X + dest.Width/2 - 45, Y: dest.Y + 6, Width: 90, Height: 18}
	drawFluentRoundRect(canvas, dBadge, badgeBrush, cardBorderPen, 6)
	canvas.DrawTextPixels("D (DISTAL)", anatFont, tagColor, dBadge, walk.TextCenter|walk.TextVCenter)

	pBadge := walk.Rectangle{X: dest.X + dest.Width/2 - 55, Y: dest.Y + dest.Height - 24, Width: 110, Height: 18}
	drawFluentRoundRect(canvas, pBadge, badgeBrush, cardBorderPen, 6)
	canvas.DrawTextPixels("P (PROXIMAL)", anatFont, tagColor, pBadge, walk.TextCenter|walk.TextVCenter)

	rBadge := walk.Rectangle{X: dest.X + 8, Y: dest.Y + dest.Height/2 - 10, Width: 22, Height: 20}
	drawFluentRoundRect(canvas, rBadge, badgeBrush, cardBorderPen, 6)
	canvas.DrawTextPixels("R", anatFont, tagColor, rBadge, walk.TextCenter|walk.TextVCenter)

	lBadge := walk.Rectangle{X: dest.X + dest.Width - 30, Y: dest.Y + dest.Height/2 - 10, Width: 22, Height: 20}
	drawFluentRoundRect(canvas, lBadge, badgeBrush, cardBorderPen, 6)
	canvas.DrawTextPixels("L", anatFont, tagColor, lBadge, walk.TextCenter|walk.TextVCenter)

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
	cx := GState.HoverX
	cy := GState.HoverY
	if cx < bounds.X || cx >= bounds.X+bounds.Width || cy < bounds.Y || cy >= bounds.Y+bounds.Height {
		return
	}

	canvas.DrawLinePixels(hairlinePen, walk.Point{X: bounds.X, Y: cy}, walk.Point{X: bounds.X + bounds.Width, Y: cy})
	canvas.DrawLinePixels(hairlinePen, walk.Point{X: cx, Y: bounds.Y}, walk.Point{X: cx, Y: bounds.Y + bounds.Height})

	rOuter := 14
	rInner := 3

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
			// Zeichne kontralateralen Spiegelpunkt als feinen grünen Kreis
			scContra := ImgToScreen(image.Pt(contraX, iy), dest, GState.Width, GState.Height)
			canvas.DrawEllipsePixels(measureGreenDash, walk.Rectangle{X: scContra.X - 7, Y: scContra.Y - 7, Width: 14, Height: 14})
		}
	}

	pen := reticlePen
	if isArmAlarm {
		pen = reticleRedPen
	}

	canvas.DrawEllipsePixels(pen, walk.Rectangle{X: cx - rOuter, Y: cy - rOuter, Width: 2 * rOuter, Height: 2 * rOuter})
	canvas.DrawEllipsePixels(pen, walk.Rectangle{X: cx - rInner, Y: cy - rInner, Width: 2 * rInner, Height: 2 * rInner})

	badgeW := 190
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
	drawFluentRoundRect(canvas, badgeRect, br, pen, 6)

	line1 := fmt.Sprintf("%.1f °C  ·  ΔT %+.2f K", tempCur, deltaT)
	textColor := walk.RGB(2, 132, 199)
	if isArmAlarm {
		textColor = walk.RGB(220, 38, 38)
	}
	canvas.DrawTextPixels(line1, hudBoldFont, textColor, walk.Rectangle{X: bx + 8, Y: by + 5, Width: badgeW - 16, Height: 15}, walk.TextLeft)
	canvas.DrawTextPixels("⌖ Kontralaterale Spiegel-Sonde aktiv", hudFont, walk.RGB(100, 116, 139), walk.Rectangle{X: bx + 8, Y: by + 21, Width: badgeW - 16, Height: 15}, walk.TextLeft)
}

func drawColorbar(canvas *walk.Canvas, b walk.Rectangle) {
	cbW := 54
	cbH := int(float64(b.Height) * 0.72)
	cbX := b.Width - cbW - 10
	cbY := (b.Height - cbH) / 2

	cbBox := walk.Rectangle{X: cbX, Y: cbY, Width: cbW, Height: cbH}
	drawFluentRoundRect(canvas, cbBox, badgeBrush, cardBorderPen, 6)

	canvas.DrawTextPixels("°C", hudBoldFont, walk.RGB(30, 41, 59), walk.Rectangle{X: cbX, Y: cbY + 4, Width: cbW, Height: 14}, walk.TextCenter)

	barX := cbX + 24
	barY := cbY + 22
	barW := 12
	barH := cbH - 42

	updateColorbarBitmap(barH)
	if colorbarBitmap != nil {
		canvas.DrawBitmapWithOpacityPixels(colorbarBitmap, walk.Rectangle{X: barX, Y: barY, Width: barW, Height: barH}, 255)
	}
	canvas.DrawRectanglePixels(barBorderPen, walk.Rectangle{X: barX, Y: barY, Width: barW, Height: barH})

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

	armY := barY + int((45.0-34.0)/(45.0-20.0)*float64(barH))
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 2, Y: barY}, walk.Point{X: barX + barW + 5, Y: barY})
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 5, Y: barY}, walk.Point{X: barX + barW + 5, Y: armY})
	canvas.DrawLinePixels(reticleRedPen, walk.Point{X: barX + barW + 2, Y: armY}, walk.Point{X: barX + barW + 5, Y: armY})
}

func ImgToScreen(pt image.Point, dest walk.Rectangle, imgW, imgH int) walk.Point {
	if imgW <= 0 || imgH <= 0 || dest.Width <= 0 || dest.Height <= 0 {
		return walk.Point{}
	}
	sx := dest.X + int(float64(pt.X)/float64(imgW)*float64(dest.Width))
	sy := dest.Y + int(float64(pt.Y)/float64(imgH)*float64(dest.Height))
	return walk.Point{X: sx, Y: sy}
}

func ScreenToImg(x, y int, dest walk.Rectangle, imgW, imgH int) image.Point {
	if dest.Width <= 0 || dest.Height <= 0 || imgW <= 0 || imgH <= 0 {
		return image.Point{}
	}
	ix := int(float64(x-dest.X) / float64(dest.Width) * float64(imgW))
	iy := int(float64(y-dest.Y) / float64(dest.Height) * float64(imgH))
	if ix < 0 {
		ix = 0
	}
	if ix >= imgW {
		ix = imgW - 1
	}
	if iy < 0 {
		iy = 0
	}
	if iy >= imgH {
		iy = imgH - 1
	}
	return image.Pt(ix, iy)
}

func drawMiniBadge(canvas *walk.Canvas, x, y int, text string, col walk.Color) {
	bW := len(text)*7 + 16
	bH := 22
	bRect := walk.Rectangle{X: x, Y: y, Width: bW, Height: bH}
	drawFluentRoundRect(canvas, bRect, badgeBrush, cardBorderPen, 5)
	canvas.DrawTextPixels(text, hudBoldFont, col, walk.Rectangle{X: x + 6, Y: y + 4, Width: bW - 12, Height: 14}, walk.TextLeft)
}

func drawThermalPins(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if len(GState.PinProbes) == 0 || dest.Width <= 0 || dest.Height <= 0 {
		return
	}
	w, h := GState.Width, GState.Height
	for _, p := range GState.PinProbes {
		sc := ImgToScreen(p.Pt, dest, w, h)
		pen := measurePen
		br := badgeCyanBr
		tCol := walk.RGB(2, 132, 199)
		if p.Risk == "CRITICAL" {
			pen = reticleRedPen
			br = badgeAlarmBr
			tCol = walk.RGB(220, 38, 38)
		} else if p.Risk == "MODERATE" {
			pen = measureAmberPen
			tCol = walk.RGB(180, 83, 9)
		}

		// Pin Marker
		canvas.DrawEllipsePixels(pen, walk.Rectangle{X: sc.X - 6, Y: sc.Y - 6, Width: 12, Height: 12})
		canvas.DrawEllipsePixels(pen, walk.Rectangle{X: sc.X - 2, Y: sc.Y - 2, Width: 4, Height: 4})

		// Pin Callout Pill
		pillRect := walk.Rectangle{X: sc.X + 8, Y: sc.Y - 11, Width: 112, Height: 22}
		drawFluentRoundRect(canvas, pillRect, br, pen, 6)
		canvas.DrawTextPixels(fmt.Sprintf("📍%s: %.1f° (%+.1fK)", p.Label, p.TempC, p.DeltaT),
			hudBoldFont, tCol, pillRect, walk.TextCenter|walk.TextVCenter)
	}
}

func drawMeasurements(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if len(GState.Measurements) == 0 || dest.Width <= 0 || dest.Height <= 0 {
		return
	}

	w, h := GState.Width, GState.Height

	for _, m := range GState.Measurements {
		pen := measurePen
		textCol := walk.RGB(2, 132, 199)
		br := badgeBrush
		if m.Risk == "CRITICAL" {
			pen = reticleRedPen
			textCol = walk.RGB(220, 38, 38)
			br = badgeAlarmBr
		} else if m.Risk == "MODERATE" {
			pen = measureAmberPen
			textCol = walk.RGB(217, 119, 6)
		}

		switch m.Type {
		case "Lineal", "Schnittlinie":
			if len(m.Points) >= 2 {
				s1 := ImgToScreen(m.Points[0], dest, w, h)
				s2 := ImgToScreen(m.Points[1], dest, w, h)

				canvas.DrawLinePixels(pen, s1, s2)

				dx := float64(s2.X - s1.X)
				dy := float64(s2.Y - s1.Y)
				lenPx := math.Sqrt(dx*dx + dy*dy)
				if lenPx > 1 {
					nx := -dy / lenPx * 6.0
					ny := dx / lenPx * 6.0
					canvas.DrawLinePixels(pen, walk.Point{X: s1.X + int(nx), Y: s1.Y + int(ny)}, walk.Point{X: s1.X - int(nx), Y: s1.Y - int(ny)})
					canvas.DrawLinePixels(pen, walk.Point{X: s2.X + int(nx), Y: s2.Y + int(ny)}, walk.Point{X: s2.X - int(nx), Y: s2.Y - int(ny)})
				}

				midX := (s1.X + s2.X) / 2
				midY := (s1.Y + s2.Y) / 2
				badgeW := 165
				badgeH := 32
				bRect := walk.Rectangle{X: midX - badgeW/2, Y: midY - badgeH - 6, Width: badgeW, Height: badgeH}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s: %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 4, Y: bRect.Y + 2, Width: badgeW - 8, Height: 14}, walk.TextCenter)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 4, Y: bRect.Y + 16, Width: badgeW - 8, Height: 14}, walk.TextCenter)
			}

		case "Rechteck-ROI":
			if len(m.Points) >= 2 {
				s1 := ImgToScreen(m.Points[0], dest, w, h)
				s2 := ImgToScreen(m.Points[1], dest, w, h)

				minX := int(math.Min(float64(s1.X), float64(s2.X)))
				maxX := int(math.Max(float64(s1.X), float64(s2.X)))
				minY := int(math.Min(float64(s1.Y), float64(s2.Y)))
				maxY := int(math.Max(float64(s1.Y), float64(s2.Y)))

				roiBox := walk.Rectangle{X: minX, Y: minY, Width: maxX - minX, Height: maxY - minY}
				canvas.DrawRectanglePixels(pen, roiBox)

				midlineScreen := dest.X + dest.Width/2
				contraMinX := midlineScreen*2 - maxX
				contraMaxX := midlineScreen*2 - minX
				contraBox := walk.Rectangle{X: contraMinX, Y: minY, Width: contraMaxX - contraMinX, Height: maxY - minY}
				canvas.DrawRectanglePixels(measureGreenDash, contraBox)

				badgeW := 185
				badgeH := 36
				bRect := walk.Rectangle{X: minX, Y: minY - badgeH - 4, Width: badgeW, Height: badgeH}
				if bRect.Y < bounds.Y {
					bRect.Y = maxY + 4
				}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s · %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 2, Width: badgeW - 12, Height: 15}, walk.TextLeft)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 18, Width: badgeW - 12, Height: 15}, walk.TextLeft)
			}

		case "Polygon-ROI":
			if len(m.Points) >= 3 {
				n := len(m.Points)
				midlineScreen := dest.X + dest.Width/2
				var sumX, sumY int
				for i := 0; i < n; i++ {
					j := (i + 1) % n
					s1 := ImgToScreen(m.Points[i], dest, w, h)
					s2 := ImgToScreen(m.Points[j], dest, w, h)
					canvas.DrawLinePixels(pen, s1, s2)
					canvas.DrawEllipsePixels(pen, walk.Rectangle{X: s1.X - 3, Y: s1.Y - 3, Width: 6, Height: 6})

					// Kontralateral gespiegeltes Polygon
					c1 := walk.Point{X: midlineScreen*2 - s1.X, Y: s1.Y}
					c2 := walk.Point{X: midlineScreen*2 - s2.X, Y: s2.Y}
					canvas.DrawLinePixels(measureGreenDash, c1, c2)
					sumX += s1.X
					sumY += s1.Y
				}
				cx, cy := sumX/n, sumY/n
				badgeW, badgeH := 195, 36
				bRect := walk.Rectangle{X: cx - badgeW/2, Y: cy - badgeH - 8, Width: badgeW, Height: badgeH}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("⬡ %s · %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 2, Width: badgeW - 12, Height: 15}, walk.TextLeft)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 18, Width: badgeW - 12, Height: 15}, walk.TextLeft)
			}

		case "Kreis-ROI":
			if len(m.Points) >= 2 {
				sc := ImgToScreen(m.Points[0], dest, w, h)
				sp := ImgToScreen(m.Points[1], dest, w, h)
				dx := sp.X - sc.X
				dy := sp.Y - sc.Y
				radPx := int(math.Sqrt(float64(dx*dx + dy*dy)))
				if radPx < 2 {
					radPx = 2
				}

				canvas.DrawEllipsePixels(pen, walk.Rectangle{X: sc.X - radPx, Y: sc.Y - radPx, Width: 2 * radPx, Height: 2 * radPx})
				coreRad := int(float64(radPx) * 0.5)
				canvas.DrawEllipsePixels(hairlinePen, walk.Rectangle{X: sc.X - coreRad, Y: sc.Y - coreRad, Width: 2 * coreRad, Height: 2 * coreRad})
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X - 4, Y: sc.Y}, walk.Point{X: sc.X + 4, Y: sc.Y})
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X, Y: sc.Y - 4}, walk.Point{X: sc.X, Y: sc.Y + 4})

				badgeW := 170
				badgeH := 36
				bRect := walk.Rectangle{X: sc.X + radPx + 4, Y: sc.Y - 18, Width: badgeW, Height: badgeH}
				if bRect.X+badgeW > bounds.X+bounds.Width {
					bRect.X = sc.X - radPx - 4 - badgeW
				}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s: %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 2, Width: badgeW - 12, Height: 15}, walk.TextLeft)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 18, Width: badgeW - 12, Height: 15}, walk.TextLeft)
			}

		case "Goniometer":
			if len(m.Points) >= 3 {
				s1 := ImgToScreen(m.Points[0], dest, w, h)
				sv := ImgToScreen(m.Points[1], dest, w, h)
				s3 := ImgToScreen(m.Points[2], dest, w, h)

				canvas.DrawLinePixels(pen, s1, sv)
				canvas.DrawLinePixels(pen, sv, s3)
				canvas.DrawEllipsePixels(pen, walk.Rectangle{X: sv.X - 14, Y: sv.Y - 14, Width: 28, Height: 28})

				badgeW := 160
				badgeH := 34
				bRect := walk.Rectangle{X: sv.X + 16, Y: sv.Y - 17, Width: badgeW, Height: badgeH}
				if bRect.X+badgeW > bounds.X+bounds.Width {
					bRect.X = sv.X - 16 - badgeW
				}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s: %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 2, Width: badgeW - 12, Height: 14}, walk.TextLeft)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 16, Width: badgeW - 12, Height: 14}, walk.TextLeft)
			}

		case "Spot":
			if len(m.Points) >= 1 {
				sc := ImgToScreen(m.Points[0], dest, w, h)
				canvas.DrawEllipsePixels(pen, walk.Rectangle{X: sc.X - 8, Y: sc.Y - 8, Width: 16, Height: 16})
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X - 12, Y: sc.Y}, walk.Point{X: sc.X + 12, Y: sc.Y})
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X, Y: sc.Y - 12}, walk.Point{X: sc.X, Y: sc.Y + 12})

				badgeW := 130
				badgeH := 24
				bRect := walk.Rectangle{X: sc.X + 12, Y: sc.Y - 12, Width: badgeW, Height: badgeH}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s · %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 4, Y: bRect.Y + 4, Width: badgeW - 8, Height: 16}, walk.TextCenter)
			}

		case "Kreuz-Profil":
			if len(m.Points) >= 1 {
				sc := ImgToScreen(m.Points[0], dest, w, h)
				radPx := 40
				if len(m.Points) >= 2 {
					sr := ImgToScreen(m.Points[1], dest, w, h)
					radPx = int(math.Abs(float64(sr.X - sc.X)))
					if radPx < 15 {
						radPx = 15
					}
				}
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X - radPx, Y: sc.Y}, walk.Point{X: sc.X + radPx, Y: sc.Y})
				canvas.DrawLinePixels(pen, walk.Point{X: sc.X, Y: sc.Y - radPx}, walk.Point{X: sc.X, Y: sc.Y + radPx})
				canvas.DrawEllipsePixels(measureGreenDash, walk.Rectangle{X: sc.X - radPx/2, Y: sc.Y - radPx/2, Width: radPx, Height: radPx})

				badgeW := 195
				badgeH := 36
				bRect := walk.Rectangle{X: sc.X + 12, Y: sc.Y - 18, Width: badgeW, Height: badgeH}
				drawFluentRoundRect(canvas, bRect, br, pen, 6)
				canvas.DrawTextPixels(fmt.Sprintf("%s · %s", m.Label, m.ValueStr), hudBoldFont, textCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 2, Width: badgeW - 12, Height: 15}, walk.TextLeft)
				canvas.DrawTextPixels(m.DetailsStr, hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 18, Width: badgeW - 12, Height: 15}, walk.TextLeft)
			}
		}
	}
}

func drawActiveDrawing(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if !GState.IsDrawing || len(GState.ActivePoints) == 0 || dest.Width <= 0 || dest.Height <= 0 {
		return
	}

	w, h := GState.Width, GState.Height
	mousePt := ScreenToImg(GState.HoverX, GState.HoverY, dest, w, h)
	sMouse := ImgToScreen(mousePt, dest, w, h)

	switch GState.ActiveTool {
	case ToolRuler, ToolProfileLine:
		s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
		canvas.DrawLinePixels(measureDashPen, s1, sMouse)
		m := ComputeLineMetrics(GState.RawGray, w, h, GState.ActivePoints[0], mousePt)
		badgeText := fmt.Sprintf("%.1f mm (ΔT %.2f K)", m.DistMm, m.DeltaT)
		drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, badgeText, walk.RGB(2, 132, 199))

	case ToolRectROI:
		s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
		minX := int(math.Min(float64(s1.X), float64(sMouse.X)))
		maxX := int(math.Max(float64(s1.X), float64(sMouse.X)))
		minY := int(math.Min(float64(s1.Y), float64(sMouse.Y)))
		maxY := int(math.Max(float64(s1.Y), float64(sMouse.Y)))
		canvas.DrawRectanglePixels(measureDashPen, walk.Rectangle{X: minX, Y: minY, Width: maxX - minX, Height: maxY - minY})

		midlineScreen := dest.X + dest.Width/2
		contraMinX := midlineScreen*2 - maxX
		contraMaxX := midlineScreen*2 - minX
		canvas.DrawRectanglePixels(measureGreenDash, walk.Rectangle{X: contraMinX, Y: minY, Width: contraMaxX - contraMinX, Height: maxY - minY})

		m := ComputeRectROI(GState.RawGray, w, h, image.Rect(GState.ActivePoints[0].X, GState.ActivePoints[0].Y, mousePt.X, mousePt.Y))
		badgeText := fmt.Sprintf("ROI: %.1f cm² · Mean: %.1f°C · ΔT: %.2f K", m.AreaCm2, m.MeanT, m.DeltaT)
		drawMiniBadge(canvas, minX, minY-22, badgeText, walk.RGB(2, 132, 199))

	case ToolPolygonROI:
		n := len(GState.ActivePoints)
		for i := 0; i < n; i++ {
			sCur := ImgToScreen(GState.ActivePoints[i], dest, w, h)
			canvas.DrawEllipsePixels(measurePen, walk.Rectangle{X: sCur.X - 3, Y: sCur.Y - 3, Width: 6, Height: 6})
			if i > 0 {
				sPrev := ImgToScreen(GState.ActivePoints[i-1], dest, w, h)
				canvas.DrawLinePixels(measurePen, sPrev, sCur)
			}
		}
		sLast := ImgToScreen(GState.ActivePoints[n-1], dest, w, h)
		sFirst := ImgToScreen(GState.ActivePoints[0], dest, w, h)
		canvas.DrawLinePixels(measureDashPen, sLast, sMouse)
		if n >= 2 {
			canvas.DrawLinePixels(hairlinePen, sMouse, sFirst)
		}
		drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, fmt.Sprintf("⬡ Polygon (%d Pkt.) · Klick=Eckpunkt, Button/Doppelklick=Schließen", n), walk.RGB(2, 132, 199))

	case ToolCircleROI:
		s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
		dx := sMouse.X - s1.X
		dy := sMouse.Y - s1.Y
		radPx := int(math.Sqrt(float64(dx*dx + dy*dy)))
		canvas.DrawEllipsePixels(measureDashPen, walk.Rectangle{X: s1.X - radPx, Y: s1.Y - radPx, Width: 2 * radPx, Height: 2 * radPx})
		canvas.DrawLinePixels(hairlinePen, s1, sMouse)

		imgRad := int(math.Sqrt(float64((mousePt.X-GState.ActivePoints[0].X)*(mousePt.X-GState.ActivePoints[0].X) + (mousePt.Y-GState.ActivePoints[0].Y)*(mousePt.Y-GState.ActivePoints[0].Y))))
		cm := ComputeCircleROI(GState.RawGray, w, h, GState.ActivePoints[0], imgRad)
		badgeText := fmt.Sprintf("R: %.1f mm · Halo ΔT: %+.2f K", cm.RadiusMm, cm.HaloDeltaT)
		drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, badgeText, walk.RGB(2, 132, 199))

	case ToolGoniometer:
		if len(GState.ActivePoints) == 1 {
			s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
			canvas.DrawLinePixels(measureDashPen, s1, sMouse)
			drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, "Punkt 2 (Scheitelpunkt) setzen", walk.RGB(2, 132, 199))
		} else if len(GState.ActivePoints) == 2 {
			s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
			sv := ImgToScreen(GState.ActivePoints[1], dest, w, h)
			canvas.DrawLinePixels(measurePen, s1, sv)
			canvas.DrawLinePixels(measureDashPen, sv, sMouse)
			gm := ComputeGoniometerAngle(GState.ActivePoints[0], GState.ActivePoints[1], mousePt)
			drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, fmt.Sprintf("Winkel: %.1f° (%s)", gm.AngleDeg, gm.Category), walk.RGB(2, 132, 199))
		}

	case ToolCrosshairSigma:
		s1 := ImgToScreen(GState.ActivePoints[0], dest, w, h)
		dx := sMouse.X - s1.X
		dy := sMouse.Y - s1.Y
		radPx := int(math.Sqrt(float64(dx*dx + dy*dy)))
		if radPx < 20 {
			radPx = 20
		}
		canvas.DrawLinePixels(measureDashPen, walk.Point{X: s1.X - radPx, Y: s1.Y}, walk.Point{X: s1.X + radPx, Y: s1.Y})
		canvas.DrawLinePixels(measureDashPen, walk.Point{X: s1.X, Y: s1.Y - radPx}, walk.Point{X: s1.X, Y: s1.Y + radPx})
		canvas.DrawEllipsePixels(measureGreenDash, walk.Rectangle{X: s1.X - radPx/2, Y: s1.Y - radPx/2, Width: radPx, Height: radPx})
		imgRad := int(float64(radPx) / GState.Zoom)
		cm := ComputeCrosshairMetrics(GState.RawGray, w, h, GState.ActivePoints[0], imgRad, 31)
		drawMiniBadge(canvas, sMouse.X+12, sMouse.Y-12, fmt.Sprintf("➕ Kreuz: R=%.1fmm · σ=±%.2fK · Z=%+.1fσ", cm.RadiusMm, cm.StdDev, cm.ZScore), walk.RGB(2, 132, 199))
	}
}

func drawActiveCrosshair(canvas *walk.Canvas, bounds, dest walk.Rectangle) {
	if dest.Width <= 0 || dest.Height <= 0 || len(GState.RawGray) == 0 {
		return
	}

	var pt image.Point
	radPx := 45
	if GState.HasCrosshairPoint {
		pt = GState.CrosshairPoint
		if GState.CrosshairRadius > 0 {
			radPx = GState.CrosshairRadius
		}
	} else if GState.LastResult != nil && len(GState.LastResult.Hotspots) > 0 {
		hs := GState.LastResult.Hotspots[0]
		pt = image.Pt(hs.Region.CenterX, hs.Region.CenterY)
		radPx = int(math.Max(35.0, math.Sqrt(float64(hs.Region.AreaPixels))*1.4))
	} else {
		return
	}

	sc := ImgToScreen(pt, dest, GState.Width, GState.Height)
	screenRad := int(float64(radPx) * GState.Zoom * float64(dest.Width) / float64(GState.Width))
	if screenRad < 15 {
		screenRad = 15
	}

	cm := ComputeCrosshairMetrics(GState.RawGray, GState.Width, GState.Height, pt, radPx, 41)

	crossPenH, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))
	defer crossPenH.Dispose()
	crossPenV, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(217, 119, 6))
	defer crossPenV.Dispose()

	canvas.DrawLinePixels(crossPenH, walk.Point{X: sc.X - screenRad, Y: sc.Y}, walk.Point{X: sc.X + screenRad, Y: sc.Y})
	canvas.DrawLinePixels(crossPenV, walk.Point{X: sc.X, Y: sc.Y - screenRad}, walk.Point{X: sc.X, Y: sc.Y + screenRad})

	sSigma := int(float64(screenRad) * (cm.SpatialSigma / cm.RadiusMm))
	if sSigma < 6 {
		sSigma = screenRad / 2
	}
	canvas.DrawEllipsePixels(measureGreenDash, walk.Rectangle{X: sc.X - sSigma, Y: sc.Y - sSigma, Width: 2 * sSigma, Height: 2 * sSigma})

	canvas.DrawLinePixels(measureGreenDash, walk.Point{X: sc.X - sSigma, Y: sc.Y - 4}, walk.Point{X: sc.X - sSigma, Y: sc.Y + 4})
	canvas.DrawLinePixels(measureGreenDash, walk.Point{X: sc.X + sSigma, Y: sc.Y - 4}, walk.Point{X: sc.X + sSigma, Y: sc.Y + 4})
	canvas.DrawLinePixels(measureGreenDash, walk.Point{X: sc.X - 4, Y: sc.Y - sSigma}, walk.Point{X: sc.X + 4, Y: sc.Y - sSigma})
	canvas.DrawLinePixels(measureGreenDash, walk.Point{X: sc.X - 4, Y: sc.Y + sSigma}, walk.Point{X: sc.X + 4, Y: sc.Y + sSigma})

	sTwoSigma := int(float64(sSigma) * 2.0)
	if sTwoSigma <= screenRad {
		canvas.DrawLinePixels(reticleRedPen, walk.Point{X: sc.X - sTwoSigma, Y: sc.Y - 3}, walk.Point{X: sc.X - sTwoSigma, Y: sc.Y + 3})
		canvas.DrawLinePixels(reticleRedPen, walk.Point{X: sc.X + sTwoSigma, Y: sc.Y - 3}, walk.Point{X: sc.X + sTwoSigma, Y: sc.Y + 3})
		canvas.DrawLinePixels(reticleRedPen, walk.Point{X: sc.X - 3, Y: sc.Y - sTwoSigma}, walk.Point{X: sc.X + 3, Y: sc.Y - sTwoSigma})
		canvas.DrawLinePixels(reticleRedPen, walk.Point{X: sc.X - 3, Y: sc.Y + sTwoSigma}, walk.Point{X: sc.X + 3, Y: sc.Y + sTwoSigma})
	}

	canvas.DrawEllipsePixels(reticleRedPen, walk.Rectangle{X: sc.X - 3, Y: sc.Y - 3, Width: 6, Height: 6})

	badgeW := 215
	badgeH := 36
	bx := sc.X + 12
	by := sc.Y - screenRad - 30
	if by < bounds.Y+60 {
		by = sc.Y + screenRad + 10
	}
	if bx+badgeW > bounds.X+bounds.Width-20 {
		bx = sc.X - badgeW - 12
	}
	bRect := walk.Rectangle{X: bx, Y: by, Width: badgeW, Height: badgeH}
	drawFluentRoundRect(canvas, bRect, badgeBrush, measurePen, 6)
	badgeCol := walk.RGB(2, 132, 199)
	if cm.Risk == "CRITICAL" {
		badgeCol = walk.RGB(220, 38, 38)
	}
	canvas.DrawTextPixels(fmt.Sprintf("➕ Entzündungs-Kreuz · Peak %.1f°C", cm.PeakT), hudBoldFont, badgeCol, walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 3, Width: badgeW - 12, Height: 14}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("μ=%.1f°C · σ=±%.2fK · Z=%+.1fσ", cm.MeanT, cm.StdDev, cm.ZScore), hudFont, walk.RGB(71, 85, 105), walk.Rectangle{X: bRect.X + 6, Y: bRect.Y + 18, Width: badgeW - 12, Height: 14}, walk.TextLeft)
}
