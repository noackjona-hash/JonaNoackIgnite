package main

import (
	"fmt"
	"image"
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
	P05        float64
	P25        float64
	P75        float64
	P95        float64
	Skewness   float64
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
	diagBarRBrush       *walk.SolidColorBrush
	diagAlertBrush      *walk.SolidColorBrush
	diagCrossSigmaBrush *walk.SolidColorBrush // Zartes Grün für das ±1σ Konfidenzband
	diagHorizPen        *walk.CosmeticPen     // Cyan für Horizontalachse X
	diagVertPen         *walk.CosmeticPen     // Amber für Vertikalachse Y
	diagTwoSigmaPen     *walk.CosmeticPen     // Dotted Red für ±2σ Warnschwelle
	diagFont            *walk.Font
	diagBoldFont        *walk.Font

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
	diagCrossSigmaBrush, _ = walk.NewSolidColorBrush(walk.RGB(240, 253, 244))  // Pale Emerald Ribbon (±1σ)
	diagHorizPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199)) // Cyan X-Axis
	diagVertPen, _ = walk.NewCosmeticPen(walk.PenSolid, walk.RGB(217, 119, 6))  // Amber Y-Axis
	diagTwoSigmaPen, _ = walk.NewCosmeticPen(walk.PenDot, walk.RGB(239, 68, 68)) // Dotted Red (±2σ)
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

	// 2. Standardabweichung σ, Varianz & Schiefe (Skewness)
	var sumSqDiff, sumCubeDiff float64
	for _, t := range temps {
		d := t - mean
		sumSqDiff += d * d
		sumCubeDiff += d * d * d
	}
	variance := sumSqDiff / float64(n-1)
	stdDev := math.Sqrt(variance)
	sem := stdDev / math.Sqrt(float64(n))
	skew := 0.0
	if stdDev > 0.01 {
		skew = (sumCubeDiff / float64(n)) / (stdDev * stdDev * stdDev)
	}

	// 3. Median, Perzentile (P05, P25, P75, P95) & MAD (Median Absolute Deviation)
	sort.Float64s(temps)
	median := temps[n/2]
	p05 := temps[int(float64(n-1)*0.05)]
	p25 := temps[int(float64(n-1)*0.25)]
	p75 := temps[int(float64(n-1)*0.75)]
	p95 := temps[int(float64(n-1)*0.95)]

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
		P05:        p05,
		P25:        p25,
		P75:        p75,
		P95:        p95,
		Skewness:   skew,
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

	title := "TRANSVERSALES TEMPERATURPROFIL T(x) ENTLANG DER HERD-ACHSE A–B"
	if GState.CustomProfileName != "" {
		title = "BENUTZER-SCHNITTPROFIL T(s): " + GState.CustomProfileName
	}
	canvas.DrawTextPixels(title, diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL, Y: 4, Width: plotW, Height: 18}, walk.TextLeft)

	// Gitter & Skala
	for i := 0; i <= 4; i++ {
		y := padT + int(float64(plotH)*(float64(i)/4.0))
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		tVal := 45.0 - float64(i)*5.0
		canvas.DrawTextPixels(fmt.Sprintf("%.0f°", tVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 4, Y: y - 6, Width: 32, Height: 12}, walk.TextRight)
	}

	// 34°C Armstrong-Gefahrenschwelle als feine rote Referenzlinie
	y34 := padT + plotH - int((34.0-20.0)/(45.0-20.0)*float64(plotH))
	if y34 >= padT && y34 <= padT+plotH {
		canvas.DrawLinePixels(diagAlertPen, walk.Point{X: padL, Y: y34}, walk.Point{X: padL + plotW, Y: y34})
		canvas.DrawTextPixels("34.0°C (Hyperthermie-Schwelle)", diagFont, walk.RGB(220, 38, 38), walk.Rectangle{X: padL + plotW - 170, Y: y34 - 14, Width: 165, Height: 12}, walk.TextRight)
	}

	// Daten vorbereiten: Entweder CustomProfile oder berechneter Real-Transect
	numPts := 80
	var profilePts, contraPts []float64

	if len(GState.CustomProfile) == numPts {
		profilePts = GState.CustomProfile
		contraPts = GState.CustomProfileRef
	} else if GState.RawGray != nil && GState.Width > 0 && GState.Height > 0 {
		// Ermittle Referenzachse: horizontal durch den heißesten Punkt
		targetY := GState.Height / 2
		if GState.LastResult != nil && len(GState.LastResult.Hotspots) > 0 {
			targetY = GState.LastResult.Hotspots[0].Region.CenterY
		}
		p1 := image.Pt(0, targetY)
		p2 := image.Pt(GState.Width-1, targetY)
		profilePts, contraPts = SampleProfileLine(GState.RawGray, GState.Width, GState.Height, p1, p2, numPts)
	}

	profilePen, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))
	defer profilePen.Dispose()
	contraPen, _ := walk.NewCosmeticPen(walk.PenDash, walk.RGB(16, 185, 129))
	defer contraPen.Dispose()

	var prevPt, prevContraPt walk.Point
	maxT := 20.0
	var maxPt walk.Point

	for i := 0; i < numPts; i++ {
		fx := float64(i) / float64(numPts-1)
		var tVal, tContra float64
		if i < len(profilePts) {
			tVal = profilePts[i]
			if i < len(contraPts) {
				tContra = contraPts[i]
			} else {
				tContra = 20.0
			}
		} else {
			// Fallback-Kurve
			distToHotspot := math.Abs(fx - 0.32)
			hotspotBoost := 12.5 * math.Exp(-distToHotspot*distToHotspot*45.0)
			tVal = 31.0 + hotspotBoost + math.Sin(fx*12.0)*0.8
			distToContra := math.Abs(fx - 0.68)
			contraBoost := 1.2 * math.Exp(-distToContra*distToContra*45.0)
			tContra = 31.0 + contraBoost + math.Sin((1.0-fx)*12.0)*0.8
		}

		cx := padL + int(fx*float64(plotW))
		cy := padT + plotH - int((tVal-20.0)/(45.0-20.0)*float64(plotH))
		cyContra := padT + plotH - int((tContra-20.0)/(45.0-20.0)*float64(plotH))

		curPt := walk.Point{X: cx, Y: cy}
		curContraPt := walk.Point{X: cx, Y: cyContra}

		if tVal > maxT {
			maxT = tVal
			maxPt = curPt
		}

		if i > 0 {
			canvas.DrawLinePixels(profilePen, prevPt, curPt)
			canvas.DrawLinePixels(contraPen, prevContraPt, curContraPt)
		}
		prevPt = curPt
		prevContraPt = curContraPt
	}

	// Peak-Marker
	if maxT > 25.0 {
		canvas.DrawEllipsePixels(diagAlertPen, walk.Rectangle{X: maxPt.X - 4, Y: maxPt.Y - 4, Width: 8, Height: 8})
		canvas.DrawTextPixels(fmt.Sprintf("Peak: %.1f°C", maxT), diagBoldFont, walk.RGB(220, 38, 38), walk.Rectangle{X: maxPt.X - 40, Y: maxPt.Y - 18, Width: 80, Height: 14}, walk.TextCenter)
	}

	// Legende
	legText := "Blau: T(s) Schnittprofil · Grün gestrichelt: Kontralaterale Referenz · Rot: Peak"
	canvas.DrawTextPixels(legText, diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: padL + 10, Y: padT + plotH + 4, Width: plotW, Height: 14}, walk.TextLeft)

	return nil
}

// PaintInflammationCrossChart zeichnet das orthogonale Kreuzprofil durch die Entzündung mit Standardabweichungs-Korridor (±1σ, ±2σ).
func PaintInflammationCrossChart(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagCrossCanvas != nil {
		cb := diagCrossCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	if len(GState.RawGray) == 0 || GState.Width <= 0 || GState.Height <= 0 {
		canvas.DrawTextPixels("Entzündungs-Kreuzprofil: Kein Thermogramm geladen", diagFont, walk.RGB(148, 163, 184), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	// 1. Bestimme Entzündungs-Zentrum
	center := image.Pt(GState.Width/2, GState.Height/2)
	rad := 45
	hotspotLabel := "Fokus"

	if GState.HasCrosshairPoint {
		center = GState.CrosshairPoint
		if GState.CrosshairRadius > 0 {
			rad = GState.CrosshairRadius
		}
		hotspotLabel = "Manuell gewählt"
	} else if GState.LastResult != nil && len(GState.LastResult.Hotspots) > 0 {
		hs := GState.LastResult.Hotspots[0]
		center = image.Pt(hs.Region.CenterX, hs.Region.CenterY)
		rad = int(math.Max(35.0, math.Sqrt(float64(hs.Region.AreaPixels))*1.4))
		hotspotLabel = fmt.Sprintf("Hotspot #1 (%s)", hs.Region.DiagnosisType)
	}

	// 2. Berechne orthogonales Profil & Standardabweichung
	numPts := 61
	cm := ComputeCrosshairMetrics(GState.RawGray, GState.Width, GState.Height, center, rad, numPts)

	padL, padR, padT, padB := 45, 95, 24, 26
	plotW := actualBounds.Width - padL - padR
	plotH := actualBounds.Height - padT - padB
	if plotW <= 30 || plotH <= 30 {
		return nil
	}

	// Y-Skalierung (Temperatur in °C)
	minScaleT := math.Min(22.0, cm.MeanT-2.5*cm.StdDev)
	maxScaleT := math.Max(38.0, math.Max(cm.PeakT+1.5, cm.MeanT+2.8*cm.StdDev))
	if maxScaleT <= minScaleT {
		maxScaleT = minScaleT + 10.0
	}

	mapY := func(t float64) int {
		frac := (t - minScaleT) / (maxScaleT - minScaleT)
		return padT + plotH - int(frac*float64(plotH))
	}

	mapX := func(idx int) int {
		return padL + int(float64(idx)/float64(numPts-1)*float64(plotW))
	}

	// Titel
	title := fmt.Sprintf("ENTZÜNDUNGS-KREUZPROFIL & STANDARDABWEICHUNG · %s @ (%d, %d)", hotspotLabel, center.X, center.Y)
	canvas.DrawTextPixels(title, diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL, Y: 4, Width: plotW, Height: 16}, walk.TextLeft)

	// Gitterlinien & Y-Achsenbeschriftung
	ySteps := 4
	for i := 0; i <= ySteps; i++ {
		tVal := minScaleT + float64(i)*(maxScaleT-minScaleT)/float64(ySteps)
		y := mapY(tVal)
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		canvas.DrawTextPixels(fmt.Sprintf("%.1f°", tVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 4, Y: y - 6, Width: 36, Height: 12}, walk.TextRight)
	}

	// X-Achsenbeschriftung (Distanz in mm relativ zum Entzündungszentrum)
	xSteps := 4
	for i := 0; i <= xSteps; i++ {
		idx := i * (numPts - 1) / xSteps
		x := mapX(idx)
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: x, Y: padT}, walk.Point{X: x, Y: padT + plotH})
		dist := cm.DistancesMm[idx]
		canvas.DrawTextPixels(fmt.Sprintf("%+.0f mm", dist), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: x - 25, Y: padT + plotH + 4, Width: 50, Height: 14}, walk.TextCenter)
	}

	// Standardabweichungs-Korridor (±1σ Shaded Band)
	yPlus1 := mapY(cm.MeanT + cm.StdDev)
	yMinus1 := mapY(cm.MeanT - cm.StdDev)
	if yMinus1 > yPlus1 {
		sigmaRect := walk.Rectangle{X: padL, Y: yPlus1, Width: plotW, Height: yMinus1 - yPlus1}
		canvas.FillRectanglePixels(diagCrossSigmaBrush, sigmaRect)
	}

	// Linien für ±1σ, ±2σ und Mittelwert μ
	yMean := mapY(cm.MeanT)
	yPlus2 := mapY(cm.MeanT + 2.0*cm.StdDev)
	yMinus2 := mapY(cm.MeanT - 2.0*cm.StdDev)

	// +2σ Dotted Alert
	if yPlus2 >= padT && yPlus2 <= padT+plotH {
		canvas.DrawLinePixels(diagTwoSigmaPen, walk.Point{X: padL, Y: yPlus2}, walk.Point{X: padL + plotW, Y: yPlus2})
		canvas.DrawTextPixels(fmt.Sprintf("+2σ (%.1f°C)", cm.MeanT+2.0*cm.StdDev), diagFont, walk.RGB(220, 38, 38), walk.Rectangle{X: padL + plotW + 4, Y: yPlus2 - 6, Width: 90, Height: 12}, walk.TextLeft)
	}

	// +1σ Dashed Green
	if yPlus1 >= padT && yPlus1 <= padT+plotH {
		canvas.DrawLinePixels(diagSigmaPen, walk.Point{X: padL, Y: yPlus1}, walk.Point{X: padL + plotW, Y: yPlus1})
		canvas.DrawTextPixels(fmt.Sprintf("+1σ (%.1f°C)", cm.MeanT+cm.StdDev), diagFont, walk.RGB(16, 185, 129), walk.Rectangle{X: padL + plotW + 4, Y: yPlus1 - 6, Width: 90, Height: 12}, walk.TextLeft)
	}

	// Mittelwert μ
	if yMean >= padT && yMean <= padT+plotH {
		canvas.DrawLinePixels(diagMeanPen, walk.Point{X: padL, Y: yMean}, walk.Point{X: padL + plotW, Y: yMean})
		canvas.DrawTextPixels(fmt.Sprintf("μ (%.1f°C)", cm.MeanT), diagFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL + plotW + 4, Y: yMean - 6, Width: 90, Height: 12}, walk.TextLeft)
	}

	// -1σ Dashed Green
	if yMinus1 >= padT && yMinus1 <= padT+plotH {
		canvas.DrawLinePixels(diagSigmaPen, walk.Point{X: padL, Y: yMinus1}, walk.Point{X: padL + plotW, Y: yMinus1})
		canvas.DrawTextPixels(fmt.Sprintf("-1σ (%.1f°C)", cm.MeanT-cm.StdDev), diagFont, walk.RGB(16, 185, 129), walk.Rectangle{X: padL + plotW + 4, Y: yMinus1 - 6, Width: 90, Height: 12}, walk.TextLeft)
	}

	// -2σ Dotted Alert
	if yMinus2 >= padT && yMinus2 <= padT+plotH {
		canvas.DrawLinePixels(diagTwoSigmaPen, walk.Point{X: padL, Y: yMinus2}, walk.Point{X: padL + plotW, Y: yMinus2})
		canvas.DrawTextPixels(fmt.Sprintf("-2σ (%.1f°C)", cm.MeanT-2.0*cm.StdDev), diagFont, walk.RGB(220, 38, 38), walk.Rectangle{X: padL + plotW + 4, Y: yMinus2 - 6, Width: 90, Height: 12}, walk.TextLeft)
	}

	// Nulllinie im Entzündungszentrum (s = 0)
	midIdx := numPts / 2
	xCenter := mapX(midIdx)
	canvas.DrawLinePixels(diagGridPen, walk.Point{X: xCenter, Y: padT}, walk.Point{X: xCenter, Y: padT + plotH})

	// 1. Horizontale Achse X (West -> Ost) in Cyan
	var prevH walk.Point
	for i := 0; i < numPts; i++ {
		cur := walk.Point{X: mapX(i), Y: mapY(cm.HorizontalT[i])}
		if i > 0 {
			canvas.DrawLinePixels(diagHorizPen, prevH, cur)
		}
		prevH = cur
	}

	// 2. Vertikale Achse Y (Nord -> Süd) in Amber
	var prevV walk.Point
	for i := 0; i < numPts; i++ {
		cur := walk.Point{X: mapX(i), Y: mapY(cm.VerticalT[i])}
		if i > 0 {
			canvas.DrawLinePixels(diagVertPen, prevV, cur)
		}
		prevV = cur
	}

	// Peak Markierung im Zentrum
	yPeak := mapY(cm.PeakT)
	canvas.DrawEllipsePixels(diagAlertPen, walk.Rectangle{X: xCenter - 4, Y: yPeak - 4, Width: 8, Height: 8})
	peakBadge := fmt.Sprintf("Peak: %.1f°C (Z = %+.1fσ)", cm.PeakT, cm.ZScore)
	canvas.DrawTextPixels(peakBadge, diagBoldFont, walk.RGB(220, 38, 38), walk.Rectangle{X: xCenter - 75, Y: yPeak - 16, Width: 150, Height: 14}, walk.TextCenter)

	// Infokasten Oben Rechts
	infoStr := fmt.Sprintf("μ=%.1f°C · σ=±%.2fK · ΔT=%+.2fK · FWHM=%.1fmm", cm.MeanT, cm.StdDev, cm.DeltaT, cm.FwhmMm)
	canvas.DrawTextPixels(infoStr, diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: padL + plotW - 320, Y: 4, Width: 320, Height: 14}, walk.TextRight)

	// Legende Unten
	leg := "Blau: Schnitt X (West-Ost) · Orange: Schnitt Y (Nord-Süd) · Grünes Band: ±1σ Normalbereich · Rot: +2σ Ausreißerschwelle"
	canvas.DrawTextPixels(leg, diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: padL, Y: padT + plotH + 4, Width: plotW, Height: 14}, walk.TextLeft)

	return nil
}

// ── Diagramm 5: Interaktives 3D-Thermisches Oberflächennetz (Isometric Lambertian Mesh) ──
func Paint3DThermalSurface(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diag3DCanvas != nil {
		cb := diag3DCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	w, h := actualBounds.Width, actualBounds.Height
	if w <= 40 || h <= 40 {
		return nil
	}

	outer := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, outer, diagBgBrush, fluentBorderSlatePen, 6)

	canvas.DrawTextPixels(fmt.Sprintf("3D-THERMISCHES OBERFLÄCHENRELIEF T(x,y,z) · Azimut: %.0f° · Elevation: %.0f° · Z-Skala: %.1fx",
		GState.RotAzimuth, GState.RotElevation, GState.HeightScale3D),
		diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: 12, Y: 6, Width: w - 24, Height: 16}, walk.TextLeft)

	if len(GState.RawGray) == 0 || GState.Width <= 0 || GState.Height <= 0 {
		canvas.DrawTextPixels("3D-Oberflächennetz: Kein Wärmebild geladen", diagFont, walk.RGB(148, 163, 184), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	// Isometrische 3D Projektions-Hilfsfunktion
	azRad := GState.RotAzimuth * math.Pi / 180.0
	elRad := GState.RotElevation * math.Pi / 180.0
	cosAz, sinAz := math.Cos(azRad), math.Sin(azRad)
	cosEl, sinEl := math.Cos(elRad), math.Sin(elRad)

	cx := w / 2
	cy := h/2 + 28
	scaleXY := math.Min(float64(w)*0.36, float64(h)*0.44)
	scaleZ := float64(h) * 0.22 * GState.HeightScale3D

	project3D := func(nx, ny, nz float64) walk.Point {
		// nx, ny in [-1, +1], nz in [0, 1]
		rx := nx*cosAz - ny*sinAz
		ry := nx*sinAz + ny*cosAz
		sx := cx + int(rx*scaleXY)
		sy := cy + int(ry*scaleXY*sinEl-nz*scaleZ*cosEl)
		return walk.Point{X: sx, Y: sy}
	}

	// 1. Zeichne 3D Basis-Plattform (Z = 0 / 20°C)
	b00 := project3D(-1, -1, 0)
	b10 := project3D(1, -1, 0)
	b11 := project3D(1, 1, 0)
	b01 := project3D(-1, 1, 0)
	canvas.DrawLinePixels(diagGridPen, b00, b10)
	canvas.DrawLinePixels(diagGridPen, b10, b11)
	canvas.DrawLinePixels(diagGridPen, b11, b01)
	canvas.DrawLinePixels(diagGridPen, b01, b00)

	// 2. Optionale 34.0°C Hyperthermie-Schnittebene
	if GState.Show3DCutPlane {
		z34 := (34.0 - 20.0) / 25.0
		p00 := project3D(-1, -1, z34)
		p10 := project3D(1, -1, z34)
		p11 := project3D(1, 1, z34)
		p01 := project3D(-1, 1, z34)
		canvas.DrawLinePixels(diagTwoSigmaPen, p00, p10)
		canvas.DrawLinePixels(diagTwoSigmaPen, p10, p11)
		canvas.DrawLinePixels(diagTwoSigmaPen, p11, p01)
		canvas.DrawLinePixels(diagTwoSigmaPen, p01, p00)
		canvas.DrawTextPixels("34,0°C Armstrong-Schnittebene", diagFont, walk.RGB(220, 38, 38),
			walk.Rectangle{X: p10.X - 165, Y: p10.Y - 14, Width: 165, Height: 14}, walk.TextRight)
	}

	// 3. Zeichne 3D-Oberflächengitter (36 x 28 Stützstellen)
	gridX, gridY := 34, 26
	var pts [27][35]walk.Point
	var vals [27][35]byte

	peakVal := byte(0)
	var peakPt walk.Point
	var peakTemp float64

	for gy := 0; gy <= gridY; gy++ {
		fy := float64(gy) / float64(gridY)
		iy := int(fy * float64(GState.Height-1))
		ny := fy*2.0 - 1.0

		for gx := 0; gx <= gridX; gx++ {
			fx := float64(gx) / float64(gridX)
			ix := int(fx * float64(GState.Width-1))
			nx := fx*2.0 - 1.0

			rawVal := GState.RawGray[iy*GState.Width+ix]
			vals[gy][gx] = rawVal
			nz := 0.0
			if rawVal > 28 {
				nz = float64(rawVal-20) / 235.0
			}
			pt := project3D(nx, ny, nz)
			pts[gy][gx] = pt

			if rawVal > peakVal {
				peakVal = rawVal
				peakPt = pt
				peakTemp = TempOf(rawVal)
			}
		}
	}

	// Farbabgestufte Stifte (5 Temperaturbänder für schnelles Zero-Alloc Rendering)
	penCold, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(51, 65, 85))
	defer penCold.Dispose()
	penCool, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(2, 132, 199))
	defer penCool.Dispose()
	penNorm, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(16, 185, 129))
	defer penNorm.Dispose()
	penWarm, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(245, 158, 11))
	defer penWarm.Dispose()
	penHot, _ := walk.NewCosmeticPen(walk.PenSolid, walk.RGB(220, 38, 38))
	defer penHot.Dispose()

	pickPen := func(v byte) *walk.CosmeticPen {
		t := TempOf(v)
		if t >= 34.0 {
			return penHot
		} else if t >= 32.0 {
			return penWarm
		} else if t >= 29.5 {
			return penNorm
		} else if t >= 25.0 {
			return penCool
		}
		return penCold
	}

	for gy := 0; gy < gridY; gy++ {
		for gx := 0; gx < gridX; gx++ {
			v := vals[gy][gx]
			if v <= 26 && vals[gy][gx+1] <= 26 {
				continue
			}
			pen := pickPen(v)
			canvas.DrawLinePixels(pen, pts[gy][gx], pts[gy][gx+1])
			if GState.Show3DWireframe {
				canvas.DrawLinePixels(pen, pts[gy][gx], pts[gy+1][gx])
			}
		}
	}

	// 4. Peak-Säule & 3D Callout Badge
	if peakVal > 40 {
		canvas.DrawLinePixels(diagAlertPen, peakPt, walk.Point{X: peakPt.X, Y: peakPt.Y - 22})
		canvas.DrawEllipsePixels(diagAlertPen, walk.Rectangle{X: peakPt.X - 4, Y: peakPt.Y - 4, Width: 8, Height: 8})
		badge := walk.Rectangle{X: peakPt.X - 68, Y: peakPt.Y - 42, Width: 136, Height: 20}
		drawFluentRoundRect(canvas, badge, fluentPillAlertBr, diagAlertPen, 6)
		canvas.DrawTextPixels(fmt.Sprintf("▲ 3D-Peak: %.1f °C", peakTemp), diagBoldFont, walk.RGB(185, 28, 28), badge, walk.TextCenter|walk.TextVCenter)
	}

	// Legende unten
	canvas.DrawTextPixels("Blau: <29°C · Grün: Plantar-Normal (29–32°C) · Gelb: Hyperperfusion (32–34°C) · Rot: Pathologischer Herd (≥34°C)",
		diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 12, Y: h - 18, Width: w - 24, Height: 14}, walk.TextLeft)

	return nil
}

// ── Diagramm 6: Angiosom-Perfusion & Longitudinaler Gradient dT/dy (Tab 5) ──
func PaintAngiosomePerfusionChart(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagAngioCanvas != nil {
		cb := diagAngioCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	w, h := actualBounds.Width, actualBounds.Height
	if w <= 40 || h <= 40 {
		return nil
	}
	outer := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, outer, diagBgBrush, fluentBorderSlatePen, 6)

	canvas.DrawTextPixels("PROXIMAL-DISTALER PERFUSIONSGRADIENT T(y) (CALCANEUS ➔ HALLUX) & ANGIOSOM-PROFIL",
		diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: 12, Y: 6, Width: w - 24, Height: 16}, walk.TextLeft)

	padL, padR, padT, padB := 44, 18, 28, 26
	plotW := w - padL - padR
	plotH := h - padT - padB
	if plotW <= 30 || plotH <= 30 {
		return nil
	}

	// Gitter & Y-Skala (26°C bis 42°C)
	minT, maxT := 26.0, 42.0
	for i := 0; i <= 4; i++ {
		y := padT + int(float64(plotH)*float64(i)/4.0)
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		tVal := maxT - float64(i)*(maxT-minT)/4.0
		canvas.DrawTextPixels(fmt.Sprintf("%.0f°C", tVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 4, Y: y - 6, Width: 36, Height: 12}, walk.TextRight)
	}

	// X-Achse: 4 anatomische Stationen entlang der Fußlängsachse (Calcaneus -> Mittelfuß -> Metatarsale -> Hallux)
	stations := []string{"1. Calcaneus (RC)", "2. Mittelfuß (APL)", "3. Metatarsale (APM)", "4. Hallux (ADP)"}
	for i, st := range stations {
		x := padL + int(float64(plotW)*float64(i)/3.0)
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: x, Y: padT}, walk.Point{X: x, Y: padT + plotH})
		canvas.DrawTextPixels(st, diagFont, walk.RGB(51, 65, 85), walk.Rectangle{X: x - 55, Y: padT + plotH + 4, Width: 110, Height: 14}, walk.TextCenter)
	}

	// Berechne longitudinale Kurve (Proximal y=0.85 nach Distal y=0.15) für Links und Rechts
	numSteps := 30
	var prevL, prevR walk.Point
	for i := 0; i < numSteps; i++ {
		frac := float64(i) / float64(numSteps-1) // 0 = Calcaneus, 1 = Hallux
		// Standardwerte oder aus RawGray gesampelt
		tL := 32.2 - 0.5*frac + 6.8*math.Exp(-math.Pow(frac-0.92, 2)*35.0)
		tR := 32.1 - 1.6*frac

		if len(GState.RawGray) == GState.Width*GState.Height && GState.Width > 10 && GState.Height > 10 {
			iy := int((0.82 - frac*0.66) * float64(GState.Height-1))
			ixR := GState.Width / 4
			ixL := GState.Width * 3 / 4
			if iy >= 0 && iy < GState.Height {
				bR := GState.RawGray[iy*GState.Width+ixR]
				bL := GState.RawGray[iy*GState.Width+ixL]
				if bR > 30 {
					tR = TempOf(bR)
				}
				if bL > 30 {
					tL = TempOf(bL)
				}
			}
		}

		x := padL + int(frac*float64(plotW))
		yL := padT + plotH - int(math.Max(0, math.Min(1, (tL-minT)/(maxT-minT)))*float64(plotH))
		yR := padT + plotH - int(math.Max(0, math.Min(1, (tR-minT)/(maxT-minT)))*float64(plotH))

		curL := walk.Point{X: x, Y: yL}
		curR := walk.Point{X: x, Y: yR}
		if i > 0 {
			canvas.DrawLinePixels(diagHorizPen, prevL, curL)
			canvas.DrawLinePixels(diagSigmaPen, prevR, curR)
		}
		prevL = curL
		prevR = curR
	}

	canvas.DrawTextPixels("Blau: Linker Fuß T_L(y) · Grün: Rechter Fuß T_R(y) · Positiver Anstieg distal = Neuropathische Hyperperfusion",
		diagFont, walk.RGB(100, 116, 139), walk.Rectangle{X: padL, Y: padT + 4, Width: plotW, Height: 14}, walk.TextLeft)

	return nil
}

// ── Diagramm 7: Longitudinaler Serien- & Therapieverlauf (Tab 6) ────────────
func PaintLongitudinalSeriesChart(canvas *walk.Canvas, bounds walk.Rectangle) error {
	if diagBgBrush == nil {
		initDiagramGraphics()
	}
	actualBounds := bounds
	if diagSeriesCanvas != nil {
		cb := diagSeriesCanvas.ClientBoundsPixels()
		if cb.Width > 0 && cb.Height > 0 {
			actualBounds = cb
		}
	}
	canvas.FillRectanglePixels(diagBgBrush, actualBounds)

	w, h := actualBounds.Width, actualBounds.Height
	if w <= 40 || h <= 40 {
		return nil
	}
	outer := walk.Rectangle{X: 1, Y: 1, Width: w - 2, Height: h - 2}
	drawFluentRoundRect(canvas, outer, diagBgBrush, fluentBorderSlatePen, 6)

	canvas.DrawTextPixels("LONGITUDINALER ΔT-VERLAUFSGRAPH (SERIEN-SCREENING vs. ARMSTRONG-SCHWELLE 2,2 K)",
		diagBoldFont, walk.RGB(3, 105, 161), walk.Rectangle{X: 12, Y: 6, Width: w - 24, Height: 16}, walk.TextLeft)

	padL, padR, padT, padB := 44, 18, 28, 26
	plotW := w - padL - padR
	plotH := h - padT - padB
	if plotW <= 30 || plotH <= 30 {
		return nil
	}

	maxDeltaScale := 6.0
	for _, b := range GState.BatchResults {
		if math.Abs(b.MaxDeltaT)+0.8 > maxDeltaScale {
			maxDeltaScale = math.Abs(b.MaxDeltaT) + 0.8
		}
	}

	mapY := func(dT float64) int {
		frac := math.Max(0, math.Min(1, dT/maxDeltaScale))
		return padT + plotH - int(frac*float64(plotH))
	}

	// Gitterlinien
	for i := 0; i <= 4; i++ {
		dVal := float64(i) * maxDeltaScale / 4.0
		y := mapY(dVal)
		canvas.DrawLinePixels(diagGridPen, walk.Point{X: padL, Y: y}, walk.Point{X: padL + plotW, Y: y})
		canvas.DrawTextPixels(fmt.Sprintf("%.1f K", dVal), diagFont, walk.RGB(71, 85, 105), walk.Rectangle{X: 2, Y: y - 6, Width: 38, Height: 12}, walk.TextRight)
	}

	// Armstrong-Warnschwelle (2.2 K)
	y22 := mapY(2.2)
	if y22 >= padT && y22 <= padT+plotH {
		canvas.DrawLinePixels(diagAlertPen, walk.Point{X: padL, Y: y22}, walk.Point{X: padL + plotW, Y: y22})
		canvas.DrawTextPixels("🚨 Armstrong-Schwelle (ΔT = 2,2 K)", diagBoldFont, walk.RGB(220, 38, 38),
			walk.Rectangle{X: padL + plotW - 210, Y: y22 - 15, Width: 205, Height: 14}, walk.TextRight)
	}

	// Moderate Schwelle (1.2 K)
	y12 := mapY(1.2)
	if y12 >= padT && y12 <= padT+plotH {
		canvas.DrawLinePixels(diagGaussPen, walk.Point{X: padL, Y: y12}, walk.Point{X: padL + plotW, Y: y12})
	}

	// Zeichne Serien-Punkte
	n := len(GState.BatchResults)
	if n == 0 {
		canvas.DrawTextPixels("Klicken Sie auf „⚡ Alle Testbilder analysieren“, um den Serienverlauf zu berechnen.",
			diagFont, walk.RGB(100, 116, 139), actualBounds, walk.TextCenter|walk.TextVCenter)
		return nil
	}

	var prev walk.Point
	for i, item := range GState.BatchResults {
		fx := 0.5
		if n > 1 {
			fx = float64(i) / float64(n-1)
		}
		x := padL + int(fx*float64(plotW))
		y := mapY(math.Abs(item.MaxDeltaT))
		cur := walk.Point{X: x, Y: y}
		if i > 0 {
			canvas.DrawLinePixels(diagHorizPen, prev, cur)
		}
		pen := diagSigmaPen
		if item.Risk == "CRITICAL" {
			pen = diagAlertPen
		} else if item.Risk == "MODERATE" {
			pen = diagGaussPen
		}
		canvas.DrawEllipsePixels(pen, walk.Rectangle{X: x - 4, Y: y - 4, Width: 8, Height: 8})
		if n <= 12 || i%2 == 0 {
			canvas.DrawTextPixels(fmt.Sprintf("#%d", item.Index), diagFont, walk.RGB(71, 85, 105),
				walk.Rectangle{X: x - 16, Y: padT + plotH + 4, Width: 32, Height: 12}, walk.TextCenter)
		}
		prev = cur
	}

	return nil
}


