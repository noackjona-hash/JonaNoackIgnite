# IGNITE v5.0.0 – Software-Architektur & Mehrsprachige Systemtrennung
**Wettbewerb:** Jugend forscht 2026  
**Fachgebiet:** Arbeitswelt / Informatik  
**Version:** 5.0.0  

---

## 1. Wissenschaftliche & Klinische Motivation

Die Version 5.0.0 von **IGNITE** erweitert die deterministische Thermografie-Pipeline um drei entscheidende klinische Module und vollzieht einen vollständigen architektonischen Paradigmenwechsel:

1. **Venen- & Adernkartierung (Vascular Mapping):**  
   Implementierung des multiskaligen **Frangi-Vesselness-Filters** auf Basis der 2D-Hesse-Matrix $\mathcal{H}$. Röhrenförmige Gefäßstrukturen (Venen) werden von fokalen Entzündungsherden differenziert und können Pflegekräften als „digitaler Venenfinder“ dienen.
2. **Perfusion & Longitudinaler Temperaturgradient ($dT/dy$):**  
   Erfassung von Durchblutungsabbrüchen entlang der anatomischen Extremitätenachse zur Früherkennung der peripheren arteriellen Verschlusskrankheit (pAVK) und diabetischen Mikroangiopathie.
3. **Bilateraler Seitenvergleich (Armstrong-Kriterium $\Delta T \ge 2{,}2\,\text{K}$):**  
   Lösung der wissenschaftlichen Kernfrage: *Wie unterscheidet man echte pathologische Entzündungen von harmloser mechanischer Belastung (Socken/Druckstellen)?* Durch den horizontalen Spiegelvergleich der Gegenseite (z. B. linker vs. rechter Fuß) werden systemische Erwärmungen als harmlos klassifiziert, während fokale Asymmetrien über der Armstrong-Schwelle sofort Alarm schlagen.
4. **Ergonomische High-End Diagnosestation:**  
   Vollständiges Redesign der Benutzeroberfläche nach Vorbild moderner kardiologischer und radiologischer Workstations (Obsidian-Farbpalette, synchronisiertes Dual-Viewport-Canvas, Live-Fadenkreuz-Telemetrie und kalibrierte Temperatur-Farbskala).

---

## 2. Mehrsprachiges Software-Design (Separation of Concerns)

Um maximale Rechenleistung, Plattformunabhängigkeit, klinische Flexibilität und ein ergonomisches Bediengefühl zu vereinen, wurde das System in **fünf spezialisierte Sprachen** unterteilt – **strikt ohne C- oder C++-Compiler**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. C# (.NET 10 / WPF)                                                        │
│    OBSIDIAN MEDICAL WORKSTATION GUI                                         │
│    - Echtes Desktop-Feeling wie Siemens syngo / GE Healthcare Diagnostik   │
│    - Dual-Viewport mit synchronem Zoom/Pan und Sub-Pixel-Fadenkreuz         │
│    - Kalibrierte Farbskala (20°C bis 42°C), DSGVO-Pseudonymisierung-Chip    │
│    - Tabbed Docking Inspector (Hotspots, Venenkarte, Perfusion)             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Lokaler IPC-Aufruf (CLI / JSON)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Go (Golang 1.27)                                                         │
│    ORCHESTRIERUNG & BILDVERARBEITUNG                                        │
│    - Otsu-Binarisierung, 2-Pass Chamfer-L2 Distanzerosion                   │
│    - Multiskaliger Frangi-Vesselness Filter (Gefäß-Eigenwerte)              │
│    - O(N) Histogramm-basierter Median & MAD-Statistik (Outlier-Filter)      │
│    - Parallele Verteilung auf alle CPU-Kerne via Goroutinen                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Native Instruktions-Einbindung
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. x86_64 Assembler (AVX2 / SIMD - Plan 9)                                  │
│    DIE HARDWARE-INNER-LOOP (6 KERNELS)                                      │
│    - VPMINUB, VPMAXUB: 32 Pixel parallel für morphologisches Min/Max        │
│    - VPSUBUSB: Vektorisierte Differenz für Top-Hat                          │
│    - VPOR + VPSUBUSB: Absoluter Differenzvergleich |a-b| für Armstrong      │
│    - thresholdMaskAVX2: Gleichzeitiger Schwellenwert- & Maskenabgleich      │
│    - VMULPS, VADDPS: 8 Float32-Werte parallel für Gauß-Separationsfaltung   │
│    - Völlig C-compilerfrei dank Go-integriertem Assembler (`go tool asm`)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Eingebettete Skript-Ausführung
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. Lua (GopherLua)                                                          │
│    KLINISCHE DIAGNOSE-LOGIK & REGEL-ENGINE                                  │
│    - Dynamische Schwellenwert- und Risikobewertung (Armstrong 2007)         │
│    - Ärzte können Diagnose-Kriterien in Textdateien anpassen,                │
│      OHNE dass das Programm neu kompiliert werden muss!                     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Audit-Transaktion
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. SQL (SQLite)                                                             │
│    REVISIONSSICHERES AUDIT-LOG & DATENSCHUTZ                                │
│    - DSGVO Art. 30 Konformität: Lokale Pseudonymisierung (ANON-<hash>)      │
│    - Speicherung von Messreihen, Parametern und Schwellenwerten             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Die Benutzeroberfläche (Redesign Highlights)

### 3.1 Farb- und Designsystem (Obsidian Medical Theme)
Die GUI in [`desktop/App.xaml`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/desktop/App.xaml) basiert auf einem eigens für ophthalmologische und radiologische Dunkelräume entwickelten Farbkanon:
* **Hintergründe:** Tiefes Obsidian (`#0B0E14`), abgesetzt durch Arbeitsflächen in Anthrazit (`#121824`) und Panels in Dunkelmarine (`#1A2234`).
* **Akzentfarben:** Electric Cyan (`#00E5FF`) für Fadenkreuze, Selektionen und Primäraktionen.
* **Klinische Statusfarben:** Emerald Green (`#00E676`) für physiologische Normwerte und Coral Alert (`#FF5252`) für kritische Entzündungsfoci ($\Delta T \ge 2{,}2\,\text{K}$).
* **Typografie:** Modernes Segoe UI Variable Display mit festen Schriftgraden, um Verwechslungen von Ziffern bei Diagnosen auszuschließen.

### 3.2 Dual-Viewport mit synchronisierter Fadenkreuz-Telemetrie
* **Linker Viewport:** Kalibriertes Infrarot-Originalthermogramm mit umschaltbarer Farbpalette (Ironbow, Rainbow, Grayscale).
* **Rechter Viewport:** Diagnostisches Overlay mit transparent gerenderten Venenbäumen (Frangi-Maske) und rot leuchtenden Entzündungsherden inklusive ID-Badges.
* **Synchrones Fadenkreuz:** Bewegt sich die Maus über einen beliebigen Viewport, wird das Fadenkreuz im Partner-Viewport subpixelgenau nachgeführt. Die Telemetrie-Bar im Kopfbereich gibt unmittelbar den Pixelwert, die geschätzte Temperatur ($^\circ\text{C}$) und die relative Temperaturabweichung zum Gewebemedian ($\Delta T$) aus.

### 3.3 Kalibrierte vertikale Farbskala
Zwischen den Viewports befindet sich eine metrische Temperaturskala von $20{,}0^\circ\text{C}$ bis $42{,}0^\circ\text{C}$ mit 6 Referenzmarkern. Dadurch können Ärzte und Pflegekräfte die Farbverteilung unmittelbar quantitativ erfassen.

---

## 4. Die x86_64 AVX2-Assembler-Kernels im Detail

Alle hardwarenahen Rechenschleifen liegen in [`core/pkg/morphology/avx2_amd64.s`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/core/pkg/morphology/avx2_amd64.s):

1. **`minVectorAVX2(src, dst *byte, count int)`:**
   Führt 256-Bit `VPMINUB`-Instruktionen aus. 32 Pixel werden in einem Takt verglichen und das Minimum in den Zielpuffer geschrieben.
2. **`maxVectorAVX2(src, dst *byte, count int)`:**
   Führt `VPMAXUB`-Instruktionen für die morphologische Dilation aus (32 Pixel parallel).
3. **`subVectorAVX2(a, b, dst *byte, count int)`:**
   Nutzt saturierende Subtraktion `VPSUBUSB`. Berechnet die Top-Hat-Differenz $I - \text{Opening}(I)$ ohne Überlaufgefahr für 32 Pixel parallel.
4. **`absDiffVectorAVX2(a, b, dst *byte, count int)`:**
   Berechnet den vorzeichenlosen Absolutbetrag $|a - b| = \max(a-b, 0) \lor \max(b-a, 0)$ via `VPSUBUSB` und `VPOR` für den bilateralen Armstrong-Seitenvergleich.
5. **`thresholdMaskAVX2(diff, orig, mask, dst *byte, count int, threshold, origMedian byte)`:**
   Broadcastet Schwellenwerte via `VPBROADCASTQ` in `YMM0`/`YMM1` und kombiniert Hotspot-Schwellwert, Temperaturminimum und anatomische Gewebemaske parallel für 32 Pixel.
6. **`fmaVectorFloat32AVX2(src, dst *float32, factor float32, count int)`:**
   Führt 8 Single-Precision Float-Multiplikationen und Additionen (`VMULPS` + `VADDPS`) parallel aus, um die 2D-Gauß-Filterung des Frangi-Filters drastisch zu beschleunigen.

---

## 5. Deployment & Installer-Pipeline

### 5.1 Inno Setup 6 Installer (`installer/setup.iss`)
* **Architektur:** Reine 64-Bit-Installation (`ArchitecturesInstallIn64BitMode=x64compatible`).
* **Kompression:** `lzma2/ultra64` mit solidem Wörterbuch für minimale Dateigröße (28.3 MB Gesamt-Installer).
* **Auslieferungsinhalt:**
  * Kompilierte C# .NET 10 WPF Suite (`Ignite.Desktop.exe`).
  * Autonomer Go AVX2 Rechenkern (`ignite-core.exe`).
  * Klinische Lua-Regelskripte (`rules/*.lua`).
  * Vollständige wissenschaftliche Dokumentation (`docs/`).
  * Radiometrische Testaufnahmen (`test-data/`).
* **Sicherheit:** `PrivilegesRequired=lowest` – Installation ohne Administratorrechte im lokalen Benutzerprofil oder Systemordner möglich.

### 5.2 Automatisches Build-Skript (`installer/build_installer.ps1`)
Führt in vier automatisierten Schritten den kompletten Build aus:
1. `go build` des AVX2-Kerns.
2. `dotnet publish` der .NET 10 Desktop-Anwendung.
3. Synchronisation aller Regeln und Abhängigkeiten.
4. Aufruf des Inno Setup Compilers (`ISCC.exe`) zur Erstellung von `dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe`.

### 5.3 Kontinuierliche Integration (GitHub Actions)
In [`.github/workflows/ci_v5.yml`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/.github/workflows/ci_v5.yml) läuft bei jedem Push und Tag:
* Validierung aller Go- und AVX2-Assembler-Unittests.
* Kompilierung und Veröffentlichung der WPF-Suite.
* Installation von Inno Setup via Chocolatey.
* Generierung und Bereitstellung des Installers als Release-Artefakt.

---

## 6. Gemessene Performance (1440x1080 Thermogramm)

Gemessen auf x86_64 Standard-Hardware (Intel Core i7, 4 Kerne):

| Pipeline-Stufe | Technologie / Instruktion | Gemessene Latenz |
| :--- | :--- | :--- |
| **Körper-Maskierung (Otsu + Chamfer)** | Go (Goroutinen) | 19,6 ms |
| **Top-Hat-Filter (Opening + Differenz)** | x86_64 AVX2 (`VPMINUB`, `VPMAXUB`, `VPSUBUSB`) | **37,8 ms** |
| **Outlier-Thresholding (MAD + Maske)** | x86_64 AVX2 (`thresholdMaskAVX2`) | 4,2 ms |
| **Geometrie- & Zirkularitäts-Filter** | Go (4-Connected BFS) | 3,5 ms |
| **Frangi-Venenkartierung (3 Skalen)** | AVX2 Float32 FMA (`fmaVectorFloat32AVX2`) | 88,6 ms |
| **Longitudinaler Perfusion-Gradient** | Go ($dT/dy$ Kernel) | 2,0 ms |
| **Bilateraler Seitenvergleich** | AVX2 Abs-Diff (`absDiffVectorAVX2`) | 5,8 ms |
| **Klinische Risikobewertung** | Eingebettetes Lua (`armstrong_criteria.lua`) | < 0,1 ms |
| **Gesamtlaufzeit der Pipeline** | **End-to-End** | **~169,5 ms** |
| **GPU-Farbrendering (Ironbow)** | C# / WPF Hardware-Canvas | 0,0 ms (Hardware) |

