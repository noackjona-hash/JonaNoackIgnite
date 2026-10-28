# IGNITE Explainer Pipeline — 42-Stufige Diagnostik in reinem Python & Assembler

> **Jugend forscht 2026** — Fachgebiet Arbeitswelt / Informatik  
> **Projekt:** IGNITE Medical Imaging Suite (v5.0.0)  
> **Autor:** Jona Noack  
> **Klinische Kernmission:** Deterministische, berührungslose Früherkennung subklinischer Gewebeentzündungen, diabetischer Fußulzera (DFS / DFU) und vaskulärer Durchblutungsstörungen mittels hochauflösender LWIR-Infrarot-Thermografie (8–14 µm).

---

## 1. Übersicht & Ziel dieser Version

Dieser Ordner (`ignite_explainer/`) wurde speziell für **Präsentationen, Jury-Gespräche und die wissenschaftliche Erklärung** des Algorithmus entwickelt:
1. **Ultra-Modular & Verständlich:**  
   Die gesamte 42-stufige Diagnose-Pipeline ist in 7 logische, klinisch motivierte Phasen unterteilt. Jede Datei enthält ausführliche deutsche Dokumentation, die mathematischen Formeln und den biophysikalischen Hintergrund.
2. **Jeder einzelne Schritt wird exportiert:**  
   Für genau ein geladenes Thermogramm (z. B. `test-data/bild (1).jpeg`) berechnet die Pipeline alle 42 Stufen und exportiert für jede Stufe:
   * Ein hochauflösendes Diagnosebild (`exports/step_XX_*.png`) mit Farbskala, Kennzahlen-Banner und Visualisierung.
   * Eine strukturierte JSON-Datei (`exports/step_XX_*.json`) mit Ausführungszeiten (in ms) und physikalischen Messwerten.
   * Eine interaktive HTML-Präsentationsgalerie (`exports/index.html`), die sich offline in jedem Browser öffnen lässt!
3. **Reines Python + ein kleines bisschen x86_64 Assembler:**  
   * **Reines Python:** Keine komplexe GUI, keine externen Abhängigkeiten über Standard-Bibliotheken hinaus (`numpy`, `opencv-python`, `scipy`, `matplotlib`).
   * **x86_64 SIMD Assembler:** In `assembly/` demonstrieren wir maschinennahe Vektorisierung (SSE2/AVX2 mit `PSUBUSB` / `VPSUBUSB`), die direkt über Python `ctypes` und Windows `VirtualAlloc` im RAM ausgeführt wird — **über 7.600× schneller als ein Python-Loop!**
4. **Isolierte Virtuelle Umgebung:**  
   1-Klick Setup via `setup_env.bat` / `setup_env.ps1` und Start via `run_pipeline.bat` / `run_pipeline.ps1`.

---

## 2. Schnellstart (In 2 Schritten)

### Schritt 1: Virtuelle Umgebung einrichten
Doppelklick auf:
```cmd
setup_env.bat
```
*(oder in PowerShell: `.\setup_env.ps1`)*  
Erstellt automatisch die virtuelle Umgebung `.venv`, aktualisiert `pip` und installiert alle benötigten Pakete.

### Schritt 2: Pipeline ausführen & alle 42 Schritte exportieren
Doppelklick auf:
```cmd
run_pipeline.bat
```
*(oder in PowerShell: `.\run_pipeline.ps1`)*  
Lädt standardmäßig `../test-data/bild (1).jpeg`, berechnet alle 42 Stufen, exportiert die Bilder nach `exports/` und generiert `exports/index.html`.

Um ein anderes Bild zu analysieren:
```cmd
.venv\Scripts\python.exe main.py "pfad\zu\deinem_bild.jpeg"
```

---

## 3. Die 7 Phasen & 42 Berechnungsstufen

| Phase | Modul | Stufen | Hauptziel & Algorithmus |
| :--- | :--- | :--- | :--- |
| **Phase I** | [`core/phase1_radiometry.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase1_radiometry.py) | **1 – 6** | **Sensor & Radiometrie:** Sensorkalibrierung ($T = f(I)$), 3x3 Median Dead-Pixel Reparatur, kantenerhaltender Bilateralfilter (NETD-Rauschunterdrückung), metrisches 0.6 mm/px Gitter, Stefan-Boltzmann Driftkompensation, dynamisches Kontrast-Stretching. |
| **Phase II** | [`core/phase2_segmentation.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase2_segmentation.py) | **7 – 12** | **Anatomische Gewebesegmentierung:** Multi-Otsu Interklassenvarianz $\sigma_B^2$, Hypothermie-Fallback für unterkühlte Zehenkuppen (pAVK), 4-Wege BFS Zusammenhangskomponenten, Bedding-Purge (< 2%), Chamfer-$L_2$ euklidisches Distanzfeld, 0.5% Sub-Prozent Kanten-Erosion. |
| **Phase III** | [`core/phase3_depth_3d.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase3_depth_3d.py) | **13 – 18** | **3D Anatomical Inflation & Winkelkorrektur:** Shape-from-Silhouette Halbzylinder-Inflation $Z(x, y)$, 3D-Normalenfeld $\vec{n}$, Lambertian Kosinus-Blickwinkel $\cos\theta$, LWIR Fresnel-Hautemissivität $\varepsilon(\theta) = \varepsilon_0 \cos^p\theta$, tangentiale Kosinus-Temperaturkompensation ($\Delta T \le 1{,}2\,\text{K}$). |
| **Phase IV** | [`core/phase4_morphology.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase4_morphology.py) | **19 – 24** | **Morphologische Anomalie-Extraktion:** Dynamischer Kernradius $R = \max(15, 0{,}05 \cdot \min(W, H))$, 1D horizontale/vertikale Minkowski Erosion $\mathcal{E}$, 1D horizontale/vertikale Dilation $\mathcal{D}$ (Opening $I \circ B$), White Top-Hat $\text{WTH}(I) = I - (I \circ B)$ via **x86_64 SIMD Assembler** (`VPSUBUSB`). |
| **Phase V** | [`core/phase5_statistics.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase5_statistics.py) | **25 – 30** | **Statistische Schwellwertbildung:** 256-Bin Gewebehistogramm, linearer $\mathcal{O}(N)$ Median via CDF-Inversion, Hampel-MAD Skalenschätzer $\hat{\sigma} = 1{,}4826 \cdot \text{MAD}$, biologischer $20\,^\circ\text{C}$ Temperaturboden, Vektorschwelle $\tau = \text{Med} + 3{,}0\hat{\sigma}$, geodätische Dual-Threshold Hysterese. |
| **Phase VI** | [`core/phase6_geometry.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase6_geometry.py) | **31 – 36** | **Geometrische Morphologie & Gefäße:** 4-Wege BFS Hotspot-Clusterung, Flächenfilterung ($A \ge 0{,}03\%$ Gewebefläche), Zirkularitäts-Index $C = \frac{4\pi A}{P^2} \ge 0{,}08$, Sensorrand-Kollisionsfilter, 2D-Hesse-Matrix $\mathcal{H}$, multiskaliger Frangi-Vesselness-Filter (Ausschluss oberflächlicher Venen). |
| **Phase VII** | [`core/phase7_triage.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/core/phase7_triage.py) | **37 – 42** | **Biophysikalische Differentialdiagnose & Triage:** Perifokaler Randgradient $G_{\text{edge}} = \frac{\text{d}T}{\text{d}r}$, Vasodilatations-Halo $\Delta T_{\text{halo}}$, 2D-Laplace Divergenz $\nabla^2 T$, homologer Armstrong-Seitenvergleich ($\Delta T_{\text{contra}} \ge 2{,}2\,\text{K}$), Ausschluss diffuser Muskelhyperthermie, IWGDF Armstrong Triage-Einstufung. |

---

## 4. Das "kleine bisschen Assembler": Hardware-Beschleunigung

In [`assembly/`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/assembly/) befindet sich die maschinennahe Optimierung:
* [`simd_tophat_sub.asm`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/assembly/simd_tophat_sub.asm): Echter x86-64 NASM Assemblercode mit `PSUBUSB` (16 Bytes parallel pro Takt).
* [`fast_simd.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/assembly/fast_simd.py): Python-Bridge, die den Maschinencode über `ctypes` und Windows `VirtualAlloc` direkt im RAM ausführt.

### Live-Benchmark-Ergebnis (640 × 480 Bild = 307.200 Pixel):
* **Naiver Python-Loop:** $\approx 297{,}56\,\text{ms}$
* **NumPy Vektorisierung:** $\approx 2{,}49\,\text{ms}$
* **IGNITE x86_64 SIMD Assembler:** $\approx \mathbf{0{,}039\,\text{ms}}$
* **➔ Geschwindigkeitsvorteil: Über 7.600× schneller als Python!**

---

## 5. Ordnerstruktur

```
ignite_explainer/
│
├── README.md                          # Dieses Dokument (Vollständige Projektübersicht)
├── requirements.txt                   # Minimale Python-Abhängigkeiten (numpy, cv2, scipy, matplotlib)
├── setup_env.bat / setup_env.ps1      # 1-Klick Setup für die virtuelle Umgebung (.venv)
├── run_pipeline.bat / run_pipeline.ps1# 1-Klick Start (Analysiert 1 Bild, exportiert alle 42 Stufen)
├── main.py                            # Hauptprogramm (CLI-Einstiegspunkt)
├── generate_gallery.py                # Generiert die interaktive HTML-Präsentation exports/index.html
│
├── assembly/                          # DAS "KLEINE BISSCHEN ASSEMBLER"
│   ├── README.md                      # Warum Assembler in der Medizin-Informatik?
│   ├── simd_tophat_sub.asm            # Reiner x86-64 NASM-Quellcode (PSUBUSB / VPSUBUSB)
│   ├── simd_threshold.asm             # Vektorisierter Schwellwertvergleich in Assembler
│   └── fast_simd.py                   # Python CTypes In-Memory Ausführung & Benchmark
│
├── core/                              # DIE 7 MODULAREN KLINISCHEN PHASEN
│   ├── __init__.py
│   ├── context.py                     # PipelineContext, PipelineConfig & StepResult
│   ├── exporter.py                    # Rendert für jeden Schritt ein PNG mit Farbbanner & JSON
│   ├── phase1_radiometry.py           # Stufen 1–6 (Sensor & Kalibrierung)
│   ├── phase2_segmentation.py         # Stufen 7–12 (Segmentierung & Geodäten)
│   ├── phase3_depth_3d.py             # Stufen 13–18 (3D Anatomie & Winkelkorrektur)
│   ├── phase4_morphology.py           # Stufen 19–24 (Top-Hat & SIMD-Assembler)
│   ├── phase5_statistics.py           # Stufen 25–30 (Hampel-MAD & Statistik)
│   ├── phase6_geometry.py             # Stufen 31–36 (Geometrie & Frangi-Gefäße)
│   └── phase7_triage.py               # Stufen 37–42 (Armstrong, Halo, Laplace & Triage)
│
└── exports/                           # Hier liegen alle 42 exportierten Bilder & index.html
    ├── step_01_radiometrische_sensorkalibrierung.png / .json
    ├── ...
    ├── step_42_klinische_triage__armstrongregel.png / .json
    └── index.html                     # Interaktive PACS-Präsentationsgalerie
```
