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

// CalculateMultiOtsuThresholds computes a 3-class Multi-Otsu thresholding pair (tLow, tHigh)
// separating cold background, cool distal/extremity tissue, and warm core tissue.
func CalculateMultiOtsuThresholds(src *imageutil.GrayMatrix) (uint8, uint8, float64, float64) {
	total := len(src.Data)
	if total == 0 {
		return 85, 160, 0, 0
	}

	var hist [256]float64
	invTotal := 1.0 / float64(total)
	for _, v := range src.Data {
		hist[v] += invTotal
	}

	// Cumulative zeroth (P) and first (S) moments for O(1) interval evaluation
	var P [256]float64
	var S [256]float64
	P[0] = hist[0]
	S[0] = 0
	for i := 1; i < 256; i++ {
		P[i] = P[i-1] + hist[i]
		S[i] = S[i-1] + float64(i)*hist[i]
	}
	globalMean := S[255]

	// 2-class variance reference
	var bestVar2 float64
	for t := 0; t < 255; t++ {
		w0 := P[t]
		w1 := 1.0 - w0
		if w0 <= 1e-9 || w1 <= 1e-9 {
			continue
		}
		m0 := S[t] / w0
		m1 := (S[255] - S[t]) / w1
		v := w0*(m0-globalMean)*(m0-globalMean) + w1*(m1-globalMean)*(m1-globalMean)
		if v > bestVar2 {
			bestVar2 = v
		}
	}

	// Exhaustive fast 3-class Multi-Otsu over 256 bins (~32k ops, < 0.1 ms)
	var bestVar3 float64
	bestT1, bestT2 := uint8(85), uint8(160)
	for t1 := 10; t1 < 230; t1++ {
		w0 := P[t1]
		if w0 <= 0.01 {
			continue
		}
		m0 := S[t1] / w0
		term0 := w0 * (m0 - globalMean) * (m0 - globalMean)

		for t2 := t1 + 10; t2 < 250; t2++ {
			w1 := P[t2] - P[t1]
			w2 := 1.0 - P[t2]
			if w1 <= 0.005 || w2 <= 0.005 {
				continue
			}
			m1 := (S[t2] - S[t1]) / w1
			m2 := (S[255] - S[t2]) / w2
			v := term0 + w1*(m1-globalMean)*(m1-globalMean) + w2*(m2-globalMean)*(m2-globalMean)
			if v > bestVar3 {
				bestVar3 = v
				bestT1 = uint8(t1)
				bestT2 = uint8(t2)
			}
		}
	}

	return bestT1, bestT2, bestVar2, bestVar3
}

// SegmentBodyMask creates a binary foreground mask (255 = tissue, 0 = background)
// using Otsu's method (with Multi-Otsu cool-extremity guard) and fallback for low-contrast images.
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
	tLow, tHigh, var2, var3 := CalculateMultiOtsuThresholds(src)
	// When warm proximal legs skew 2-class Otsu high above cool contralateral toes (tLow >= 78),
	// Multi-Otsu separates background cleanly while retaining cool red/orange distal toes.
	if var2 > 0 && var3 > var2*1.12 && tLow >= 78 && int(threshold) > int(tLow)+12 && int(tHigh) >= int(threshold)-10 {
		threshold = tLow
	}

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
