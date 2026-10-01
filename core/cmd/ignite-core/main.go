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

func main() {
	mode := flag.String("mode", "cli", "Run mode: 'cli' or 'server'")
	port := flag.Int("port", 54321, "Port for IPC/HTTP server")
	inputPath := flag.String("input", "", "Path to thermal image for CLI analysis")
	outputJSON := flag.String("output", "", "Path to output JSON result")
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

	// CLI Mode
	if *inputPath == "" {
		fmt.Println("IGNITE Core v5.0.0 (Go + x86_64 AVX2)")
		fmt.Println("Usage:")
		fmt.Println("  ignite-core -mode=server -port=54321")
		fmt.Println("  ignite-core -mode=cli -input=\"path/to/image.jpg\" -output=\"result.json\"")
		return
	}

	gray, err := imageutil.LoadImageAsGray(*inputPath)
	if err != nil {
		log.Fatalf("Failed to load image: %v", err)
	}

	cfg := pipeline.DefaultPipelineConfig()
	result := pipeline.Run(gray, cfg)

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
