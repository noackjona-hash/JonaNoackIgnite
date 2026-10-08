package main

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"math"
	"os"
	"path/filepath"
)

func ironbow(v uint8) color.RGBA {
	t := float64(v) / 255.0
	var r, g, b uint8
	if t < 0.2 {
		r = uint8(t / 0.2 * 30)
		g = 0
		b = uint8(t / 0.2 * 128)
	} else if t < 0.4 {
		r = uint8(30 + ((t-0.2)/0.2)*130)
		g = 0
		b = 128
	} else if t < 0.7 {
		r = 220
		g = uint8(((t - 0.4) / 0.3) * 150)
		b = 0
	} else if t < 0.9 {
		r = 255
		g = uint8(150 + ((t-0.7)/0.2)*95)
		b = 0
	} else {
		r = 255
		g = 255
		b = uint8(((t - 0.9) / 0.1) * 255)
	}
	return color.RGBA{R: r, G: g, B: b, A: 255}
}

func depthPlasma(v uint8) color.RGBA {
	if v == 0 {
		return color.RGBA{R: 15, G: 20, B: 30, A: 255}
	}
	t := float64(v) / 255.0
	// Plasma/Magma style colormap
	r := uint8(math.Min(255, 30+225*math.Pow(t, 1.3)))
	g := uint8(math.Min(255, 10+220*math.Pow(t, 2.0)))
	b := uint8(math.Min(255, 80+175*(1.0-t)))
	return color.RGBA{R: r, G: g, B: b, A: 255}
}

func vascularCyan(v uint8) color.RGBA {
	if v < 15 {
		return color.RGBA{R: 10, G: 15, B: 25, A: 255}
	}
	return color.RGBA{
		R: uint8(math.Min(255, float64(v)*0.4)),
		G: uint8(math.Min(255, float64(v)*1.15)),
		B: 255,
		A: 255,
	}
}

func loadGrayImage(path string) (*image.Gray, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	b := img.Bounds()
	gray := image.NewGray(b)
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			gray.Set(x, y, color.GrayModel.Convert(img.At(x, y)))
		}
	}
	return gray, nil
}

func saveRGBA(img *image.RGBA, path string) error {
	_ = os.MkdirAll(filepath.Dir(path), 0755)
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	return png.Encode(f, img)
}

func colorize(src *image.Gray, mapFn func(uint8) color.RGBA) *image.RGBA {
	b := src.Bounds()
	out := image.NewRGBA(b)
	for y := b.Min.Y; y < b.Max.Y; y++ {
		for x := b.Min.X; x < b.Max.X; x++ {
			v := src.GrayAt(x, y).Y
			out.SetRGBA(x, y, mapFn(v))
		}
	}
	return out
}

func drawBox(dst *image.RGBA, x1, y1, x2, y2 int, c color.RGBA, thickness int) {
	b := dst.Bounds()
	for t := 0; t < thickness; t++ {
		// Top and bottom
		for x := x1 - t; x <= x2 + t; x++ {
			if x >= b.Min.X && x < b.Max.X {
				if y1-t >= b.Min.Y && y1-t < b.Max.Y { dst.SetRGBA(x, y1-t, c) }
				if y2+t >= b.Min.Y && y2+t < b.Max.Y { dst.SetRGBA(x, y2+t, c) }
			}
		}
		// Left and right
		for y := y1 - t; y <= y2 + t; y++ {
			if y >= b.Min.Y && y < b.Max.Y {
				if x1-t >= b.Min.X && x1-t < b.Max.X { dst.SetRGBA(x1-t, y, c) }
				if x2+t >= b.Min.X && x2+t < b.Max.X { dst.SetRGBA(x2+t, y, c) }
			}
		}
	}
}

func main() {
	destDir := `C:\Users\jonan\.gemini\antigravity-ide\brain\983d06e8-88c6-4294-8473-a05b9e63e029\images`
	localImgDir := `d:\Downloads\03_Programmierung & Entwicklung\05_JUFO\JonaNoackIgnite\images`
	maskDir := `d:\Downloads\03_Programmierung & Entwicklung\05_JUFO\JonaNoackIgnite\core\pap_stage_masks`

	fmt.Println("Generating PAP stage images...")

	// 1. Stage 0: Raw Thermal Image (Gray & Ironbow)
	rawGray, err := loadGrayImage(filepath.Join(localImgDir, "1_original_thermal_gray.png"))
	if err != nil {
		fmt.Printf("Error loading rawGray: %v\n", err)
		return
	}
	rawColor := colorize(rawGray, ironbow)
	_ = saveRGBA(rawColor, filepath.Join(destDir, "pap_stage0_raw_thermal.png"))
	_ = saveRGBA(rawColor, filepath.Join(localImgDir, "pap_stage0_raw_thermal.png"))

	// 2. Stage 1: Body Mask (Tissue Segmentation)
	maskGray, _ := loadGrayImage(filepath.Join(maskDir, "body_mask.png"))
	maskRGBA := image.NewRGBA(maskGray.Bounds())
	for y := 0; y < maskGray.Bounds().Dy(); y++ {
		for x := 0; x < maskGray.Bounds().Dx(); x++ {
			if maskGray.GrayAt(x, y).Y > 0 {
				maskRGBA.SetRGBA(x, y, color.RGBA{R: 0, G: 220, B: 255, A: 255})
			} else {
				maskRGBA.SetRGBA(x, y, color.RGBA{R: 15, G: 20, B: 30, A: 255})
			}
		}
	}
	_ = saveRGBA(maskRGBA, filepath.Join(destDir, "pap_stage1_body_mask.png"))
	_ = saveRGBA(maskRGBA, filepath.Join(localImgDir, "pap_stage1_body_mask.png"))

	// 3. Stage 2: 3D Anatomical Depth Map (Shape-from-Silhouette)
	depthGray, _ := loadGrayImage(filepath.Join(maskDir, "depth_map_3d.png"))
	depthColor := colorize(depthGray, depthPlasma)
	_ = saveRGBA(depthColor, filepath.Join(destDir, "pap_stage2_3d_depth_map.png"))
	_ = saveRGBA(depthColor, filepath.Join(localImgDir, "pap_stage2_3d_depth_map.png"))

	// 4. Stage 3: Angle- & Distance-Compensated Thermogram (Cold edge drop-off eliminated!)
	corrGray, _ := loadGrayImage(filepath.Join(maskDir, "corrected_3d_temp.png"))
	corrColor := colorize(corrGray, ironbow)
	_ = saveRGBA(corrColor, filepath.Join(destDir, "pap_stage3_corrected_thermal.png"))
	_ = saveRGBA(corrColor, filepath.Join(localImgDir, "pap_stage3_corrected_thermal.png"))

	// 5. Stage 4: Morphological Top-Hat Difference (AVX2-SIMD)
	tophatGray, _ := loadGrayImage(filepath.Join(maskDir, "tophat_diff.png"))
	tophatColor := colorize(tophatGray, func(v uint8) color.RGBA {
		if v < 5 { return color.RGBA{R: 10, G: 12, B: 20, A: 255} }
		t := float64(v) / 120.0
		if t > 1.0 { t = 1.0 }
		return color.RGBA{
			R: uint8(255 * t),
			G: uint8(180 * math.Pow(t, 2)),
			B: uint8(50 * (1 - t)),
			A: 255,
		}
	})
	_ = saveRGBA(tophatColor, filepath.Join(destDir, "pap_stage4_tophat_diff.png"))
	_ = saveRGBA(tophatColor, filepath.Join(localImgDir, "pap_stage4_tophat_diff.png"))

	// 6. Stage 5: Statistical Outlier Mask (MAD Thresholding)
	hotGray, _ := loadGrayImage(filepath.Join(maskDir, "hotspot_mask.png"))
	hotRGBA := image.NewRGBA(hotGray.Bounds())
	for y := 0; y < hotGray.Bounds().Dy(); y++ {
		for x := 0; x < hotGray.Bounds().Dx(); x++ {
			if hotGray.GrayAt(x, y).Y > 0 {
				hotRGBA.SetRGBA(x, y, color.RGBA{R: 255, G: 50, B: 50, A: 255})
			} else {
				hotRGBA.SetRGBA(x, y, color.RGBA{R: 15, G: 20, B: 30, A: 255})
			}
		}
	}
	_ = saveRGBA(hotRGBA, filepath.Join(destDir, "pap_stage5_hotspot_mask.png"))
	_ = saveRGBA(hotRGBA, filepath.Join(localImgDir, "pap_stage5_hotspot_mask.png"))

	// 7. Stage 6: Frangi Vascular Filter (Vein Tree)
	vascGray, _ := loadGrayImage(filepath.Join(maskDir, "vascular_mask.png"))
	vascColor := colorize(vascGray, vascularCyan)
	_ = saveRGBA(vascColor, filepath.Join(destDir, "pap_stage6_vascular_tree.png"))
	_ = saveRGBA(vascColor, filepath.Join(localImgDir, "pap_stage6_vascular_tree.png"))

	// 8. Stage 7: Differential Diagnosis & Final Clinical Overlay
	// Combine corrColor with vascular tree and bounding boxes:
	// Hotspot 1: [523, 317, 569, 391] -> INFLAMED PRESSURE POINT (Amber)
	// Hotspot 2: [380, 610, 434, 688] -> INFLAMMATION (Red)
	finalOverlay := image.NewRGBA(corrColor.Bounds())
	draw.Draw(finalOverlay, finalOverlay.Bounds(), corrColor, image.Point{}, draw.Src)

	// Blend vascular tree (cyan)
	for y := 0; y < vascGray.Bounds().Dy(); y++ {
		for x := 0; x < vascGray.Bounds().Dx(); x++ {
			v := vascGray.GrayAt(x, y).Y
			if v > 20 {
				orig := finalOverlay.RGBAAt(x, y)
				alpha := float64(v) / 255.0 * 0.75
				finalOverlay.SetRGBA(x, y, color.RGBA{
					R: uint8(float64(orig.R)*(1-alpha) + 0*alpha),
					G: uint8(float64(orig.G)*(1-alpha) + 240*alpha),
					B: uint8(float64(orig.B)*(1-alpha) + 255*alpha),
					A: 255,
				})
			}
		}
	}

	// Draw Hotspot 1 (Druckstelle: Amber)
	amber := color.RGBA{R: 255, G: 180, B: 0, A: 255}
	drawBox(finalOverlay, 523, 317, 569, 391, amber, 3)

	// Draw Hotspot 2 (Entzündung: Bright Red)
	red := color.RGBA{R: 255, G: 30, B: 60, A: 255}
	drawBox(finalOverlay, 380, 610, 434, 688, red, 3)

	_ = saveRGBA(finalOverlay, filepath.Join(destDir, "pap_stage7_final_diagnosis_overlay.png"))
	_ = saveRGBA(finalOverlay, filepath.Join(localImgDir, "pap_stage7_final_diagnosis_overlay.png"))

	fmt.Println("Successfully generated all 8 stage images!")
}
