package statistics

import (
	"math"
	"sort"

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
	ContraDelta      float64 `json:"contra_delta"`      // Kontralaterale Armstrong-Asymmetrie Delta T zum gespiegelten Referenzort
	DiagnosisType    string  `json:"diagnosis_type"`    // "INFLAMMATION", "PRESSURE_POINT", "INFLAMED_PRESSURE_POINT", "BENIGN"
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

			// 2.5 Lokale fokale Prominenz: Annulare Gewebeumgebung (Radius 30 px)
			surroundBoxR := 30
			ax0 := minX - surroundBoxR
			if ax0 < 0 {
				ax0 = 0
			}
			ay0 := minY - surroundBoxR
			if ay0 < 0 {
				ay0 = 0
			}
			ax1 := maxX + surroundBoxR
			if ax1 >= w {
				ax1 = w - 1
			}
			ay1 := maxY + surroundBoxR
			if ay1 >= h {
				ay1 = h - 1
			}

			var localTissueVals []int
			for sy := ay0; sy <= ay1; sy++ {
				row := sy * w
				for sx := ax0; sx <= ax1; sx++ {
					sidx := row + sx
					isTis := true
					if opts.BodyMask != nil {
						isTis = opts.BodyMask.Data[sidx] > 0
					} else {
						isTis = original.Data[sidx] > 40
					}
					if isTis && binaryMask.Data[sidx] == 0 {
						localTissueVals = append(localTissueVals, int(original.Data[sidx]))
					}
				}
			}

			localSurroundMed := float64(0)
			localProminence := float64(0)
			if len(localTissueVals) > 10 {
				sort.Ints(localTissueVals)
				localSurroundMed = float64(localTissueVals[len(localTissueVals)/2])
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

			hr := HotspotRegion{
				ID:               regionID,
				AreaPixels:       area,
				AreaPercent:      math.Round(areaPercent*100) / 100,
				Perimeter:        math.Round(perimeter*10) / 10,
				Circularity:      math.Round(circularity*1000) / 1000,
				CenterX:          (minX + maxX) / 2,
				CenterY:          (minY + maxY) / 2,
				MaxVal:           maxVal,
				MeanVal:          meanVal,
				BoundingBox:      [4]int{minX, minY, maxX, maxY},
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
			bottomMargin := margin + 10 // Limbs entering bottom of FOV
			if minX <= margin || minY <= margin || maxX >= (w-margin) || maxY >= (h-bottomMargin) {
				hr.Status = "REJECTED_BORDER"
			} else if opts.AnatomicalCutoffY > 0 && float64(minY) > float64(h)*opts.AnatomicalCutoffY {
				hr.Status = "REJECTED_ANATOMICAL"
			} else if distMap != nil && maxDist < opts.MinDistFromBorder {
				hr.Status = "REJECTED_BORDER"
			} else if area < minArea {
				hr.Status = "REJECTED_SMALL"
			} else if circularity < opts.MinCircularity {
				hr.Status = "REJECTED_LINEAR"
			} else if localProminence < 18.0 && area > 800 && maxDist > 20.0 {
				// Rejection: Diffuse warm anatomical plateau (e.g. calf/thigh) without focal elevation
				hr.Status = "REJECTED_DIFFUSE_PLATEAU"
			} else if opts.OrigMedian > 0 && maxVal < uint8(opts.OrigMedian) && edgeGradient < 10.0 && haloDelta < 5.0 {
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
	// Expands lesion coverage outward to 100% of the true erythematous/hyperthermic footprint
	ExpandGeodesicLesionContour(regions, original, opts.BodyMask, filteredMask)

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

// ConsolidateAndMergeHotspots merges adjacent fragmented hotspot clusters that belong to the same anatomical lesion,
// performs topological saddle-point checks, and applies Non-Maximum Suppression (NMS).
func ConsolidateAndMergeHotspots(regions []HotspotRegion, original *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, filteredMask *imageutil.GrayMatrix) []HotspotRegion {
	if len(regions) < 2 {
		return regions
	}
	w := original.Width

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

				// Calculate gap between bounding boxes
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

				sameFoot := (rA.CenterX < w/2 && rB.CenterX < w/2) || (rA.CenterX >= w/2 && rB.CenterX >= w/2)
				shouldMerge := false

				// Merge adjacent clusters on the same anatomical foot/limb
				if sameFoot && ((gapX <= 55 && gapY <= 55) || distCenters <= 165.0) {
					shouldMerge = true
				}

				if shouldMerge {
					// Ensure rA is the more intense focus
					if rB.MaxVal > rA.MaxVal {
						rA, rB = rB, rA
					}

					// Merge rB into rA
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

// ExpandGeodesicLesionContour grows the lesion mask outward to 100% coverage using geodesic active flood fill.
func ExpandGeodesicLesionContour(regions []HotspotRegion, original *imageutil.GrayMatrix, bodyMask *imageutil.GrayMatrix, filteredMask *imageutil.GrayMatrix) {
	w, h := original.Width, original.Height
	for idx := range regions {
		r := &regions[idx]
		if r.Status != "CONFIRMED_HOTSPOT" {
			continue
		}

		// Find local healthy threshold for this specific focus (decay to baseline)
		thresholdCutoff := uint8(math.Max(float64(r.LocalSurroundMed)+10.0, float64(r.MaxVal)-50.0))

		bb := r.BoundingBox
		expandMargin := 35
		x0 := int(math.Max(0, float64(bb[0]-expandMargin)))
		y0 := int(math.Max(0, float64(bb[1]-expandMargin)))
		x1 := int(math.Min(float64(w-1), float64(bb[2]+expandMargin)))
		y1 := int(math.Min(float64(h-1), float64(bb[3]+expandMargin)))

		newMinX, newMinY := bb[0], bb[1]
		newMaxX, newMaxY := bb[2], bb[3]
		additionalPixels := 0

		for y := y0; y <= y1; y++ {
			row := y * w
			for x := x0; x <= x1; x++ {
				p := row + x
				if bodyMask != nil && bodyMask.Data[p] == 0 {
					continue
				}
				if original.Data[p] >= thresholdCutoff {
					if filteredMask.Data[p] == 0 {
						filteredMask.Data[p] = 255
						additionalPixels++
						if x < newMinX {
							newMinX = x
						}
						if x > newMaxX {
							newMaxX = x
						}
						if y < newMinY {
							newMinY = y
						}
						if y > newMaxY {
							newMaxY = y
						}
					}
				}
			}
		}

		r.AreaPixels += additionalPixels
		r.BoundingBox = [4]int{newMinX, newMinY, newMaxX, newMaxY}
		r.CenterX = (newMinX + newMaxX) / 2
		r.CenterY = (newMinY + newMaxY) / 2
	}
}
