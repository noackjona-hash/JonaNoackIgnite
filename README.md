# IGNITE Medical Imaging Suite (v5.0.0)

**IGNITE** ist eine deterministische, hochauflösende Infrarot-Thermografie-Workstation zur automatisierten Früherkennung subklinischer Gewebeentzündungen, diabetischer Fußulzera und vaskulärer Auffälligkeiten. 

Entwickelt für den deutschen Jugendwettbewerb **Jugend forscht 2026** (Fachgebiet Arbeitswelt / Informatik), verbindet IGNITE modernste computergestützte Bildverarbeitung mit der Ergonomie klassischer medizinischer Diagnosestationen.

---

## 🚀 Neuheiten & Highlights in Version 5.0.0

* **Next-Gen Obsidian Glass Cockpit & Ergonomie:**
  * **Obsidian Medical Dark Mode:** Ergonomisches, kontrastoptimiertes Farbkonzept (`#07090E` Deep Space Canvas, `#0D111A` Frosted Slate Glass, `#00F0FF` Laser Cyan, `#2563EB` Cobalt Blue, `#FF2A55` Armstrong Alarm Red).
  * **Interaktiver Vorhang-Wipe-Split-Slider (`[🌓 Vorhang-Wipe]`):** Stufenloses, interaktives Überblenden per beweglichem Center-Handle `[ ◀ 🌓 ▶ ]` zwischen dem Roh-Wärmebild und dem radiometrischen Befund-Overlay mit hardware-beschleunigtem Clipping.
  * **2.5D Isometrisches Relief-Topografie-Mapping (`[🏔️ 3D-Relief]`):** Räumliche 2.5D-Projektion der Temperaturwerte als 3D-Relief mit berechnetem Hillshading (Schattierungsvektor) – pathologische Hyperthermien heben sich wie vulkanische Bergspitzen unmittelbar vom kühleren Normalgewebe ab.
  * **256-Kanal Radiometrisches Histogramm & Quantilspektrum (`[📊 Spektrum]`):** Live-Histogramm aller 256 Graustufen/Temperaturstufen mit visueller Kennzeichnung von Median, Normalinterquartilbereich (Q25–Q75) und pathologischen MAD-Ausreißerschwellen direkt über dem Farbskalen-Ramp.
  * **5-Zonen Anatomische Armstrong-Matrix (`[🦶 Zonen]`):** Automatische anatomische Zerlegung des Fußes in Hallux (Großzehe), Metatarsale I–II (medialer Ballen), Metatarsale III–V (lateraler Ballen), Plantargewölbe (Mittelfuß) und Calcaneus (Ferse) mit zonenbasierter Ulkus-Risikostufe (Klasse 0 bis 3).
  * **Dual-Viewport & Live-Fadenkreuz:** Synchronisiertes Pan & Zoom zwischen Infrarot-Originalaufnahme und diagnostischem Befund-Overlay mit pixelgenauer Temperatur- & Differenzanzeige.
  * **Modulare Inspector-Tabs:** Schneller Wechsel zwischen Entzündungsherden (Hotspots), Frangi-Venenkartierung, Perfusion-Gradienten, Radiometrie-Spektrum und 5-Zonen-Matrix.
* **Venen- & Adernkartierung (Vascular Mapping):** Multiskaliger **Frangi-Vesselness-Filter** basierend auf der 2D-Hesse-Matrix $\mathcal{H}$ zur präzisen Segmentierung tubulärer Blutgefäße und deren Unterscheidung von Entzündungsherden.
* **Perfusion & Longitudinaler Temperaturgradient ($dT/dy$):** Automatische Erkennung distaler Durchblutungsabbrüche zur Früherkennung von pAVK („Schaufensterkrankheit“) und diabetischer Mikroangiopathie.
* **Bilateraler Seitenvergleich (Armstrong-Kriterium $\Delta T \ge 2{,}2\,\text{K}$):** Spiegelbildlicher Vergleich beider Extremitäten (L vs. R) zur eindeutigen Unterscheidung zwischen harmloser mechanischer Belastung (Socken/Druckstellen) und echten pathologischen Entzündungen.
* **6 spezialisierte x86_64 AVX2-Assembler-Kernels:**
  * `minVectorAVX2` & `maxVectorAVX2`: 32 Pixel parallel pro CPU-Takt für morphologische Erosion und Dilation.
  * `subVectorAVX2`: Sättigende Subtraktion (`VPSUBUSB`) für die Top-Hat-Filterung.
  * `absDiffVectorAVX2`: Vektorisierte Differenz $|a - b|$ für den Armstrong-Seitenvergleich.
  * `thresholdMaskAVX2`: Gleichzeitiges Binarisieren, Schwellwertabgleich und Gewebemaskierung in 256-Bit-Registern.
  * `fmaVectorFloat32AVX2`: Vektorisierte Gleitkomma-Faltung für den Frangi-Gefäßfilter.
* **Automatisierter Windows-Installer (Inno Setup 6):**
  * Standalone-Installationsassistent (`dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe`, 28.3 MB) mit LZMA2/Ultra64-Kompression, Startmenü- und Desktop-Icons sowie sauberem Uninstaller.
  * Ein-Klick-Buildskript [`installer/build_installer.ps1`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/installer/build_installer.ps1).
* **CI/CD GitHub Actions Workflow:** Vollautomatisches Testen des AVX2-Kerns, Kompilieren der .NET 10 WPF Suite, Bauen des Inno Setup Installers und Veröffentlichen von Release-Artefakten via [`.github/workflows/ci_v5.yml`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/.github/workflows/ci_v5.yml).

---

## 🛠️ Software-Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. C# (.NET 10 / WPF)                                                        │
│    OBSIDIAN MEDICAL WORKSTATION GUI                                         │
│    - Dual-Viewport mit synchronem Zoom/Pan und Fadenkreuz                   │
│    - DSGVO-Pseudonymisierung (ANON-<hash>), Hardware-Status-Pills           │
│    - Kalibrierte Farbskala (Ironbow/Rainbow), Docking-Tabs, Hotspot-Liste   │
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
│    HARDWARE INNER-LOOP (6 KERNELS)                                          │
│    - VPMINUB, VPMAXUB, VPSUBUSB, VPOR, VMULPS, VADDPS                       │
│    - 32 Byte-Pixel bzw. 8 Float32-Werte GLEICHZEITIG pro Taktzyklus         │
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

## 📊 Gemessene Performance (1440x1080 Thermogramm)

| Pipeline-Stufe | Technologie / Instruktion | Gemessene Latenz |
| :--- | :--- | :--- |
| **Körper-Maskierung (Otsu + Chamfer)** | Go (Goroutinen) | 19,6 ms |
| **Top-Hat-Filter (Opening + Differenz)** | x86_64 AVX2 (`VPMINUB`, `VPMAXUB`, `VPSUBUSB`) | **37,8 ms** (@1440x1080) / **1,4 ms** (@160x120) |
| **Outlier-Thresholding (MAD + Maske)** | x86_64 AVX2 (`thresholdMaskAVX2`) | 4,2 ms |
| **Geometrie & Zirkularität** | Go (4-Connected BFS) | 3,5 ms |
| **Frangi-Venenkartierung (3 Skalen)** | AVX2 Float32 FMA (`fmaVectorFloat32AVX2`) | 88,6 ms |
| **Longitudinaler Gradient (Perfusion)** | Go ($dT/dy$ Kernel) | 2,0 ms |
| **Bilateraler Seitenvergleich** | AVX2 Abs-Diff (`absDiffVectorAVX2`) | 5,8 ms |
| **Klinische Risikobewertung** | Eingebettetes Lua (`armstrong_criteria.lua`) | < 0,1 ms |
| **Gesamte Pipeline-Laufzeit** | **End-to-End** | **~169,5 ms** |
| **GPU-Farbrendering (Ironbow)** | C# / WPF Hardware-Canvas | 0,0 ms CPU-Last |

---

## 📦 Installation & Ausführung

### Option A: Windows Installer (Empfohlen)
Laden Sie die aktuelle Setup-Datei aus dem Release-Verzeichnis oder GitHub Actions herunter und führen Sie sie aus:
* **Datei:** `dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe` (28.3 MB)
* Installiert die vollständige Anwendung inklusive aller vorkompilierten AVX2-Binärdateien, Lua-Regeln, Testdaten und Dokumentationen.

### Option B: Automatisiertes Build-Skript (PowerShell)
Um das gesamte Projekt inklusive Go-Kern, .NET 10 WPF Suite und Inno Setup Installer aus dem Quellcode zu bauen:
```powershell
.\installer\build_installer.ps1
```

### Option C: Manueller Start für Entwickler

#### 1. Rechenkern kompilieren & testen (Go + AVX2)
```bash
cd core
go test -v ./pkg/...
go build -o ignite-core.exe ./cmd/ignite-core
cd ..
```

#### 2. Desktop-Workstation kompilieren & starten (C# .NET 10)
```bash
cd desktop
dotnet build -c Release
dotnet run --no-build -c Release
```

#### 3. CLI-Analyse eines Einzelbildes
```bash
.\core\ignite-core.exe -mode=cli -input="test-data/bild (1).jpeg" -output="ergebnis.json"
```

---

## 📜 Klinische Lua-Regeln

Die medizinische Klassifikation erfolgt dynamisch über Textskripte im Ordner `rules/`:
* [`rules/armstrong_criteria.lua`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/rules/armstrong_criteria.lua): Armstrong-Kriterien ($\Delta T \ge 2{,}2\,\text{K}$ und Zirkularität).
* [`rules/vein_detection.lua`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/rules/vein_detection.lua): Unterscheidung von röhrenförmigen Gefäßen und runden Herden.
* [`rules/perfusion_eval.lua`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/rules/perfusion_eval.lua): Stadieneinteilung von Durchblutungsabbrüchen.

---

## 📖 Wissenschaftliche Dokumentation
* [Architektur-Dokumentation v5.0.0](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/docs/ARCHITECTURE_v5.md)
* [Mathematische Algorithmen-Beschreibung](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/docs/ALGORITHM.md)
* [Schriftliche Arbeit (Jugend forscht 2026)](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/docs/SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md)

