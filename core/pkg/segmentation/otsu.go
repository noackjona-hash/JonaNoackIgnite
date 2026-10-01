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
	return mask
}
