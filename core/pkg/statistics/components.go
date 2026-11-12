package statistics

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// HotspotRegion represents a segmented inflammatory hotspot cluster.
type HotspotRegion struct {
	ID               int     `json:"id"`
	AreaPixels       int     `json:"area_pixels"`
	AreaPercent      float64 `json:"area_percent"` // Percentage of body tissue
	Perimeter        float64 `json:"perimeter"`
	Circularity      float64 `json:"circularity"`  // 4 * pi * Area / Perimeter^2
	CenterX          int     `json:"center_x"`
	CenterY          int     `json:"center_y"`
	MaxVal           uint8   `json:"max_val"`
	MeanVal          float64 `json:"mean_val"`
	BoundingBox      [4]int  `json:"bounding_box"`      // [minX, minY, maxX, maxY]
	Status           string  `json:"status"`            // "REJECTED_SMALL", "REJECTED_LINEAR", "REJECTED_BORDER", "REJECTED_DIFFUSE_PLATEAU", "CONFIRMED_HOTSPOT"
	EdgeGradient     float64 `json:"edge_gradient"`     // Mittlerer Temperaturabfall am Rand zur gesunden Umgebung
	ThermalLaplacian float64 `json:"thermal_laplacian"` // Diskreter 2D-Laplace-Operator nabla^2 T (Zentraler Wärmequell-Fokus)
	HaloDelta        float64 `json:"halo_delta"`        // Perifokaler Halo-Temperaturüberschuss gegenüber Median
	PeakToMean       float64 `json:"peak_to_mean"`      // Schärfegrad / Fokus-Spitzheitsfaktor (Max-Median) / (Mean-Median)
	LocalProminence  float64 `json:"local_prominence"`  // Lokale Überhöhung über gesunde Gewebeumgebung (Kelvin/Einheiten)
	LocalSurroundMed float64 `json:"local_surround_med"` // Lokaler Median der gesunden Gewebeumgebung im Ring
	ContraDelta      float64 `json:"contra_delta"`       // Kontralaterale Armstrong-Asymmetrie Delta T zum gespiegelten Referenzort
	ContraMeasured   bool    `json:"contra_measured,omitempty"` // Flag ob kontralateraler Seitenvergleich tatsächlich gemessen wurde
	DiagnosisType    string  `json:"diagnosis_type"`     // "INFLAMMATION", "PRESSURE_POINT", "INFLAMED_PRESSURE_POINT", "BENIGN"
	ConfidenceScore  float64 `json:"confidence_score"`  // Konfidenz der Differentialdiagnose (0 - 100%)
}

// FilterOptions sets parameters for geometric region filtering.
type FilterOptions struct {
	MinAreaFraction   float64 // default 0.0005 (0.05% of tissue)
	MinCircularity    float64 // default 0.08 (allows irregular lesions, discards veins)
	BorderMarginPx    int     // default 25 px (reject camera frame edges)
	MinDistFromBorder float32 // default 8.0 px (reject skin-air interface artifacts)
	AnatomicalCutoffY float64 // default 0.65 (reject warm ankles/calves below the feet)
	OrigMedian        float64 // Gewebe-Median zur biophysikalischen Halo- & Differenzanalyse
	BodyMask          *imageutil.GrayMatrix // Segmentierte Gewebemaske zur exakten Umgebungsanalyse
}

// DefaultFilterOptions returns standard geometric parameters.
func DefaultFilterOptions() FilterOptions {
	return FilterOptions{
		MinAreaFraction:   0.0005,
		MinCircularity:    0.08,
		BorderMarginPx:    15,
		MinDistFromBorder: 8.0,
		AnatomicalCutoffY: 0.65, // As in original IGNITE publication
		OrigMedian:        0.0,
	}
}

// ExtractHotspots identifies 4-connected components and filters by area, circularity, and distance from tissue borders.
func ExtractHotspots(binaryMask *imageutil.GrayMatrix, original *imageutil.GrayMatrix, distMap *imageutil.FloatMatrix, totalTissuePixels int, opts FilterOptions) ([]HotspotRegion, *imageutil.GrayMatrix) {
	w, h := binaryMask.Width, binaryMask.Height
	visited := make([]bool, w*h)
	filteredMask := imageutil.NewGrayMatrix(w, h)

	minArea := int(float64(totalTissuePixels) * opts.MinAreaFraction)
	if minArea < 15 {
		minArea = 15
	}

	var regions []HotspotRegion
	regionID := 1

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := y*w + x
			if binaryMask.Data[idx] == 0 || visited[idx] {
				continue
			}

			// BFS for 4-connected component
			queue := []int{idx}
			visited[idx] = true

			var compPixels []int
			minX, maxX := x, x
			minY, maxY := y, y
			var perimeter float64
			var sumVal float64
			var maxVal uint8
			var maxDist float32

			head := 0
			for head < len(queue) {
				curr := queue[head]
				head++
				compPixels = append(compPixels, curr)

				cx := curr % w
				cy := curr / w

				if cx < minX {
					minX = cx
				}
				if cx > maxX {
					maxX = cx
				}
				if cy < minY {
					minY = cy
				}
				if cy > maxY {
					maxY = cy
				}

				origVal := original.Data[curr]
				sumVal += float64(origVal)
				if origVal > maxVal {
					maxVal = origVal
				}

				if distMap != nil {
					d := distMap.Data[curr]
					if d > maxDist {
						maxDist = d
					}
				}

				neighbors := [4]int{
					curr - 1, // left
					curr + 1, // right
					curr - w, // up
					curr + w, // down
				}

				isBoundary := false
				if cx == 0 || cx == w-1 || cy == 0 || cy == h-1 {
					isBoundary = true
				}

				for _, nb := range neighbors {
					if nb < 0 || nb >= len(visited) {
						continue
					}
					nbX := nb % w
					nbY := nb / w
					if math.Abs(float64(nbX-cx))+math.Abs(float64(nbY-cy)) > 1.5 {
						continue
					}

					if binaryMask.Data[nb] == 0 {
						isBoundary = true
					} else if !visited[nb] {
						visited[nb] = true
						queue = append(queue, nb)
					}
				}

				if isBoundary {
					perimeter += 1.0
				}
			}

			area := len(compPixels)
			if perimeter < 1.0 {
				perimeter = 1.0
			}
			circularity := (4.0 * math.Pi * float64(area)) / (perimeter * perimeter)
			if circularity > 1.0 {
				circularity = 1.0
			}

			areaPercent := float64(0)
			if totalTissuePixels > 0 {
				areaPercent = (float64(area) / float64(totalTissuePixels)) * 100.0
			}

			// Biophysikalische Merkmale zur Differenzierung: Entzündung vs. Druckstelle
			var boundaryGradSum float64
			var boundaryGradCount int
			haloPixelsMap := make(map[int]bool)

			// 1. Randgradient & Perifokaler Ring (1-3 Pixel Außenzone)
			for _, p := range compPixels {
				px := p % w
				py := p / w
				pVal := float64(original.Data[p])

				// 4 Nachbarn prüfen
				nbs := [4]int{p - 1, p + 1, p - w, p + w}
				for _, nb := range nbs {
					if nb < 0 || nb >= len(binaryMask.Data) {
						continue
					}
					nbX := nb % w
					nbY := nb / w
					if math.Abs(float64(nbX-px))+math.Abs(float64(nbY-py)) > 1.5 {
						continue
					}

					// Liegt Nachbar außerhalb der Hotspot-Maske?
					if binaryMask.Data[nb] == 0 {
						isTissue := true
						if opts.BodyMask != nil {
							isTissue = opts.BodyMask.Data[nb] > 0
						} else {
							isTissue = original.Data[nb] > 40
						}
						if isTissue {
							nbVal := float64(original.Data[nb])
							diff := pVal - nbVal
							if diff > 0 {
								boundaryGradSum += diff
								boundaryGradCount++
							}
							haloPixelsMap[nb] = true
						}
					}
				}
			}

			edgeGradient := float64(0)
			if boundaryGradCount > 0 {
				edgeGradient = math.Round((boundaryGradSum/float64(boundaryGradCount))*10) / 10
			}

			// 2. Halo-Effekt: Mittlere Temperatur des perifokalen Geweberings
			origMed := opts.OrigMedian
			if origMed <= 0 {
				origMed = float64(maxVal) - 20.0
			}
			var haloSum float64
			var haloCount int
			for hp := range haloPixelsMap {
				haloSum += float64(original.Data[hp])
				haloCount++
			}
			haloDelta := float64(0)
			if haloCount > 0 {
				haloMean := haloSum / float64(haloCount)
				haloDelta = math.Round((haloMean-origMed)*10) / 10
			}

			// 2.5 Lokale fokale Prominenz: Saubere äußere Annular-Umgebung (ohne Eigenkontamination der Läsion)
			boxSpanX := maxX - minX + 1
			boxSpanY := maxY - minY + 1
			outerPad := 56
			if boxSpanX > outerPad {
				outerPad = boxSpanX
			}
			if boxSpanY > outerPad {
				outerPad = boxSpanY
			}
			if outerPad > 85 {
				outerPad = 85
			}
			exclMargin := 8 // Exclude immediate inflammatory halo slope around binary core
			ex0, ey0, ex1, ey1 := minX-exclMargin, minY-exclMargin, maxX+exclMargin, maxY+exclMargin

			ax0 := minX - outerPad
			if ax0 < 0 {
				ax0 = 0
			}
			ay0 := minY - outerPad
			if ay0 < 0 {
				ay0 = 0
			}
			ax1 := maxX + outerPad
			if ax1 >= w {
				ax1 = w - 1
			}
			ay1 := maxY + outerPad
			if ay1 >= h {
				ay1 = h - 1
			}

			var ringHist [256]int
			ringCount := 0
			for sy := ay0; sy <= ay1; sy++ {
				row := sy * w
				for sx := ax0; sx <= ax1; sx++ {
					// Exclude inner bounding core + immediate slope so the ring reflects healthy host tissue
					if sx >= ex0 && sx <= ex1 && sy >= ey0 && sy <= ey1 {
						continue
					}
					sidx := row + sx
					isTis := true
					if opts.BodyMask != nil {
						isTis = opts.BodyMask.Data[sidx] > 0
					} else {
						isTis = original.Data[sidx] > 40
					}
					if isTis && binaryMask.Data[sidx] == 0 {
						ringHist[original.Data[sidx]]++
						ringCount++
					}
				}
			}

			localSurroundMed := float64(0)
			localProminence := float64(0)
			if ringCount > 20 {
				// 40th percentile of outer non-hot tissue avoids skew from residual erythema in one quadrant
				targetIdx := (ringCount * 40) / 100
				cum := 0
				for b := 0; b < 256; b++ {
					cum += ringHist[b]
					if cum > targetIdx {
						localSurroundMed = float64(b)
						break
					}
				}
				localProminence = math.Max(0.0, float64(maxVal)-localSurroundMed)
			} else {
				localSurroundMed = origMed
				localProminence = math.Max(0.0, float64(maxVal)-localSurroundMed)
			}

			// 3. 2D Laplace-Operator nabla^2 T am Kern des Herdes (Metabolische Wärmequelle vs. flaches Druckplateau)
			var peakIdx int
			for _, p := range compPixels {
				if original.Data[p] == maxVal {
					peakIdx = p
					break
				}
			}
			pkX := peakIdx % w
			pkY := peakIdx / w
			thermalLaplacian := float64(0)
			if pkX > 0 && pkX < w-1 && pkY > 0 && pkY < h-1 {
				cVal := float64(original.Data[peakIdx])
				lapVal := float64(original.Data[peakIdx+1]) + float64(original.Data[peakIdx-1]) +
					float64(original.Data[peakIdx+w]) + float64(original.Data[peakIdx-w]) - (4.0 * cVal)
				thermalLaplacian = math.Round(lapVal*10) / 10
			}

			// 4. Fokus-Spitzheit (Peak-To-Mean Ratio)
			meanVal := math.Round((sumVal/float64(area))*10) / 10
			peakDelta := float64(maxVal) - origMed
			meanDelta := meanVal - origMed
			peakToMean := float64(1.0)
			if meanDelta > 0.5 {
				peakToMean = math.Round((peakDelta/meanDelta)*100) / 100
			}

			// 5. Differentialdiagnose-Klassifikation
			diagnosisType := "BENIGN"
			confidence := 80.0
			deltaT := float64(maxVal) - origMed

			isSharpEdge := edgeGradient >= 3.0
			hasInflamHalo := haloDelta >= 5.0
			isMetabolicPeak := thermalLaplacian <= -3.5 || peakToMean >= 1.25

			if deltaT >= 22.0 { // Armstrong kritische Schwelle (>= 2.2 K)
				if isSharpEdge && !hasInflamHalo {
					diagnosisType = "INFLAMED_PRESSURE_POINT"
					confidence = 94.0
				} else {
					diagnosisType = "INFLAMMATION"
					confidence = 96.0
				}
			} else if deltaT >= 10.0 { // Mäßige Hyperthermie (1.0 K bis 2.1 K)
				if isSharpEdge && !hasInflamHalo {
					diagnosisType = "PRESSURE_POINT"
					confidence = 88.0
				} else if hasInflamHalo || isMetabolicPeak {
					diagnosisType = "INFLAMMATION"
					confidence = 85.0
				} else {
					diagnosisType = "PRESSURE_POINT"
					confidence = 82.0
				}
			} else {
				if isSharpEdge {
					diagnosisType = "PRESSURE_POINT"
					confidence = 78.0
				} else {
					diagnosisType = "BENIGN"
					confidence = 90.0
				}
			}

			// Berechne den fokalen Kern der Hyperthermie (Gewebe nahe dem Temperaturmaximum):
			// T >= maxVal - 28 und T >= origMed
			coreMinX, coreMaxX := w, 0
			coreMinY, coreMaxY := h, 0
			var coreCount int
			for _, p := range compPixels {
				pval := original.Data[p]
				if pval >= maxVal-28 && float64(pval) >= origMed {
					px := p % w
					py := p / w
					if px < coreMinX {
						coreMinX = px
					}
					if px > coreMaxX {
						coreMaxX = px
					}
					if py < coreMinY {
						coreMinY = py
					}
					if py > coreMaxY {
						coreMaxY = py
					}
					coreCount++
				}
			}

			finalBox := [4]int{minX, minY, maxX, maxY}
			if coreCount >= 10 && coreMaxX >= coreMinX && coreMaxY >= coreMinY {
				pad := 6
				bx0 := coreMinX - pad
				if bx0 < minX {
					bx0 = minX
				}
				if bx0 < 0 {
					bx0 = 0
				}
				by0 := coreMinY - pad
				if by0 < minY {
					by0 = minY
				}
				if by0 < 0 {
					by0 = 0
				}
				bx1 := coreMaxX + pad
				if bx1 > maxX {
					bx1 = maxX
				}
				if bx1 >= w {
					bx1 = w - 1
				}
				by1 := coreMaxY + pad
				if by1 > maxY {
					by1 = maxY
				}
				if by1 >= h {
					by1 = h - 1
				}
				finalBox = [4]int{bx0, by0, bx1, by1}
			}

			hr := HotspotRegion{
				ID:               regionID,
				AreaPixels:       area,
				AreaPercent:      math.Round(areaPercent*100) / 100,
				Perimeter:        math.Round(perimeter*10) / 10,
				Circularity:      math.Round(circularity*1000) / 1000,
				CenterX:          (finalBox[0] + finalBox[2]) / 2,
				CenterY:          (finalBox[1] + finalBox[3]) / 2,
				MaxVal:           maxVal,
				MeanVal:          meanVal,
				BoundingBox:      finalBox,
				EdgeGradient:     edgeGradient,
				ThermalLaplacian: thermalLaplacian,
				HaloDelta:        haloDelta,
				PeakToMean:       peakToMean,
				LocalProminence:  math.Round(localProminence*10) / 10,
				LocalSurroundMed: math.Round(localSurroundMed*10) / 10,
				DiagnosisType:    diagnosisType,
				ConfidenceScore:  confidence,
			}

			// 1. Rejection: Camera frame border artifacts
			margin := opts.BorderMarginPx
			if margin < 25 {
				margin = 25
			}
			boxW := maxX - minX + 1
			boxH := maxY - minY + 1
			minBoxDim := boxW
			maxBoxDim := boxH
			if boxH < minBoxDim {
				minBoxDim = boxH
				maxBoxDim = boxW
			}
			isNarrowStreak := (boxW <= 4 && boxH >= 15) || (boxH <= 4 && boxW >= 15)
			// FLIR MSX visible-light edge overlay creases produce small slivers with non-physical sharp thermal jumps
			isMSXCrease := (edgeGradient >= 14.5 && area < 450 && circularity < 0.55) ||
				(minBoxDim <= 18 && maxBoxDim >= minBoxDim*2 && area < 450 && edgeGradient >= 12.0) ||
				(minBoxDim <= 16 && maxBoxDim >= minBoxDim*3 && area < 450 && circularity < 0.40)

			bottomMargin := margin + 30 // Limbs entering bottom of FOV (55 px margin)
			if minX <= margin || minY <= margin || maxX >= (w-margin) || maxY >= (h-bottomMargin) {
				hr.Status = "REJECTED_BORDER"
			} else if opts.AnatomicalCutoffY > 0 && float64(minY) > float64(h)*opts.AnatomicalCutoffY {
				hr.Status = "REJECTED_ANATOMICAL"
			} else if distMap != nil && maxDist < opts.MinDistFromBorder {
				hr.Status = "REJECTED_BORDER"
			} else if area < minArea {
				hr.Status = "REJECTED_SMALL"
			} else if isNarrowStreak || isMSXCrease {
				hr.Status = "REJECTED_LINEAR"
			} else if circularity < opts.MinCircularity && (area < 800 || (localProminence < 25.0 && float64(maxVal)-origMed < 18.0)) {
				hr.Status = "REJECTED_LINEAR"
			} else if (localProminence < 32.0 && edgeGradient < 4.5) || (localProminence < 20.0 && area > 600) {
				// Rejection: Diffuse warm anatomical plateau (e.g. calf/thigh/heel) without steep focal gradient
				hr.Status = "REJECTED_DIFFUSE_PLATEAU"
			} else if opts.OrigMedian > 0 && float64(maxVal) <= opts.OrigMedian {
				hr.Status = "REJECTED_COLD"
			} else {
				hr.Status = "CONFIRMED_HOTSPOT"
				for _, p := range compPixels {
					filteredMask.Data[p] = 255
				}
				regionID++
			}

			regions = append(regions, hr)
		}
	}

	// Post-Processing Phase A: Topological Saddle-Point Merging & Spatial Non-Maximum Suppression (NMS)
	// Eliminates duplicate/overlapping boxes on the same anatomical lesion focus
	regions = ConsolidateAndMergeHotspots(regions, original, opts.BodyMask, filteredMask)

	// Post-Processing Phase B: Geodesic Level-Set Active Contour Expansion
	// Expands lesion coverage outward to capture the true erythematous/hyperthermic footprint
	ExpandGeodesicLesionContour(regions, original, opts.BodyMask, filteredMask, opts.OrigMedian)

	// Cleanly re-index remaining confirmed hotspots
	confID := 1
	for idx := range regions {
		if regions[idx].Status == "CONFIRMED_HOTSPOT" {
			regions[idx].ID = confID
			confID++
		}
	}

	return regions, filteredMask
}

// hasTissueBridge verifies along a line segment that two clusters belong to the same continuous limb
// rather than spanning empty background air across the inter-pedal cleft.
func hasTissueBridge(bodyMask *imageutil.GrayMatrix, x0, y0, x1, y1 int) bool {
	if bodyMask == nil {
		return true
	}
	steps := int(math.Hypot(float64(x1-x0), float64(y1-y0)))
	if steps <= 2 {
		return true
	}
	airGaps := 0
	for s := 1; s < steps; s++ {
		t := float64(s) / float64(steps)
		x := int(math.Round(float64(x0) + t*float64(x1-x0)))
		y := int(math.Round(float64(y0) + t*float64(y1-y0)))
		if x >= 0 && x < bodyMask.Width && y >= 0 && y < bodyMask.Height {
			if bodyMask.At(x, y) == 0 {
				airGaps++
				if airGaps > 5 {
					return false
				}
			}
		}
	}
	return true
}

// ConsolidateAndMergeHotspots merges adjacent fragmented hotspot clusters that belong to the same anatomical lesion,
// performs topological saddle-point checks, and applies Non-Maximum Suppression (NMS).
func ConsolidateAndMergeHotspots(regions []HotspotRegion, original *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, filteredMask *imageutil.GrayMatrix) []HotspotRegion {
	if len(regions) < 2 {
		return regions
	}

	// Iterative multi-pass merging of adjacent/overlapping clusters
	changed := true
	for changed {
		changed = false
		for i := 0; i < len(regions); i++ {
			if regions[i].Status != "CONFIRMED_HOTSPOT" {
				continue
			}
			for j := i + 1; j < len(regions); j++ {
				if regions[j].Status != "CONFIRMED_HOTSPOT" {
					continue
				}

				rA := &regions[i]
				rB := &regions[j]

				bbA := rA.BoundingBox
				bbB := rB.BoundingBox

				gapX := 0
				if bbA[0] > bbB[2] {
					gapX = bbA[0] - bbB[2]
				} else if bbB[0] > bbA[2] {
					gapX = bbB[0] - bbA[2]
				}

				gapY := 0
				if bbA[1] > bbB[3] {
					gapY = bbA[1] - bbB[3]
				} else if bbB[1] > bbA[3] {
					gapY = bbB[1] - bbA[3]
				}

				distCenters := math.Hypot(float64(rA.CenterX-rB.CenterX), float64(rA.CenterY-rB.CenterY))

				shouldMerge := false
				maxMergeDist := 50.0
				maxGap := 24
				if ((gapX <= maxGap && gapY <= maxGap) || distCenters <= maxMergeDist) &&
					hasTissueBridge(bodyMask, rA.CenterX, rA.CenterY, rB.CenterX, rB.CenterY) {
					shouldMerge = true
				}

				if shouldMerge {
					if rB.MaxVal > rA.MaxVal {
						rA, rB = rB, rA
					}

					rA.AreaPixels += rB.AreaPixels
					rA.AreaPercent += rB.AreaPercent
					if bbB[0] < rA.BoundingBox[0] {
						rA.BoundingBox[0] = bbB[0]
					}
					if bbB[1] < rA.BoundingBox[1] {
						rA.BoundingBox[1] = bbB[1]
					}
					if bbB[2] > rA.BoundingBox[2] {
						rA.BoundingBox[2] = bbB[2]
					}
					if bbB[3] > rA.BoundingBox[3] {
						rA.BoundingBox[3] = bbB[3]
					}
					rA.CenterX = (rA.BoundingBox[0] + rA.BoundingBox[2]) / 2
					rA.CenterY = (rA.BoundingBox[1] + rA.BoundingBox[3]) / 2
					if float64(rB.MaxVal) > float64(rA.MaxVal) {
						rA.MaxVal = rB.MaxVal
					}
					if rB.LocalProminence > rA.LocalProminence {
						rA.LocalProminence = rB.LocalProminence
					}
					if rB.ThermalLaplacian < rA.ThermalLaplacian {
						rA.ThermalLaplacian = rB.ThermalLaplacian
					}

					rB.Status = "MERGED_INTO_PRIMARY"
					changed = true
					break
				}
			}
			if changed {
				break
			}
		}
	}

	return regions
}

// ExpandGeodesicLesionContour performs connected geodesic FWHM region growth from confirmed hotspot seeds
// using the clean annular tissue baseline (LocalSurroundMed) to capture the full erythematous lesion footprint.
func ExpandGeodesicLesionContour(regions []HotspotRegion, original *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, filteredMask *imageutil.GrayMatrix, origMedianOpt ...float64) {
	origMed := 0.0
	if len(origMedianOpt) > 0 {
		origMed = origMedianOpt[0]
	}
	w, h := original.Width, original.Height
	minDim := w
	if h < minDim {
		minDim = h
	}
	maxGrowDist := math.Max(32.0, math.Min(76.0, float64(minDim)*0.068))
	maxDistSq := maxGrowDist * maxGrowDist
	totalPx := w * h
	if totalPx == 0 {
		return
	}

	visited := make([]bool, totalPx)
	for idx := range regions {
		r := &regions[idx]
		if r.Status != "CONFIRMED_HOTSPOT" {
			continue
		}

		// Thermal FWHM Isotherm Cutoff anchored on clean healthy ring baseline,
		// with warm-forefoot guard when global foot median is hyper-warm (>= 202)
		baseTemp := r.LocalSurroundMed
		if origMed >= 202.0 && origMed > baseTemp+15.0 {
			cappedMed := math.Min(origMed, float64(r.MaxVal)-30.0)
			baseTemp = 0.5*baseTemp + 0.5*cappedMed
		}
		prom := math.Max(10.0, float64(r.MaxVal)-baseTemp)
		cutoffF := baseTemp + 0.22*prom
		if minBase := baseTemp + 10.0; cutoffF < minBase {
			cutoffF = minBase
		}
		if maxKeep := float64(r.MaxVal) - 18.0; cutoffF > maxKeep {
			cutoffF = maxKeep
		}
		if cutoffF < 112.0 {
			cutoffF = 112.0
		}
		thresholdCutoff := uint8(math.Round(cutoffF))

		bb := r.BoundingBox
		// Collect initial 4-connected seeds already confirmed inside this region's bounding box
		var queue []int
		for y := bb[1]; y <= bb[3]; y++ {
			row := y * w
			for x := bb[0]; x <= bb[2]; x++ {
				p := row + x
				if filteredMask.Data[p] > 0 && !visited[p] {
					visited[p] = true
					queue = append(queue, p)
				}
			}
		}
		if len(queue) == 0 {
			continue
		}

		// Allow slightly larger radius when the confirmed core is already wide
		seedDiag := math.Hypot(float64(bb[2]-bb[0]), float64(bb[3]-bb[1]))
		allowedR := math.Max(maxGrowDist, seedDiag*0.65+24.0)
		if allowedR > 88.0 {
			allowedR = 88.0
		}
		limitDistSq := math.Max(maxDistSq, allowedR*allowedR)
		maxGrownArea := r.AreaPixels * 12
		if maxGrownArea < 18000 {
			maxGrownArea = 18000
		}
		if maxGrownArea > 26000 {
			maxGrownArea = 26000
		}

		additionalPixels := 0
		newMinX, newMinY, newMaxX, newMaxY := bb[0], bb[1], bb[2], bb[3]
		head := 0
		for head < len(queue) {
			curr := queue[head]
			head++
			cx := curr % w

			neighbors := [4]int{-1, 1, -w, w}
			for _, off := range neighbors {
				np := curr + off
				if np < 0 || np >= totalPx || visited[np] {
					continue
				}
				nx := np % w
				if nx-cx > 1 || cx-nx > 1 {
					continue
				}
				ny := np / w
				// Never expand into cold ambient room background (< 100), even if inside search radius
				if bodyMask != nil && bodyMask.Data[np] == 0 && original.Data[np] < 105 {
					continue
				}
				dx := float64(nx - r.CenterX)
				dy := float64(ny - r.CenterY)
				if dx*dx+dy*dy > limitDistSq {
					continue
				}
				if original.Data[np] < thresholdCutoff {
					continue
				}
				// Stop expansion if approaching a distinct cooler-valley-separated secondary peak
				if original.Data[np] > original.Data[curr]+12 && dx*dx+dy*dy > 1225.0 {
					continue
				}

				visited[np] = true
				queue = append(queue, np)
				if filteredMask.Data[np] == 0 {
					filteredMask.Data[np] = 255
					additionalPixels++
					if r.AreaPixels+additionalPixels >= maxGrownArea {
						break
					}
				}
				if nx < newMinX {
					newMinX = nx
				}
				if nx > newMaxX {
					newMaxX = nx
				}
				if ny < newMinY {
					newMinY = ny
				}
				if ny > newMaxY {
					newMaxY = ny
				}
			}
			if r.AreaPixels+additionalPixels >= maxGrownArea {
				break
			}
		}

		// Local MSX-crease & necrotic notch hole-filling within the grown lesion footprint (2 passes)
		for pass := 0; pass < 2; pass++ {
			var toFill []int
			for y := newMinY + 1; y < newMaxY; y++ {
				row := y * w
				for x := newMinX + 1; x < newMaxX; x++ {
					p := row + x
					if filteredMask.Data[p] > 0 || original.Data[p] < 95 {
						continue
					}
					cnt := 0
					if filteredMask.Data[p-1] > 0 { cnt++ }
					if filteredMask.Data[p+1] > 0 { cnt++ }
					if filteredMask.Data[p-w] > 0 { cnt++ }
					if filteredMask.Data[p+w] > 0 { cnt++ }
					if filteredMask.Data[p-w-1] > 0 { cnt++ }
					if filteredMask.Data[p-w+1] > 0 { cnt++ }
					if filteredMask.Data[p+w-1] > 0 { cnt++ }
					if filteredMask.Data[p+w+1] > 0 { cnt++ }
					if cnt >= 5 {
						toFill = append(toFill, p)
					}
				}
			}
			if len(toFill) == 0 {
				break
			}
			for _, p := range toFill {
				filteredMask.Data[p] = 255
				additionalPixels++
			}
		}

		r.AreaPixels += additionalPixels
		r.BoundingBox = [4]int{newMinX, newMinY, newMaxX, newMaxY}
		if totalPx > 0 {
			r.AreaPercent = math.Round((float64(r.AreaPixels)/float64(totalPx))*10000.0) / 100.0
		}
	}
}
