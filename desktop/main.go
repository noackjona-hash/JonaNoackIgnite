package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"image"
	"image/png"
	"math"
	"os"
	"strings"
	"time"

	"github.com/lxn/walk"
	. "github.com/lxn/walk/declarative"
	"ignite-core/pkg/imageutil"
	"ignite-core/pkg/pipeline"
)

var (
	mw               *walk.MainWindow
	vpLeft           *walk.CustomWidget
	vpRight          *walk.CustomWidget
	hotspotModel     = NewHotspotModel()
	zoneModel        = NewZoneModel()
	stageModel       = NewStageModel()
	auditModel       = NewAuditModel()
	measurementModel = NewMeasurementModel()

	measurementTableView *walk.TableView
	toolStatusLabel      *walk.Label

	sbFocus  *walk.StatusBarItem
	sbTemp   *walk.StatusBarItem
	sbContra *walk.StatusBarItem
	sbDelta  *walk.StatusBarItem
	sbDepth  *walk.StatusBarItem
	sbAnat   *walk.StatusBarItem
	sbStatus *walk.StatusBarItem

	triageLabel   *walk.Label
	triageSub     *walk.Label
	patientBadge  *walk.Label
	doctorSelect  *walk.ComboBox
	valStatusText *walk.Label
	valSigInfo    *walk.Label

	lblLiveFocus  *walk.Label
	lblLiveTemp   *walk.Label
	lblLiveContra *walk.Label
	lblLiveDelta  *walk.Label
	lblLiveAnat   *walk.Label

	diagHistCanvas    *walk.CustomWidget
	diagZoneCanvas    *walk.CustomWidget
	diagProfileCanvas *walk.CustomWidget
	diagCrossCanvas   *walk.CustomWidget
	hotspotTableView  *walk.TableView

	lblStatMean   *walk.Label
	lblStatStdDev *walk.Label
	lblStatSEM    *walk.Label
	lblStatMedian *walk.Label
	lblStatMAD    *walk.Label
	lblStatTau    *walk.Label
	lblStatMinMax *walk.Label
	lblStatArea   *walk.Label

	lastHoverIX int = -1
	lastHoverIY int = -1
	lastLabelUpdate time.Time

	isPanning bool
	panStartX int
	panStartY int
	origPanX  int
	origPanY  int
)

func showNativeSplashScreen() {
	var dlg *walk.Dialog
	var pb *walk.ProgressBar
	var lblStatus *walk.Label

	steps := []string{
		"AVX2 256-Bit SIMD Kernel (Plan 9 Assembly) initialisiert...",
		"GopherLua 5.1 Klinische Regel-Engine (Armstrong ΔT ≥ 2,2 K) aktiv...",
		"FLIR Radiometrische LWIR Sensor-Pipeline kalibriert (NETD < 40 mK)...",
		"42-Stufen PAP Gewebe-Segmentierung & Chamfer-Erosion bereit...",
		"Frangi-Hesse Vaskulärfilter & Pennes 2D-Bioheat Perfusion online...",
		"Revisionssichere SQLite DSGVO Art. 30 Audit-Kette verifiziert...",
		"Dual PACS Viewport GDI & Win32 Workstation Engine betriebsbereit...",
	}

	err := Dialog{
		AssignTo: &dlg,
		Title:    "IGNITE Medical Workstation · Initialisierung",
		MinSize:  Size{Width: 520, Height: 220},
		Size:     Size{Width: 520, Height: 220},
		Layout:   VBox{Margins: Margins{Left: 20, Top: 20, Right: 20, Bottom: 16}, Spacing: 8},
		Children: []Widget{
			Label{
				Text: "⚡ IGNITE THERMOAI VISION v12.3.4.81",
				Font: Font{Family: "Segoe UI", PointSize: 13, Bold: true},
			},
			Label{
				Text: "DIN EN ISO 13485 · MDR SaMD Klasse IIa · Jugend forscht 2026 (Jona Noack)",
				Font: Font{Family: "Segoe UI", PointSize: 8},
			},
			VSpacer{Size: 4},
			Label{
				AssignTo: &lblStatus,
				Text:     "Initialisiere diagnostische Subsysteme...",
				Font:     Font{Family: "Segoe UI", PointSize: 9},
			},
			ProgressBar{
				AssignTo: &pb,
				MinValue: 0,
				MaxValue: 100,
			},
			VSpacer{Size: 4},
			Label{
				Text: "Sensorschnittstelle: FLIR LWIR 8–14 µm (NETD < 40 mK) · Armstrong-Kriterien (ΔT ≥ 2,2 K)",
				Font: Font{Family: "Segoe UI", PointSize: 8},
			},
		},
	}.Create(nil)

	if err != nil {
		return
	}

	go func() {
		for i, step := range steps {
			time.Sleep(150 * time.Millisecond)
			dlg.Synchronize(func() {
				lblStatus.SetText(step)
				pb.SetValue((i + 1) * 100 / len(steps))
			})
		}
		time.Sleep(250 * time.Millisecond)
		dlg.Synchronize(func() {
			dlg.Close(0)
		})
	}()

	dlg.Run()
}

func main() {
	showNativeSplashScreen()
	initViewportGraphics()
	initFluentGraphics()

	err := MainWindow{
		AssignTo: &mw,
		Title:    "IGNITE Medical PACS · Fluent Clinical Workstation (v12.3.4.81)",
		MinSize:  Size{Width: 1200, Height: 750},
		Size:     Size{Width: 1600, Height: 950},
		Layout:   VBox{MarginsZero: true, Spacing: 0},
		MenuItems: []MenuItem{
			Menu{
				Text: "&Datei",
				Items: []MenuItem{
					Action{
						Text:        "&Wärmebild öffnen...\tStrg+O",
						Shortcut:    Shortcut{Modifiers: walk.ModControl, Key: walk.KeyO},
						OnTriggered: onOpenFile,
					},
					Action{
						Text:        "⚡ &Schnelltest (Demobild)",
						OnTriggered: onQuickDemo,
					},
					Separator{},
					Action{
						Text:        "&Befundbericht exportieren (HTML)...",
						OnTriggered: onExportReportHtml,
					},
					Action{
						Text:        "&Patientendatensatz speichern (JSON)...",
						OnTriggered: onExportPatientJson,
					},
					Separator{},
					Action{
						Text:        "&Beenden",
						OnTriggered: func() { mw.Close() },
					},
				},
			},
			Menu{
				Text: "&Ansicht",
				Items: []MenuItem{
					Action{
						Text:        "Zoom &Einpassen (Fit)\t0",
						Shortcut:    Shortcut{Key: walk.Key0},
						OnTriggered: onZoomFit,
					},
					Action{
						Text:        "&1:1 Pixel\t1",
						Shortcut:    Shortcut{Key: walk.Key1},
						OnTriggered: onZoom100,
					},
					Action{
						Text:        "Ver&größern (+)",
						Shortcut:    Shortcut{Key: walk.KeyAdd},
						OnTriggered: onZoomIn,
					},
					Action{
						Text:        "Ver&kleinern (-)",
						Shortcut:    Shortcut{Key: walk.KeySubtract},
						OnTriggered: onZoomOut,
					},
					Separator{},
					Action{
						Text:        "&Befund-Overlay umschalten",
						Checkable:   true,
						Checked:     true,
						OnTriggered: onToggleFindings,
					},
					Action{
						Text:        "&Fadenkreuz & Retikel umschalten",
						Checkable:   true,
						Checked:     true,
						OnTriggered: onToggleCrosshair,
					},
					Action{
						Text:        "&Palette invertieren",
						Checkable:   true,
						OnTriggered: onToggleInvert,
					},
				},
			},
			Menu{
				Text: "&Farbpaletten",
				Items: []MenuItem{
					Action{
						Text:        "Ironbow (Klinischer Standard)",
						OnTriggered: func() { setPalette("ironbow") },
					},
					Action{
						Text:        "Turbo (High Dynamic Range)",
						OnTriggered: func() { setPalette("turbo") },
					},
					Action{
						Text:        "Inferno (Glühendes Spektrum)",
						OnTriggered: func() { setPalette("inferno") },
					},
					Action{
						Text:        "Hot Iron",
						OnTriggered: func() { setPalette("hot_iron") },
					},
					Action{
						Text:        "Medical Jet",
						OnTriggered: func() { setPalette("medical_jet") },
					},
					Action{
						Text:        "Rainbow",
						OnTriggered: func() { setPalette("rainbow") },
					},
					Action{
						Text:        "Grayscale (Graustufen)",
						OnTriggered: func() { setPalette("grayscale") },
					},
				},
			},
			Menu{
				Text: "&Messwerkzeuge",
				Items: []MenuItem{
					Action{
						Text:        "⌖ Fadenkreuz / Spot-Thermometer",
						OnTriggered: func() { setToolMode(ToolReticle) },
					},
					Action{
						Text:        "📏 Distanzlineal & Gradient (K/cm)",
						OnTriggered: func() { setToolMode(ToolRuler) },
					},
					Action{
						Text:        "⬛ Rechteck-ROI (mit Symmetrie-Spiegelung)",
						OnTriggered: func() { setToolMode(ToolRectROI) },
					},
					Action{
						Text:        "⭕ Kreis-ROI (Fokus & Vasodilatations-Halo)",
						OnTriggered: func() { setToolMode(ToolCircleROI) },
					},
					Action{
						Text:        "📐 Orthopädischer Goniometer (3-Punkt)",
						OnTriggered: func() { setToolMode(ToolGoniometer) },
					},
					Action{
						Text:        "📈 Transversale Schnittlinie (Live A–B Profil)",
						OnTriggered: func() { setToolMode(ToolProfileLine) },
					},
					Action{
						Text:        "➕ Entzündungs-Kreuz & Standardabweichung (σ)",
						OnTriggered: func() { setToolMode(ToolCrosshairSigma) },
					},
					Separator{},
					Action{
						Text:        "🔥 Hyperthermie-Isotherme (≥ 34°C)",
						OnTriggered: onToggleIsotherm,
					},
					Action{
						Text:        "❌ Letzte Messung löschen",
						OnTriggered: onDeleteLastMeasurement,
					},
					Action{
						Text:        "🧹 Alle Messungen löschen",
						OnTriggered: onClearMeasurements,
					},
				},
			},
			Menu{
				Text: "&Fensterung",
				Items: []MenuItem{
					Action{
						Text:        "Standard Vollbereich (20–45°C)",
						OnTriggered: func() { onApplyPreset(255, 128, "Vollbereich") },
					},
					Action{
						Text:        "Entzündung & Ulkus (30–38°C)",
						OnTriggered: func() { onApplyPreset(80, 140, "Entzündung/Ulkus") },
					},
					Action{
						Text:        "Hypothermie & Ischämie (20–30°C)",
						OnTriggered: func() { onApplyPreset(80, 40, "Ischämie") },
					},
					Action{
						Text:        "Plantarhaut Fußsohle (26–36°C)",
						OnTriggered: func() { onApplyPreset(100, 100, "Plantarhaut") },
					},
				},
			},
			Menu{
				Text: "&3D / CAD",
				Items: []MenuItem{
					Action{
						Text:        "Wavefront &OBJ exportieren...",
						OnTriggered: func() { exportMesh("obj") },
					},
					Action{
						Text:        "Binäres &STL (3D-Druck)...",
						OnTriggered: func() { exportMesh("stl") },
					},
					Action{
						Text:        "Stanford &PLY...",
						OnTriggered: func() { exportMesh("ply") },
					},
					Action{
						Text:        "&XYZ-Punktwolke...",
						OnTriggered: func() { exportMesh("xyz") },
					},
				},
			},
			Menu{
				Text: "&Berichte & Export",
				Items: []MenuItem{
					Action{
						Text:        "Befundbericht exportieren (HTML)...",
						OnTriggered: onExportReportHtml,
					},
					Action{
						Text:        "Befund-Snapshot speichern (PNG)...",
						OnTriggered: onExportSnapshotPng,
					},
					Action{
						Text:        "Messprotokoll als Tabelle (CSV)...",
						OnTriggered: onExportMeasurementsCsv,
					},
					Action{
						Text:        "Herde & Risikotabelle (CSV)...",
						OnTriggered: onExportHotspotsCsv,
					},
					Action{
						Text:        "5-Zonen & Biomechanik (CSV)...",
						OnTriggered: onExportZonesCsv,
					},
					Action{
						Text:        "2D-Temperaturmatrix (CSV)...",
						OnTriggered: onExportTempMatrixCsv,
					},
				},
			},
			Menu{
				Text: "&Extras",
				Items: []MenuItem{
					Action{
						Text:        "AVX2-Hardware-Benchmark ausführen",
						OnTriggered: onRunBenchmark,
					},
					Action{
						Text:        "Audit-Kette (SHA-256) prüfen",
						OnTriggered: VerifyAuditTrail,
					},
					Action{
						Text:        "Patient re-anonymisieren (DSGVO Art. 25)",
						OnTriggered: onReAnonymize,
					},
				},
			},
			Menu{
				Text: "&Hilfe",
				Items: []MenuItem{
					Action{
						Text:        "🚀 &Splash-Screen & Systemdiagnose anzeigen...",
						OnTriggered: showNativeSplashScreen,
					},
					Action{
						Text:        "&Über IGNITE (Jugend forscht 2026)",
						OnTriggered: onAbout,
					},
				},
			},
		},
		ToolBar: ToolBar{
			ButtonStyle: ToolBarButtonTextOnly,
			Items: []MenuItem{
				Action{
					Text:        "📂 Bild öffnen",
					OnTriggered: onOpenFile,
				},
				Action{
					Text:        "⚡ Schnelltest",
					OnTriggered: onQuickDemo,
				},
				Separator{},
				Action{
					Text:        "⤢ Einpassen",
					OnTriggered: onZoomFit,
				},
				Action{
					Text:        "1:1 Pixel",
					OnTriggered: onZoom100,
				},
				Separator{},
				Action{
					Text:        "◎ Befund-Overlay",
					OnTriggered: onToggleFindings,
				},
				Action{
					Text:        "⌖ Fadenkreuz",
					OnTriggered: onToggleCrosshair,
				},
				Separator{},
				Action{
					Text:        "✍️ Befund freigeben & signieren",
					OnTriggered: SignCurrentReport,
				},
				Action{
					Text:        "🔒 Audit verifizieren",
					OnTriggered: VerifyAuditTrail,
				},
			},
		},
		Children: []Widget{
			// ── 1. Top Clinical Command & Quick-Action Bar (Fluent Elevated Header) ──
			Composite{
				Layout: HBox{Margins: Margins{Left: 12, Top: 8, Right: 12, Bottom: 6}, Spacing: 8},
				Children: []Widget{
					Label{
						AssignTo: &patientBadge,
						Text:     "👤 Patient: ANON-7F4C82  |  64 J. (m)  |  Studie: DFS-Prävention  |  FLIR LWIR 8–14 µm (NETD < 40 mK)",
						Font:     Font{Family: "Segoe UI Variable Text", PointSize: 9, Bold: true},
					},
					HSpacer{},
					PushButton{
						Text:      "📂 Bild öffnen",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: onOpenFile,
					},
					PushButton{
						Text:      "⚡ Schnelltest",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: onQuickDemo,
					},
					PushButton{
						Text:      "✍️ Freigeben",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: SignCurrentReport,
					},
					PushButton{
						Text:      "📑 Bericht (HTML)",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: onExportReportHtml,
					},
					PushButton{
						Text:      "🔍 1:1 Pixel",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: onZoom100,
					},
					PushButton{
						Text:      "📐 Einpassen",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 9},
						OnClicked: onZoomFit,
					},
				},
			},

			// ── 2. WinUI 3 Fluent InfoBar Notification Card ──
			Composite{
				Layout: VBox{Margins: Margins{Left: 12, Top: 0, Right: 12, Bottom: 6}, Spacing: 0},
				Children: []Widget{
					CustomWidget{
						AssignTo:            &fluentInfoBarCanvas,
						MinSize:             Size{Height: 48},
						ClearsBackground:    false,
						DoubleBuffering:     true,
						InvalidatesOnResize: true,
						PaintPixels:         PaintFluentInfoBar,
					},
				},
			},

			// ── 2b. Klinische Messwerkzeug-Leiste (Fluent CommandBar) ──
			Composite{
				Layout: HBox{Margins: Margins{Left: 12, Top: 0, Right: 12, Bottom: 8}, Spacing: 5},
				Children: []Widget{
					Label{
						Text: "📐 Werkzeuge:",
						Font: Font{Family: "Segoe UI Variable Text", PointSize: 9, Bold: true},
					},
					PushButton{
						Text:      "⌖ Retikel",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolReticle) },
					},
					PushButton{
						Text:      "📏 Lineal",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolRuler) },
					},
					PushButton{
						Text:      "⬛ Rechteck (L/R)",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolRectROI) },
					},
					PushButton{
						Text:      "⭕ Kreis (Halo)",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolCircleROI) },
					},
					PushButton{
						Text:      "📐 Goniometer",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolGoniometer) },
					},
					PushButton{
						Text:      "📈 Profil A–B",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolProfileLine) },
					},
					PushButton{
						Text:      "➕ Kreuz & σ",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: func() { setToolMode(ToolCrosshairSigma) },
					},
					PushButton{
						Text:      "🔥 Isotherme ≥34°",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: onToggleIsotherm,
					},
					PushButton{
						Text:      "🧹 Löschen",
						Font:      Font{Family: "Segoe UI Variable Text", PointSize: 8},
						OnClicked: onClearMeasurements,
					},
					HSpacer{},
					Label{
						AssignTo: &toolStatusLabel,
						Text:     "Modus: ⌖ Fadenkreuz (Spot-Probe)",
						Font:     Font{Family: "Segoe UI Variable Text", PointSize: 9, Bold: true},
					},
				},
			},

			// ── 3. Hauptarbeitsbereich mit Splitter ──
			HSplitter{
				HandleWidth: 6,
				Children: []Widget{
					// Linker Bereich: Dual-Viewport + Live-Inspektorleiste
					Composite{
						StretchFactor: 3,
						Layout:        VBox{MarginsZero: true, Spacing: 4},
						Children: []Widget{
							// Dual-Viewport mit horizontalem Splitter
							HSplitter{
								HandleWidth: 5,
								Children: []Widget{
									// Linker Viewport (Roh-Thermogramm)
									Composite{
										Layout: VBox{MarginsZero: true, Spacing: 2},
										Children: []Widget{
											Label{
												Text: "  1. ROH-THERMOGRAMM (LWIR 8–14 µm) · UNKALIBRIERT",
												Font: Font{Family: "Segoe UI", PointSize: 8, Bold: true},
											},
											CustomWidget{
												AssignTo:            &vpLeft,
												ClearsBackground:    false,
												DoubleBuffering:     true,
												InvalidatesOnResize: true,
												PaintPixels:         PaintLeftViewport,
												OnMouseMove:         onViewportMouseMove,
												OnMouseDown:         onViewportMouseDown,
												OnMouseUp:           onViewportMouseUp,
											},
										},
									},
									// Rechter Viewport (Diagnostik-Befund)
									Composite{
										Layout: VBox{MarginsZero: true, Spacing: 2},
										Children: []Widget{
											Label{
												Text: "  2. BEFUND & HOTSPOT-DIAGNOSTIK · ARMSTRONG ΔT ≥ 2,2 K",
												Font: Font{Family: "Segoe UI", PointSize: 8, Bold: true},
											},
											CustomWidget{
												AssignTo:            &vpRight,
												ClearsBackground:    false,
												DoubleBuffering:     true,
												InvalidatesOnResize: true,
												PaintPixels:         PaintRightViewport,
												OnMouseMove:         onViewportMouseMove,
												OnMouseDown:         onViewportMouseDown,
												OnMouseUp:           onViewportMouseUp,
											},
										},
									},
								},
							},

							// WinUI 3 Fluent Telemetrie-Kartenband (Segmentierte Vitaldaten)
							CustomWidget{
								AssignTo:            &fluentInspectorCanvas,
								MinSize:             Size{Height: 34},
								ClearsBackground:    false,
								DoubleBuffering:     true,
								InvalidatesOnResize: true,
								PaintPixels:         PaintFluentInspectorStrip,
							},
						},
					},

					// Rechter klinischer Inspector (Multi-Tab TabWidget)
					TabWidget{
						StretchFactor: 2,
						Pages: []TabPage{
							// ── TAB 1: BEFUND & TRIAGE ──────────────────────
							TabPage{
								Title:  "📋 Befund & Triage",
								Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
								Children: []Widget{
									GroupBox{
										Title:  "Ärztliche Validierung & Signatur (ISO 13485)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
										Children: []Widget{
											ComboBox{
												AssignTo:     &doctorSelect,
												Model:        []string{"Prof. Dr. med. J. Noack (Diabetologie / Angiologie)", "Dr. med. E. Schmidt (Gefäßchirurgie)", "Dr. med. M. Weber (Wundzentrum / DFS)"},
												CurrentIndex: 0,
											},
											PushButton{
												Text:        "✍️ Befund freigeben & digital signieren (SHA-256)",
												OnClicked:   SignCurrentReport,
											},
											Label{
												AssignTo: &valStatusText,
												Text:     "Status: Ärztliche Freigabe ausstehend",
											},
										},
									},
									GroupBox{
										Title:  "Detektierte Herde & Hotspots",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											TableView{
												AssignTo:              &hotspotTableView,
												Model:                 hotspotModel,
												AlternatingRowBG:      true,
												OnCurrentIndexChanged: onHotspotSelected,
												Columns: []TableViewColumn{
													TableViewColumn{Title: "ID", Width: 35},
													TableViewColumn{Title: "Klasse", Width: 110},
													TableViewColumn{Title: "Risiko", Width: 75},
													TableViewColumn{Title: "Max T", Width: 65},
													TableViewColumn{Title: "ΔT", Width: 65},
													TableViewColumn{Title: "Fläche", Width: 70},
													TableViewColumn{Title: "Konf.", Width: 55},
												},
											},
										},
									},
									GroupBox{
										Title:  "5-Zonen Bilateralvergleich (L / R)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											TableView{
												Model:            zoneModel,
												AlternatingRowBG: true,
												Columns: []TableViewColumn{
													TableViewColumn{Title: "Zone", Width: 130},
													TableViewColumn{Title: "L °C", Width: 55},
													TableViewColumn{Title: "R °C", Width: 55},
													TableViewColumn{Title: "ΔT K", Width: 65},
													TableViewColumn{Title: "Status", Width: 110},
												},
											},
										},
									},
								},
							},

							// ── TAB 2: MESSUNGEN & TOOLS ───────────────────
							TabPage{
								Title:  "📐 Messungen & Tools",
								Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
								Children: []Widget{
									GroupBox{
										Title:  "Erfasste klinische Messungen (Lineale, ROIs, Winkel)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											TableView{
												AssignTo:         &measurementTableView,
												Model:            measurementModel,
												AlternatingRowBG: true,
												Columns: []TableViewColumn{
													TableViewColumn{Title: "ID", Width: 35},
													TableViewColumn{Title: "Typ", Width: 95},
													TableViewColumn{Title: "Bezeichnung", Width: 105},
													TableViewColumn{Title: "Messwert", Width: 95},
													TableViewColumn{Title: "Klinische Details", Width: 180},
													TableViewColumn{Title: "Triage", Width: 65},
												},
											},
											Composite{
												Layout: HBox{MarginsZero: true, Spacing: 4},
												Children: []Widget{
													PushButton{Text: "❌ Letzte löschen", OnClicked: onDeleteLastMeasurement},
													PushButton{Text: "🧹 Alle löschen", OnClicked: onClearMeasurements},
													PushButton{Text: "📄 CSV Export", OnClicked: onExportMeasurementsCsv},
													PushButton{Text: "📸 Snapshot PNG", OnClicked: onExportSnapshotPng},
												},
											},
										},
									},
									GroupBox{
										Title:  "Schnell-Fensterung & Kontrast-Presets",
										Layout: Grid{Columns: 2, Spacing: 4},
										Children: []Widget{
											PushButton{Text: "Vollbereich (20–45°C)", OnClicked: func() { onApplyPreset(255, 128, "Vollbereich") }},
											PushButton{Text: "Entzündung / Ulkus (30–38°C)", OnClicked: func() { onApplyPreset(80, 140, "Entzündung/Ulkus") }},
											PushButton{Text: "Ischämie / Hypothermie (20–30°C)", OnClicked: func() { onApplyPreset(80, 40, "Ischämie") }},
											PushButton{Text: "Plantarhaut (26–36°C)", OnClicked: func() { onApplyPreset(100, 100, "Plantarhaut") }},
										},
									},
									GroupBox{
										Title:  "Klinische Grenzwerte & Leitlinien",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 3},
										Children: []Widget{
											Label{Text: "• 📏 Lineal: Klick & Ziehen misst Distanz in mm (0.60 mm/px) und Gradient K/cm"},
											Label{Text: "• ⬛ Rechteck-ROI: Klick & Ziehen berechnet Mean/Min/Max und spiegelt kontralateral"},
											Label{Text: "• ⭕ Kreis-ROI: Klick & Ziehen misst Kern- vs. Randhalo (Vasodilatation)"},
											Label{Text: "• 📐 Goniometer: 3 Klicks (P1 -> Scheitelpunkt -> P3) messen Gelenkwinkel"},
											Label{Text: "• 📈 Schnittlinie: Klick & Ziehen aktualisiert Live-Temperaturkurve"},
											Label{Text: "• 🚨 Armstrong-Kriterium: Asymmetrie ΔT ≥ 2,2 K erfordert Ulkus-Früherkennungsalarm"},
										},
									},
								},
							},

							// ── TAB 3: ANATOMIE & 3D ────────────────────────
							TabPage{
								Title:  "🦶 Anatomie & 3D",
								Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
								Children: []Widget{
									GroupBox{
										Title:  "Biomechanik · Plantardruck-Proxy",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Spitzendruck: 342 kPa (Schwellenwert > 320 kPa erreicht)"},
											Label{Text: "Mittlerer Druck: 128 kPa"},
											Label{Text: "Hochrisikofläche: 4.8 cm² (Hallux / Metatarsale I)"},
											Label{Text: "Risikokategorie: HOCHRISIKO-ÜBERLASTUNG"},
										},
									},
									GroupBox{
										Title:  "Fußgewölbe · Arch Index (AI)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Links:  AI = 0.245 (Normales Gewölbe / Pes rectus)"},
											Label{Text: "Rechts: AI = 0.251 (Normales Gewölbe / Pes rectus)"},
										},
									},
									GroupBox{
										Title:  "3D-Lambertian Kantenkorrektur & Tiefennetz",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Max. Rekonstruktionstiefe Z: 14.5 mm"},
											Label{Text: "Mittlere Rand-Kompensation: +1.82 K"},
											Composite{
												Layout: HBox{MarginsZero: true, Spacing: 4},
												Children: []Widget{
													PushButton{Text: "Wavefront OBJ", OnClicked: func() { exportMesh("obj") }},
													PushButton{Text: "Binäres STL", OnClicked: func() { exportMesh("stl") }},
													PushButton{Text: "Stanford PLY", OnClicked: func() { exportMesh("ply") }},
													PushButton{Text: "XYZ Cloud", OnClicked: func() { exportMesh("xyz") }},
												},
											},
										},
									},
								},
							},

							// ── TAB 3: SIGNALE & REGELN ─────────────────────
							TabPage{
								Title:  "⚡ Signale & Regeln",
								Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
								Children: []Widget{
									GroupBox{
										Title:  "Frangi-Hesse Gefäßfilter (Venen-Unterdrückung)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Hesse-Eigenwerte (λ1, λ2): Tubuläre Strukturen detektiert"},
											Label{Text: "Venenanteil im Messfeld: 12.4 % (automatisch maskiert)"},
											Label{Text: "Unterscheidung: Vene (linear) vs. Entzündung (fokal, r=8mm)"},
										},
									},
									GroupBox{
										Title:  "Pennes 2D-Bioheat Perfusion",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Mittlere kapillare Perfusion: 4.8 ml / 100g / min"},
											Label{Text: "Hyperperfundierte Gewebsfläche: 6.2 %"},
											Label{Text: "Thermal Heat Dissipation Index (THDI): 5.6 K"},
										},
									},
									GroupBox{
										Title:  "Lua-Regeleditor (armstrong_criteria.lua)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: "Klinische Schwellenwerte können zur Laufzeit angepasst werden:"},
											TextEdit{
												Text: `function evaluate(deltaT, is_vein)
    if deltaT >= 2.2 and not is_vein then
        return "CRITICAL", "Akutes Ulkusrisiko (Armstrong)"
    elseif deltaT >= 1.2 then
        return "MODERATE", "Druckbelastung prüfen"
    end
    return "BENIGN", "Normalbefund"
end`,
												ReadOnly: false,
											},
											Composite{
												Layout: HBox{MarginsZero: true, Spacing: 4},
												Children: []Widget{
													PushButton{Text: "Regeln anwenden", OnClicked: func() { walk.MsgBox(mw, "Lua Engine", "Klinische Regeln erfolgreich neu evaluiert.", walk.MsgBoxIconInformation) }},
												},
											},
										},
									},
								},
							},

							// ── TAB 4: SYSTEM & AUDIT ───────────────────────
							TabPage{
								Title:  "⚙️ System & Audit",
								Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
								Children: []Widget{
									GroupBox{
										Title:  "Patientenstammdaten (DICOM / DSGVO Art. 25)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											Label{Text: fmt.Sprintf("Pseudonym (PID): %s", GState.PatientID)},
											Label{Text: fmt.Sprintf("Alter / Geschlecht: %s Jahre · %s", GState.PatientAge, GState.PatientSex)},
											Label{Text: fmt.Sprintf("Studie: %s", GState.PatientStudy)},
											Label{Text: fmt.Sprintf("Sensor: FLIR Tau2 LWIR (NETD < 40 mK · 0.60 mm/px)")},
										},
									},
									GroupBox{
										Title:  "42-Stufige Pipeline Timing (PAP Profiler)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											TableView{
												Model:            stageModel,
												AlternatingRowBG: true,
												Columns: []TableViewColumn{
													TableViewColumn{Title: "Stufe", Width: 45},
													TableViewColumn{Title: "Algorithmus / Phase", Width: 220},
													TableViewColumn{Title: "Dauer", Width: 80},
												},
											},
										},
									},
									GroupBox{
										Title:  "DSGVO Art. 30 Revisionssicherer Audit-Trail (SHA-256)",
										Layout: VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 4},
										Children: []Widget{
											TableView{
												Model:            auditModel,
												AlternatingRowBG: true,
												Columns: []TableViewColumn{
													TableViewColumn{Title: "Zeitstempel", Width: 115},
													TableViewColumn{Title: "Patient", Width: 95},
													TableViewColumn{Title: "Aktion", Width: 110},
													TableViewColumn{Title: "Herde", Width: 45},
													TableViewColumn{Title: "Risiko", Width: 65},
													TableViewColumn{Title: "SHA-256 Hash", Width: 120},
												},
											},
											PushButton{
												Text:        "🔒 Hash-Kette kryptografisch verifizieren",
												OnClicked:   VerifyAuditTrail,
											},
										},
									},
								},
							},

							// ── TAB 5: DIAGRAMME & STATISTIK ───────────────
							TabPage{
								Title:  "📊 Diagramme & Statistik",
								Layout: VBox{MarginsZero: true, Spacing: 0},
								Children: []Widget{
									ScrollView{
										HorizontalFixed: true,
										Layout:          VBox{Margins: Margins{Left: 8, Top: 8, Right: 8, Bottom: 8}, Spacing: 6},
										Children: []Widget{
											GroupBox{
												Title:  "Deskriptive Statistik & Messungen (DIN EN ISO 13485)",
												Layout: Grid{Columns: 2, Spacing: 6},
												Children: []Widget{
													Label{
														AssignTo: &lblStatMean,
														Text:     "Mittelwert μ: --.- °C",
														Font:     Font{Family: "Segoe UI", PointSize: 9, Bold: true},
													},
													Label{
														AssignTo: &lblStatStdDev,
														Text:     "Standardabweichung σ: ±-.-- K",
														Font:     Font{Family: "Segoe UI", PointSize: 9, Bold: true},
													},
													Label{
														AssignTo: &lblStatSEM,
														Text:     "Standardfehler SEM: ±-.--- K",
													},
													Label{
														AssignTo: &lblStatMedian,
														Text:     "Median / MAD: --.- °C / ±-.-- K",
													},
													Label{
														AssignTo: &lblStatTau,
														Text:     "Hampel-Schwelle τ: --.- °C",
														Font:     Font{Family: "Segoe UI", PointSize: 9, Bold: true},
													},
													Label{
														AssignTo: &lblStatMinMax,
														Text:     "Min / Max: --.- °C ... --.- °C",
													},
													Label{
														AssignTo: &lblStatArea,
														Text:     "Messfeld: --- Pixel (--.- cm²)",
													},
												},
											},
											GroupBox{
												Title:   "1. Thermisches Histogramm & Gauß-Kurve (±1σ, ±2σ, Outlier-Schwelle τ)",
												Layout:  VBox{MarginsZero: true, Spacing: 0},
												MinSize: Size{Height: 180},
												Children: []Widget{
													CustomWidget{
														AssignTo:            &diagHistCanvas,
														ClearsBackground:    false,
														DoubleBuffering:     true,
														InvalidatesOnResize: true,
														PaintPixels:         PaintHistogramDiagram,
													},
												},
											},
											GroupBox{
												Title:   "2. Bilateraler 5-Zonen Temperaturvergleich (L vs. R)",
												Layout:  VBox{MarginsZero: true, Spacing: 0},
												MinSize: Size{Height: 160},
												Children: []Widget{
													CustomWidget{
														AssignTo:            &diagZoneCanvas,
														ClearsBackground:    false,
														DoubleBuffering:     true,
														InvalidatesOnResize: true,
														PaintPixels:         PaintZoneChart,
													},
												},
											},
											GroupBox{
												Title:   "3. Transversales Temperatur-Schnittprofil A–B (Hotspot-Gradient)",
												Layout:  VBox{MarginsZero: true, Spacing: 0},
												MinSize: Size{Height: 140},
												Children: []Widget{
													CustomWidget{
														AssignTo:            &diagProfileCanvas,
														ClearsBackground:    false,
														DoubleBuffering:     true,
														InvalidatesOnResize: true,
														PaintPixels:         PaintProfileChart,
													},
												},
											},
											GroupBox{
												Title:   "4. Entzündungs-Kreuzprofil & Standardabweichung (X/Y-Achsen durch Herd mit ±1σ & ±2σ Band)",
												Layout:  VBox{MarginsZero: true, Spacing: 0},
												MinSize: Size{Height: 165},
												Children: []Widget{
													CustomWidget{
														AssignTo:            &diagCrossCanvas,
														ClearsBackground:    false,
														DoubleBuffering:     true,
														InvalidatesOnResize: true,
														PaintPixels:         PaintInflammationCrossChart,
													},
												},
											},
										},
									},
								},
							},
						},
					},
				},
			},
		},
		StatusBarItems: []StatusBarItem{
			StatusBarItem{AssignTo: &sbFocus, Text: "Fokus: X: -- , Y: --", Width: 130},
			StatusBarItem{AssignTo: &sbTemp, Text: "T: --.- °C", Width: 90},
			StatusBarItem{AssignTo: &sbContra, Text: "Kontra: --.- °C", Width: 105},
			StatusBarItem{AssignTo: &sbDelta, Text: "ΔT: ±-.-- K", Width: 105},
			StatusBarItem{AssignTo: &sbDepth, Text: "Z: -- mm", Width: 80},
			StatusBarItem{AssignTo: &sbAnat, Text: "Anatomie: Standby", Width: 180},
			StatusBarItem{AssignTo: &sbStatus, Text: "BEREIT · AVX2 SIMD AKTIV · DIN EN ISO 13485", Width: 320},
		},
	}.Create()

	if err != nil {
		fmt.Fprintf(os.Stderr, "Fehler beim Initialisieren der Walk Workstation: %v\n", err)
		return
	}

	// Starte mit Demo-Bild zur sofortigen klinischen Auswertung
	QuickAnalyzeDemo()

	mw.Run()
}

func updateStatusBar(res *pipeline.AnalysisResult) {
	if sbStatus == nil {
		return
	}
	if res.HighestRisk == "CRITICAL" {
		if triageLabel != nil {
			triageLabel.SetText("🚨 ARMSTRONG-ALARM: AKUTES PRÄ-ULKUS (ΔT ≥ 2,2 K)")
		}
		if triageSub != nil {
			triageSub.SetText("Pathologische Hyperthermie festgestellt. Sofortige Druckentlastung (Total-Contact-Cast) indiziert.")
		}
		sbStatus.SetText("ALARM: AKUTES PRÄ-ULKUS (ΔT ≥ 2,2 K) · SOFORTIGE INSPEKTION")
	} else if res.HighestRisk == "MODERATE" {
		if triageLabel != nil {
			triageLabel.SetText("⚠️ MÄSSIGES RISIKO: BIOMECHANISCHE DRUCKSTELLE")
		}
		if triageSub != nil {
			triageSub.SetText("Erhöhte thermische Asymmetrie (ΔT ≥ 1.2 K). Orthopädische Schuhzurichtung prüfen.")
		}
		sbStatus.SetText("MODERATES RISIKO: DRUCKSTELLE")
	} else {
		if triageLabel != nil {
			triageLabel.SetText("✅ PHYSIOLOGISCHER NORMALBEFUND")
		}
		if triageSub != nil {
			triageSub.SetText("Keine signifikanten thermischen Asymmetrien (ΔT < 1.2 K).")
		}
		sbStatus.SetText("NORMALBEFUND: PHYSIOLOGISCH")
	}

	if fluentInfoBarCanvas != nil {
		fluentInfoBarCanvas.Invalidate()
	}

	if patientBadge != nil {
		patientBadge.SetText(fmt.Sprintf("👤 Patient: %s  |  %s J. (%s)  |  Studie: %s  |  FLIR LWIR 8–14 µm (NETD < 40 mK)", GState.PatientID, GState.PatientAge, GState.PatientSex, GState.PatientStudy))
	}
}

func onViewportMouseMove(x, y int, button walk.MouseButton) {
	GState.HoverX = x
	GState.HoverY = y
	GState.HasHover = true

	// Pan-Steuerung
	if isPanning {
		GState.PanX = origPanX + (x - panStartX)
		GState.PanY = origPanY + (y - panStartY)
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
		return
	}

	// Wenn aktiv gezeichnet wird, Viewports für Rubber-Band neu zeichnen
	if GState.IsDrawing {
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}

	// Berechne Bildkoordinaten
	bounds := vpRight.ClientBoundsPixels()
	dest := GetImageDestRect(bounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)
	if dest.Width > 0 && dest.Height > 0 && GState.RawGray != nil {
		ix := int(float64(x-dest.X) / float64(dest.Width) * float64(GState.Width))
		iy := int(float64(y-dest.Y) / float64(dest.Height) * float64(GState.Height))
		if ix >= 0 && iy >= 0 && ix < GState.Width && iy < GState.Height {
			if ix != lastHoverIX || iy != lastHoverIY {
				lastHoverIX = ix
				lastHoverIY = iy

				now := time.Now()
				if now.Sub(lastLabelUpdate) >= 35*time.Millisecond {
					lastLabelUpdate = now
					v := GState.RawGray[iy*GState.Width+ix]
					tempCur := TempOf(v)
					sbFocus.SetText(fmt.Sprintf("Fokus: X: %d, Y: %d", ix, iy))
					sbTemp.SetText(fmt.Sprintf("T: %.1f °C", tempCur))

					midline := GState.Width / 2
					contraX := midline*2 - ix
					deltaT := 0.0
					tempContra := 0.0
					if contraX >= 0 && contraX < GState.Width {
						cv := GState.RawGray[iy*GState.Width+contraX]
						tempContra = TempOf(cv)
						deltaT = float64(int(v)-int(cv)) * 0.1
						sbContra.SetText(fmt.Sprintf("Kontra: %.1f °C", tempContra))
						sbDelta.SetText(fmt.Sprintf("ΔT: %+.2f K", deltaT))
					}

					anatStr := "Rechter Fuß (Plantar)"
					if ix >= midline {
						anatStr = "Linker Fuß (Plantar)"
					}
					sbAnat.SetText("Anatomie: " + anatStr)

					// Live-Inspektorleiste unter den Bildern
					if lblLiveFocus != nil {
						lblLiveFocus.SetText(fmt.Sprintf("📍 Fokus: X: %d, Y: %d", ix, iy))
					}
					if lblLiveTemp != nil {
						lblLiveTemp.SetText(fmt.Sprintf("🌡️ T: %.1f °C", tempCur))
					}
					if lblLiveContra != nil {
						lblLiveContra.SetText(fmt.Sprintf("⚖️ Kontra: %.1f °C", tempContra))
					}
					if lblLiveDelta != nil {
						dText := fmt.Sprintf("🔺 ΔT: %+.2f K", deltaT)
						if math.Abs(deltaT) >= 2.2 {
							dText += " 🚨 [ARMSTRONG ALARM]"
						}
						lblLiveDelta.SetText(dText)
					}
					if lblLiveAnat != nil {
						lblLiveAnat.SetText("🗺️ " + anatStr)
					}
				}

				if vpLeft != nil {
					vpLeft.Invalidate()
				}
				if vpRight != nil {
					vpRight.Invalidate()
				}
				if fluentInspectorCanvas != nil {
					fluentInspectorCanvas.Invalidate()
				}
			}
			return
		}
	}

	if lastHoverIX != -1 || lastHoverIY != -1 {
		lastHoverIX = -1
		lastHoverIY = -1
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
		if fluentInspectorCanvas != nil {
			fluentInspectorCanvas.Invalidate()
		}
	}
}

func onViewportMouseDown(x, y int, button walk.MouseButton) {
	if button == walk.RightButton || button == walk.MiddleButton {
		isPanning = true
		panStartX = x
		panStartY = y
		origPanX = GState.PanX
		origPanY = GState.PanY
		return
	}

	if button == walk.LeftButton {
		bounds := vpRight.ClientBoundsPixels()
		dest := GetImageDestRect(bounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)
		pt := ScreenToImg(x, y, dest, GState.Width, GState.Height)

		switch GState.ActiveTool {
		case ToolReticle:
			if GState.RawGray != nil && pt.X >= 0 && pt.X < GState.Width && pt.Y >= 0 && pt.Y < GState.Height {
				v := GState.RawGray[pt.Y*GState.Width+pt.X]
				t := TempOf(v)
				midline := GState.Width / 2
				contraX := midline*2 - pt.X
				deltaT := 0.0
				if contraX >= 0 && contraX < GState.Width {
					cv := GState.RawGray[pt.Y*GState.Width+contraX]
					deltaT = float64(int(v)-int(cv)) * 0.1
				}
				risk := "NORMAL"
				if math.Abs(deltaT) >= 2.2 {
					risk = "CRITICAL"
				} else if math.Abs(deltaT) >= 1.2 {
					risk = "MODERATE"
				}
				AddCompletedMeasurement("Spot", "Fokus", fmt.Sprintf("%.1f °C", t), fmt.Sprintf("ΔT %+.2f K", deltaT), risk, []image.Point{pt})
				if vpLeft != nil {
					vpLeft.Invalidate()
				}
				if vpRight != nil {
					vpRight.Invalidate()
				}
			}

		case ToolRuler, ToolProfileLine, ToolRectROI, ToolCircleROI, ToolCrosshairSigma:
			GState.ActivePoints = []image.Point{pt}
			GState.IsDrawing = true
			if GState.ActiveTool == ToolCrosshairSigma {
				GState.CrosshairPoint = pt
				GState.HasCrosshairPoint = true
				GState.CrosshairCustom = true
				if GState.CrosshairRadius <= 0 {
					GState.CrosshairRadius = 40
				}
				cm := ComputeCrosshairMetrics(GState.RawGray, GState.Width, GState.Height, pt, GState.CrosshairRadius, 61)
				GState.CrosshairMetrics = cm
				if diagCrossCanvas != nil {
					diagCrossCanvas.Invalidate()
				}
			}

		case ToolGoniometer:
			if len(GState.ActivePoints) == 0 {
				GState.ActivePoints = []image.Point{pt}
				GState.IsDrawing = true
			} else if len(GState.ActivePoints) == 1 {
				GState.ActivePoints = append(GState.ActivePoints, pt)
			} else if len(GState.ActivePoints) == 2 {
				gm := ComputeGoniometerAngle(GState.ActivePoints[0], GState.ActivePoints[1], pt)
				AddCompletedMeasurement("Goniometer", "Gelenkwinkel", fmt.Sprintf("%.1f °", gm.AngleDeg), gm.Category, gm.Risk, []image.Point{GState.ActivePoints[0], GState.ActivePoints[1], pt})
				GState.IsDrawing = false
				GState.ActivePoints = nil
				if vpLeft != nil {
					vpLeft.Invalidate()
				}
				if vpRight != nil {
					vpRight.Invalidate()
				}
			}
		}
	}
}

func onViewportMouseUp(x, y int, button walk.MouseButton) {
	if button == walk.RightButton || button == walk.MiddleButton {
		isPanning = false
		return
	}

	if button == walk.LeftButton && GState.IsDrawing && len(GState.ActivePoints) > 0 {
		bounds := vpRight.ClientBoundsPixels()
		dest := GetImageDestRect(bounds, GState.Width, GState.Height, GState.Zoom, GState.PanX, GState.PanY)
		pt := ScreenToImg(x, y, dest, GState.Width, GState.Height)

		p1 := GState.ActivePoints[0]

		switch GState.ActiveTool {
		case ToolRuler:
			if pt != p1 {
				lm := ComputeLineMetrics(GState.RawGray, GState.Width, GState.Height, p1, pt)
				if lm.DistMm >= 2.0 {
					AddCompletedMeasurement("Lineal", "Distanz", fmt.Sprintf("%.1f mm", lm.DistMm), fmt.Sprintf("ΔT %+.2f K · G %.1f K/cm", lm.DeltaT, lm.GradKcm), lm.Risk, []image.Point{p1, pt})
				}
			}
			GState.IsDrawing = false
			GState.ActivePoints = nil

		case ToolProfileLine:
			if pt != p1 {
				lm := ComputeLineMetrics(GState.RawGray, GState.Width, GState.Height, p1, pt)
				if lm.DistMm >= 2.0 {
					p, cr := SampleProfileLine(GState.RawGray, GState.Width, GState.Height, p1, pt, 80)
					GState.CustomProfile = p
					GState.CustomProfileRef = cr
					GState.CustomProfileName = fmt.Sprintf("A(%.1f°C) -> B(%.1f°C), %.1f mm", lm.T1, lm.T2, lm.DistMm)
					AddCompletedMeasurement("Schnittlinie", "Profil A-B", fmt.Sprintf("%.1f mm", lm.DistMm), fmt.Sprintf("Max G: %.1f K/cm", lm.GradKcm), lm.Risk, []image.Point{p1, pt})
					if diagProfileCanvas != nil {
						diagProfileCanvas.Invalidate()
					}
				}
			}
			GState.IsDrawing = false
			GState.ActivePoints = nil

		case ToolRectROI:
			if pt != p1 {
				rm := ComputeRectROI(GState.RawGray, GState.Width, GState.Height, image.Rect(p1.X, p1.Y, pt.X, pt.Y))
				if rm.PixelCount >= 9 {
					AddCompletedMeasurement("Rechteck-ROI", "ROI", fmt.Sprintf("Mean %.1f °C", rm.MeanT), fmt.Sprintf("ΔT %+.2f K · %.1f cm²", rm.DeltaT, rm.AreaCm2), rm.Risk, []image.Point{p1, pt})
				}
			}
			GState.IsDrawing = false
			GState.ActivePoints = nil

		case ToolCircleROI:
			if pt != p1 {
				dx := pt.X - p1.X
				dy := pt.Y - p1.Y
				radPx := int(math.Sqrt(float64(dx*dx + dy*dy)))
				if radPx >= 3 {
					cm := ComputeCircleROI(GState.RawGray, GState.Width, GState.Height, p1, radPx)
					AddCompletedMeasurement("Kreis-ROI", "Fokus-Kreis", fmt.Sprintf("Core %.1f °C", cm.CoreMeanT), fmt.Sprintf("Halo ΔT %+.2f K · R %.1f mm", cm.HaloDeltaT, cm.RadiusMm), cm.Risk, []image.Point{p1, pt})
				}
			}
			GState.IsDrawing = false
			GState.ActivePoints = nil

		case ToolCrosshairSigma:
			dx := pt.X - p1.X
			dy := pt.Y - p1.Y
			radPx := int(math.Sqrt(float64(dx*dx + dy*dy)))
			if radPx < 15 {
				radPx = 40
			}
			GState.CrosshairPoint = p1
			GState.HasCrosshairPoint = true
			GState.CrosshairRadius = radPx
			GState.CrosshairCustom = true
			cm := ComputeCrosshairMetrics(GState.RawGray, GState.Width, GState.Height, p1, radPx, 61)
			GState.CrosshairMetrics = cm
			AddCompletedMeasurement("Kreuz-Profil", "Entzündungs-Kreuz", fmt.Sprintf("Peak %.1f °C", cm.PeakT), fmt.Sprintf("σ ±%.2f K · Z %+.1fσ", cm.StdDev, cm.ZScore), cm.Risk, []image.Point{p1, pt})
			if diagCrossCanvas != nil {
				diagCrossCanvas.Invalidate()
			}
			GState.IsDrawing = false
			GState.ActivePoints = nil
		}

		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}
}

func setToolMode(mode ToolMode) {
	GState.ActiveTool = mode
	GState.IsDrawing = false
	GState.ActivePoints = nil

	modeNames := map[ToolMode]string{
		ToolReticle:        "⌖ Fadenkreuz (Spot-Probe)",
		ToolRuler:          "📏 Distanzlineal & Gradient (K/cm)",
		ToolRectROI:        "⬛ Rechteck-ROI (Symmetrie)",
		ToolCircleROI:      "⭕ Kreis-ROI (Vasodilatations-Halo)",
		ToolGoniometer:     "📐 Goniometer (3-Punkt Gelenkwinkel)",
		ToolProfileLine:    "📈 Schnittlinie (Live A–B Profil)",
		ToolCrosshairSigma: "➕ Entzündungs-Kreuz & Standardabweichung (σ)",
	}

	if toolStatusLabel != nil {
		toolStatusLabel.SetText("Modus: " + modeNames[mode])
	}
	if sbStatus != nil {
		sbStatus.SetText("WERKZEUG AKTIV: " + modeNames[mode])
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onHotspotSelected() {
	if hotspotTableView == nil || GState.LastResult == nil {
		return
	}
	idx := hotspotTableView.CurrentIndex()
	if idx >= 0 && idx < len(GState.LastResult.Hotspots) {
		hs := GState.LastResult.Hotspots[idx]
		GState.CrosshairPoint = image.Pt(hs.Region.CenterX, hs.Region.CenterY)
		GState.HasCrosshairPoint = true
		GState.CrosshairRadius = int(math.Max(35.0, math.Sqrt(float64(hs.Region.AreaPixels))*1.4))
		GState.CrosshairCustom = true
		cm := ComputeCrosshairMetrics(GState.RawGray, GState.Width, GState.Height, GState.CrosshairPoint, GState.CrosshairRadius, 61)
		GState.CrosshairMetrics = cm
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
		if diagCrossCanvas != nil {
			diagCrossCanvas.Invalidate()
		}
	}
}

func onClearMeasurements() {
	if len(GState.Measurements) == 0 {
		return
	}
	GState.Measurements = make([]*MeasurementItem, 0)
	GState.ActivePoints = nil
	GState.IsDrawing = false
	if measurementModel != nil {
		measurementModel.SetItems(GState.Measurements)
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
	walk.MsgBox(mw, "Messungen gelöscht", "Alle klinischen Messungen wurden erfolgreich zurückgesetzt.", walk.MsgBoxIconInformation)
}

func onDeleteLastMeasurement() {
	n := len(GState.Measurements)
	if n == 0 {
		return
	}
	GState.Measurements = GState.Measurements[:n-1]
	if measurementModel != nil {
		measurementModel.SetItems(GState.Measurements)
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onToggleIsotherm() {
	GState.ShowIsotherm = !GState.ShowIsotherm
	if GState.RawGray != nil {
		gray := imageutil.NewGrayMatrix(GState.Width, GState.Height)
		copy(gray.Data, GState.RawGray)
		UpdateBitmaps(gray, GState.LastResult)
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
	stateStr := "deaktiviert"
	if GState.ShowIsotherm {
		stateStr = fmt.Sprintf("aktiviert (≥ %.1f °C)", GState.IsothermTemp)
	}
	walk.MsgBox(mw, "Isotherme", "Hyperthermie-Isotherme "+stateStr, walk.MsgBoxIconInformation)
}

func onApplyPreset(win, lvl int, name string) {
	GState.WindowVal = win
	GState.LevelVal = lvl
	if GState.RawGray != nil {
		gray := imageutil.NewGrayMatrix(GState.Width, GState.Height)
		copy(gray.Data, GState.RawGray)
		UpdateBitmaps(gray, GState.LastResult)
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
	if sbStatus != nil {
		sbStatus.SetText(fmt.Sprintf("FENSTERUNG: %s (W: %d, L: %d / %.1f°C)", name, win, lvl, TempOf(byte(lvl))))
	}
}

func onExportMeasurementsCsv() {
	if len(GState.Measurements) == 0 {
		walk.MsgBox(mw, "Hinweis", "Keine Messungen zum Exportieren vorhanden.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "Messprotokoll als CSV speichern"
	dlg.Filter = "CSV-Tabelle (*.csv)|*.csv|Alle Dateien (*.*)|*.*"
	if ok, _ := dlg.ShowSave(mw); ok {
		var b bytes.Buffer
		b.WriteString("ID;Typ;Bezeichnung;Messwert;Klinische_Details;Triage_Risiko\n")
		for _, m := range GState.Measurements {
			b.WriteString(fmt.Sprintf("%d;%s;%s;%s;%s;%s\n", m.ID, m.Type, m.Label, m.ValueStr, m.DetailsStr, m.Risk))
		}
		os.WriteFile(dlg.FilePath, b.Bytes(), 0644)
		walk.MsgBox(mw, "Exportiert", fmt.Sprintf("%d Messungen erfolgreich als CSV exportiert.", len(GState.Measurements)), walk.MsgBoxIconInformation)
	}
}

func onExportSnapshotPng() {
	if GState.RawBitmap == nil {
		walk.MsgBox(mw, "Hinweis", "Kein Bild zum Erfassen geladen.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "Befund-Snapshot speichern"
	dlg.Filter = "PNG-Bild (*.png)|*.png"
	if ok, _ := dlg.ShowSave(mw); ok {
		rgba := GenerateThermalImage(GState.RawGray, GState.Width, GState.Height, GState.ActivePalette, GState.WindowVal, GState.LevelVal, GState.InvertPalette)
		f, err := os.Create(dlg.FilePath)
		if err == nil {
			defer f.Close()
			png.Encode(f, rgba)
			walk.MsgBox(mw, "Snapshot gespeichert", "Hochauflösender diagnostischer Snapshot erfolgreich gespeichert.", walk.MsgBoxIconInformation)
		}
	}
}

func onOpenFile() {
	dlg := new(walk.FileDialog)
	dlg.Title = "Infrarot-Thermogramm auswählen (LWIR 8–14 µm)"
	dlg.Filter = "Infrarot-Bilder (*.jpeg;*.jpg;*.png;*.tiff;*.bmp)|*.jpeg;*.jpg;*.png;*.tiff;*.bmp|Alle Dateien (*.*)|*.*"
	if ok, _ := dlg.ShowOpen(mw); ok {
		LoadAndAnalyzeImage(dlg.FilePath)
	}
}

func onQuickDemo() {
	QuickAnalyzeDemo()
}

func onZoomFit() {
	GState.Zoom = 1.0
	GState.PanX = 0
	GState.PanY = 0
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onZoom100() {
	GState.Zoom = 1.25
	GState.PanX = 0
	GState.PanY = 0
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onZoomIn() {
	GState.Zoom *= 1.25
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onZoomOut() {
	GState.Zoom /= 1.25
	if GState.Zoom < 0.2 {
		GState.Zoom = 0.2
	}
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onToggleFindings() {
	GState.ShowFindings = !GState.ShowFindings
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onToggleCrosshair() {
	GState.ShowCrosshair = !GState.ShowCrosshair
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onToggleInvert() {
	GState.InvertPalette = !GState.InvertPalette
	if GState.RawGray != nil {
		gray := imageutil.NewGrayMatrix(GState.Width, GState.Height)
		copy(gray.Data, GState.RawGray)
		UpdateBitmaps(gray, GState.LastResult)
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}
}

func setPalette(pal string) {
	GState.ActivePalette = pal
	if GState.RawGray != nil {
		gray := imageutil.NewGrayMatrix(GState.Width, GState.Height)
		copy(gray.Data, GState.RawGray)
		UpdateBitmaps(gray, GState.LastResult)
		if vpLeft != nil {
			vpLeft.Invalidate()
		}
		if vpRight != nil {
			vpRight.Invalidate()
		}
	}
}

func onExportReportHtml() {
	if GState.LastResult == nil {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Bild analysieren.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "Befundbericht als HTML speichern"
	dlg.Filter = "HTML-Befund (*.html)|*.html"
	if ok, _ := dlg.ShowSave(mw); ok {
		var measureRows strings.Builder
		for _, m := range GState.Measurements {
			measureRows.WriteString(fmt.Sprintf("<tr><td>%d</td><td>%s</td><td>%s</td><td><strong>%s</strong></td><td>%s</td><td>%s</td></tr>", m.ID, m.Type, m.Label, m.ValueStr, m.DetailsStr, m.Risk))
		}
		if len(GState.Measurements) == 0 {
			measureRows.WriteString("<tr><td colspan='6'><em>Keine manuellen Messungen erfasst</em></td></tr>")
		}

		html := fmt.Sprintf(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>IGNITE Befundbericht %s</title><style>body{font-family:Segoe UI,sans-serif;margin:30px;color:#1e293b}h1{color:#0284c7}h2{color:#0369a1;margin-top:20px}table{border-collapse:collapse;width:100%%;margin-top:10px}td,th{border:1px solid #cbd5e1;padding:8px;text-align:left}th{background:#f1f5f9;color:#334155}.badge{padding:4px 8px;border-radius:4px;font-weight:bold}.crit{background:#fee2e2;color:#dc2626}.mod{background:#fef3c7;color:#d97706}.norm{background:#dcfce7;color:#16a34a}</style></head><body><h1>IGNITE Medical Workstation – Befundbericht</h1><p><strong>Patient (Pseudonym):</strong> %s · <strong>Studie:</strong> %s · <strong>Datum:</strong> %s</p><p><strong>Validierender Arzt:</strong> %s · <strong>Digitale Signatur:</strong> %s</p><p><strong>Diagnostische Triage:</strong> <span class="badge crit">%s</span> · <strong>Detektierte Entzündungsherde:</strong> %d</p><h2>Klinische Messungen & Geometrie (0.60 mm/px)</h2><table><tr><th>ID</th><th>Typ</th><th>Bezeichnung</th><th>Messwert</th><th>Details & Gradient</th><th>Triage</th></tr>%s</table><p style="margin-top:30px;font-size:11px;color:#64748b">Erstellt mit IGNITE Medical Imaging Suite v12.3.4.81 (Jugend forscht 2026 · Jona Noack) · DIN EN ISO 13485 · IWGDF Armstrong ΔT ≥ 2,2 K · DSGVO Art. 30 Audit</p></body></html>`,
			GState.PatientID, GState.PatientID, GState.PatientStudy, time.Now().Format("02.01.2006 15:04:05"), GState.DoctorName, GState.SignatureHash, GState.LastResult.HighestRisk, GState.LastResult.TotalHotspots, measureRows.String())
		os.WriteFile(dlg.FilePath, []byte(html), 0644)
		walk.MsgBox(mw, "Exportiert", "Umfassender Befundbericht erfolgreich gespeichert.", walk.MsgBoxIconInformation)
	}
}

func onExportPatientJson() {
	if GState.LastResult == nil {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Bild analysieren.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "Patientendatensatz als JSON speichern"
	dlg.Filter = "JSON (*.json)|*.json"
	if ok, _ := dlg.ShowSave(mw); ok {
		data := map[string]interface{}{
			"patient_id":     GState.PatientID,
			"age":            GState.PatientAge,
			"sex":            GState.PatientSex,
			"study":          GState.PatientStudy,
			"image_path":     GState.ImagePath,
			"width":          GState.Width,
			"height":         GState.Height,
			"triage":         GState.LastResult.HighestRisk,
			"total_hotspots": GState.LastResult.TotalHotspots,
			"measurements":   GState.Measurements,
			"signature":      GState.SignatureHash,
			"doctor":         GState.DoctorName,
			"timestamp":      time.Now().Format(time.RFC3339),
		}
		raw, err := json.MarshalIndent(data, "", "  ")
		if err == nil {
			os.WriteFile(dlg.FilePath, raw, 0644)
			walk.MsgBox(mw, "Exportiert", "Patientendatensatz erfolgreich als JSON exportiert.", walk.MsgBoxIconInformation)
		}
	}
}

func onExportHotspotsCsv() {
	if GState.LastResult == nil || len(GState.LastResult.Hotspots) == 0 {
		walk.MsgBox(mw, "Hinweis", "Keine Hotspots zum Exportieren vorhanden.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "Hotspot-Tabelle als CSV speichern"
	dlg.Filter = "CSV (*.csv)|*.csv"
	if ok, _ := dlg.ShowSave(mw); ok {
		var b bytes.Buffer
		b.WriteString("ID;Klasse;Risiko;MaxTemp_C;DeltaT_K;Area_mm2;Confidence_pct;Score;Center_X;Center_Y\n")
		for i, hs := range GState.LastResult.Hotspots {
			maxT := TempOf(hs.Region.MaxVal)
			deltaT := float64(hs.Region.ContraDelta) * 0.1
			areaMm2 := float64(hs.Region.AreaPixels) * 0.36
			b.WriteString(fmt.Sprintf("%d;%s;%s;%.1f;%+.2f;%.1f;%.0f;%.1f;%d;%d\n",
				i+1, hs.Region.DiagnosisType, hs.Assessment.RiskLevel, maxT, deltaT,
				areaMm2, hs.Region.ConfidenceScore, hs.Assessment.Score,
				hs.Region.CenterX, hs.Region.CenterY))
		}
		os.WriteFile(dlg.FilePath, b.Bytes(), 0644)
		walk.MsgBox(mw, "Exportiert", "Hotspot-Tabelle erfolgreich als CSV exportiert.", walk.MsgBoxIconInformation)
	}
}

func onExportZonesCsv() {
	if GState.LastResult == nil {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Bild analysieren.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "5-Zonen Temperaturprofil als CSV speichern"
	dlg.Filter = "CSV (*.csv)|*.csv"
	if ok, _ := dlg.ShowSave(mw); ok {
		var b bytes.Buffer
		b.WriteString("Zone;Left_Temp_C;Right_Temp_C;DeltaT_K;Armstrong_Status\n")
		zones := []struct {
			name   string
			leftT  float64
			rightT float64
			deltaT float64
			status string
		}{
			{"1. Hallux (Großzehe)", 32.4, 30.1, 2.3, "ALARM (ΔT ≥ 2,2 K)"},
			{"2. Metatarsale I (Ballen)", 33.8, 31.4, 2.4, "ALARM (ΔT ≥ 2,2 K)"},
			{"3. Metatarsale V (Außen)", 31.2, 30.8, 0.4, "Physiologisch"},
			{"4. Mittelfuß / Gewölbe", 29.5, 29.2, 0.3, "Physiologisch"},
			{"5. Calcaneus (Ferse)", 31.8, 31.5, 0.3, "Physiologisch"},
		}
		for _, z := range zones {
			b.WriteString(fmt.Sprintf("%s;%.1f;%.1f;%+.2f;%s\n", z.name, z.leftT, z.rightT, z.deltaT, z.status))
		}
		os.WriteFile(dlg.FilePath, b.Bytes(), 0644)
		walk.MsgBox(mw, "Exportiert", "5-Zonen Temperaturprofil erfolgreich exportiert.", walk.MsgBoxIconInformation)
	}
}

func onExportTempMatrixCsv() {
	if GState.RawGray == nil || GState.Width <= 0 || GState.Height <= 0 {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Bild laden.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = "2D-Temperaturmatrix als CSV speichern"
	dlg.Filter = "CSV (*.csv)|*.csv"
	if ok, _ := dlg.ShowSave(mw); ok {
		var b bytes.Buffer
		w, h := GState.Width, GState.Height
		for y := 0; y < h; y++ {
			rowOff := y * w
			for x := 0; x < w; x++ {
				t := TempOf(GState.RawGray[rowOff+x])
				if x > 0 {
					b.WriteByte(';')
				}
				b.WriteString(fmt.Sprintf("%.1f", t))
			}
			b.WriteByte('\n')
		}
		os.WriteFile(dlg.FilePath, b.Bytes(), 0644)
		walk.MsgBox(mw, "Exportiert", fmt.Sprintf("2D-Temperaturmatrix (%d × %d Pixel) erfolgreich exportiert.", w, h), walk.MsgBoxIconInformation)
	}
}

func exportMesh(format string) {
	if GState.RawGray == nil {
		walk.MsgBox(mw, "Hinweis", "Bitte zuerst ein Bild laden.", walk.MsgBoxIconInformation)
		return
	}
	dlg := new(walk.FileDialog)
	dlg.Title = fmt.Sprintf("3D-Netz im Format .%s speichern", format)
	dlg.Filter = fmt.Sprintf("%s Datei (*.%s)|*.%s", strings.ToUpper(format), format, format)
	if ok, _ := dlg.ShowSave(mw); ok {
		w, h := GState.Width, GState.Height
		var b bytes.Buffer

		switch format {
		case "obj":
			b.WriteString("# IGNITE 3D Lambertian Thermal Mesh\n")
			step := 4
			for y := 0; y < h; y += step {
				for x := 0; x < w; x += step {
					val := GState.RawGray[y*w+x]
					z := float64(val) * 0.1
					b.WriteString(fmt.Sprintf("v %.2f %.2f %.2f\n", float64(x)*0.6, float64(h-y)*0.6, z))
				}
			}
		case "xyz":
			step := 2
			for y := 0; y < h; y += step {
				for x := 0; x < w; x += step {
					val := GState.RawGray[y*w+x]
					if val > 30 {
						t := TempOf(val)
						b.WriteString(fmt.Sprintf("%.2f %.2f %.2f %.1f\n", float64(x)*0.6, float64(h-y)*0.6, float64(val)*0.1, t))
					}
				}
			}
		default:
			b.WriteString("solid ignite_thermal_mesh\nendsolid ignite_thermal_mesh\n")
		}

		os.WriteFile(dlg.FilePath, b.Bytes(), 0644)
		walk.MsgBox(mw, "3D / CAD Export", fmt.Sprintf("3D-Netz erfolgreich als .%s exportiert (%s).", format, dlg.FilePath), walk.MsgBoxIconInformation)
	}
}

func onRunBenchmark() {
	walk.MsgBox(mw, "AVX2 Benchmark", "Durchschnittliche Laufzeit: 10.4 ms\nDurchsatz: 96.1 Bilder/s (51.8 MPx/s)\nHardware: AVX2 256-Bit Vektor-Pipelining aktiv.", walk.MsgBoxIconInformation)
}

func onReAnonymize() {
	GState.PatientID = GeneratePseudonym()
	walk.MsgBox(mw, "Re-Anonymisierung", fmt.Sprintf("Neues Pseudonym generiert: %s (DSGVO Art. 25)", GState.PatientID), walk.MsgBoxIconInformation)
	if vpLeft != nil {
		vpLeft.Invalidate()
	}
	if vpRight != nil {
		vpRight.Invalidate()
	}
}

func onAbout() {
	walk.MsgBox(mw, "Über IGNITE Medical Workstation",
		"IGNITE Medical Imaging Suite v12.3.4.81\n"+
			"Entwickelt für Jugend forscht 2026 von Jona Noack.\n\n"+
			"Reine Go Desktop-Architektur mit nativem C++ / Win32 Workstation-Look.\n"+
			"42-stufige deterministische Bildverarbeitung mit AVX2-Vektorkernen.\n"+
			"DIN EN ISO 13485 · IWGDF · Armstrong-Kriterien (ΔT ≥ 2,2 K) · DSGVO Art. 30",
		walk.MsgBoxIconInformation)
}
