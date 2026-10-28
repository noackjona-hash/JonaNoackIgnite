# IGNITE Medical Imaging Suite (v12.3.4.81)

**IGNITE** ist eine deterministische, hochauflösende Infrarot-Thermografie-Workstation zur automatisierten Früherkennung subklinischer Gewebeentzündungen, diabetischer Fußulzera und vaskulärer Auffälligkeiten. 

Entwickelt für den deutschen Jugendwettbewerb **Jugend forscht 2026** (Fachgebiet Arbeitswelt / Informatik), verbindet IGNITE modernste computergestützte Bildverarbeitung mit der Ergonomie klassischer medizinischer Diagnosestationen.

---

## 🚀 Neuheiten & Highlights in Version 12.3.4.81

* **Reine Go Native PACS Workstation (`desktop/`) & Ergonomie:**
  * **Authentischer Win32 / C++ Workstation-Look:** Extrem schlanke, blitzschnelle native Windows-Oberfläche (ohne CGO/gcc, Win32 Common Controls 6.0 via Walk) mit direkter In-Process Anbindung an den Go-Rechenkern (Zero-IPC / Zero-Copy).
  * **Interaktive Viewport-Messwerkzeuge (Toolbar & Shortcuts):**
    * `⌖ Retikel`: Live-Spot-Probe mit kontralateraler Referenz.
    * `📏 Caliper-Lineal`: Metrische Distanz ($0{,}60\,\text{mm/px}$) und thermischer Gewebegradient $G = \frac{\Delta T}{\Delta s}$ in $\text{K/cm}$ mit automatischer Armstrong-Risikoklassifikation.
    * `⬛ Bilaterales Rechteck-ROI`: $T_{\text{min}}, T_{\text{max}}, T_{\text{mean}}, \sigma$, Gewebefläche in $\text{mm}^2/\text{cm}^2$ und automatische kontralateral gespiegelte Referenz-ROI mit bilateralem $\Delta T$.
    * `⭕ Zirkuläres Halo-ROI`: Differenzierung von Kern- vs. periphärem Vasodilatations-Ring ($\Delta T_{\text{halo}}$).
    * `📐 Orthopädischer Goniometer`: 3-Punkt-Winkelmessung mit Gradbogen und Hallux-Valgus-Einstufung.
    * `📈 Dynamische Schnittlinie`: Transversalprofil $A \to B$ zur Echtzeit-Visualisierung der Temperaturverteilung.
  * **Dynamische Isothermen-Bänderung ($T \ge 34{,}0\,^\circ\text{C}$):**
    * Hebt potenziell ulzeröse Gewebebereiche leuchtend hervor.
  * **Klinische Fensterungs-Presets (Window / Level):**
    * *Auto (Min–Max)*, *DFS/DFU Fokus ($28–36\,^\circ\text{C}$)*, *Ischämie-Screening ($22–32\,^\circ\text{C}$)*, *High-Contrast Hotspot ($30–38\,^\circ\text{C}$)*.
  * **Erweiterte wissenschaftliche Farbpaletten:**
    * Google **Turbo (Scientific HDR)** und **Inferno** ergänzen Ironbow, Medical Jet, Rainbow, Viridis und Grayscale.
  * **Umfassende Export-Suite:**
    * Hochauflösender PNG-Snapshot des Viewports inklusive Messungen.
    * Revisionssicherer CSV-Export aller geometrischen & thermischen Messungen.
    * 3D-Mesh-Export als **Wavefront OBJ**, **XYZ Point Cloud** oder **STL Surface Mesh**.
* **42-stufige deterministische Bildverarbeitungs-Pipeline (`core/`):**
  * Otsu-Schwellenwert-Segmentierung & 2-Pass Chamfer-$L_2$ Distanzerosion zur randartefaktfreien Gewebemaskierung.
  * Morphologischer White Top-Hat zur Isolation fokaler Temperaturspitzen.
  * Robustes Hampel/MAD-Outlier-Thresholding ($\tau = \text{Median} + k \times 1{,}4826 \times \text{MAD}$).
  * Multiskaliger **Frangi-Hesse-Filter** zur Differenzierung tubulärer Blutgefäße von runden Entzündungsherden.
  * Pennes 2D-Bioheat Perfusion & THDI (Thermal Heat Dissipation Index).
* **11 spezialisierte x86_64 AVX2-Assembler-Kernels (`core/pkg/morphology/*.s`):**
  * `minVectorAVX2` & `maxVectorAVX2`: Morphologische Erosion/Dilation (32 Pixel parallel pro CPU-Takt).
  * `subVectorAVX2`: Sättigende Subtraktion (`VPSUBUSB`) für den Top-Hat-Filter.
  * `absDiffVectorAVX2`: Vektorisierte Differenz $|a - b|$ für den Armstrong-Seitenvergleich.
  * `thresholdMaskAVX2`: Paralleles Binarisieren & Gewebemaskierung.
  * `fmaVectorFloat32AVX2`: Gleitkomma-Faltung (FMA) für den Frangi-Gefäßfilter.
  * `mulScalarFloat32AVX2`, `dotProductFloat32AVX2`, `addVectorFloat32AVX2`, `scaleOffsetFloat32AVX2`, `laplacian2DVectorFloat32AVX2`, `sumAndSumSqUint8AVX2`.
* **Automatisierter Windows-Installer (Inno Setup 6):**
  * Standalone-Installationsassistent (`dist/IGNITE_Medical_Suite_v12.3.4.81_Setup.exe`) mit Ultra64-Kompression, Startmenü- und Desktop-Icons sowie uninstaller.
  * 1-Klick-Buildskript [`installer/build_installer.ps1`](installer/build_installer.ps1).
* **Modernisierte CI/CD GitHub Actions:**
  * Schnelle, automatisierte Builds für Go 1.24+ AVX2 Core, Go PACS Workstation, Python-Validierung und Inno Setup Paketierung via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 🛠️ Software-Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. Go (Walk / Win32)                                                        │
│    NATIVE GO MEDICAL PACS WORKSTATION GUI (desktop/)                        │
│    - Reines Go ohne CGO/gcc mit authentischem C++ / Win32 Workstation-Look  │
│    - Direkte In-Process Anbindung an den Go-Kern (Zero-IPC / Zero-Copy)     │
│    - Dual-Viewport mit synchronem Zoom/Pan, Live-Fadenkreuz & HUD           │
│    - 6 interaktive Messmodi, Isothermen, Windowing, Paletten (Turbo/Inferno)│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Direkter In-Process Aufruf (Zero-Copy)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Go (Golang 1.24+)                                                        │
│    42-STUFIGE DETERMINISTISCHE PIPELINE & BILDVERARBEITUNG (core/)          │
│    - Otsu-Binarisierung, 2-Pass Chamfer-L2 Distanzerosion                  │
│    - Multiskaliger Frangi-Vesselness Filter (Hesse-Eigenwerte λ1, λ2)       │
│    - O(N) Histogramm-basierter Median & MAD-Statistik (Hampel Outlier)      │
│    - Parallele Verteilung auf CPU-Kerne via Goroutinen                      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Direkte SIMD-Instruktionseinbindung
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. x86_64 Assembler (AVX2 / SIMD - Plan 9)                                  │
│    HARDWARE INNER-LOOP (11 KERNELS) (core/pkg/morphology/*.s)               │
│    - VPMINUB, VPMAXUB, VPSUBUSB, VPOR, VFMADD231PS, VMULPS, VADDPS          │
│    - 32 Byte-Pixel bzw. 8 Float32-Werte GLEICHZEITIG pro Taktzyklus         │
│    - Völlig C-compilerfrei dank Go-integriertem Assembler (`go tool asm`)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Eingebetteter Interpreter
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Lua (GopherLua 5.1)                                                      │
│    KLINISCHE DIAGNOSE-LOGIK & REGEL-ENGINE (rules/)                         │
│    - Dynamische Schwellenwert- und Risikobewertung (Armstrong 2007)         │
│    - Ärzte können Kriterien anpassen OHNE Neukompilierung                   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Audit-Transaktion
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. SQL (SQLite) & Kryptografie                                              │
│    REVISIONSSICHERES AUDIT-LOG & DATENSCHUTZ (desktop/ignite_medical.db)    │
│    - DSGVO Art. 30 Konformität: Lokale Pseudonymisierung (ANON-<hash>)      │
│    - SHA-256 Hash-Ketten für forensische Revisionssicherheit                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Gemessene Performance (1440x1080 Thermogramm)

| Pipeline-Stufe | Technologie / Instruktion | Gemessene Latenz |
| :--- | :--- | :--- |
| **Körper-Maskierung (Otsu + Chamfer)** | Go (Goroutinen) | 19,6 ms |
| **Top-Hat-Filter (Opening + Differenz)** | x86_64 AVX2 (`minVectorAVX2`, `maxVectorAVX2`, `subVectorAVX2`) | **37,8 ms** (@1440x1080) / **1,4 ms** (@160x120) |
| **Outlier-Thresholding (MAD + Maske)** | x86_64 AVX2 (`thresholdMaskAVX2`) | 4,2 ms |
| **Geometrie & Zirkularität** | Go (4-Connected BFS) | 3,5 ms |
| **Frangi-Venenkartierung (3 Skalen)** | AVX2 Float32 FMA (`fmaVectorFloat32AVX2`) | 88,6 ms |
| **Longitudinaler Gradient (Perfusion)** | Go ($dT/dy$ Kernel) | 2,0 ms |
| **Bilateraler Seitenvergleich** | AVX2 Abs-Diff (`absDiffVectorAVX2`) | 5,8 ms |
| **Klinische Risikobewertung** | Eingebettetes Lua (`armstrong_criteria.lua`) | < 0,1 ms |
| **Gesamte Pipeline-Laufzeit** | **End-to-End** | **~169,5 ms** |
| **GDI-Farbrendering & Viewports** | Go Walk / Win32 GDI | < 1 ms |

---

## 📦 Installation & Ausführung

### Option A: Windows Installer (Empfohlen)
Laden Sie die Setup-Datei aus dem Release-Verzeichnis oder GitHub Actions herunter und führen Sie sie aus:
* **Datei:** `dist/IGNITE_Medical_Suite_v12.3.4.81_Setup.exe`
* Installiert die vollständige Anwendung inklusive aller vorkompilierten AVX2-Binärdateien, Lua-Regeln, Testdaten und Dokumentationen.

### Option B: Automatisiertes 1-Klick Build-Skript (PowerShell)
Um das gesamte Projekt inklusive Go-Kern, Go Desktop Workstation und Inno Setup Installer aus dem Quellcode zu bauen:
```powershell
.\installer\build_installer.ps1
```

### Option C: Manueller Start für Entwickler

#### 1. Rechenkern kompilieren & testen (Go + AVX2)
```bash
cd core
go test -v ./pkg/...
go build -ldflags="-s -w" -o ignite-core.exe ./cmd/ignite-core
cd ..
```

#### 2. Native Go Desktop-Workstation kompilieren & starten
```bash
cd desktop
go build -ldflags="-H windowsgui -s -w" -o Ignite.exe .
.\Ignite.exe
```

#### 3. CLI-Analyse eines Einzelbildes
```bash
.\core\ignite-core.exe -mode=cli -input="test-data/bild (1).jpeg" -output="ergebnis.json"
```

---

## 📜 Klinische Lua-Regeln

Die medizinische Klassifikation erfolgt dynamisch über Textskripte im Ordner `rules/`:
* [`rules/armstrong_criteria.lua`](rules/armstrong_criteria.lua): Armstrong-Kriterien ($\Delta T \ge 2{,}2\,\text{K}$ und Zirkularität).
* [`rules/vein_detection.lua`](rules/vein_detection.lua): Unterscheidung von röhrenförmigen Gefäßen und runden Herden.
* [`rules/perfusion_eval.lua`](rules/perfusion_eval.lua): Stadieneinteilung von Durchblutungsabbrüchen.

---

## 📖 Wissenschaftliche Dokumentation & Berichte
* [Wissenschaftliche Monographie](docs/WISSENSCHAFTLICHE_DOKUMENTATION.md)
* [Architektur-Dokumentation](docs/ARCHITECTURE_v5.md)
* [Mathematische Algorithmen-Beschreibung](docs/ALGORITHM.md)
* [42-Stufen Programmablaufplan (PAP)](docs/PROGRAMMABLAUFPLAN_42_STUFEN.md)
* [Schriftliche Arbeit (Jugend forscht 2026)](docs/SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md)
* [Schriftliche Arbeit (PDF-Druckfassung)](docs/SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.pdf)
* [Optimierungs-Bericht & Benchmarks](docs/OPTIMIZATIONS.md)
* [Performance- & Optimierungs-Leitfaden](docs/OPTIMIZATION_GUIDE.md)
