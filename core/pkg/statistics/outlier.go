package statistics

import (
	"math"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/morphology"
)

// ThresholdMode selects the statistical model.
type ThresholdMode string

const (
	ModeGaussian ThresholdMode = "GAUSSIAN"
	ModeMAD      ThresholdMode = "MAD"
)

// OutlierStats holds intermediate statistical distribution values.
type OutlierStats struct {
	Mean       float64 `json:"mean"`
	StdDev     float64 `json:"std_dev"`
	Median     float64 `json:"median"`
	MAD        float64 `json:"mad"`
	OrigMedian float64 `json:"orig_median"`
	Threshold  uint8   `json:"threshold"`
	Mode       string  `json:"mode"`
}

// CalculateMADThreshold computes Median and MAD in O(N) using histogram bins.
// Also calculates the median of the original tissue image to prevent false positives on cold tissue.
func CalculateMADThreshold(diff *imageutil.GrayMatrix, orig *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, k float64) OutlierStats {
	var hist [256]int
	var origHist [256]int
	var totalValid int
	var sum float64
	var sumSq float64

	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		hist[v]++
		if orig != nil {
			origHist[orig.Data[i]]++
		}
		totalValid++
		sum += float64(v)
		sumSq += float64(v) * float64(v)
	}

	if totalValid == 0 {
		return OutlierStats{Threshold: 255}
	}

	mean := sum / float64(totalValid)
	variance := (sumSq / float64(totalValid)) - (mean * mean)
	if variance < 0 {
		variance = 0
	}
	stdDev := math.Sqrt(variance)

	// O(N) Histogram-based median of difference image:
	half := totalValid / 2
	var accum int
	var median float64
	for v := 0; v < 256; v++ {
		accum += hist[v]
		if accum >= half {
			median = float64(v)
			break
		}
	}

	// O(N) Median of original image
	accum = 0
	var origMedian float64
	for v := 0; v < 256; v++ {
		accum += origHist[v]
		if accum >= half {
			origMedian = float64(v)
			break
		}
	}

	// O(N) Histogram-based MAD: median(|X - median|)
	var absHist [256]int
	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		dev := int(math.Abs(float64(v) - median))
		if dev > 255 {
			dev = 255
		}
		absHist[dev]++
	}

	accum = 0
	var mad float64
	for dev := 0; dev < 256; dev++ {
		accum += absHist[dev]
		if accum >= half {
			mad = float64(dev)
			break
		}
	}

	// Robust standard deviation estimate = 1.4826 * MAD
	rawThreshold := median + k*1.4826*mad
	if rawThreshold > 255 {
		rawThreshold = 255
	} else if rawThreshold < 0 {
		rawThreshold = 0
	}

	return OutlierStats{
		Mean:       mean,
		StdDev:     stdDev,
		Median:     median,
		MAD:        mad,
		OrigMedian: origMedian,
		Threshold:  uint8(math.Round(rawThreshold)),
		Mode:       string(ModeMAD),
	}
}

// CalculateGaussianThreshold computes mean + k * stdDev.
func CalculateGaussianThreshold(diff *imageutil.GrayMatrix, orig *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, k float64) OutlierStats {
	var origHist [256]int
	var totalValid int
	var sum float64
	var sumSq float64

	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		if orig != nil {
			origHist[orig.Data[i]]++
		}
		totalValid++
		sum += float64(v)
		sumSq += float64(v) * float64(v)
	}

	if totalValid == 0 {
		return OutlierStats{Threshold: 255}
	}

	mean := sum / float64(totalValid)
	variance := (sumSq / float64(totalValid)) - (mean * mean)
	if variance < 0 {
		variance = 0
	}
	stdDev := math.Sqrt(variance)

	half := totalValid / 2
	var accum int
	var origMedian float64
	for v := 0; v < 256; v++ {
		accum += origHist[v]
		if accum >= half {
			origMedian = float64(v)
			break
		}
	}

	rawThreshold := mean + k*stdDev
	if rawThreshold > 255 {
		rawThreshold = 255
	} else if rawThreshold < 0 {
		rawThreshold = 0
	}

	return OutlierStats{
		Mean:       mean,
		StdDev:     stdDev,
		OrigMedian: origMedian,
		Threshold:  uint8(math.Round(rawThreshold)),
		Mode:       string(ModeGaussian),
	}
}

// ApplyThreshold binarizes the Top-Hat difference image against the statistical threshold using AVX2 SIMD.
// CRITICAL FIX: The pixel MUST satisfy both:
// 1. diff >= threshold (statistically anomalous peak)
// 2. orig > origMedian (genuinely warmer than the baseline tissue, not cold background noise!)
func ApplyThreshold(diff *imageutil.GrayMatrix, orig *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, threshold uint8, origMedian uint8) *imageutil.GrayMatrix {
	w, h := diff.Width, diff.Height
	dst := imageutil.NewGrayMatrix(w, h)

	var origData, maskData []uint8
	if orig != nil {
		origData = orig.Data
	}
	if mask != nil {
		maskData = mask.Data
	}

	morphology.ThresholdMaskAVX2(diff.Data, origData, maskData, dst.Data, threshold, origMedian)
	return dst
}
