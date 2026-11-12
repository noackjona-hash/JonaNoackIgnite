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

type ToolMode int

const (
	ToolReticle        ToolMode = iota // Spot Probe / Fadenkreuz
	ToolRuler                          // Distanz & Gradient (K/cm)
	ToolRectROI                        // Rechteck-ROI mit kontralateraler Spiegelung
	ToolCircleROI                      // Kreis-ROI mit Entzündungs-Halo
	ToolPolygonROI                     // NEU: Polygon-Planimetrie (Wundrand & Fläche)
	ToolGoniometer                     // 3-Punkt Orthopädischer Winkel
	ToolProfileLine                    // A-B Schnittlinie für Live-Diagramm
	ToolCrosshairSigma                 // Orthogonales Entzündungs-Kreuz mit Standardabweichung (μ ± σ)
	ToolThermalPin                     // NEU: Multi-Pin Dauersonden (P1, P2, P3...)
	ToolMagnifier                      // NEU: 4x Radiometrische Subpixel-Lupe
)

type MeasurementItem struct {
	ID         int
	Type       string        // "Lineal", "Rechteck-ROI", "Kreis-ROI", "Polygon-ROI", "Goniometer", "Schnittlinie", "Spot", "Pin-Sonde"
	Label      string        // z.B. "Distanz M1"
	Points     []image.Point // Bildkoordinaten
	ValueStr   string        // Primärer Wert (z.B. "42.5 mm", "32.4°", "Mean 33.1 °C")
	DetailsStr string        // Zusatzmetrik (z.B. "ΔT 3.1 K · G 0.7 K/cm", "Fläche 12.4 cm²")
	Risk       string        // "NORMAL", "MODERATE", "CRITICAL"
}

type ThermalPinItem struct {
	ID      int
	Label   string
	Pt      image.Point
	TempC   float64
	ContraC float64
	DeltaT  float64
	Local3  float64 // 3x3 Nachbarschaftsmittel
	Zone    string
	Risk    string
}

type BatchResultItem struct {
	Index      int
	Filename   string
	FullPath   string
	PeakTempC  float64
	MaxDeltaT  float64
	MeanTempC  float64
	StdDevK    float64
	Hotspots   int
	Risk       string
	DurationMs float64
}

type AppState struct {
	// Bilddaten
	ImagePath     string
	Width         int
	Height        int
	RawGray       []byte
	RawBitmap     *walk.Bitmap
	OverlayBitmap *walk.Bitmap
	DeltaTBitmap  *walk.Bitmap
	TopHatBitmap  *walk.Bitmap
	LastResult    *pipeline.AnalysisResult
	LastRunMs     float64

	// Viewport & WinUI 3 Interaktion
	Zoom               float64
	PanX               int
	PanY               int
	HoverX             int
	HoverY             int
	HasHover           bool
	ShowCrosshair      bool
	ShowFindings       bool
	ShowHUD            bool
	ShowCurtainWipe    bool
	CurtainRatio       float64
	IsDraggingCurtain  bool
	ShowMagnifier      bool
	MagnifierZoom      float64
	ShowIsoContours    bool
	ShowAngiosomeGrid  bool
	RightViewMode      string // "overlay", "deltat", "tophat"
	InvertPalette      bool
	ActivePalette      string
	WindowVal          int
	LevelVal           int

	// Werkzeuge & Messfunktionen
	ActiveTool        ToolMode
	Measurements      []*MeasurementItem
	PinProbes         []ThermalPinItem
	NextMeasureID     int
	NextPinID         int
	ActivePoints      []image.Point
	IsDrawing         bool
	CustomProfile     []float64
	CustomProfileRef  []float64
	CustomProfileName string
	ShowIsotherm      bool
	ShowArmstrongIso  bool
	IsothermTemp      float64

	// Entzündungs-Kreuzprofil & Standardabweichung
	HasCrosshairPoint bool
	CrosshairPoint    image.Point
	CrosshairRadius   int
	CrosshairCustom   bool
	CrosshairMetrics  interface{} // *CrosshairMetrics

	// 3D Topografie-Renderer (Tab 4)
	RotAzimuth      float64
	RotElevation    float64
	HeightScale3D   float64
	Show3DWireframe bool
	Show3DCutPlane  bool

	// Serien-Browser & Longitudinal-Verlauf (Tab 6)
	TestImageFiles  []string
	CurrentImageIdx int
	BatchResults    []*BatchResultItem

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
	Zoom:              1.0,
	ShowCrosshair:     true,
	ShowFindings:      true,
	ShowHUD:           true,
	ShowCurtainWipe:   false,
	CurtainRatio:      0.50,
	ShowMagnifier:     false,
	MagnifierZoom:     3.0,
	ShowIsoContours:   false,
	ShowAngiosomeGrid: false,
	RightViewMode:     "overlay",
	ActivePalette:     "ironbow",
	WindowVal:         255,
	LevelVal:          128,
	ActiveTool:        ToolReticle,
	Measurements:      make([]*MeasurementItem, 0),
	PinProbes:         make([]ThermalPinItem, 0),
	IsothermTemp:      34.0,
	RotAzimuth:        38.0,
	RotElevation:      42.0,
	HeightScale3D:     1.8,
	Show3DWireframe:   true,
	Show3DCutPlane:    true,
	CurrentImageIdx:   0,
	BatchResults:      make([]*BatchResultItem, 0),
	PatientID:         "ANON-7F4C82",
	PatientAge:        "68",
	PatientSex:        "männlich",
	PatientRegion:     "Füße (bilateral)",
	PatientStudy:      "Plantar Pedis Bilateral (Armstrong-Protokoll)",
	PatientNote:       "V.a. diabetisches Fußsyndrom (DFS) Wagner 0 / IWGDF Risikoklasse 3",
	DoctorName:        "Prof. Dr. med. J. Noack (Diabetologie / Angiologie)",
	ParamK:            3.0,
	ParamR:            0.05,
	ParamM:            0.005,
	AuditLogs:         make([]AuditTableItem, 0),
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

// ── Farbpaletten-LUT (Ironbow, Turbo, Inferno, Viridis, Arctic, Hot Iron, Medical Jet, Rainbow, Gray) ──
func PaletteColor(val byte, pal string, inv bool) color.RGBA {
	v := float64(val) / 255.0
	if inv {
		v = 1.0 - v
	}
	v = math.Max(0.0, math.Min(1.0, v))

	switch pal {
	case "hot_iron":
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
		r := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-3.0)))
		g := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-2.0)))
		b := math.Max(0.0, math.Min(1.0, 1.5-math.Abs(4.0*v-1.0)))
		return color.RGBA{R: byte(r * 255), G: byte(g * 255), B: byte(b * 255), A: 255}

	case "viridis":
		// Perzeptuell uniforme wissenschaftliche Palette (Violett -> Blau -> Smaragdgrün -> Sonnengelb)
		var r, g, b float64
		if v < 0.33 {
			t := v / 0.33
			r = 0.26*(1-t) + 0.19*t
			g = 0.00*(1-t) + 0.40*t
			b = 0.33*(1-t) + 0.55*t
		} else if v < 0.66 {
			t := (v - 0.33) / 0.33
			r = 0.19*(1-t) + 0.21*t
			g = 0.40*(1-t) + 0.72*t
			b = 0.55*(1-t) + 0.47*t
		} else {
			t := (v - 0.66) / 0.34
			r = 0.21*(1-t) + 0.99*t
			g = 0.72*(1-t) + 0.91*t
			b = 0.47*(1-t) + 0.14*t
		}
		return color.RGBA{
			R: byte(math.Max(0, math.Min(255, r*255))),
			G: byte(math.Max(0, math.Min(255, g*255))),
			B: byte(math.Max(0, math.Min(255, b*255))),
			A: 255,
		}

	case "arctic_medical":
		// Klinische Divergenz-Palette (Eisblau -> Cyan -> Neutralweiß -> Koralle -> Karmesinrot)
		var r, g, b float64
		if v < 0.45 {
			t := v / 0.45
			r = 0.05 + 0.85*t
			g = 0.25 + 0.70*t
			b = 0.65 + 0.35*t
		} else if v < 0.55 {
			r, g, b = 0.95, 0.96, 0.98
		} else {
			t := (v - 0.55) / 0.45
			r = 0.95 + 0.05*t
			g = 0.90 * (1.0 - t*0.85)
			b = 0.90 * (1.0 - t*0.90)
		}
		return color.RGBA{
			R: byte(math.Max(0, math.Min(255, r*255))),
			G: byte(math.Max(0, math.Min(255, g*255))),
			B: byte(math.Max(0, math.Min(255, b*255))),
			A: 255,
		}

	case "turbo":
		var r, g, b float64
		if v < 0.25 {
			r = 0.15 + v*0.8
			g = v * 2.0
			b = 0.5 + v*2.0
		} else if v < 0.5 {
			r = 0.1 + (v-0.25)*1.8
			g = 0.5 + (v-0.25)*2.0
			b = 1.0 - (v-0.25)*4.0
		} else if v < 0.75 {
			r = 0.55 + (v-0.5)*1.8
			g = 1.0 - (v-0.5)*1.4
			b = 0.0
		} else {
			r = 1.0
			g = 0.65 - (v-0.75)*2.6
			b = (v - 0.75) * 0.8
		}
		return color.RGBA{
			R: byte(math.Max(0, math.Min(255, r*255))),
			G: byte(math.Max(0, math.Min(255, g*255))),
			B: byte(math.Max(0, math.Min(255, b*255))),
			A: 255,
		}

	case "inferno":
		var r, g, b float64
		if v < 0.3 {
			r = v * 1.5
			g = 0.0
			b = v * 2.5
		} else if v < 0.65 {
			r = 0.45 + (v-0.3)*1.5
			g = (v - 0.3) * 1.6
			b = 0.75 - (v-0.3)*2.1
		} else {
			r = 1.0
			g = 0.56 + (v-0.65)*1.25
			b = (v - 0.65) * 1.8
		}
		return color.RGBA{
			R: byte(math.Max(0, math.Min(255, r*255))),
			G: byte(math.Max(0, math.Min(255, g*255))),
			B: byte(math.Max(0, math.Min(255, b*255))),
			A: 255,
		}

	case "rainbow":
		hue := (1.0 - v) * 240.0
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

	isoRaw := byte(RawOf(GState.IsothermTemp))

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

		// Klinische Isothermen-Hervorhebung (>= IsothermTemp)
		if GState.ShowIsotherm && b >= isoRaw && b > 30 {
			c = color.RGBA{R: 244, G: 63, B: 94, A: 255}
		}

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
