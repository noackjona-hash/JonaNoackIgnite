package imageutil

import (
	"fmt"
	"image"
	"image/color"
	_ "image/jpeg"
	_ "image/png"
	"math"
	"os"
)

// GrayMatrix represents a 2D grayscale image backed by a continuous slice.
type GrayMatrix struct {
	Width  int
	Height int
	Data   []uint8
}

// FloatMatrix represents a 2D single-precision floating point matrix.
type FloatMatrix struct {
	Width  int
	Height int
	Data   []float32
}

// NewGrayMatrix creates a new GrayMatrix of given dimensions.
func NewGrayMatrix(w, h int) *GrayMatrix {
	return &GrayMatrix{
		Width:  w,
		Height: h,
		Data:   make([]uint8, w*h),
	}
}

// NewFloatMatrix creates a new FloatMatrix of given dimensions.
func NewFloatMatrix(w, h int) *FloatMatrix {
	return &FloatMatrix{
		Width:  w,
		Height: h,
		Data:   make([]float32, w*h),
	}
}

// At returns the pixel value at (x, y).
func (m *GrayMatrix) At(x, y int) uint8 {
	if x < 0 || x >= m.Width || y < 0 || y >= m.Height {
		return 0
	}
	return m.Data[y*m.Width+x]
}

// Set sets the pixel value at (x, y).
func (m *GrayMatrix) Set(x, y int, v uint8) {
	if x >= 0 && x < m.Width && y >= 0 && y < m.Height {
		m.Data[y*m.Width+x] = v
	}
}

// Clone creates a deep copy of the GrayMatrix.
func (m *GrayMatrix) Clone() *GrayMatrix {
	cp := NewGrayMatrix(m.Width, m.Height)
	copy(cp.Data, m.Data)
	return cp
}

// SubMatrix extracts a rectangular region [minX, minY, maxX, maxY) from the GrayMatrix.
func (m *GrayMatrix) SubMatrix(minX, minY, maxX, maxY int) *GrayMatrix {
	if minX < 0 {
		minX = 0
	}
	if minY < 0 {
		minY = 0
	}
	if maxX > m.Width {
		maxX = m.Width
	}
	if maxY > m.Height {
		maxY = m.Height
	}
	subW := maxX - minX
	subH := maxY - minY
	if subW <= 0 || subH <= 0 {
		return NewGrayMatrix(1, 1)
	}

	sub := NewGrayMatrix(subW, subH)
	for y := 0; y < subH; y++ {
		srcOff := (minY+y)*m.Width + minX
		dstOff := y * subW
		copy(sub.Data[dstOff:dstOff+subW], m.Data[srcOff:srcOff+subW])
	}
	return sub
}

// ToFloat converts uint8 matrix to float32 matrix normalized to [0, 255] or [0, 1].
func (m *GrayMatrix) ToFloat() *FloatMatrix {
	fm := NewFloatMatrix(m.Width, m.Height)
	for i, v := range m.Data {
		fm.Data[i] = float32(v)
	}
	return fm
}

// At returns the float value at (x, y).
func (m *FloatMatrix) At(x, y int) float32 {
	if x < 0 || x >= m.Width || y < 0 || y >= m.Height {
		return 0
	}
	return m.Data[y*m.Width+x]
}

// Set sets the float value at (x, y).
func (m *FloatMatrix) Set(x, y int, v float32) {
	if x >= 0 && x < m.Width && y >= 0 && y < m.Height {
		m.Data[y*m.Width+x] = v
	}
}

// Clone creates a deep copy of the FloatMatrix.
func (m *FloatMatrix) Clone() *FloatMatrix {
	cp := NewFloatMatrix(m.Width, m.Height)
	copy(cp.Data, m.Data)
	return cp
}

// MinMax returns minimum and maximum values in the float matrix.
func (m *FloatMatrix) MinMax() (float32, float32) {
	if len(m.Data) == 0 {
		return 0, 0
	}
	minVal, maxVal := m.Data[0], m.Data[0]
	for _, v := range m.Data {
		if v < minVal {
			minVal = v
		}
		if v > maxVal {
			maxVal = v
		}
	}
	return minVal, maxVal
}

// ToGray converts float32 matrix to uint8 matrix with min-max stretching.
func (m *FloatMatrix) ToGray() *GrayMatrix {
	return m.ToGrayMasked(nil)
}

// ToGrayMasked converts float32 matrix to uint8 matrix, restricting min-max stretching to masked pixels
func (m *FloatMatrix) ToGrayMasked(mask *GrayMatrix) *GrayMatrix {
	gm := NewGrayMatrix(m.Width, m.Height)
	var maxVal float32 = 0
	for i, v := range m.Data {
		if mask != nil && mask.Data[i] == 0 {
			continue
		}
		if v > maxVal {
			maxVal = v
		}
	}
	if maxVal <= 1e-6 {
		return gm
	}
	for i, v := range m.Data {
		if mask != nil && mask.Data[i] == 0 {
			gm.Data[i] = 0
			continue
		}
		norm := v / maxVal
		if norm < 0 {
			norm = 0
		} else if norm > 1 {
			norm = 1
		}
		gm.Data[i] = uint8(math.Round(float64(norm * 255.0)))
	}
	return gm
}


// LoadImageAsGray loads any JPEG/PNG image and converts it into a grayscale GrayMatrix.
func LoadImageAsGray(filePath string) (*GrayMatrix, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to open image: %w", err)
	}
	defer file.Close()

	img, _, err := image.Decode(file)
	if err != nil {
		return nil, fmt.Errorf("failed to decode image: %w", err)
	}

	bounds := img.Bounds()
	w, h := bounds.Dx(), bounds.Dy()
	mat := NewGrayMatrix(w, h)

	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			c := color.GrayModel.Convert(img.At(bounds.Min.X+x, bounds.Min.Y+y)).(color.Gray)
			mat.Set(x, y, c.Y)
		}
	}
	return mat, nil
}
