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
│ 1a. Go (Wails v2) — Native Go Desktop Workstation (`desktop-go/`)               │
│    - Reines Go-Frontend mit embedded HTML5/CSS3/JS PACS-Benutzeroberfläche       │
│    - Direkte In-Process Anbindung an den Go-Kern (Zero-IPC / Zero-Copy)          │
│    - Synchronisiertes Dual-Canvas Fadenkreuz & Vorhang-Split (Curtain Wipe)      │
│    - 4-Kategorien-Inspector (Diagnose, Anatomie, Signale, System)                │
│    - Vorkompilierte Windows x86_64 Binärdatei: `desktop-go/ignite-workstation-go.exe`│
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1b. C# (.NET 10 / WPF) — Workstation Desktop GUI (`desktop/`)                   │
│    - Klinische PACS-Benutzeroberfläche (DIN EN ISO 13485 konform)                │
│    - Dual-Viewport mit synchronisiertem Live-Fadenkreuz & Pan/Zoom               │
│    - Orthopädisches 3-Punkt Goniometer (Hallux Valgus Winkel HVA/IMA)            │
│    - Strukturierter PDF-Arztbriefexport nach IWGDF/Armstrong-Kriterien           │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1c. Python Suite (3.10+ / CLI & Fallback) (`cli.py`, `image_processing.py`)      │
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
│    - 6 hardwarenahe Vektorkerne für maximale Durchsatzrate:                     │
│      • minVectorAVX2 / maxVectorAVX2: Morphologische Erosion/Dilation (32 B/Takt)│
│      • subVectorAVX2: Sättigende Subtraktion (VPSUBUSB) für Top-Hat             │
│      • absDiffVectorAVX2: Vektorisierte Differenz |a - b| für Seitenvergleich   │
│      • thresholdMaskAVX2: Paralleles Binarisieren & Gewebemaskierung            │
│      • fmaVectorFloat32AVX2: Gleitkomma-Faltung (FMA) für Frangi-Gefäßfilter    │
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
├── desktop-go/                         # GO WAILS v2 CLINICAL WORKSTATION
│   ├── app.go                          # Go Backend-Bindings & In-Process Pipeline-Bridge
│   ├── main.go                         # Wails v2 Applikations-Einstiegspunkt
│   ├── wails.json                      # Wails Projektkonfiguration
│   ├── frontend/dist/                  # PACS Web-UI (HTML5, Vanilla CSS, JS, Dual-Canvas)
│   └── ignite-workstation-go.exe       # Vorkompilierte Windows x86_64 Desktop-App
│
├── desktop/                            # C# .NET 10 / WPF WORKSTATION
│   ├── App.xaml / App.xaml.cs          # Globale Styles (Dark/Light Slate, Segment Radios)
│   ├── MainWindow.xaml / .xaml.cs      # Hauptfenster, Viewports, Dock, TabControl
│   ├── Ignite.Desktop.csproj           # .NET 10 Projektdatei (WPF, C# 13, x64)
│   ├── Models/                         # Datenmodelle (Hotspot, Stage, Probe, etc.)
│   └── Services/                       # Klinische & Mathematische Business-Services:
│       ├── AdvancedDiagnosticService.cs# 7-Tage Risiko-Prädiktion, Pennes Bioheat, Laplace
│       ├── ClinicalAngiosomeService.cs # 6 Taylor & Palmer Angiosom-Territorien
│       ├── ClinicalReportService.cs    # IWGDF/Wagner-Armstrong strukturierter Arztbericht
│       ├── DatabaseService.cs          # SQLite DSGVO Audit-Protokoll & Hash-Signaturen
│       ├── EngineService.cs            # IPC-Bridge zum Go-Kern (`ignite-core.exe`)
│       ├── Mesh3DExportService.cs      # 3D-Export (OBJ, PLY, STL, XYZ, CSV)
│       ├── OrthopedicGoniometerService.cs # 3-Punkt Goniometer (HVA & IMA Hallux-Winkel)
│       ├── PaletteService.cs           # Farbskalen (Ironbow, Rainbow, Inferno, Gray)
│       ├── ThermalAnalysisHelper.cs    # Radiometrische Byte-zu-Temperatur Konvertierung
│       └── ThermalTopographyService.cs # 2.5D Höhenrelief & Hillshading
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

### 5.1 Inspector-Kategorisierung (WICHTIG für Agenten!)
Der rechte Inspector (`InspectorTabs`) besitzt 18 spezialisierte Tabs. Um Überlauf und horizontales Scrollen zu verhindern, ist die Leiste in **4 klinische Hauptkategorien** unterteilt:

| Kategorie-Radiobutton | Tab-Tag | Enthaltene TabItems |
| :--- | :--- | :--- |
| **`CatBtnDiagnostics`** (Diagnose) | `Diagnostics` | `TabHotspots` (Herde), `TabReport` (Arztbericht), `TabPrediction` (Prädiktion), `TabSymmetry` (Bilateral) |
| **`CatBtnAnatomy`** (Anatomie) | `Anatomy` | `TabAnatomy` (5-Zonen), `TabAngiosomes` (Angiosome), `TabBiomechanics` (Biomechanik & Druck), `Tab3DReconstruction` (3D-Kanten) |
| **`CatBtnSignals`** (Signale) | `Signals` | `TabVascular` (Vaskulär Frangi), `TabHistogram` (Spektrum), `TabProfile` (Profil %), `TabProbes` (Sonden), `TabPerfusion` (Perfusion), `TabIsotherms` (Isothermen) |
| **`CatBtnSystem`** (System) | `System` | `TabParams` (Parameter), `TabStages` (42 Stufen), `TabLua` (Leitlinien Lua), `TabAudit` (DSGVO Audit) |

> [!CAUTION]
> **VERBINDLICHE REGEL FÜR TAB-WECHSEL IN C#:**  
> **Niemals** `InspectorTabs.SelectedIndex = <zahl>` verwenden!  
> Da sich Tab-Reihenfolgen ändern können, ist **immer** die semantische Hilfsmethode aufzurufen:  
> ```csharp
> SelectInspectorTab(TabHotspots);       // Wechselt zu Herde & aktiviert Diagnose-Pill
> SelectInspectorTab(TabBiomechanics);   // Wechselt zu Biomechanik & aktiviert Anatomie-Pill
> SelectInspectorTab(TabVascular);       // Wechselt zu Vaskulär & aktiviert Signale-Pill
> SelectInspectorTab(TabParams);         // Wechselt zu Parameter & aktiviert System-Pill
> ```
> `SelectInspectorTab` aktiviert automatisch den zugehörigen Kategorie-Radiobutton und filtert die Tabs via `FilterInspectorTabsByCategory`, sodass nur die passenden 4–6 Tabs im Tabstrip sichtbar sind.

### 5.2 Viewports & Ergonomie
* **Dual-Viewport:**
  * Viewport 1 (links): `CanvasOriginal` mit Roh-Thermogramm.
  * Viewport 2 (rechts): `CanvasResult` mit Befund-Overlay.
  * Beide Viewports verfügen über `CrosshairOriginalCanvas` bzw. `CrosshairResultCanvas`. Die Methode [`UpdateSynchronizedCrosshair(x, y)`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/desktop/MainWindow.xaml.cs#L1020) synchronisiert das Fadenkreuz in Echtzeit über beide Bilder.
* **Vorhang-Wipe (Curtain Wipe):**
  * `CanvasCurtain` steuert den Bild-Split via `CurtainClipRect`.
  * Zwei dynamische Floating-Badges (`CurtainLabelLeft` und `CurtainLabelRight`) und ein Kapsel-Handle (`BorderCurtainHandle`) wandern mit dem Schieberegler mit.

---

## 6. Build-, Test- und Ausführungsbefehle

### 6.1 Go Rechenkern (`core/`)
```powershell
# In das Core-Verzeichnis wechseln
cd core

# Alle Unit- & Integrationstests ausführen
go test -v ./pkg/...

# AVX2 Rechenkern für Windows kompilieren
go build -o ignite-core.exe ./cmd/ignite-core
```

### 6.2 C# .NET 10 WPF Desktop-Workstation (`desktop/`)
```powershell
# Desktop-Projekt bauen
dotnet build desktop/Ignite.Desktop.csproj

# Desktop-Projekt im Release-Modus starten
dotnet run --project desktop/Ignite.Desktop.csproj -c Release
```

### 6.3 1-Klick Gesamt-Build (Inno Setup Installer)
```powershell
# Baut Go-Kern, C# Desktop Suite und schnürt dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe
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
3. **WPF UI-Styling:**  
   Halten Sie sich an das etablierte Designsystem in [desktop/App.xaml](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/desktop/App.xaml):  
   * Primäre Akzentfarbe: `CyanBrush` (`#0284C7`)
   * Oberflächen: `SurfaceBrush` (`#FFFFFF`), `SurfaceCardBrush` (`#FFFFFF`), `SurfaceDarkBrush` (`#0F172A`)
   * Triage: `SuccessBrush` (`#16A34A`), `WarningBrush` (`#F59E0B`), `CriticalBrush` (`#DC2626`)
   * Keine harten ad-hoc Styles in Controls – immer Ressourcen oder Vorlagen verwenden.
4. **Encoding-Vorsicht:**  
   WPF-XAML-Dateien können unter Windows mit UTF-16LE oder UTF-8 mit BOM gespeichert sein. Bei Dateiänderungen auf korrekte Zeichenkodierung achten, um Encoding-Fehler zu vermeiden.
5. **Keine harten Indizes:**  
   Wie in Abschnitt 5.1 beschrieben, immer semantische Elementnamen und `SelectInspectorTab` nutzen.
