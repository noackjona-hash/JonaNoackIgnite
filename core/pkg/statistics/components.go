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
	Status           string  `json:"status"`            // "REJECTED_SMALL", "REJECTED_LINEAR", "REJECTED_BORDER", "CONFIRMED_HOTSPOT"
	EdgeGradient     float64 `json:"edge_gradient"`     // Mittlerer Temperaturabfall am Rand zur gesunden Umgebung
	ThermalLaplacian float64 `json:"thermal_laplacian"` // Diskreter 2D-Laplace-Operator nabla^2 T (Zentraler Wärmequell-Fokus)
	HaloDelta        float64 `json:"halo_delta"`        // Perifokaler Halo-Temperaturüberschuss gegenüber Median
	PeakToMean       float64 `json:"peak_to_mean"`      // Schärfegrad / Fokus-Spitzheitsfaktor (Max-Median) / (Mean-Median)
	DiagnosisType    string  `json:"diagnosis_type"`    // "INFLAMMATION", "PRESSURE_POINT", "INFLAMED_PRESSURE_POINT", "BENIGN"
	ConfidenceScore  float64 `json:"confidence_score"`  // Konfidenz der Differentialdiagnose (0 - 100%)
}

// FilterOptions sets parameters for geometric region filtering.
type FilterOptions struct {
	MinAreaFraction   float64 // default 0.0005 (0.05% of tissue)
	MinCircularity    float64 // default 0.08 (allows irregular lesions, discards veins)
	BorderMarginPx    int     // default 15 px (reject camera frame edges)
	MinDistFromBorder float32 // default 8.0 px (reject skin-air interface artifacts)
	AnatomicalCutoffY float64 // default 0.65 (reject warm ankles/calves below the feet)
	OrigMedian        float64 // Gewebe-Median zur biophysikalischen Halo- & Differenzanalyse
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
						nbVal := float64(original.Data[nb])
						if nbVal > 20 { // nur Gewebepixel, kein Raumhintergrund
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
				DiagnosisType:    diagnosisType,
				ConfidenceScore:  confidence,
			}

			// 1. Rejection: Camera frame border artifacts
			margin := opts.BorderMarginPx
			if minX <= margin || minY <= margin || maxX >= (w-margin) || maxY >= (h-margin) {
				hr.Status = "REJECTED_BORDER"
			} else if opts.AnatomicalCutoffY > 0 && float64(minY) > float64(h)*opts.AnatomicalCutoffY {
				// Rejection: Anatomical cutoff (calves/ankles below the feet)
				hr.Status = "REJECTED_ANATOMICAL"
			} else if distMap != nil && maxDist < opts.MinDistFromBorder && edgeGradient < 3.0 && haloDelta < 5.0 {
				// 2. Rejection: Flat skin boundary air-leak artifact (no focal heat source)
				hr.Status = "REJECTED_BORDER"
			} else if area < minArea {
				// 3. Rejection: Too small
				hr.Status = "REJECTED_SMALL"
			} else if circularity < opts.MinCircularity {
				// 4. Rejection: Linear/focal artifact (vein/tendon)
				hr.Status = "REJECTED_LINEAR"
			} else if opts.OrigMedian > 0 && maxVal < uint8(opts.OrigMedian) && edgeGradient < 10.0 && haloDelta < 5.0 {
				// 5. Rejection: Below tissue baseline and lacks local focal hyperthermic peak
				hr.Status = "REJECTED_COLD"
			} else {
				// Confirmed real inflammation focus!
				hr.Status = "CONFIRMED_HOTSPOT"
				for _, p := range compPixels {
					filteredMask.Data[p] = 255
				}
				regionID++
			}

			regions = append(regions, hr)
		}
	}

	return regions, filteredMask
}
