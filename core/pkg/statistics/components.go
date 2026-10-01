package statistics

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// HotspotRegion represents a segmented inflammatory hotspot cluster.
type HotspotRegion struct {
	ID          int     `json:"id"`
	AreaPixels  int     `json:"area_pixels"`
	AreaPercent float64 `json:"area_percent"` // Percentage of body tissue
	Perimeter   float64 `json:"perimeter"`
	Circularity float64 `json:"circularity"`  // 4 * pi * Area / Perimeter^2
	CenterX     int     `json:"center_x"`
	CenterY     int     `json:"center_y"`
	MaxVal      uint8   `json:"max_val"`
	MeanVal     float64 `json:"mean_val"`
	BoundingBox [4]int  `json:"bounding_box"` // [minX, minY, maxX, maxY]
	Status      string  `json:"status"`       // "REJECTED_SMALL", "REJECTED_LINEAR", "REJECTED_BORDER", "CONFIRMED_HOTSPOT"
}

// FilterOptions sets parameters for geometric region filtering.
type FilterOptions struct {
	MinAreaFraction   float64 // default 0.0005 (0.05% of tissue)
	MinCircularity    float64 // default 0.08 (allows irregular lesions, discards veins)
	BorderMarginPx    int     // default 15 px (reject camera frame edges)
	MinDistFromBorder float32 // default 8.0 px (reject skin-air interface artifacts)
	AnatomicalCutoffY float64 // default 0.65 (reject warm ankles/calves below the feet)
}

// DefaultFilterOptions returns standard geometric parameters.
func DefaultFilterOptions() FilterOptions {
	return FilterOptions{
		MinAreaFraction:   0.0005,
		MinCircularity:    0.08,
		BorderMarginPx:    15,
		MinDistFromBorder: 8.0,
		AnatomicalCutoffY: 0.65, // As in original IGNITE publication
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

			hr := HotspotRegion{
				ID:          regionID,
				AreaPixels:  area,
				AreaPercent: math.Round(areaPercent*100) / 100,
				Perimeter:   math.Round(perimeter*10) / 10,
				Circularity: math.Round(circularity*1000) / 1000,
				CenterX:     (minX + maxX) / 2,
				CenterY:     (minY + maxY) / 2,
				MaxVal:      maxVal,
				MeanVal:     math.Round((sumVal/float64(area))*10) / 10,
				BoundingBox: [4]int{minX, minY, maxX, maxY},
			}

			// 1. Rejection: Camera frame border artifacts
			margin := opts.BorderMarginPx
			if minX <= margin || minY <= margin || maxX >= (w-margin) || maxY >= (h-margin) {
				hr.Status = "REJECTED_BORDER"
			} else if opts.AnatomicalCutoffY > 0 && float64(minY) > float64(h)*opts.AnatomicalCutoffY {
				// Rejection: Anatomical cutoff (calves/ankles below the feet)
				hr.Status = "REJECTED_ANATOMICAL"
			} else if distMap != nil && maxDist < opts.MinDistFromBorder {
				// 2. Rejection: Skin boundary air-leak artifact
				hr.Status = "REJECTED_BORDER"
			} else if area < minArea {
				// 3. Rejection: Too small
				hr.Status = "REJECTED_SMALL"
			} else if circularity < opts.MinCircularity {
				// 4. Rejection: Linear/focal artifact (vein/tendon)
				hr.Status = "REJECTED_LINEAR"
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
