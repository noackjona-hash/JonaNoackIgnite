# IGNITE Medical Imaging Suite (v5.0.0)

**IGNITE** ist eine deterministische, hochauflösende Infrarot-Thermografie-Workstation zur automatisierten Früherkennung subklinischer Gewebeentzündungen, diabetischer Fußulzera und vaskulärer Auffälligkeiten. 

Entwickelt für den deutschen Jugendwettbewerb **Jugend forscht 2026** (Fachgebiet Arbeitswelt / Informatik), verbindet IGNITE modernste computergestützte Bildverarbeitung mit der Ergonomie klassischer medizinischer Diagnosestationen.

---

## 🚀 Neuheiten in Version 5.0.0

* **Venen- & Adernkartierung (Vascular Mapping):** Multiskaliger **Frangi-Vesselness-Filter** basierend auf der Hesse-Matrix $\mathcal{H}$ zur präzisen Segmentierung von Blutgefäßen und deren Unterscheidung von Entzündungsherden.
* **Perfusion & Longitudinaler Temperaturgradient ($dT/dy$):** Automatische Erkennung distaler Durchblutungsabbrüche zur Früherkennung von pAVK („Schaufensterkrankheit“) und diabetischer Mikroangiopathie.
* **Bilateraler Seitenvergleich (Armstrong-Kriterium $\Delta T \ge 2{,}2\,\text{K}$):** Spiegelbildlicher Vergleich beider Füße (L vs. R) zur eindeutigen Unterscheidung zwischen harmloser mechanischer Belastung (Socken/Druckstellen) und echten pathologischen Entzündungen.
* **Mehrsprachige High-Performance-Architektur:** Vollständiger Refaktor ohne C/C++-Compiler-Abhängigkeiten:
  * **Rechenkern:** **Go 1.27** mit parallelen Goroutinen.
  * **Hardware-Beschleunigung:** Reiner **x86_64 AVX2-Assembler** (`VPMINUB`, `VPMAXUB`, `VPSUBUSB`) für 32 Pixel parallel pro Takt.
  * **Workstation-Frontend:** **C# (.NET 10 / WPF)** im klassischen, dichten Ingenieurs-Look mit Dual-Viewport-Canvas und Echtzeit-Fadenkreuz.
  * **Klinische Entscheidungslogik:** Eingebettetes **Lua** zur Anpassung von Schwellenwerten ohne Neukompilierung.
  * **Datenschutz:** Revisionssicheres **SQLite-Audit-Log** mit SHA-256-Pseudonymisierung (`ANON-<hash>`).

---

## 🛠️ Software-Architektur

```
[ C# .NET 10 WPF Workstation ]  <─── Dual-Viewport, Fadenkreuz, Paletten, Inspector
              │
              ├── (Inter-Process Communication / CLI / JSON)
              ▼
[ Go 1.27 Rechenkern (ignite-core) ]
              │
              ├── (x86_64 AVX2 Assembler)  ──> Morphologie (Top-Hat) mit 32 Pixeln/Takt
              ├── (Go Goroutinen)           ──> Otsu, Chamfer-Distanz, Frangi-Filter, MAD
              ├── (Eingebettetes Lua)        ──> Armstrong-Kriterien (armstrong_criteria.lua)
              └── (SQLite Datenbank)         ──> DSGVO Art. 30 Audit-Log (ignite_medical.db)
```

---

## 📊 Gemessene Performance (1440x1080 JPEG)

| Pipeline-Stufe | Sprache / Technologie | Gemessene Latenz |
| :--- | :--- | :--- |
| **Körper-Maskierung (Otsu + Chamfer)** | Go (Goroutinen) | 19,6 ms |
| **Top-Hat-Filter (Opening + Differenz)** | x86_64 AVX2 Assembler | **1,4 ms** (@160x120) / **~500 ms** (@1440x1080) |
| **Outlier-Thresholding (MAD)** | Go ($O(N)$ Histogramm) | 4,4 ms |
| **Geometrie & Zirkularität** | Go (4-Connected BFS) | 3,5 ms |
| **Frangi-Venenkartierung (3 Skalen)** | Go (2D Convolutions) | ~2000 ms (optional zuschaltbar) |
| **Longitudinaler Gradient (Perfusion)** | Go | 2,0 ms |
| **Klinische Risikobewertung** | Eingebettetes Lua | < 0,1 ms |
| **GPU-Farbrendering (Ironbow)** | C# / WPF Hardware-Canvas | 0,0 ms CPU-Last |

---

## 💻 Schnellstart & Ausführung

### Voraussetzungen
* **Go 1.27+**
* **.NET 10 SDK**
* *(Kein C- oder C++-Compiler erforderlich!)*

### 1. Rechenkern kompilieren (Go + AVX2)
```bash
cd core
go test -v ./...
go build -o ignite-core.exe ./cmd/ignite-core
cd ..
```

### 2. Desktop-Workstation kompilieren & starten (C# .NET 10)
```bash
cd desktop
dotnet build -c Release
dotnet run --no-build -c Release
```

### 3. CLI-Analyse eines Einzelbildes
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
