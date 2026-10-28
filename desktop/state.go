package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"image"
	"image/color"
	"math"
	"time"

	"github.com/lxn/walk"
	"ignite-core/pkg/pipeline"
)

type AppState struct {
	// Bilddaten
	ImagePath     string
	Width         int
	Height        int
	RawGray       []byte
	RawBitmap     *walk.Bitmap
	OverlayBitmap *walk.Bitmap
	LastResult    *pipeline.AnalysisResult

	// Viewport & Interaktion
	Zoom          float64
	PanX          int
	PanY          int
	HoverX        int
	HoverY        int
	HasHover      bool
	ShowCrosshair bool
	ShowFindings  bool
	ShowHUD       bool
	InvertPalette bool
	ActivePalette string
	WindowVal     int
	LevelVal      int

	// Patient & Klinik
	PatientID     string
	PatientAge    string
	PatientSex    string
	PatientRegion string
	PatientStudy  string
	PatientNote   string
	DoctorName    string
	IsSigned      bool
	SignatureHash string
	SignatureTime string

	// Pipeline-Parameter
	ParamK float64
	ParamR float64
	ParamM float64

	// Audit Logs
	AuditLogs []AuditTableItem
}

var GState = &AppState{
	Zoom:          1.0,
	ShowCrosshair: true,
	ShowFindings:  true,
	ShowHUD:       true,
	ActivePalette: "ironbow",
	WindowVal:     255,
	LevelVal:      128,
	PatientID:     "ANON-7F4C82",
	PatientAge:    "68",
	PatientSex:    "männlich",
	PatientRegion: "Füße (bilateral)",
	PatientStudy:  "Plantar Pedis Bilateral (Armstrong-Protokoll)",
	PatientNote:   "V.a. diabetisches Fußsyndrom (DFS) Wagner 0 / Armstrong 3",
	DoctorName:    "Prof. Dr. med. J. Noack (Diabetologie / Angiologie)",
	ParamK:        3.0,
	ParamR:        0.05,
	ParamM:        0.005,
	AuditLogs:     make([]AuditTableItem, 0),
}

func TempOf(raw byte) float64 {
	return 20.0 + 0.1*float64(raw)
}

func RawOf(temp float64) byte {
	v := (temp - 20.0) / 0.1
	if v < 0 {
		return 0
	}
	if v > 255 {
		return 255
	}
	return byte(v)
}

// ── Farbpaletten-LUT (Ironbow, Hot Iron, Medical Jet, Rainbow, Turbo, Gray) ──
func PaletteColor(val byte, pal string, inv bool) color.RGBA {
	v := float64(val) / 255.0
	if inv {
		v = 1.0 - v
	}
	v = math.Max(0.0, math.Min(1.0, v))

	switch pal {
	case "hot_iron":
		// Schwarz -> Dunkelrot -> Orange -> Gelb -> Weiß
		var r, g, b float64
		if v < 0.33 {
			r = v * 3.0
		} else if v < 0.66 {
			r = 1.0
			g = (v - 0.33) * 3.0
		} else {
			r = 1.0
			g = 1.0
			b = (v - 0.66) * 3.0
		}
		return color.RGBA{R: byte(r * 255), G: byte(g * 255), B: byte(b * 255), A: 255}

	case "medical_jet":
		// Dunkelblau -> Cyan -> Grün -> Gelb -> Rot
		r := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-3.0)))
		g := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-2.0)))
		b := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-1.0)))
		return color.RGBA{R: byte(r * 255), G: byte(g * 255), B: byte(b * 255), A: 255}

	case "rainbow":
		hue := (1.0 - v) * 240.0 // 240 (blau) bis 0 (rot)
		r, g, b := hslToRgb(hue, 1.0, 0.5)
		return color.RGBA{R: r, G: g, B: b, A: 255}

	case "grayscale":
		b := byte(v * 255)
		return color.RGBA{R: b, G: b, B: b, A: 255}

	default: // "ironbow" (Klinischer Goldstandard nach FLIR)
		var r, g, b float64
		if v < 0.25 {
			r = 0.1 + v*1.2
			b = 0.5 + v*1.8
		} else if v < 0.5 {
			r = 0.4 + (v-0.25)*2.4
			g = (v - 0.25) * 1.5
			b = 0.95 - (v-0.25)*3.0
		} else if v < 0.75 {
			r = 1.0
			g = 0.375 + (v-0.5)*2.5
			b = (v - 0.5) * 0.5
		} else {
			r = 1.0
			g = 1.0
			b = 0.125 + (v-0.75)*3.5
		}
		return color.RGBA{
			R: byte(math.Max(0, math.Min(255, r*255))),
			G: byte(math.Max(0, math.Min(255, g*255))),
			B: byte(math.Max(0, math.Min(255, b*255))),
			A: 255,
		}
	}
}

func hslToRgb(h, s, l float64) (byte, byte, byte) {
	var r, g, b float64
	if s == 0 {
		r, g, b = l, l, l
	} else {
		var q float64
		if l < 0.5 {
			q = l * (1 + s)
		} else {
			q = l + s - l*s
		}
		p := 2*l - q
		r = hue2rgb(p, q, h/360+1.0/3.0)
		g = hue2rgb(p, q, h/360)
		b = hue2rgb(p, q, h/360-1.0/3.0)
	}
	return byte(r * 255), byte(g * 255), byte(b * 255)
}

func hue2rgb(p, q, t float64) float64 {
	if t < 0 {
		t += 1
	}
	if t > 1 {
		t -= 1
	}
	if t < 1.0/6.0 {
		return p + (q-p)*6*t
	}
	if t < 1.0/2.0 {
		return q
	}
	if t < 2.0/3.0 {
		return p + (q-p)*(2.0/3.0-t)*6
	}
	return p
}

// Erzeugt ein RGBA-Bild aus Roh-Grauwerten mit Window/Level & Farbpalette
func GenerateThermalImage(raw []byte, w, h int, pal string, win, lvl int, inv bool) *image.RGBA {
	img := image.NewRGBA(image.Rect(0, 0, w, h))
	minVal := float64(lvl - win/2)
	maxVal := float64(lvl + win/2)
	span := maxVal - minVal
	if span <= 0 {
		span = 1
	}

	for i, b := range raw {
		norm := (float64(b) - minVal) / span
		if norm < 0 {
			norm = 0
		}
		if norm > 1 {
			norm = 1
		}
		pixVal := byte(norm * 255.0)
		c := PaletteColor(pixVal, pal, inv)
		offset := i * 4
		img.Pix[offset] = c.R
		img.Pix[offset+1] = c.G
		img.Pix[offset+2] = c.B
		img.Pix[offset+3] = 255
	}
	return img
}

func GeneratePseudonym() string {
	b := make([]byte, 4)
	rand.Read(b)
	return "ANON-" + hex.EncodeToString(b)
}

func RecordAudit(action string, hotspots int, risk string, durMs float64) {
	ts := time.Now().Format("2006-01-02 15:04:05")
	prevHash := "INIT_GENESIS_00000000000000000000"
	if len(GState.AuditLogs) > 0 {
		prevHash = GState.AuditLogs[len(GState.AuditLogs)-1].Hash
	}
	data := ts + "|" + GState.PatientID + "|" + action + "|" + prevHash
	h := sha256.Sum256([]byte(data))
	hashStr := hex.EncodeToString(h[:])

	item := AuditTableItem{
		Timestamp: ts,
		PatientID: GState.PatientID,
		Action:    action,
		Hotspots:  hotspots,
		Risk:      risk,
		Duration:  formatFloat(durMs, 1) + " ms",
		Hash:      hashStr,
	}
	GState.AuditLogs = append(GState.AuditLogs, item)
}
