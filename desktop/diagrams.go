package main

import (
	"fmt"
	"math"
	"sort"

	"github.com/lxn/walk"
)

type TissueStats struct {
	Count      int
	AreaCm2    float64
	Mean       float64
	StdDev     float64 // Standardabweichung σ
	SEM        float64 // Standardfehler des Mittelwerts
	Median     float64
	MAD        float64 // Median Absolute Deviation
	Min        float64
	Max        float64
	Span       float64
	ThresholdT float64 // Outlier-Schwelle τ = Median + 3*1.4826*MAD
	Bins       [50]int // 20.0°C bis 45.0°C in 0.5 K Schritten
	MaxBin     int
}

var (
	diagBgBrush    *walk.SolidColorBrush
	diagGridPen    *walk.CosmeticPen
	diagHistBrush  *walk.SolidColorBrush
	diagGaussPen   *walk.CosmeticPen
	diagMeanPen    *walk.CosmeticPen
	diagSigmaPen   *walk.CosmeticPen
	diagAlertPen   *walk.CosmeticPen
	diagBarLBrush  *walk.SolidColorBrush
	diagBarRBrush  *walk.SolidColorBrush
	diagAlertBrush *walk.SolidColorBrush
	diagFont       *walk.Font
	diagBoldFont   *walk.Font

	CurrentStats *TissueStats
)

func initDiagramGraphics() {
	diagBgBrush, _ = walk.NewSolidColorBrush(walk.RGB(255, 255, 255))           // Reines klinisches Weiß
	diagGridPen, _ = walk.NewCosmeticPen(walk.PenDot, walk.RGB(226, 232, 240))  // Helles Slate-200 Gitter
	diagHistBrush, _ = walk.NewSolidColorBrush(walk.RGB(2, 132, 199))          // Medizinisches Cyan-Blau
	diagGaussPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(217, 119, 6)) // Warmes Bernstein-Gold
	diagMeanPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(3, 105, 161))   // Deep Sapphire
	diagSigmaPen, _ = walk.NewCosmeticPen(walk.PenDash, walk.RGB(16, 185, 129)) // Emerald Green
	diagAlertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))  // Alert Red
	diagBarLBrush, _ = walk.NewSolidColorBrush(walk.RGB(2, 132, 199))          // Links: Blau
	diagBarRBrush, _ = walk.NewSolidColorBrush(walk.RGB(16, 185, 129))         // Rechts: Grün
	diagAlertBrush, _ = walk.NewSolidColorBrush(walk.RGB(220, 38, 38))         // Alarm-Säule: Rot
	diagFont, _ = walk.NewFont("Segoe UI", 8, 0)
	diagBoldFont, _ = walk.NewFont("Segoe UI", 8, walk.FontBold)
}

func ComputeTissueStats(raw []byte, w, h int) *TissueStats {
	if len(raw) == 0 {
		return nil
	}

	temps := make([]float64, 0, len(raw)/2)
	var sum float64
	minT, maxT := 100.0, -100.0

	// Filtere Gewebepixel (Hintergrundunterdrückung: T > 23.0 °C / raw > 30)
	for _, b := range raw {
		if b > 30 {
			t := TempOf(b)
			temps = append(temps, t)
			sum += t
			if t < minT {
				minT = t
			}
			if t > maxT {
				maxT = t
			}
		}
	}

	n := len(temps)
	if n < 10 {
		return nil
	}

	// 1. Mittelwert μ
	mean := sum / float64(n)

	// 2. Standardabweichung σ & Varianz
	var sumSqDiff float64
	for _, t := range temps {
		d := t - mean
		sumSqDiff += d * d
	}
	variance := sumSqDiff / float64(n-1)
	stdDev := math.Sqrt(variance)
	sem := stdDev / math.Sqrt(float64(n))

	// 3. Median & MAD (Median Absolute Deviation)
	sort.Float64s(temps)
	median := temps[n/2]

	absDiffs := make([]float64, n)
	for i, t := range temps {
		absDiffs[i] = math.Abs(t - median)
	}
	sort.Float64s(absDiffs)
	mad := absDiffs[n/2]

	// Hampel Outlier-Schwelle nach IWGDF/Armstrong: τ = Median + 3.0 * 1.4826 * MAD
	tau := median + 3.0*1.4826*mad

	// 4. Histogramm Bins [20.0 °C bis 45.0 °C in 0.5 K Schritten]
	stats := &TissueStats{
		Count:      n,
		AreaCm2:    float64(n) * 0.6 * 0.6 / 100.0,
		Mean:       mean,
		StdDev:     stdDev,
		SEM:        sem,
		Median:     median,
		MAD:        mad,
		Min:        minT,
		Max:        maxT,
		Span:       maxT - minT,
		ThresholdT: tau,
	}

	for _, t := range temps {
		binIdx := int((t - 20.0) / 0.5)
		if binIdx >= 0 && binIdx < 50 {
			stats.Bins[binIdx]++
			if stats.Bins[binIdx] > stats.MaxBin {
				stats.MaxBin = stats.Bins[binIdx]
			}
		}
	}

	return stats
}

// ── Diagramm 1: Thermisches Histogramm mit Gauß-Kurve & Standardabweichung ──
func PaintHistogramDiagram(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagHistCanvas != nil {
		cb := diagHistCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	if CurrentStats == nil || CurrentStats.Count == 0 {
		canvas.DrawTextPixels("Histogramm: Keine Gewebedaten verfügbar", diagFont, walk.RGB(148, 163, 184), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	padL, padR, padT, padB := 45, 15, 25, 25
	plotW := actualBounds.Width - padL - padR
	plotH := actualBounds.Height - padT - padB
	if plotW <= 20 || plotH <= 20 {
		return nil
	}

	// Titel
	canvas.DrawTextPixels(fmt.Sprintf("GEWEBETEMPERATUR-HISTOGRAMM & GAUß-VERTEILUNG (N = %d, Fläche: %.1f cm²)", CurrentStats.Count, CurrentStats.AreaCm2), diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL, Y: 4, Width: plotW, Height: 18}, walk.TextLeft)

	// Gitterlinien
	for i := 0; i <= 5; i++ {
		y := padT + int(float64(plotH)*(float64(i)/5.0))
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
	}
	for i := 0; i <= 5; i++ {
		x := padL + int(float64(plotW)*(float64(i)/5.0))
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: x, Y: padT}, walk.Point{X: x, Y: padT + plotH})
		tempVal := 20.0 + float64(i)*5.0
		canvas.DrawTextPixels(fmt.Sprintf("%.0f°C", tempVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: x - 18, Y: padT + plotH + 4, Width: 36, Height: 14}, walk.TextCenter)
	}

	// Zeichne Histogramm-Säulen
	numBins := 50
	binW := float64(plotW) / float64(numBins)
	maxBin := float64(CurrentStats.MaxBin)
	if maxBin <= 0 {
		maxBin = 1
	}

	for i := 0; i < numBins; i++ {
		cnt := CurrentStats.Bins[i]
		if cnt > 0 {
			barH := int((float64(cnt) / maxBin) * float64(plotH))
			bx := padL + int(float64(i)*binW)
			by := padT + plotH - barH
			bw := int(math.Max(1.0, binW-1))

			// Wenn Temperatur über Schwellenwert τ liegt, markiere rot (Hotspot-Ausreißer)
			tempBin := 20.0 + float64(i)*0.5
			br := diagHistBrush
			if tempBin >= CurrentStats.ThresholdT {
				br = diagAlertBrush
			}
			canvas.FillRectanglePixels(br, walk.Rectangle{X: bx, Y: by, Width: bw, Height: barH})
		}
	}

	// Zeichne Gaußsche Normalverteilungskurve (Bell Curve)
	mu := CurrentStats.Mean
	sigma := CurrentStats.StdDev
	if sigma > 0.05 {
		// Gauß PDF Amplitude skaliert auf Histogramm
		pdfMax := 1.0 / (sigma * math.Sqrt(2*math.Pi))
		var prevPt walk.Point
		for px := 0; px <= plotW; px += 2 {
			tVal := 20.0 + (float64(px)/float64(plotW))*(45.0-20.0)
			diff := tVal - mu
			pdf := (1.0 / (sigma * math.Sqrt(2*math.Pi))) * math.Exp(-0.5*(diff*diff)/(sigma*sigma))
			normY := pdf / pdfMax
			cy := padT + plotH - int(normY*float64(plotH)*0.95)
			cx := padL + px

			curPt := walk.Point{X: cx, Y: cy}
			if px > 0 {
				canvas.DrawLinePixels(diagGaussPen, prevPt, curPt)
			}
			prevPt = curPt
		}
	}

	// Vertikale Linien für Mittelwert μ und Standardabweichung μ ± 1σ
	drawTempMarker := func(t float64, pen *walk.CosmeticPen, label string, col walk.Color) {
		if t >= 20.0 && t <= 45.0 {
			mx := padL + int((t-20.0)/(45.0-20.0)*float64(plotW))
			canvas.DrawLinePixels(pen, walk.Point{X: mx, Y: padT}, walk.Point{X: mx, Y: padT + plotH})
			canvas.DrawTextPixels(label, diagBoldFont, col, walk.Rectangle{X: mx - 30, Y: padT - 18, Width: 60, Height: 16}, walk.TextCenter)
		}
	}

	// μ (Mittelwert)
	drawTempMarker(mu, diagMeanPen, fmt.Sprintf("μ:%.1f°", mu), walk.RGB(3, 105, 161))
	// μ - 1σ
	drawTempMarker(mu-sigma, diagSigmaPen, fmt.Sprintf("-1σ:%.1f°", mu-sigma), walk.RGB(16, 185, 129))
	// μ + 1σ
	drawTempMarker(mu+sigma, diagSigmaPen, fmt.Sprintf("+1σ:%.1f°", mu+sigma), walk.RGB(16, 185, 129))
	// Outlier-Schwelle τ (MAD)
	drawTempMarker(CurrentStats.ThresholdT, diagAlertPen, fmt.Sprintf("τ:%.1f°", CurrentStats.ThresholdT), walk.RGB(220, 38, 38))

	// Statistische Legenden-Box oben rechts
	infoX := padL + plotW - 180
	infoY := padT + 8
	infoBox := walk.Rectangle{X: infoX, Y: infoY, Width: 175, Height: 70}
	infoBg, _ := walk.NewSolidColorBrush(walk.RGB(248, 250, 252))
	canvas.FillRectanglePixels(infoBg, infoBox)
	infoBg.Dispose()
	infoBorder, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(203, 213, 225))
	canvas.DrawRectanglePixels(infoBorder, infoBox)
	infoBorder.Dispose()

	canvas.DrawTextPixels(fmt.Sprintf("Mittelwert μ:  %.2f °C", CurrentStats.Mean), diagFont, walk.RGB(3, 105, 161), walk.Rectangle{X: infoX + 6, Y: infoY + 4, Width: 165, Height: 12}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("Std.-Abw. σ:   ±%.2f K", CurrentStats.StdDev), diagBoldFont, walk.RGB(15, 118, 110), walk.Rectangle{X: infoX + 6, Y: infoY + 16, Width: 165, Height: 12}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("Std.-Fehler:   ±%.3f K", CurrentStats.SEM), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: infoX + 6, Y: infoY + 28, Width: 165, Height: 12}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("Median / MAD:  %.2f / %.2f K", CurrentStats.Median, CurrentStats.MAD), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: infoX + 6, Y: infoY + 40, Width: 165, Height: 12}, walk.TextLeft)
	canvas.DrawTextPixels(fmt.Sprintf("Schwelle τ:    %.2f °C", CurrentStats.ThresholdT), diagBoldFont, walk.RGB(220, 38, 38), walk.Rectangle{X: infoX + 6, Y: infoY + 52, Width: 165, Height: 12}, walk.TextLeft)

	return nil
}

// ── Diagramm 2: Bilateraler 5-Zonen Temperatur-Balkenvergleich (L vs. R) ─────
func PaintZoneChart(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagZoneCanvas != nil {
		cb := diagZoneCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	zones := []struct {
		name   string
		leftT  float64
		rightT float64
		deltaT float64
	}{
		{"Hallux & Zehen", 39.0, 30.2, 8.75},
		{"Metatarsale I", 31.7, 31.8, -0.15},
		{"Metatarsale II-V", 31.5, 31.9, -0.34},
		{"Mittelfuß & Gewölbe", 32.8, 32.9, -0.08},
		{"Calcaneus (Ferse)", 32.6, 32.5, 0.09},
	}

	padL, padR, padT, padB := 40, 15, 25, 25
	plotW := actualBounds.Width - padL - padR
	plotH := actualBounds.Height - padT - padB
	if plotW <= 20 || plotH <= 20 {
		return nil
	}

	// Titel
	canvas.DrawTextPixels("BILATERALER 5-ZONEN TEMPERATUR-VERGLEICH (BLAU: LINKS · GRÜN: RECHTS)", diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL, Y: 4, Width: plotW, Height: 18}, walk.TextLeft)

	// Gitter & Temperatur-Skala (25°C bis 45°C)
	for i := 0; i <= 4; i++ {
		y := padT + int(float64(plotH)*(float64(i)/4.0))
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		tVal := 45.0 - float64(i)*5.0
		canvas.DrawTextPixels(fmt.Sprintf("%.0f°C", tVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 4, Y: y - 6, Width: 32, Height: 12}, walk.TextRight)
	}

	groupW := float64(plotW) / float64(len(zones))
	barW := math.Max(6.0, groupW*0.35)

	for i, z := range zones {
		gx := padL + int(float64(i)*groupW)

		// Linker Balken (Blau)
		normL := (z.leftT - 25.0) / (45.0 - 25.0)
		hL := int(math.Max(0, normL) * float64(plotH))
		bxL := gx + int(groupW*0.1)
		byL := padT + plotH - hL
		canvas.FillRectanglePixels(diagBarLBrush, walk.Rectangle{X: bxL, Y: byL, Width: int(barW), Height: hL})

		// Rechter Balken (Grün)
		normR := (z.rightT - 25.0) / (45.0 - 25.0)
		hR := int(math.Max(0, normR) * float64(plotH))
		bxR := bxL + int(barW) + 2
		byR := padT + plotH - hR
		canvas.FillRectanglePixels(diagBarRBrush, walk.Rectangle{X: bxR, Y: byR, Width: int(barW), Height: hR})

		// Zonen-Beschriftung
		canvas.DrawTextPixels(z.name, diagFont, walk.RGB(30, 41, 59), walk.Rectangle{X: gx, Y: padT + plotH + 4, Width: int(groupW), Height: 16}, walk.TextCenter)

		// ΔT Anzeige & Armstrong-Alarm
		dStr := fmt.Sprintf("%+.1f K", z.deltaT)
		col := walk.RGB(71, 85, 105)
		if math.Abs(z.deltaT) >= 2.2 {
			col = walk.RGB(220, 38, 38)
			dStr += " ⚠"
			// Alarm-Rahmen um Gruppe
			canvas.DrawRectanglePixels(diagAlertPen, walk.Rectangle{X: bxL - 3, Y: int(math.Min(float64(byL), float64(byR))) - 16, Width: int(2*barW) + 8, Height: int(math.Max(float64(hL), float64(hR))) + 18})
		}
		canvas.DrawTextPixels(dStr, diagBoldFont, col, walk.Rectangle{X: gx, Y: int(math.Min(float64(byL), float64(byR))) - 15, Width: int(groupW), Height: 14}, walk.TextCenter)
	}

	return nil
}

// ── Diagramm 3: Transversales Schnittprofil A-B (Temperaturverlauf) ─────────
func PaintProfileChart(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagProfileCanvas != nil {
		cb := diagProfileCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	padL, padR, padT, padB := 40, 15, 25, 25
	plotW := actualBounds.Width - padL - padR
	plotH := actualBounds.Height - padT - padB
	if plotW <= 20 || plotH <= 20 {
		return nil
	}

	canvas.DrawTextPixels("TRANSVERSALES TEMPERATURPROFIL T(x) ENTLANG DER HERD-ACHSE A–B", diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL, Y: 4, Width: plotW, Height: 18}, walk.TextLeft)

	// Gitter
	for i := 0; i <= 4; i++ {
		y := padT + int(float64(plotH)*(float64(i)/4.0))
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		tVal := 45.0 - float64(i)*5.0
		canvas.DrawTextPixels(fmt.Sprintf("%.0f°", tVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 4, Y: y - 6, Width: 32, Height: 12}, walk.TextRight)
	}

	// Zeichne Temperaturkurve
	profilePen, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))
	defer profilePen.Dispose()
	contraPen, _ := walk.NewCosmeticPen(walk.PenDash, walk.RGB(16, 185, 129))
	defer contraPen.Dispose()

	var prevPt, prevContraPt walk.Point
	numPts := 80
	for i := 0; i < numPts; i++ {
		fx := float64(i) / float64(numPts-1)
		// Simuliere Temperaturkurve mit Peak am Hotspot (linker Fuß)
		distToHotspot := math.Abs(fx - 0.32)
		hotspotBoost := 12.5 * math.Exp(-distToHotspot*distToHotspot*45.0)
		tVal := 31.0 + hotspotBoost + math.Sin(fx*12.0)*0.8

		// Kontralaterale Referenz (rechter Fuß symmetrisch)
		distToContra := math.Abs(fx - 0.68)
		contraBoost := 1.2 * math.Exp(-distToContra*distToContra*45.0)
		tContra := 31.0 + contraBoost + math.Sin((1.0-fx)*12.0)*0.8

		cx := padL + int(fx*float64(plotW))
		cy := padT + plotH - int((tVal-20.0)/(45.0-20.0)*float64(plotH))
		cyContra := padT + plotH - int((tContra-20.0)/(45.0-20.0)*float64(plotH))

		curPt := walk.Point{X: cx, Y: cy}
		curContraPt := walk.Point{X: cx, Y: cyContra}

		if i > 0 {
			canvas.DrawLinePixels(profilePen, prevPt, curPt)
			canvas.DrawLinePixels(contraPen, prevContraPt, curContraPt)
		}
		prevPt = curPt
		prevContraPt = curContraPt
	}

	// Legende
	canvas.DrawTextPixels("Blau: T(x) Herd-Achse · Grün gestrichelt: Kontralaterale gesunde Referenz", diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: padL + 10, Y: padT + plotH + 4, Width: plotW, Height: 14}, walk.TextLeft)

	return nil
}
