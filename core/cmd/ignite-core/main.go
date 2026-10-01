package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
	"ignite-core/pkg/symmetry"
)

// Request payloads
type AnalyzeRequest struct {
	ImagePath string                  `json:"image_path"`
	Config    pipeline.PipelineConfig `json:"config"`
	OutputDir string                  `json:"output_dir"`
}

type SymmetryRequest struct {
	LeftImagePath  string  `json:"left_image_path"`
	RightImagePath string  `json:"right_image_path"`
	ThresholdDelta float32 `json:"threshold_delta"`
}

func saveGrayAsPNG(mat *imageutil.GrayMatrix, outPath string) error {
	img := image.NewGray(image.Rect(0, 0, mat.Width, mat.Height))
	for y := 0; y < mat.Height; y++ {
		for x := 0; x < mat.Width; x++ {
			img.SetGray(x, y, color.Gray{Y: mat.At(x, y)})
		}
	}
	f, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer f.Close()
	return png.Encode(f, img)
}

func handleAnalyze(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req AnalyzeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}

	gray, err := imageutil.LoadImageAsGray(req.ImagePath)
	if err != nil {
		http.Error(w, "Failed to load image: "+err.Error(), http.StatusInternalServerError)
		return
	}

	res := pipeline.Run(gray, req.Config)

	// Save output masks to disk if output dir specified
	if req.OutputDir != "" {
		_ = os.MkdirAll(req.OutputDir, 0755)
		if res.BodyMask != nil {
			_ = saveGrayAsPNG(res.BodyMask, filepath.Join(req.OutputDir, "body_mask.png"))
		}
		if res.TopHatDiff != nil {
			_ = saveGrayAsPNG(res.TopHatDiff, filepath.Join(req.OutputDir, "tophat_diff.png"))
		}
		if res.HotspotMask != nil {
			_ = saveGrayAsPNG(res.HotspotMask, filepath.Join(req.OutputDir, "hotspot_mask.png"))
		}
		if res.VascularMask != nil {
			_ = saveGrayAsPNG(res.VascularMask, filepath.Join(req.OutputDir, "vascular_mask.png"))
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(res)
}

func handleSymmetry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req SymmetryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}

	leftGray, err := imageutil.LoadImageAsGray(req.LeftImagePath)
	if err != nil {
		http.Error(w, "Failed to load left image: "+err.Error(), http.StatusBadRequest)
		return
	}
	rightGray, err := imageutil.LoadImageAsGray(req.RightImagePath)
	if err != nil {
		http.Error(w, "Failed to load right image: "+err.Error(), http.StatusBadRequest)
		return
	}

	thresh := req.ThresholdDelta
	if thresh <= 0 {
		thresh = 15.0
	}

	symRes := symmetry.AnalyzeBilateralSymmetry(leftGray, rightGray, nil, nil, thresh)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(symRes)
}

func handleStatus(w http.ResponseWriter, r *http.Request) {
	status := map[string]interface{}{
		"status":      "ONLINE",
		"engine":      "ignite-core",
		"version":     "5.0.0",
		"arch":        runtime.GOARCH,
		"os":          runtime.GOOS,
		"num_cpu":     runtime.NumCPU(),
		"server_time": time.Now().Format(time.RFC3339),
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

func parseROI(s string) (int, int, int, int, bool) {
	if s == "" {
		return 0, 0, 0, 0, false
	}
	var x1, y1, x2, y2 int
	n, err := fmt.Sscanf(s, "%d,%d,%d,%d", &x1, &y1, &x2, &y2)
	if err != nil || n != 4 || x2 <= x1 || y2 <= y1 {
		return 0, 0, 0, 0, false
	}
	return x1, y1, x2, y2, true
}

func pasteMask(dst, src *imageutil.GrayMatrix, ox, oy int) {
	for y := 0; y < src.Height; y++ {
		dy := oy + y
		if dy < 0 || dy >= dst.Height {
			continue
		}
		for x := 0; x < src.Width; x++ {
			dx := ox + x
			if dx >= 0 && dx < dst.Width {
				dst.Set(dx, dy, src.At(x, y))
			}
		}
	}
}

func main() {
	mode := flag.String("mode", "cli", "Run mode: 'cli', 'server', 'symmetry', 'split-symmetry'")
	port := flag.Int("port", 54321, "Port for IPC/HTTP server")
	inputPath := flag.String("input", "", "Path to thermal image for CLI analysis")
	outputJSON := flag.String("output", "", "Path to output JSON result")
	maskDir := flag.String("maskdir", "", "Directory to save output masks (vascular_mask.png, etc.)")
	roiStr := flag.String("roi", "", "ROI bounding box: minX,minY,maxX,maxY")
	kFactor := flag.Float64("k", 2.5, "Outlier threshold multiplier")
	kernelFactor := flag.Float64("kernel", 0.05, "Top-Hat kernel size factor")
	threshMode := flag.String("threshmode", "MAD", "Threshold mode: MAD or GAUSSIAN")
	enableVascular := flag.Bool("vascular", true, "Enable Frangi vascular filter")
	enablePerfusion := flag.Bool("perfusion", true, "Enable longitudinal perfusion profiling")
	leftPath := flag.String("left", "", "Path to left image for bilateral symmetry")
	rightPath := flag.String("right", "", "Path to right image for bilateral symmetry")
	threshDelta := flag.Float64("threshdelta", 15.0, "Threshold delta for bilateral symmetry")
	flag.Parse()

	if *mode == "server" {
		http.HandleFunc("/api/status", handleStatus)
		http.HandleFunc("/api/analyze", handleAnalyze)
		http.HandleFunc("/api/symmetry", handleSymmetry)

		addr := fmt.Sprintf("127.0.0.1:%d", *port)
		log.Printf("[IGNITE-CORE v5.0.0] High-Performance Engine listening on http://%s", addr)
		if err := http.ListenAndServe(addr, nil); err != nil {
			log.Fatalf("Server failed: %v", err)
		}
		return
	}

	if *mode == "split-symmetry" {
		if *inputPath == "" {
			log.Fatalf("split-symmetry requires -input")
		}
		gray, err := imageutil.LoadImageAsGray(*inputPath)
		if err != nil {
			log.Fatalf("Failed to load image: %v", err)
		}
		midX := gray.Width / 2
		leftHalf := gray.SubMatrix(0, 0, midX, gray.Height)
		rightHalf := gray.SubMatrix(midX, 0, gray.Width, gray.Height)
		symRes := symmetry.AnalyzeBilateralSymmetry(leftHalf, rightHalf, nil, nil, float32(*threshDelta))
		data, err := json.MarshalIndent(symRes, "", "  ")
		if err != nil {
			log.Fatalf("Serialization failed: %v", err)
		}
		if *outputJSON != "" {
			_ = os.WriteFile(*outputJSON, data, 0644)
		} else {
			fmt.Println(string(data))
		}
		return
	}

	if *mode == "symmetry" {
		if *leftPath == "" || *rightPath == "" {
			log.Fatalf("symmetry requires -left and -right paths")
		}
		leftGray, err := imageutil.LoadImageAsGray(*leftPath)
		if err != nil {
			log.Fatalf("Failed to load left image: %v", err)
		}
		rightGray, err := imageutil.LoadImageAsGray(*rightPath)
		if err != nil {
			log.Fatalf("Failed to load right image: %v", err)
		}
		symRes := symmetry.AnalyzeBilateralSymmetry(leftGray, rightGray, nil, nil, float32(*threshDelta))
		data, err := json.MarshalIndent(symRes, "", "  ")
		if err != nil {
			log.Fatalf("Serialization failed: %v", err)
		}
		if *outputJSON != "" {
			_ = os.WriteFile(*outputJSON, data, 0644)
		} else {
			fmt.Println(string(data))
		}
		return
	}

	// CLI Mode
	if *inputPath == "" {
		fmt.Println("IGNITE Core v5.0.0 (Go + x86_64 AVX2)")
		fmt.Println("Usage:")
		fmt.Println("  ignite-core -mode=server -port=54321")
		fmt.Println("  ignite-core -mode=cli -input=\"path/to/image.jpg\" -output=\"result.json\"")
		fmt.Println("  ignite-core -mode=split-symmetry -input=\"dual_feet.jpg\" -output=\"sym.json\"")
		return
	}

	gray, err := imageutil.LoadImageAsGray(*inputPath)
	if err != nil {
		log.Fatalf("Failed to load image: %v", err)
	}

	fullW, fullH := gray.Width, gray.Height
	rx1, ry1, rx2, ry2, hasROI := parseROI(*roiStr)
	imgToProcess := gray
	if hasROI {
		imgToProcess = gray.SubMatrix(rx1, ry1, rx2, ry2)
	}

	cfg := pipeline.DefaultPipelineConfig()
	cfg.KFactor = *kFactor
	cfg.KernelFactor = *kernelFactor
	cfg.ThresholdMode = *threshMode
	cfg.RunVascularMap = *enableVascular
	cfg.RunPerfusion = *enablePerfusion

	result := pipeline.Run(imgToProcess, cfg)

	if hasROI {
		for i := range result.Hotspots {
			result.Hotspots[i].Region.CenterX += rx1
			result.Hotspots[i].Region.CenterY += ry1
			result.Hotspots[i].Region.BoundingBox[0] += rx1
			result.Hotspots[i].Region.BoundingBox[1] += ry1
			result.Hotspots[i].Region.BoundingBox[2] += rx1
			result.Hotspots[i].Region.BoundingBox[3] += ry1
		}
	}

	if *maskDir != "" {
		_ = os.MkdirAll(*maskDir, 0755)
		if hasROI {
			if result.BodyMask != nil {
				fullMask := imageutil.NewGrayMatrix(fullW, fullH)
				pasteMask(fullMask, result.BodyMask, rx1, ry1)
				_ = saveGrayAsPNG(fullMask, filepath.Join(*maskDir, "body_mask.png"))
			}
			if result.TopHatDiff != nil {
				fullDiff := imageutil.NewGrayMatrix(fullW, fullH)
				pasteMask(fullDiff, result.TopHatDiff, rx1, ry1)
				_ = saveGrayAsPNG(fullDiff, filepath.Join(*maskDir, "tophat_diff.png"))
			}
			if result.HotspotMask != nil {
				fullHot := imageutil.NewGrayMatrix(fullW, fullH)
				pasteMask(fullHot, result.HotspotMask, rx1, ry1)
				_ = saveGrayAsPNG(fullHot, filepath.Join(*maskDir, "hotspot_mask.png"))
			}
			if result.VascularMask != nil {
				fullVasc := imageutil.NewGrayMatrix(fullW, fullH)
				pasteMask(fullVasc, result.VascularMask, rx1, ry1)
				_ = saveGrayAsPNG(fullVasc, filepath.Join(*maskDir, "vascular_mask.png"))
			}
		} else {
			if result.BodyMask != nil {
				_ = saveGrayAsPNG(result.BodyMask, filepath.Join(*maskDir, "body_mask.png"))
			}
			if result.TopHatDiff != nil {
				_ = saveGrayAsPNG(result.TopHatDiff, filepath.Join(*maskDir, "tophat_diff.png"))
			}
			if result.HotspotMask != nil {
				_ = saveGrayAsPNG(result.HotspotMask, filepath.Join(*maskDir, "hotspot_mask.png"))
			}
			if result.VascularMask != nil {
				_ = saveGrayAsPNG(result.VascularMask, filepath.Join(*maskDir, "vascular_mask.png"))
			}
		}
	}

	data, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		log.Fatalf("Failed to serialize result: %v", err)
	}

	if *outputJSON != "" {
		if err := os.WriteFile(*outputJSON, data, 0644); err != nil {
			log.Fatalf("Failed to write output JSON: %v", err)
		}
		fmt.Printf("Analysis complete. Saved to %s (Total time: %.2f ms, Hotspots: %d)\n", *outputJSON, result.Timing.TotalMs, result.TotalHotspots)
	} else {
		fmt.Println(string(data))
	}
}
