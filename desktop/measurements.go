package main

import (
	"fmt"
	"image"
	"math"
)

// RectROIMetrics enthält thermodynamische und bilaterale Kennzahlen einer rechteckigen ROI.
type RectROIMetrics struct {
	MinT        float64
	MaxT        float64
	MeanT       float64
	StdDev      float64
	AreaMm2     float64
	AreaCm2     float64
	PixelCount  int
	ContraMeanT float64
	DeltaT      float64
	Risk        string
}

// CircleROIMetrics enthält Kennzahlen für zirkuläre Herde inklusive Vasodilatations-Halo.
type CircleROIMetrics struct {
	Center     image.Point
	RadiusPx   int
	RadiusMm   float64
	AreaMm2    float64
	AreaCm2    float64
	PixelCount int
	CoreMeanT  float64
	PeriMeanT  float64
	HaloDeltaT float64 // Kern vs. Peripherie (Vasodilatation)
	MaxT       float64
	MinT       float64
	Risk       string
}

// LineMetrics enthält Distanz- und Gradientenkennwerte.
type LineMetrics struct {
	P1       image.Point
	P2       image.Point
	DistMm   float64
	T1       float64
	T2       float64
	DeltaT   float64
	GradKcm  float64
	Risk     string
}

// GoniometerMetrics erfasst orthopädische Gelenk- und Deformitätswinkel.
type GoniometerMetrics struct {
	P1       image.Point
	Vertex   image.Point // Scheitelpunkt B
	P3       image.Point
	AngleDeg float64
	Category string
	Risk     string
}

// PolygonROIMetrics enthält die planimetrische Wundrand- und Flächenanalyse eines Polygons.
type PolygonROIMetrics struct {
	Points      []image.Point
	VertexCount int
	PerimeterMm float64
	AreaMm2     float64
	AreaCm2     float64
	PixelCount  int
	MinT        float64
	MaxT        float64
	MeanT       float64
	StdDev      float64
	ContraMeanT float64
	DeltaT      float64
	Risk        string
}

// CrosshairMetrics enthält Messdaten des orthogonalen Kreuzprofils durch eine Entzündung.
type CrosshairMetrics struct {
	Center       image.Point
	RadiusPx     int
	RadiusMm     float64
	HorizontalT  []float64 // X-Achsen-Temperaturwerte (West -> Ost)
	VerticalT    []float64 // Y-Achsen-Temperaturwerte (Nord -> Süd)
	DistancesMm  []float64 // Relative Distanz -R_mm bis +R_mm
	MeanT        float64   // Gewebemittelwert entlang des Kreuzes / Referenz
	StdDev       float64   // Standardabweichung σ
	PeakT        float64   // Maximale Temperatur im Zentrum / Peak
	DeltaT       float64   // Peak - MeanT
	ZScore       float64   // (PeakT - MeanT) / StdDev (Anzahl Standardabweichungen)
	FwhmMm       float64   // Halbwertsbreite (Full Width at Half Maximum) in mm
	SpatialSigma float64   // Räumliche Standardabweichung der thermischen Streuung in mm
	Risk         string    // NORMAL, MODERATE, CRITICAL
}

// SampleProfileLine sampelt reale Temperaturen entlang einer beliebig orientierten Strecke A->B.
func SampleProfileLine(raw []byte, w, h int, p1, p2 image.Point, numSamples int) (profile, contraProfile []float64) {
	if len(raw) == 0 || w <= 0 || h <= 0 || numSamples <= 1 {
		return nil, nil
	}

	profile = make([]float64, numSamples)
	contraProfile = make([]float64, numSamples)
	midline := w / 2

	for i := 0; i < numSamples; i++ {
		t := float64(i) / float64(numSamples-1)
		x := int(float64(p1.X) + t*float64(p2.X-p1.X) + 0.5)
		y := int(float64(p1.Y) + t*float64(p2.Y-p1.Y) + 0.5)

		if x >= 0 && x < w && y >= 0 && y < h {
			b := raw[y*w+x]
			profile[i] = TempOf(b)

			contraX := midline*2 - x
			if contraX >= 0 && contraX < w {
				cb := raw[y*w+contraX]
				contraProfile[i] = TempOf(cb)
			} else {
				contraProfile[i] = profile[i]
			}
		} else {
			profile[i] = 20.0
			contraProfile[i] = 20.0
		}
	}

	return profile, contraProfile
}

// ComputeLineMetrics berechnet Distanz (0.60 mm/px) und Temperaturgradient K/cm.
func ComputeLineMetrics(raw []byte, w, h int, p1, p2 image.Point) LineMetrics {
	dx := float64(p2.X-p1.X) * 0.60
	dy := float64(p2.Y-p1.Y) * 0.60
	distMm := math.Sqrt(dx*dx + dy*dy)

	var t1, t2 float64 = 20.0, 20.0
	if len(raw) == w*h {
		if p1.X >= 0 && p1.X < w && p1.Y >= 0 && p1.Y < h {
			t1 = TempOf(raw[p1.Y*w+p1.X])
		}
		if p2.X >= 0 && p2.X < w && p2.Y >= 0 && p2.Y < h {
			t2 = TempOf(raw[p2.Y*w+p2.X])
		}
	}

	deltaT := math.Abs(t2 - t1)
	distCm := distMm / 10.0
	gradKcm := 0.0
	if distCm > 0.05 {
		gradKcm = deltaT / distCm
	}

	risk := "NORMAL"
	if deltaT >= 2.2 || gradKcm >= 1.5 {
		risk = "CRITICAL"
	} else if deltaT >= 1.2 || gradKcm >= 0.8 {
		risk = "MODERATE"
	}

	return LineMetrics{
		P1:      p1,
		P2:      p2,
		DistMm:  distMm,
		T1:      t1,
		T2:      t2,
		DeltaT:  deltaT,
		GradKcm: gradKcm,
		Risk:    risk,
	}
}

// ComputeRectROI wertet eine rechteckige ROI sowie deren kontralaterales Spiegelbild aus.
func ComputeRectROI(raw []byte, w, h int, r image.Rectangle) RectROIMetrics {
	norm := r.Canon()
	x1 := int(math.Max(0, float64(norm.Min.X)))
	x2 := int(math.Min(float64(w-1), float64(norm.Max.X)))
	y1 := int(math.Max(0, float64(norm.Min.Y)))
	y2 := int(math.Min(float64(h-1), float64(norm.Max.Y)))

	if x2 <= x1 || y2 <= y1 || len(raw) != w*h {
		return RectROIMetrics{Risk: "NORMAL"}
	}

	var sum, sumSq float64
	minT, maxT := 100.0, -100.0
	count := 0

	midline := w / 2
	var contraSum float64
	contraCount := 0

	for y := y1; y <= y2; y++ {
		rowOff := y * w
		for x := x1; x <= x2; x++ {
			b := raw[rowOff+x]
			t := TempOf(b)
			sum += t
			sumSq += t * t
			if t < minT {
				minT = t
			}
			if t > maxT {
				maxT = t
			}
			count++

			contraX := midline*2 - x
			if contraX >= 0 && contraX < w {
				cb := raw[rowOff+contraX]
				contraSum += TempOf(cb)
				contraCount++
			}
		}
	}

	if count == 0 {
		return RectROIMetrics{Risk: "NORMAL"}
	}

	mean := sum / float64(count)
	variance := (sumSq / float64(count)) - (mean * mean)
	if variance < 0 {
		variance = 0
	}
	stdDev := math.Sqrt(variance)

	contraMean := mean
	if contraCount > 0 {
		contraMean = contraSum / float64(contraCount)
	}
	deltaT := math.Abs(mean - contraMean)

	areaMm2 := float64(count) * (0.60 * 0.60)
	areaCm2 := areaMm2 / 100.0

	risk := "NORMAL"
	if deltaT >= 2.2 || maxT >= 34.0 {
		risk = "CRITICAL"
	} else if deltaT >= 1.2 || maxT >= 32.0 {
		risk = "MODERATE"
	}

	return RectROIMetrics{
		MinT:        minT,
		MaxT:        maxT,
		MeanT:       mean,
		StdDev:      stdDev,
		AreaMm2:     areaMm2,
		AreaCm2:     areaCm2,
		PixelCount:  count,
		ContraMeanT: contraMean,
		DeltaT:      deltaT,
		Risk:        risk,
	}
}

// ComputeCircleROI wertet eine kreisförmige Hotspot-ROI mit Fokus vs. Randhalo aus.
func ComputeCircleROI(raw []byte, w, h int, center image.Point, radiusPx int) CircleROIMetrics {
	if radiusPx < 1 {
		radiusPx = 1
	}
	rSq := radiusPx * radiusPx
	coreRSq := int(float64(rSq) * 0.25) // Kern: innere 25% Fläche

	var sumCore, sumPeri float64
	var countCore, countPeri int
	minT, maxT := 100.0, -100.0
	totalCount := 0

	yMin := int(math.Max(0, float64(center.Y-radiusPx)))
	yMax := int(math.Min(float64(h-1), float64(center.Y+radiusPx)))
	xMin := int(math.Max(0, float64(center.X-radiusPx)))
	xMax := int(math.Min(float64(w-1), float64(center.X+radiusPx)))

	for y := yMin; y <= yMax; y++ {
		dy := y - center.Y
		dySq := dy * dy
		rowOff := y * w
		for x := xMin; x <= xMax; x++ {
			dx := x - center.X
			distSq := dx*dx + dySq
			if distSq <= rSq {
				b := raw[rowOff+x]
				t := TempOf(b)
				if t < minT {
					minT = t
				}
				if t > maxT {
					maxT = t
				}
				totalCount++

				if distSq <= coreRSq {
					sumCore += t
					countCore++
				} else if distSq >= int(float64(rSq)*0.64) { // Peripherie: äußerer Ring ab 80% Radius
					sumPeri += t
					countPeri++
				}
			}
		}
	}

	coreMean := 20.0
	if countCore > 0 {
		coreMean = sumCore / float64(countCore)
	}
	periMean := 20.0
	if countPeri > 0 {
		periMean = sumPeri / float64(countPeri)
	}
	haloDelta := coreMean - periMean

	areaMm2 := float64(totalCount) * (0.60 * 0.60)
	areaCm2 := areaMm2 / 100.0
	radiusMm := float64(radiusPx) * 0.60

	risk := "NORMAL"
	if haloDelta >= 1.5 || maxT >= 34.0 {
		risk = "CRITICAL"
	} else if haloDelta >= 0.8 || maxT >= 32.0 {
		risk = "MODERATE"
	}

	return CircleROIMetrics{
		Center:     center,
		RadiusPx:   radiusPx,
		RadiusMm:   radiusMm,
		AreaMm2:    areaMm2,
		AreaCm2:    areaCm2,
		PixelCount: totalCount,
		CoreMeanT:  coreMean,
		PeriMeanT:  periMean,
		HaloDeltaT: haloDelta,
		MaxT:       maxT,
		MinT:       minT,
		Risk:       risk,
	}
}

// ComputeGoniometerAngle berechnet den Winkel im Scheitelpunkt B (P1 -> Vertex B -> P3).
func ComputeGoniometerAngle(p1, vertex, p3 image.Point) GoniometerMetrics {
	v1x := float64(p1.X - vertex.X)
	v1y := float64(p1.Y - vertex.Y)
	v2x := float64(p3.X - vertex.X)
	v2y := float64(p3.Y - vertex.Y)

	len1 := math.Sqrt(v1x*v1x + v1y*v1y)
	len2 := math.Sqrt(v2x*v2x + v2y*v2y)

	if len1 < 1e-4 || len2 < 1e-4 {
		return GoniometerMetrics{P1: p1, Vertex: vertex, P3: p3, AngleDeg: 0, Category: "Messfehler", Risk: "NORMAL"}
	}

	dot := v1x*v2x + v1y*v2y
	cosTheta := dot / (len1 * len2)
	cosTheta = math.Max(-1.0, math.Min(1.0, cosTheta))
	rad := math.Acos(cosTheta)
	deg := rad * (180.0 / math.Pi)

	cat := "Physiologischer Winkel"
	risk := "NORMAL"
	if deg >= 15.0 && deg < 20.0 {
		cat = "Leichter Hallux Valgus (Grad I)"
		risk = "MODERATE"
	} else if deg >= 20.0 && deg < 40.0 {
		cat = "Mäßiger Hallux Valgus (Grad II)"
		risk = "MODERATE"
	} else if deg >= 40.0 {
		cat = "Schwerer Hallux Valgus (Grad III - Ulkusgefahr)"
		risk = "CRITICAL"
	}

	return GoniometerMetrics{
		P1:       p1,
		Vertex:   vertex,
		P3:       p3,
		AngleDeg: deg,
		Category: cat,
		Risk:     risk,
	}
}

// AddCompletedMeasurement fügt eine fertige Messung zum AppState und TableModel hinzu.
func AddCompletedMeasurement(mType, label, valStr, detStr, risk string, pts []image.Point) *MeasurementItem {
	GState.NextMeasureID++
	item := &MeasurementItem{
		ID:         GState.NextMeasureID,
		Type:       mType,
		Label:      fmt.Sprintf("%s #%d", label, GState.NextMeasureID),
		Points:     pts,
		ValueStr:   valStr,
		DetailsStr: detStr,
		Risk:       risk,
	}
	GState.Measurements = append(GState.Measurements, item)

	if measurementModel != nil {
		measurementModel.SetItems(GState.Measurements)
	}

	RecordAudit("MEASUREMENT_ADD", GState.NextMeasureID, risk, 0.5)
	return item
}

// ComputeCrosshairMetrics berechnet das orthogonale Kreuzprofil und die Standardabweichung durch einen Entzündungsherd.
func ComputeCrosshairMetrics(raw []byte, w, h int, center image.Point, radiusPx int, numSamples int) CrosshairMetrics {
	if radiusPx <= 0 {
		radiusPx = 45
	}
	if numSamples < 21 {
		numSamples = 61
	}
	if numSamples%2 == 0 {
		numSamples++
	}

	radiusMm := float64(radiusPx) * 0.60
	horizT := make([]float64, numSamples)
	vertT := make([]float64, numSamples)
	distMm := make([]float64, numSamples)

	midIdx := numSamples / 2
	var allT []float64
	var sumT float64

	peakT := -100.0
	minT := 100.0

	for i := 0; i < numSamples; i++ {
		// Offset in Pixels relativ zum Zentrum: von -radiusPx bis +radiusPx
		relFrac := float64(i-midIdx) / float64(midIdx)
		offsetPx := int(relFrac * float64(radiusPx))
		distMm[i] = relFrac * radiusMm

		// 1. Horizontaler Punkt (X = Center.X + offsetPx, Y = Center.Y)
		hx := center.X + offsetPx
		hy := center.Y
		ht := 20.0
		if hx >= 0 && hx < w && hy >= 0 && hy < h && len(raw) > 0 {
			b := raw[hy*w+hx]
			if b > 30 {
				ht = TempOf(b)
				allT = append(allT, ht)
				sumT += ht
			}
		}
		horizT[i] = ht
		if ht > peakT {
			peakT = ht
		}
		if ht < minT && ht > 20.0 {
			minT = ht
		}

		// 2. Vertikaler Punkt (X = Center.X, Y = Center.Y + offsetPx)
		vx := center.X
		vy := center.Y + offsetPx
		vt := 20.0
		if vx >= 0 && vx < w && vy >= 0 && vy < h && len(raw) > 0 {
			b := raw[vy*w+vx]
			if b > 30 {
				vt = TempOf(b)
				allT = append(allT, vt)
				sumT += vt
			}
		}
		vertT[i] = vt
		if vt > peakT {
			peakT = vt
		}
		if vt < minT && vt > 20.0 {
			minT = vt
		}
	}

	if peakT < 20.0 {
		peakT = 20.0
	}

	// Berechne Mittelwert μ und Standardabweichung σ
	meanT := 30.5
	stdDev := 0.75
	if len(allT) >= 4 {
		meanT = sumT / float64(len(allT))
		var sumSq float64
		for _, v := range allT {
			d := v - meanT
			sumSq += d * d
		}
		stdDev = math.Sqrt(sumSq / float64(len(allT)-1))
		if stdDev < 0.15 {
			stdDev = 0.50
		}
	}

	deltaT := peakT - meanT
	zScore := 0.0
	if stdDev > 0 {
		zScore = deltaT / stdDev
	}

	// Halbwertsbreite FWHM (Full Width at Half Maximum)
	halfMaxT := meanT + deltaT*0.5
	var leftIdx, rightIdx int = 0, numSamples - 1
	foundL, foundR := false, false
	for i := 0; i <= midIdx; i++ {
		if horizT[i] >= halfMaxT {
			leftIdx = i
			foundL = true
			break
		}
	}
	for i := numSamples - 1; i >= midIdx; i-- {
		if horizT[i] >= halfMaxT {
			rightIdx = i
			foundR = true
			break
		}
	}
	fwhmMm := 0.0
	if foundL && foundR && rightIdx >= leftIdx {
		fwhmMm = float64(rightIdx-leftIdx) / float64(numSamples-1) * (2.0 * radiusMm)
	} else {
		fwhmMm = radiusMm * 0.45
	}
	spatialSigma := fwhmMm / 2.355 // Gaußsche Relation FWHM = 2.355 * σ_spatial

	risk := "NORMAL"
	if deltaT >= 2.2 || zScore >= 3.0 || peakT >= 34.0 {
		risk = "CRITICAL"
	} else if deltaT >= 1.2 || zScore >= 2.0 || peakT >= 32.0 {
		risk = "MODERATE"
	}

	return CrosshairMetrics{
		Center:       center,
		RadiusPx:     radiusPx,
		RadiusMm:     radiusMm,
		HorizontalT:  horizT,
		VerticalT:    vertT,
		DistancesMm:  distMm,
		MeanT:        meanT,
		StdDev:       stdDev,
		PeakT:        peakT,
		DeltaT:       deltaT,
		ZScore:       zScore,
		FwhmMm:       fwhmMm,
		SpatialSigma: spatialSigma,
		Risk:         risk,
	}
}

// pointInPolygon prüft mittels Ray-Casting (Jordan Curve Theorem), ob (px, py) innerhalb des Polygons liegt.
func pointInPolygon(px, py int, pts []image.Point) bool {
	n := len(pts)
	if n < 3 {
		return false
	}
	inside := false
	j := n - 1
	for i := 0; i < n; i++ {
		xi, yi := pts[i].X, pts[i].Y
		xj, yj := pts[j].X, pts[j].Y
		intersect := ((yi > py) != (yj > py)) &&
			(float64(px) < float64(xj-xi)*float64(py-yi)/float64(yj-yi)+float64(xi))
		if intersect {
			inside = !inside
		}
		j = i
	}
	return inside
}

// ComputePolygonROI berechnet die Wundplanimetrie (Umfang, Gauß-Trapezfläche, Gewebetemperatur & kontralaterale Spiegelung).
func ComputePolygonROI(raw []byte, w, h int, pts []image.Point) PolygonROIMetrics {
	n := len(pts)
	if n < 3 || len(raw) != w*h {
		return PolygonROIMetrics{Points: pts, VertexCount: n, Risk: "NORMAL"}
	}

	// 1. Umfang (Perimeter) & Gaußsche Trapezformel (Shoelace)
	var perimPx, shoelace float64
	minX, maxX := pts[0].X, pts[0].X
	minY, maxY := pts[0].Y, pts[0].Y

	for i := 0; i < n; i++ {
		j := (i + 1) % n
		dx := float64(pts[j].X - pts[i].X)
		dy := float64(pts[j].Y - pts[i].Y)
		perimPx += math.Sqrt(dx*dx + dy*dy)
		shoelace += float64(pts[i].X*pts[j].Y - pts[j].X*pts[i].Y)

		if pts[i].X < minX {
			minX = pts[i].X
		}
		if pts[i].X > maxX {
			maxX = pts[i].X
		}
		if pts[i].Y < minY {
			minY = pts[i].Y
		}
		if pts[i].Y > maxY {
			maxY = pts[i].Y
		}
	}

	perimMm := perimPx * 0.60
	areaPxGeom := math.Abs(shoelace) * 0.5

	if minX < 0 {
		minX = 0
	}
	if maxX >= w {
		maxX = w - 1
	}
	if minY < 0 {
		minY = 0
	}
	if maxY >= h {
		maxY = h - 1
	}

	var sum, sumSq, contraSum float64
	minT, maxT := 100.0, -100.0
	count, contraCount := 0, 0
	midline := w / 2

	for y := minY; y <= maxY; y++ {
		rowOff := y * w
		for x := minX; x <= maxX; x++ {
			if pointInPolygon(x, y, pts) {
				b := raw[rowOff+x]
				t := TempOf(b)
				sum += t
				sumSq += t * t
				if t < minT {
					minT = t
				}
				if t > maxT {
					maxT = t
				}
				count++

				contraX := midline*2 - x
				if contraX >= 0 && contraX < w {
					cb := raw[rowOff+contraX]
					contraSum += TempOf(cb)
					contraCount++
				}
			}
		}
	}

	if count == 0 {
		return PolygonROIMetrics{Points: pts, VertexCount: n, PerimeterMm: perimMm, Risk: "NORMAL"}
	}

	mean := sum / float64(count)
	variance := (sumSq / float64(count)) - (mean * mean)
	if variance < 0 {
		variance = 0
	}
	stdDev := math.Sqrt(variance)

	contraMean := mean
	if contraCount > 0 {
		contraMean = contraSum / float64(contraCount)
	}
	deltaT := math.Abs(mean - contraMean)

	effPx := math.Max(float64(count), areaPxGeom)
	areaMm2 := effPx * (0.60 * 0.60)
	areaCm2 := areaMm2 / 100.0

	risk := "NORMAL"
	if deltaT >= 2.2 || maxT >= 34.0 {
		risk = "CRITICAL"
	} else if deltaT >= 1.2 || maxT >= 32.0 {
		risk = "MODERATE"
	}

	return PolygonROIMetrics{
		Points:      pts,
		VertexCount: n,
		PerimeterMm: perimMm,
		AreaMm2:     areaMm2,
		AreaCm2:     areaCm2,
		PixelCount:  count,
		MinT:        minT,
		MaxT:        maxT,
		MeanT:       mean,
		StdDev:      stdDev,
		ContraMeanT: contraMean,
		DeltaT:      deltaT,
		Risk:        risk,
	}
}

// AddThermalPin setzt eine dauerhafte Multi-Pin Thermosonde (P1, P2, ...) auf das Bild.
func AddThermalPin(raw []byte, w, h int, pt image.Point) ThermalPinItem {
	GState.NextPinID++
	id := GState.NextPinID
	label := fmt.Sprintf("P%d", id)

	tempC := 20.0
	contraC := 20.0
	localSum := 0.0
	localCnt := 0

	if len(raw) == w*h && pt.X >= 0 && pt.X < w && pt.Y >= 0 && pt.Y < h {
		tempC = TempOf(raw[pt.Y*w+pt.X])
		midline := w / 2
		contraX := midline*2 - pt.X
		if contraX >= 0 && contraX < w {
			contraC = TempOf(raw[pt.Y*w+contraX])
		} else {
			contraC = tempC
		}

		for dy := -1; dy <= 1; dy++ {
			for dx := -1; dx <= 1; dx++ {
				nx, ny := pt.X+dx, pt.Y+dy
				if nx >= 0 && nx < w && ny >= 0 && ny < h {
					localSum += TempOf(raw[ny*w+nx])
					localCnt++
				}
			}
		}
	}

	local3 := tempC
	if localCnt > 0 {
		local3 = localSum / float64(localCnt)
	}
	deltaT := tempC - contraC

	// Anatomische Zone bestimmen
	side := "Rechts"
	if pt.X >= w/2 {
		side = "Links"
	}
	relY := float64(pt.Y) / float64(math.Max(1, float64(h)))
	zone := side + " · Mittelfuß"
	if relY < 0.28 {
		zone = side + " · Hallux/Digiti"
	} else if relY < 0.48 {
		zone = side + " · Metatarsale"
	} else if relY > 0.72 {
		zone = side + " · Calcaneus"
	}

	risk := "NORMAL"
	if math.Abs(deltaT) >= 2.2 || tempC >= 34.0 {
		risk = "CRITICAL"
	} else if math.Abs(deltaT) >= 1.2 || tempC >= 32.0 {
		risk = "MODERATE"
	}

	pin := ThermalPinItem{
		ID:      id,
		Label:   label,
		Pt:      pt,
		TempC:   tempC,
		ContraC: contraC,
		DeltaT:  deltaT,
		Local3:  local3,
		Zone:    zone,
		Risk:    risk,
	}
	GState.PinProbes = append(GState.PinProbes, pin)

	AddCompletedMeasurement("Pin-Sonde", fmt.Sprintf("Sonde %s (%s)", label, zone),
		fmt.Sprintf("%.1f °C", tempC),
		fmt.Sprintf("ΔT %+.2f K · 3×3 Ø %.1f°C", deltaT, local3),
		risk, []image.Point{pt})

	return pin
}

// GetSubpixelMatrix extrahiert ein 5x5 Temperatur-Zahlenraster um den Cursor für die Präzisionslupe.
func GetSubpixelMatrix(raw []byte, w, h int, cx, cy int) [5][5]float64 {
	var mat [5][5]float64
	for dy := -2; dy <= 2; dy++ {
		for dx := -2; dx <= 2; dx++ {
			x, y := cx+dx, cy+dy
			if len(raw) == w*h && x >= 0 && x < w && y >= 0 && y < h {
				mat[dy+2][dx+2] = TempOf(raw[y*w+x])
			} else {
				mat[dy+2][dx+2] = 20.0
			}
		}
	}
	return mat
}


