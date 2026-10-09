package segmentation

import (
	"ignite-core/pkg/imageutil"
)

// CalculateOtsuThreshold computes the optimal global binarization threshold via Otsu's method.
func CalculateOtsuThreshold(src *imageutil.GrayMatrix) uint8 {
	var hist [256]int
	totalPixels := len(src.Data)
	if totalPixels == 0 {
		return 128
	}

	for _, v := range src.Data {
		hist[v]++
	}

	var sumTotal float64
	for t := 0; t < 256; t++ {
		sumTotal += float64(t * hist[t])
	}

	var sumBackground float64
	var weightBackground int
	var maxVariance float64
	var bestThreshold uint8 = 128

	for t := 0; t < 256; t++ {
		weightBackground += hist[t]
		if weightBackground == 0 {
			continue
		}
		weightForeground := totalPixels - weightBackground
		if weightForeground == 0 {
			break
		}

		sumBackground += float64(t * hist[t])
		meanBackground := sumBackground / float64(weightBackground)
		meanForeground := (sumTotal - sumBackground) / float64(weightForeground)

		// Inter-class variance
		diff := meanBackground - meanForeground
		betweenClassVariance := float64(weightBackground) * float64(weightForeground) * diff * diff

		if betweenClassVariance > maxVariance {
			maxVariance = betweenClassVariance
			bestThreshold = uint8(t)
		}
	}

	return bestThreshold
}

// SegmentBodyMask creates a binary foreground mask (255 = tissue, 0 = background)
// using Otsu's method with contrast fallback for low-contrast images.
func SegmentBodyMask(src *imageutil.GrayMatrix) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	mask := imageutil.NewGrayMatrix(w, h)

	minVal, maxVal := uint8(255), uint8(0)
	for _, v := range src.Data {
		if v < minVal {
			minVal = v
		}
		if v > maxVal {
			maxVal = v
		}
	}

	threshold := CalculateOtsuThreshold(src)

	// Low dynamic range fallback
	if (maxVal - minVal) < 30 {
		threshold = minVal + uint8(float64(maxVal-minVal)*0.3)
	}

	for i, v := range src.Data {
		if v >= threshold {
			mask.Data[i] = 255
		} else {
			mask.Data[i] = 0
		}
	}

	// 2. Anatomical Body Component Filtering:
	// Eliminate small detached background clutter/bedsheet reflections (< 2% of largest body part)
	visited := make([]bool, w*h)
	type compInfo struct {
		pixels []int
		area   int
	}
	var comps []compInfo
	maxCompArea := 0

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			idx := y*w + x
			if mask.Data[idx] == 0 || visited[idx] {
				continue
			}

			// BFS 4-connected component
			queue := []int{idx}
			visited[idx] = true
			var cPixels []int

			head := 0
			for head < len(queue) {
				curr := queue[head]
				head++
				cPixels = append(cPixels, curr)

				cx := curr % w
				cy := curr / w

				// 4 neighbors
				if cx > 0 && mask.Data[curr-1] > 0 && !visited[curr-1] {
					visited[curr-1] = true
					queue = append(queue, curr-1)
				}
				if cx < w-1 && mask.Data[curr+1] > 0 && !visited[curr+1] {
					visited[curr+1] = true
					queue = append(queue, curr+1)
				}
				if cy > 0 && mask.Data[curr-w] > 0 && !visited[curr-w] {
					visited[curr-w] = true
					queue = append(queue, curr-w)
				}
				if cy < h-1 && mask.Data[curr+w] > 0 && !visited[curr+w] {
					visited[curr+w] = true
					queue = append(queue, curr+w)
				}
			}

			if len(cPixels) > maxCompArea {
				maxCompArea = len(cPixels)
			}
			comps = append(comps, compInfo{pixels: cPixels, area: len(cPixels)})
		}
	}

	// Keep only primary anatomical bodies (area >= 2% of largest component and >= 1000 px)
	minBodyArea := int(float64(maxCompArea) * 0.02)
	if minBodyArea < 1000 {
		minBodyArea = 1000
	}

	for _, c := range comps {
		if c.area < minBodyArea {
			for _, p := range c.pixels {
				mask.Data[p] = 0
			}
		}
	}

	return mask
}
