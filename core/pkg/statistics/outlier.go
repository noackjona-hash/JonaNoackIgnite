package statistics

import (
	"math"

	"ignite-core/pkg/imageutil"
)

// ThresholdMode selects the statistical model.
type ThresholdMode string

const (
	ModeGaussian ThresholdMode = "GAUSSIAN"
	ModeMAD      ThresholdMode = "MAD"
)

// OutlierStats holds intermediate statistical distribution values.
type OutlierStats struct {
	Mean      float64 `json:"mean"`
	StdDev    float64 `json:"std_dev"`
	Median    float64 `json:"median"`
	MAD       float64 `json:"mad"`
	Threshold uint8   `json:"threshold"`
	Mode      string  `json:"mode"`
}

// CalculateMADThreshold computes Median and MAD in O(N) using histogram bins.
func CalculateMADThreshold(diff *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, k float64) OutlierStats {
	var hist [256]int
	var totalValid int
	var sum float64
	var sumSq float64

	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		hist[v]++
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

	// O(N) Histogram-based median:
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
		Mean:      mean,
		StdDev:    stdDev,
		Median:    median,
		MAD:       mad,
		Threshold: uint8(math.Round(rawThreshold)),
		Mode:      string(ModeMAD),
	}
}

// CalculateGaussianThreshold computes mean + k * stdDev.
func CalculateGaussianThreshold(diff *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, k float64) OutlierStats {
	var totalValid int
	var sum float64
	var sumSq float64

	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
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

	rawThreshold := mean + k*stdDev
	if rawThreshold > 255 {
		rawThreshold = 255
	} else if rawThreshold < 0 {
		rawThreshold = 0
	}

	return OutlierStats{
		Mean:      mean,
		StdDev:    stdDev,
		Threshold: uint8(math.Round(rawThreshold)),
		Mode:      string(ModeGaussian),
	}
}

// ApplyThreshold binarizes the Top-Hat difference image against the statistical threshold.
func ApplyThreshold(diff *imageutil.GrayMatrix, mask *imageutil.GrayMatrix, threshold uint8) *imageutil.GrayMatrix {
	w, h := diff.Width, diff.Height
	dst := imageutil.NewGrayMatrix(w, h)

	for i, v := range diff.Data {
		if mask != nil && mask.Data[i] == 0 {
			dst.Data[i] = 0
			continue
		}
		if v >= threshold {
			dst.Data[i] = 255
		} else {
			dst.Data[i] = 0
		}
	}
	return dst
}
