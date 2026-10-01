package morphology

import (
	"sync"

	"ignite-core/pkg/imageutil"
)

// Morphological opening = Dilation of Erosion.
// Top-Hat = Input - Opening(Input).

// Erode1DHorizontal computes 1D horizontal erosion along image rows with radius r.
func Erode1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewGrayMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		startRow := wid * chunk
		endRow := startRow + chunk
		if endRow > h {
			endRow = h
		}
		if startRow >= endRow {
			continue
		}

		wg.Add(1)
		go func(r0, r1 int) {
			defer wg.Done()
			for y := r0; y < r1; y++ {
				rowOffset := y * w
				for x := 0; x < w; x++ {
					minVal := uint8(255)
					xMin := x - r
					if xMin < 0 {
						xMin = 0
					}
					xMax := x + r
					if xMax >= w {
						xMax = w - 1
					}
					for kx := xMin; kx <= xMax; kx++ {
						v := src.Data[rowOffset+kx]
						if v < minVal {
							minVal = v
						}
					}
					dst.Data[rowOffset+x] = minVal
				}
			}
		}(startRow, endRow)
	}
	wg.Wait()
	return dst
}

// Erode1DVertical computes 1D vertical erosion along image columns with radius r.
func Erode1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewGrayMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		startRow := wid * chunk
		endRow := startRow + chunk
		if endRow > h {
			endRow = h
		}
		if startRow >= endRow {
			continue
		}

		wg.Add(1)
		go func(r0, r1 int) {
			defer wg.Done()
			for y := r0; y < r1; y++ {
				yMin := y - r
				if yMin < 0 {
					yMin = 0
				}
				yMax := y + r
				if yMax >= h {
					yMax = h - 1
				}
				rowOffset := y * w
				for x := 0; x < w; x++ {
					minVal := uint8(255)
					for ky := yMin; ky <= yMax; ky++ {
						v := src.Data[ky*w+x]
						if v < minVal {
							minVal = v
						}
					}
					dst.Data[rowOffset+x] = minVal
				}
			}
		}(startRow, endRow)
	}
	wg.Wait()
	return dst
}

// Dilate1DHorizontal computes 1D horizontal dilation along image rows with radius r.
func Dilate1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewGrayMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		startRow := wid * chunk
		endRow := startRow + chunk
		if endRow > h {
			endRow = h
		}
		if startRow >= endRow {
			continue
		}

		wg.Add(1)
		go func(r0, r1 int) {
			defer wg.Done()
			for y := r0; y < r1; y++ {
				rowOffset := y * w
				for x := 0; x < w; x++ {
					maxVal := uint8(0)
					xMin := x - r
					if xMin < 0 {
						xMin = 0
					}
					xMax := x + r
					if xMax >= w {
						xMax = w - 1
					}
					for kx := xMin; kx <= xMax; kx++ {
						v := src.Data[rowOffset+kx]
						if v > maxVal {
							maxVal = v
						}
					}
					dst.Data[rowOffset+x] = maxVal
				}
			}
		}(startRow, endRow)
	}
	wg.Wait()
	return dst
}

// Dilate1DVertical computes 1D vertical dilation along image columns with radius r.
func Dilate1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	dst := imageutil.NewGrayMatrix(w, h)
	var wg sync.WaitGroup
	workers := 8
	chunk := (h + workers - 1) / workers

	for wid := 0; wid < workers; wid++ {
		startRow := wid * chunk
		endRow := startRow + chunk
		if endRow > h {
			endRow = h
		}
		if startRow >= endRow {
			continue
		}

		wg.Add(1)
		go func(r0, r1 int) {
			defer wg.Done()
			for y := r0; y < r1; y++ {
				yMin := y - r
				if yMin < 0 {
					yMin = 0
				}
				yMax := y + r
				if yMax >= h {
					yMax = h - 1
				}
				rowOffset := y * w
				for x := 0; x < w; x++ {
					maxVal := uint8(0)
					for ky := yMin; ky <= yMax; ky++ {
						v := src.Data[ky*w+x]
						if v > maxVal {
							maxVal = v
						}
					}
					dst.Data[rowOffset+x] = maxVal
				}
			}
		}(startRow, endRow)
	}
	wg.Wait()
	return dst
}

// Opening computes separable morphological opening with radius r.
func Opening(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	erodedH := Erode1DHorizontal(src, r)
	eroded := Erode1DVertical(erodedH, r)
	dilatedH := Dilate1DHorizontal(eroded, r)
	opened := Dilate1DVertical(dilatedH, r)
	return opened
}

// TopHat computes the morphological Top-Hat transform: src - Opening(src).
// Subtraction uses AVX2 SIMD acceleration.
func TopHat(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	opened := Opening(src, r)
	dst := imageutil.NewGrayMatrix(src.Width, src.Height)
	SubVector(src.Data, opened.Data, dst.Data)
	return dst
}

// DynamicKernelRadius computes kernel radius based on image resolution (e.g. 5% of min dimension).
func DynamicKernelRadius(width, height int, factor float64) int {
	minDim := width
	if height < minDim {
		minDim = height
	}
	raw := int(float64(minDim) * factor)
	if raw < 1 {
		raw = 1
	}
	return raw
}
