# AGENTS.md — Entwickler- & AI-Agenten-Leitfaden für IGNITE Medical Imaging Suite

> **Zweck dieser Datei:**  
> Dieses Dokument dient als zentrale, verbindliche Wissensbasis und Architektur-Dokumentation für alle zukünftigen AI-Agenten (Antigravity, Gemini, Claude, GPT, Cursor, Copilot etc.) sowie Softwareentwickler, die an der **IGNITE Medical Imaging Suite** arbeiten.  
> **Bitte vor jeder Modifikation oder Fehlerbehebung dieses Dokument aufmerksam lesen!**

---

## 1. Projektübersicht & Mission

* **Projektname:** IGNITE Medical Imaging Suite (v5.0.0+)
* **Wettbewerb & Kontext:** Entwickelt für **Jugend forscht 2026** (Fachgebiet Arbeitswelt / Informatik) von **Jona Noack**.
* **Klinische Kernmission:**  
  Vollautomatisierte, deterministische und berührungslose Früherkennung subklinischer Gewebeentzündungen, diabetischer Fußulzera (DFS / DFU) und vaskulärer Durchblutungsstörungen mittels hochauflösender Infrarot-Thermografie (LWIR, Long-Wave Infrared, 8–14 µm).
* **Medizinische Leitlinien & Standards:**
  * **DIN EN ISO 13485:** Qualitätsmanagement für Medizinprodukte.
  * **IWGDF (International Working Group on the Diabetic Foot):** Leitlinien zur Prävention und Behandlung des diabetischen Fußsyndroms.
  * **Armstrong-Kriterien (2007):** Eine kontralaterale Temperaturdifferenz von $\Delta T \ge 2{,}2\,\text{K}$ ($\approx 2{,}2\,^\circ\text{C}$) gilt als signifikanter Prädiktor für ein bevorstehendes neuropathisches Gewebeulkus.
  * **DSGVO Art. 30 & Art. 25:** Lokale Speicherung, kryptografische Pseudonymisierung (`ANON-<hash>`), revisionssicherer SQLite-Audit-Trail.

---

## 2. Polyglotte Multi-Tier-Architektur

IGNITE ist bewusst modular als Hochleistungs-Pipeline aufgebaut, die native Hardware-Beschleunigung mit einer ergonomischen klinischen Benutzeroberfläche verbindet:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. Go (Walk / Win32) — Native Go Medical PACS Workstation (`desktop/`)          │
│    - Reines Go ohne CGO/gcc mit authentischem C++ / Win32 / Qt Workstation-Look  │
│    - Direkte In-Process Anbindung an den Go-Kern (Zero-IPC / Zero-Copy)          │
│    - Resizable Dual-Viewport HSplitter mit schnellem GDI-Rendering               │
│    - 4-Kategorien-Inspector (Diagnose, Anatomie, Signale, System)                │
│    - Vorkompilierte Windows x86_64 Binärdatei: `desktop/Ignite.exe` (nur 8,3 MB) │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. Python Suite (3.10+ / CLI & Fallback) (`cli.py`, `image_processing.py`)      │
│    - Automatisierte Go-Core-Anbindung (`run_go_core_pipeline`), Fallback-Pipeline │
│    - CLI-Befehle: analyze, batch, compare, eval, info, audit                     │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ In-Process Call / IPC-Aufruf via CLI
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 2. Go (Golang 1.24+) — Bildverarbeitung & Pipeline-Kern (`core/`)              │
│    - 42-stufige deterministische Bildverarbeitungs-Pipeline (`pkg/pipeline`)     │
│    - Siehe vollständiger PAP: `docs/PROGRAMMABLAUFPLAN_42_STUFEN.md`             │
│    - Otsu-Schwellenwert-Segmentierung & 2-Pass Chamfer-L2 Distanzerosion         │
│    - Multiskaliger Frangi-Vesselness-Filter (Hesse-Matrix-Eigenwerte λ1, λ2)     │
│    - O(N) Histogramm-basierter Median & MAD-Statistik (Median Absolute Deviation)│
│    - Multi-Threading über Go Goroutinen                                         │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Direkte SIMD-Instruktionseinbindung
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 3. x86_64 Assembler (AVX2 / SIMD — Plan 9 Syntax) (`core/pkg/morphology/*.s`)    │
│    - 11 hardwarenahe Vektorkerne für maximale Durchsatzrate:                    │
│      • minVectorAVX2 / maxVectorAVX2: Morphologische Erosion/Dilation (32 B/Takt)│
│      • subVectorAVX2: Sättigende Subtraktion (VPSUBUSB) für Top-Hat             │
│      • absDiffVectorAVX2: Vektorisierte Differenz |a - b| für Seitenvergleich   │
│      • thresholdMaskAVX2: Paralleles Binarisieren & Gewebemaskierung            │
│      • fmaVectorFloat32AVX2: Gleitkomma-Faltung (FMA) für Frangi-Gefäßfilter    │
│      • mulScalarFloat32AVX2: Skalar-Vektor Multiplikation                       │
│      • dotProductFloat32AVX2: 256-Bit Vektor-Skalarprodukt mit Horizon-Summe    │
│      • addVectorFloat32AVX2: Parallele Gleitkomma-Vektoraddition                │
│      • scaleOffsetFloat32AVX2: Lineare Radiometrietransformation T = a*x + b     │
│      • laplacian2DVectorFloat32AVX2: 5-Punkt diskreter 2D-Laplace-Operator      │
│      • sumAndSumSqUint8AVX2: Parallele Reduktion Sum & SumSq mit Maskierung     │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Eingebetteter Interpreter
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 4. Lua (GopherLua 5.1) — Klinische Regel-Engine (`rules/`)                      │
│    - Entkoppelte medizinische Entscheidungslogik (`rules/armstrong_criteria.lua`)│
│    - Ärzte können Diagnose-Schwellenwerte anpassen OHNE Neukompilierung!         │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Audit-Transaktionen
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ 5. SQLite & Kryptografie — Revisionssicheres Audit-Log (`desktop/ignite_medical.db`)│
│    - DSGVO Art. 30 Verfahrensverzeichnis & Evaluationsprotokolle                 │
│    - SHA-256 Hash-Ketten für forensische Unveränderbarkeit                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Ordnerstruktur & Schlüsseldateien

```
JonaNoackIgnite/
│
├── core/                               # GO 1.24+ PIPELINE & AVX2 RECHENKERN
│   ├── cmd/ignite-core/main.go         # Go CLI-Einstiegspunkt (-mode=cli, -input=...)
│   ├── pkg/imageutil/                  # Bild-Decoder, Radiometrie-Helfer
│   ├── pkg/morphology/                 # Top-Hat, Dilation, Erosion + AVX2 .s Assembler
│   ├── pkg/perfusion/                  # Longitudinaler Gradient dT/dy
│   ├── pkg/pipeline/                   # 42-stufige Diagnose-Pipeline Orchestrierung
│   ├── pkg/reconstruction3d/           # Lambertian 3D-Kantenkorrektur & Mesh-Erzeugung
│   ├── pkg/rules/                      # GopherLua Bridge & Evaluator
│   ├── pkg/segmentation/               # Otsu-Binarisierung, Chamfer Gewebe-Erosion
│   ├── pkg/statistics/                 # O(N) Median, MAD, Quantile, Z-Scores
│   ├── pkg/symmetry/                   # Bilateraler Armstrong-Seitenvergleich
│   ├── pkg/vascular/                   # Frangi-Hesse Vesselness-Filter + AVX2 FMA
│   └── ignite-core.exe                 # Vorkompilierte Windows x86_64 Binärdatei
│
├── desktop/                            # GO WAILS v2 CLINICAL WORKSTATION
│   ├── app.go                          # Go Backend-Bindings & In-Process Pipeline-Bridge
│   ├── main.go                         # Wails v2 Applikations-Einstiegspunkt
│   ├── wails.json                      # Wails Projektkonfiguration
│   ├── frontend/dist/                  # PACS Web-UI (HTML5, Vanilla CSS, JS, Dual-Canvas)
│   ├── ignite_medical.db               # SQLite Audit-Datenbank
│   └── Ignite.exe                      # Vorkompilierte Windows x86_64 Desktop-App
│
├── rules/                              # KLINISCHE LUA-ENTSCHEIDUNGSREGELN
│   ├── armstrong_criteria.lua          # Primäre IWGDF/Armstrong Schwellwert-Logik
│   ├── vein_detection.lua              # Unterscheidung Vene vs. runder Entzündungsherd
│   └── perfusion_eval.lua              # Stadieneinteilung von Durchblutungsabbrüchen
│
├── test-data/                          # ECHTE THERMOGRAFIE-AUFNAHMEN (FLIR LWIR)
│   ├── bild (1).jpeg ... bild (26).jpeg# Kalibrierte Testdatensätze für Regressionstests
│
├── installer/                          # INNO SETUP 6 INSTALLER BUILD-SYSTEM
│   ├── ignite_setup_v5.iss             # Inno Setup Script
│   └── build_installer.ps1             # PowerShell 1-Klick-Build (Core -> Desktop -> Setup)
│
├── .github/workflows/ci_v5.yml         # CI/CD: Automated Tests, Builds & Releases
├── README.md                           # Öffentliche Projektdokumentation
└── AGENTS.md                           # DIESE DATEI (AI-Agenten-Leitfaden)
```

---

## 4. Kernalgorithmen & Mathematischer Hintergrund

### 4.1 42-Stufige Diagnostische Pipeline
Die Pipeline verarbeitet Infrarotdaten in 4 Phasen:
1. **Phase 1: Vorverarbeitung & Gewebemaskierung (Stufen 1–10):**
   * Otsu-Schwellenwertfilterung zur Trennung von Fuß/Körper und Raumhintergrund.
   * 2-Pass Chamfer-$L_2$-Distanztransformation zur kontrollierten Rand-Erosion (Unterdrückung von Reflexionsartefakten an der Hautkante).
2. **Phase 2: Morphologische Hotspot-Detektion (Stufen 11–20):**
   * Morphologischer White Top-Hat: $\text{WTH}(I) = I - (I \circ B)$ mit flachem kreisförmigem Strukturelement $B$. Isoliert fokale Temperaturspitzen von großflächigen Hintergrundgradienten.
   * Vektorisiert mit AVX2 `VPMINUB` (Erosion), `VPMAXUB` (Dilation), `VPSUBUSB` (Subtraktion).
3. **Phase 3: Robustes Outlier-Thresholding (Stufen 21–30):**
   * Robustes **MAD (Median Absolute Deviation)** nach Hampel:  
     $$\text{MAD} = \text{median}(|x_i - \text{median}(X)|)$$
   * Schwellenwert: $\tau = \text{Median} + k \times 1{,}4826 \times \text{MAD}$ (Standard $k = 3{,}0$).
4. **Phase 4: Klinische Klassifikation & Gefäßdifferenzierung (Stufen 31–42):**
   * **Frangi-Hesse-Filter:** 2D-Hesse-Matrix $\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}$. Eigenwerte $\lambda_1, \lambda_2$ berechnen die tubuläre Struktur (Gefäß vs. runder Herd).
   * **Bilateraler Seitenvergleich:** Kontralateraler Vergleich beider Füße (L vs. R). $\Delta T \ge 2{,}2\,\text{K}$ löst Armstrong-Alarm aus.
   * **Pennes 2D Bioheat Modell & THDI:** Thermal Heat Dissipation Index zur Bestimmung von Gewebestauungen.

---

## 5. GUI-Architektur & Inspector-Tab-System

### 5.1 Inspector-Kategorisierung & Klinische Messwerkzeuge
Der rechte Inspector der Go Walk PACS Workstation ist in **6 klinische Fachbereiche** unterteilt:

| Tab-Titel | Tab-Inhalt & Funktionsumfang |
| :--- | :--- |
| **`📋 Befund & Triage`** | Detektierte Herde & Hotspots, IWGDF/Armstrong Risiko-Score, Triage, ärztliche Validierung & SHA-256 Signatur |
| **`📐 Messungen & Tools`** | Caliper-Lineal (mm, $\Delta T/\Delta s$ in K/cm), Rechteck-ROI (mit kontralateraler Spiegelung), Kreis-ROI (Halo), 3-Punkt Goniometer (Hallux Valgus), Fensterung (Presets), CSV & Snapshot-PNG Export |
| **`🦶 Anatomie & 3D`** | 5-Zonen Temperaturprofil (Hallux, Ballen, Ferse), Biomechanik & Arch-Index, 3D-Lambertian Kantenkorrektur & Mesh-Export (OBJ, STL, PLY, XYZ) |
| **`⚡ Signale & Regeln`** | Frangi-Hesse Vaskulärfilter (Venenunterdrückung), Pennes 2D-Bioheat Perfusion, GopherLua 5.1 Regel-Editor |
| **`⚙️ System & Audit`** | Patientenstammdaten (DICOM / DSGVO Art. 25), 42-Stufen PAP Timing Profiler, revisionssicherer SHA-256 Audit-Trail |
| **`📊 Diagramme & Statistik`** | Deskriptive Statistik ($\mu$, $\sigma$, SEM, Median, MAD, $\tau$), Thermisches Histogramm, 5-Zonen Vergleich, Real-Sampled Schnittprofil A–B |

### 5.2 Interaktive klinische Werkzeuge & Viewport-Ergonomie
* **6 Interaktive Messmodi:**
  * `⌖ Retikel`: Live-Spot-Probe mit kontralateraler Referenz.
  * `📏 Lineal`: Metrische Distanz (0.60 mm/px) und thermischer Gradient $\frac{\Delta T}{\Delta s}$ in K/cm.
  * `⬛ Rechteck-ROI`: Statistische Auswertung ($T_{\text{min}}, T_{\text{max}}, T_{\text{mean}}, \sigma$) und automatische kontralaterale Vergleichs-ROI.
  * `⭕ Kreis-ROI`: Differenzierung von Herd-Zentrum vs. periphärem Vasodilatations-Halo ($\Delta T_{\text{halo}}$).
  * `📐 Goniometer`: 3-Punkt Orthopädischer Winkel (z. B. Hallux-Valgus-Winkel $\alpha$).
  * `📈 Schnittlinie`: Dynamisches Transversalprofil $A \to B$ zur Echtzeit-Visualisierung im Diagramm-Tab.
* **Isothermen & Kontrast-Presets:**
  * `🔥 Isotherme ≥ 34°C`: Hebt potenziell ulzeröse Gewebebereiche leuchtend hervor.
  * `Kontrast-Presets`: Vollbereich (20–45°C), Entzündung/Ulkus (30–38°C), Ischämie (20–30°C), Plantarhaut (26–36°C).
* **Dual-Viewport & Fadenkreuz:**
  * Viewport 1 (links): Roh-Thermogramm (LWIR 8–14 µm) mit anatomischen Marken (D, P, L, R) und 50-mm Maßstab.
  * Viewport 2 (rechts): Diagnostik-Befundung mit Hotspot-Konturen, Bounding-Boxes, Mess-Overlays und radiometrischer Farbskala.
  * Farbpaletten: Ironbow, Turbo (Scientific HDR), Inferno, Hot Iron, Medical Jet, Rainbow, Grayscale.

---

## 6. Build-, Test- und Ausführungsbefehle

### 6.1 Go Rechenkern (`core/`)
```powershell
# In das Core-Verzeichnis wechseln
cd core

# Alle Unit- & Integrationstests ausführen
go test -v ./pkg/...

# AVX2 Rechenkern für Windows kompilieren
go build -ldflags="-s -w" -o ignite-core.exe ./cmd/ignite-core
```

### 6.2 Go Native Walk Medical Workstation (`desktop/`)
```powershell
# In das Desktop-Verzeichnis wechseln
cd desktop

# Native Walk Workstation (reines Go, C++ / Win32 Flair) kompilieren
go build -ldflags="-H windowsgui -s -w" -o Ignite.exe .

# Desktop-Workstation direkt starten
.\Ignite.exe
```

### 6.3 1-Klick Gesamt-Build (Inno Setup Installer)
```powershell
# Baut Go-Kern, Go Desktop Suite und schnürt dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe
.\installer\build_installer.ps1
```

### 6.4 CLI-Einzeltest
```powershell
.\core\ignite-core.exe -mode=cli -input="test-data/bild (1).jpeg" -output="test_output.json"
```

---

## 7. Goldene Regeln für AI-Agenten (Coding Guidelines)

1. **Deterministische Reproduzierbarkeit:**  
   Medizinische Algorithmen dürfen **keine** nicht-deterministischen Zufallswerte oder undokumentierte Heuristiken enthalten. Jeder Befund muss für denselben Rohdatensatz bit-identisch reproduzierbar sein.
2. **Klinische Integrität & Kommentare:**  
   Bestehende mathematische Formeln, anatomische Bezeichnungen (z. B. Os metatarsale, Calcaneus, Hallux, Taylor & Palmer Angiosome) und Quellcode-Kommentare **müssen zwingend erhalten bleiben**.
3. **PACS UI-Design & Web-Styling:**  
   Halten Sie sich an das etablierte Designsystem in `desktop/frontend/dist/style.css`:  
   * Primäre Akzentfarbe: Cyan (`#0284C7` / `#38BDF8`)
   * Oberflächen: Dark Slate (`#0B0F19`, `#0F172A`, `#1E293B`)
   * Triage: `Success` (`#16A34A`), `Warning` (`#F59E0B`), `Critical` (`#DC2626`)
4. **Zero-IPC In-Process Anbindung:**  
   Die Desktop-Suite bindet `core` direkt als Go-Bibliothek ein. Diagnostische Aufrufe erfolgen in-process via `pipeline.Run(...)` ohne IPC-Latenz.
