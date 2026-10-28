//go:build wails

package main

import (
	"encoding/base64"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
	"ignite-core/pkg/reconstruction3d"
	"ignite-core/pkg/rules"
)

// RawImageDto carries a raw grayscale thermogram for client-side tools.
type RawImageDto struct {
	Path   string `json:"path"`
	Name   string `json:"name"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
	Raw    string `json:"raw_base64"`
}

// BenchmarkDto summarises a pipeline benchmark run.
type BenchmarkDto struct {
	Runs   int     `json:"runs"`
	MeanMs float64 `json:"mean_ms"`
	MinMs  float64 `json:"min_ms"`
	MaxMs  float64 `json:"max_ms"`
	Fps    float64 `json:"fps"`
	Mpx    float64 `json:"megapixels_per_s"`
}

func findDir(rel string) string {
	for _, c := range []string{"../" + rel, rel, "../../" + rel} {
		if st, err := os.Stat(c); err == nil && st.IsDir() {
			abs, _ := filepath.Abs(c)
			return abs
		}
	}
	return ""
}

// ListTestImages lists all thermograms of the bundled test-data folder (filmstrip).
func (a *App) ListTestImages() []string {
	dir := findDir("test-data")
	if dir == "" {
		return nil
	}
	entries, _ := os.ReadDir(dir)
	var out []string
	for _, e := range entries {
		n := strings.ToLower(e.Name())
		if !e.IsDir() && (strings.HasSuffix(n, ".jpeg") || strings.HasSuffix(n, ".jpg") || strings.HasSuffix(n, ".png")) {
			out = append(out, filepath.Join(dir, e.Name()))
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if len(out[i]) != len(out[j]) {
			return len(out[i]) < len(out[j])
		}
		return out[i] < out[j]
	})
	return out
}

// LoadRawImage loads an image as raw gray PNG without running the pipeline.
func (a *App) LoadRawImage(path string) (*RawImageDto, error) {
	g, err := imageutil.LoadImageAsGray(path)
	if err != nil {
		return nil, err
	}
	return &RawImageDto{Path: path, Name: filepath.Base(path), Width: g.Width, Height: g.Height, Raw: grayMatrixToBase64(g)}, nil
}

// GetThumbnail returns a 160px wide Ironbow thumbnail for the filmstrip.
func (a *App) GetThumbnail(path string) string {
	g, err := imageutil.LoadImageAsGray(path)
	if err != nil {
		return ""
	}
	tw := 160
	th := g.Height * tw / g.Width
	small := imageutil.NewGrayMatrix(tw, th)
	for y := 0; y < th; y++ {
		for x := 0; x < tw; x++ {
			small.Data[y*tw+x] = g.At(x*g.Width/tw, y*g.Height/th)
		}
	}
	return grayMatrixToBase64(small)
}

// SelectSecondImage opens a dialog to pick a contralateral / follow-up image.
func (a *App) SelectSecondImage() (*RawImageDto, error) {
	p, err := a.SelectThermalImage()
	if err != nil || p == "" {
		return nil, err
	}
	return a.LoadRawImage(p)
}

// SaveTextFile opens a save dialog and writes text content (CSV/JSON/HTML/XYZ...).
func (a *App) SaveTextFile(suggested, content string) (string, error) {
	p, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{Title: "Exportieren", DefaultFilename: suggested})
	if err != nil || p == "" {
		return "", err
	}
	if err := os.WriteFile(p, []byte(content), 0644); err != nil {
		return "", err
	}
	a.recordAudit("EXPORT:"+filepath.Ext(p), p, 0, "-", 0, 0)
	return p, nil
}

// SaveDataURL opens a save dialog and writes a base64 data URL (PNG exports).
func (a *App) SaveDataURL(suggested, dataURL string) (string, error) {
	i := strings.Index(dataURL, ",")
	if i < 0 {
		return "", fmt.Errorf("ungültige Bilddaten")
	}
	raw, err := base64.StdEncoding.DecodeString(dataURL[i+1:])
	if err != nil {
		return "", err
	}
	p, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{Title: "Bild exportieren", DefaultFilename: suggested})
	if err != nil || p == "" {
		return "", err
	}
	if err := os.WriteFile(p, raw, 0644); err != nil {
		return "", err
	}
	a.recordAudit("EXPORT:"+filepath.Ext(p), p, 0, "-", 0, 0)
	return p, nil
}

// ExportMesh writes the 3D mesh (obj|ply|stl|xyz) of the last analysis.
func (a *App) ExportMesh(format string) (string, error) {
	if a.lastRes == nil || a.lastRes.DepthMap3D == nil {
		return "", fmt.Errorf("keine 3D-Rekonstruktion vorhanden – zuerst Bild analysieren")
	}
	format = strings.ToLower(format)
	p, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title: "3D-Netz exportieren", DefaultFilename: "ignite_mesh." + format})
	if err != nil || p == "" {
		return "", err
	}
	mesh := reconstruction3d.GenerateMesh(a.lastRes.DepthMap3D, a.lastRes.Corrected3DImage, a.lastRes.BodyMask, 0.6, 2)
	switch format {
	case "obj":
		err = mesh.ExportOBJ(p)
	case "ply":
		err = mesh.ExportPLY(p)
	case "stl":
		err = mesh.ExportSTL(p)
	case "xyz":
		err = mesh.ExportXYZ(p)
	default:
		err = fmt.Errorf("unbekanntes Format %s", format)
	}
	if err == nil {
		a.recordAudit("EXPORT_3D_"+strings.ToUpper(format), p, 0, "-", 0, 0)
	}
	return p, err
}

// GetDefaultLua returns the clinical Lua rule file (armstrong_criteria.lua).
func (a *App) GetDefaultLua() string {
	if d := findDir("rules"); d != "" {
		if b, err := os.ReadFile(filepath.Join(d, "armstrong_criteria.lua")); err == nil {
			return string(b)
		}
	}
	return "-- armstrong_criteria.lua nicht gefunden\n"
}

// ValidateLua checks syntax of a Lua rule script. Empty string = OK.
func (a *App) ValidateLua(src string) string {
	eng := rules.NewLuaRuleEngine()
	defer eng.Close()
	if err := eng.LoadScriptFromString(src); err != nil {
		return err.Error()
	}
	return ""
}

// AnalyzeWithLua re-runs the pipeline with a user-edited Lua rule set.
func (a *App) AnalyzeWithLua(path string, cfg pipeline.PipelineConfig, lua string) (*ThermalResultDto, error) {
	tmp := filepath.Join(os.TempDir(), "ignite_rules_live.lua")
	if err := os.WriteFile(tmp, []byte(lua), 0644); err != nil {
		return nil, err
	}
	defer os.Remove(tmp)
	cfg.LuaScriptPath = tmp
	r, err := a.AnalyzeThermal(path, cfg)
	if err == nil {
		a.recordAudit("LUA_RULES_RELOADED", tmp, r.TotalHotspots, r.HighestRisk, 0, r.Timing.TotalMs)
	}
	return r, err
}

// RunBenchmark measures pipeline latency over n runs on the current (or demo) image.
func (a *App) RunBenchmark(n int) (*BenchmarkDto, error) {
	if n < 1 {
		n = 3
	}
	g := a.lastGray
	if g == nil {
		return nil, fmt.Errorf("zuerst ein Bild laden")
	}
	cfg := pipeline.DefaultPipelineConfig()
	b := &BenchmarkDto{Runs: n, MinMs: 1e18}
	for i := 0; i < n; i++ {
		t := time.Now()
		pipeline.Run(g, cfg)
		ms := float64(time.Since(t).Microseconds()) / 1000.0
		b.MeanMs += ms
		if ms < b.MinMs {
			b.MinMs = ms
		}
		if ms > b.MaxMs {
			b.MaxMs = ms
		}
	}
	b.MeanMs /= float64(n)
	b.Fps = 1000.0 / b.MeanMs
	b.Mpx = float64(g.Width*g.Height) / 1e6 * b.Fps
	a.recordAudit("BENCHMARK", fmt.Sprintf("%d runs", n), 0, "-", 0, b.MeanMs)
	return b, nil
}
