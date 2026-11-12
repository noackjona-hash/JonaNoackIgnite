package morphology

import (
	"runtime"
	"sync"

	"ignite-core/pkg/imageutil"
)

// Morphological opening = Dilation of Erosion.
// Top-Hat = Input - Opening(Input).

func vhgwWorkerCount(span int) int {
	workers := runtime.GOMAXPROCS(0)
	if workers > 8 {
		workers = 8
	}
	if workers < 1 || span < 16 {
		return 1
	}
	if workers > span {
		return span
	}
	return workers
}

func fillNeutralOrMasked(src, mask *imageutil.GrayMatrix, neutral uint8) *imageutil.GrayMatrix {
	dst := src.Clone()
	if mask != nil && len(mask.Data) == len(dst.Data) {
		for i, m := range mask.Data {
			if m == 0 {
				dst.Data[i] = neutral
			}
		}
	}
	return dst
}

// vhgwHorizontal computes exact O(1)-per-pixel 1D horizontal erosion/dilation
// via parallelized van Herk-Gil-Werman prefix/suffix scanning.
func vhgwHorizontal(src, mask *imageutil.GrayMatrix, r int, isDilate, masked bool) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	neutral := uint8(255)
	if isDilate {
		neutral = 0
	}
	if r <= 0 || w <= 0 || h <= 0 {
		if masked {
			return fillNeutralOrMasked(src, mask, neutral)
		}
		return src.Clone()
	}

	dst := imageutil.NewGrayMatrix(w, h)
	k := 2*r + 1
	numBlocks := (w+k-2)/k + 1
	m := numBlocks * k
	workers := vhgwWorkerCount(h)

	var maskData []uint8
	if masked && mask != nil && len(mask.Data) == len(src.Data) {
		maskData = mask.Data
	}

	var wg sync.WaitGroup
	for wk := 0; wk < workers; wk++ {
		yStart := wk * h / workers
		yEnd := (wk + 1) * h / workers
		if yStart >= yEnd {
			continue
		}
		wg.Add(1)
		go func(y0, y1 int) {
			defer wg.Done()
			buf := make([]uint8, m)
			g := make([]uint8, m)
			hBuf := make([]uint8, m)

			for y := y0; y < y1; y++ {
				rowOff := y * w
				if maskData != nil {
					for i := 0; i < r; i++ {
						buf[i] = neutral
					}
					for x := 0; x < w; x++ {
						if maskData[rowOff+x] > 0 {
							buf[r+x] = src.Data[rowOff+x]
						} else {
							buf[r+x] = neutral
						}
					}
					for i := r + w; i < m; i++ {
						buf[i] = neutral
					}
				} else {
					leftPad := src.Data[rowOff]
					rightPad := src.Data[rowOff+w-1]
					for i := 0; i < r; i++ {
						buf[i] = leftPad
					}
					copy(buf[r:r+w], src.Data[rowOff:rowOff+w])
					for i := r + w; i < m; i++ {
						buf[i] = rightPad
					}
				}

				for b := 0; b < numBlocks; b++ {
					bOff := b * k
					cur := buf[bOff]
					g[bOff] = cur
					if isDilate {
						for i := 1; i < k; i++ {
							v := buf[bOff+i]
							if v > cur {
								cur = v
							}
							g[bOff+i] = cur
						}
						end := bOff + k - 1
						cur = buf[end]
						hBuf[end] = cur
						for i := k - 2; i >= 0; i-- {
							v := buf[bOff+i]
							if v > cur {
								cur = v
							}
							hBuf[bOff+i] = cur
						}
					} else {
						for i := 1; i < k; i++ {
							v := buf[bOff+i]
							if v < cur {
								cur = v
							}
							g[bOff+i] = cur
						}
						end := bOff + k - 1
						cur = buf[end]
						hBuf[end] = cur
						for i := k - 2; i >= 0; i-- {
							v := buf[bOff+i]
							if v < cur {
								cur = v
							}
							hBuf[bOff+i] = cur
						}
					}
				}

				for x := 0; x < w; x++ {
					if maskData != nil && maskData[rowOff+x] == 0 {
						dst.Data[rowOff+x] = neutral
						continue
					}
					left := x
					right := x + k - 1
					if left%k == 0 {
						dst.Data[rowOff+x] = hBuf[left]
					} else {
						a := hBuf[left]
						bVal := g[right]
						if isDilate {
							if bVal > a {
								a = bVal
							}
						} else {
							if bVal < a {
								a = bVal
							}
						}
						dst.Data[rowOff+x] = a
					}
				}
			}
		}(yStart, yEnd)
	}
	wg.Wait()
	return dst
}

// vhgwVertical computes exact O(1)-per-pixel 1D vertical erosion/dilation
// via parallel column tiles and AVX2 MinVector/MaxVector row operations.
func vhgwVertical(src, mask *imageutil.GrayMatrix, r int, isDilate, masked bool) *imageutil.GrayMatrix {
	w, h := src.Width, src.Height
	neutral := uint8(255)
	if isDilate {
		neutral = 0
	}
	if r <= 0 || w <= 0 || h <= 0 {
		if masked {
			return fillNeutralOrMasked(src, mask, neutral)
		}
		return src.Clone()
	}

	dst := imageutil.NewGrayMatrix(w, h)
	k := 2*r + 1
	numBlocks := (h+k-2)/k + 1
	m := numBlocks * k
	workers := vhgwWorkerCount(w)

	var maskData []uint8
	if masked && mask != nil && len(mask.Data) == len(src.Data) {
		maskData = mask.Data
	}

	var wg sync.WaitGroup
	for wk := 0; wk < workers; wk++ {
		xStart := wk * w / workers
		xEnd := (wk + 1) * w / workers
		if xStart >= xEnd {
			continue
		}
		wg.Add(1)
		go func(x0, x1 int) {
			defer wg.Done()
			tw := x1 - x0
			buf := make([]uint8, m*tw)
			g := make([]uint8, m*tw)
			hBuf := make([]uint8, m*tw)

			for vy := 0; vy < m; vy++ {
				dstSlice := buf[vy*tw : (vy+1)*tw]
				if maskData != nil {
					if vy < r || vy >= r+h {
						for dx := 0; dx < tw; dx++ {
							dstSlice[dx] = neutral
						}
					} else {
						sy := vy - r
						rowBase := sy*w + x0
						for dx := 0; dx < tw; dx++ {
							if maskData[rowBase+dx] > 0 {
								dstSlice[dx] = src.Data[rowBase+dx]
							} else {
								dstSlice[dx] = neutral
							}
						}
					}
				} else {
					sy := vy - r
					if sy < 0 {
						sy = 0
					} else if sy >= h {
						sy = h - 1
					}
					copy(dstSlice, src.Data[sy*w+x0:sy*w+x1])
				}
			}

			for b := 0; b < numBlocks; b++ {
				bOff := b * k
				firstOff := bOff * tw
				copy(g[firstOff:firstOff+tw], buf[firstOff:firstOff+tw])
				for i := 1; i < k; i++ {
					curOff := (bOff + i) * tw
					prevOff := (bOff + i - 1) * tw
					copy(g[curOff:curOff+tw], g[prevOff:prevOff+tw])
					if isDilate {
						MaxVector(buf[curOff:curOff+tw], g[curOff:curOff+tw])
					} else {
						MinVector(buf[curOff:curOff+tw], g[curOff:curOff+tw])
					}
				}

				endIdx := bOff + k - 1
				endOff := endIdx * tw
				copy(hBuf[endOff:endOff+tw], buf[endOff:endOff+tw])
				for i := k - 2; i >= 0; i-- {
					curOff := (bOff + i) * tw
					nextOff := (bOff + i + 1) * tw
					copy(hBuf[curOff:curOff+tw], hBuf[nextOff:nextOff+tw])
					if isDilate {
						MaxVector(buf[curOff:curOff+tw], hBuf[curOff:curOff+tw])
					} else {
						MinVector(buf[curOff:curOff+tw], hBuf[curOff:curOff+tw])
					}
				}
			}

			for y := 0; y < h; y++ {
				left := y
				right := y + k - 1
				dstRow := dst.Data[y*w+x0 : y*w+x1]
				copy(dstRow, hBuf[left*tw:(left+1)*tw])
				if left%k != 0 {
					if isDilate {
						MaxVector(g[right*tw:(right+1)*tw], dstRow)
					} else {
						MinVector(g[right*tw:(right+1)*tw], dstRow)
					}
				}
				if maskData != nil {
					maskRow := maskData[y*w+x0 : y*w+x1]
					for dx := 0; dx < tw; dx++ {
						if maskRow[dx] == 0 {
							dstRow[dx] = neutral
						}
					}
				}
			}
		}(xStart, xEnd)
	}
	wg.Wait()
	return dst
}

// Erode1DHorizontal computes 1D horizontal erosion along image rows with radius r using O(1) van Herk-Gil-Werman.
func Erode1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwHorizontal(src, nil, r, false, false)
}

// Erode1DVertical computes 1D vertical erosion along image columns with radius r using AVX2 SIMD MinVector + vHGW.
func Erode1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwVertical(src, nil, r, false, false)
}

// Dilate1DHorizontal computes 1D horizontal dilation along image rows with radius r using O(1) van Herk-Gil-Werman.
func Dilate1DHorizontal(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwHorizontal(src, nil, r, true, false)
}

// Dilate1DVertical computes 1D vertical dilation along image columns with radius r using AVX2 SIMD MaxVector + vHGW.
func Dilate1DVertical(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwVertical(src, nil, r, true, false)
}

// Erode1DHorizontalMasked computes 1D horizontal erosion restricted to active mask pixels (neutral=255 outside mask).
func Erode1DHorizontalMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwHorizontal(src, mask, r, false, true)
}

// Erode1DVerticalMasked computes 1D vertical erosion restricted to active mask pixels (neutral=255 outside mask).
func Erode1DVerticalMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwVertical(src, mask, r, false, true)
}

// Dilate1DHorizontalMasked computes 1D horizontal dilation restricted to active mask pixels (neutral=0 outside mask).
func Dilate1DHorizontalMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwHorizontal(src, mask, r, true, true)
}

// Dilate1DVerticalMasked computes 1D vertical dilation restricted to active mask pixels (neutral=0 outside mask).
func Dilate1DVerticalMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	return vhgwVertical(src, mask, r, true, true)
}

// Opening computes separable morphological opening with radius r.
func Opening(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	erodedH := Erode1DHorizontal(src, r)
	eroded := Erode1DVertical(erodedH, r)
	dilatedH := Dilate1DHorizontal(eroded, r)
	opened := Dilate1DVertical(dilatedH, r)
	return opened
}

// OpeningMasked computes separable morphological opening restricted strictly to active tissue mask pixels.
func OpeningMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	erodedH := Erode1DHorizontalMasked(src, mask, r)
	eroded := Erode1DVerticalMasked(erodedH, mask, r)
	dilatedH := Dilate1DHorizontalMasked(eroded, mask, r)
	opened := Dilate1DVerticalMasked(dilatedH, mask, r)
	return opened
}

// CloseBinaryMasked computes separable morphological closing (Erosion of Dilation) inside tissue mask
// to heal narrow MSX optical crease splits (1-4 px) inside confirmed hotspot candidates.
func CloseBinaryMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	if r <= 0 {
		return src.Clone()
	}
	dilatedH := Dilate1DHorizontalMasked(src, mask, r)
	dilated := Dilate1DVerticalMasked(dilatedH, mask, r)
	erodedH := Erode1DHorizontalMasked(dilated, mask, r)
	closed := Erode1DVerticalMasked(erodedH, mask, r)
	if mask != nil && len(mask.Data) == len(closed.Data) {
		for i, m := range mask.Data {
			if m == 0 {
				closed.Data[i] = 0
			}
		}
	}
	return closed
}

// TopHat computes the morphological Top-Hat transform: src - Opening(src).
// Subtraction uses AVX2 SIMD acceleration.
func TopHat(src *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	opened := Opening(src, r)
	dst := imageutil.NewGrayMatrix(src.Width, src.Height)
	SubVector(src.Data, opened.Data, dst.Data)
	return dst
}

// TopHatMasked computes the masked morphological Top-Hat transform inside tissue mask only.
func TopHatMasked(src, mask *imageutil.GrayMatrix, r int) *imageutil.GrayMatrix {
	opened := OpeningMasked(src, mask, r)
	dst := imageutil.NewGrayMatrix(src.Width, src.Height)
	SubVector(src.Data, opened.Data, dst.Data)
	if mask != nil && len(mask.Data) == len(dst.Data) {
		for i, m := range mask.Data {
			if m == 0 {
				dst.Data[i] = 0
			}
		}
	}
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
