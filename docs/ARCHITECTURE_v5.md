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

---

## 2. Mehrsprachiges Software-Design (Separation of Concerns)

Um maximale Rechenleistung, Plattformunabhängigkeit, klinische Flexibilität und ein ergonomisches Bediengefühl zu vereinen, wurde das System in **fünf spezialisierte Sprachen** unterteilt – **strikt ohne C- oder C++-Compiler**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. C# (.NET 10 / WPF)                                                        │
│    KLASSISCHE MEDICAL WORKSTATION GUI                                       │
│    - Echtes Desktop-Feeling (wie ImageJ / OsiriX / Siemens Diagnostik)      │
│    - Dual-Viewport mit synchronem Zoom/Pan und Fadenkreuz                   │
│    - Docking-Panels, Schieberegler, False-Color Paletten (Ironbow/Rainbow)   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Lokaler IPC-Aufruf (CLI / HTTP JSON)
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
│    DIE HARDWARE-INNER-LOOP                                                  │
│    - VPMINUB, VPMAXUB, VPSUBUSB Vektorinstruktionen                         │
│    - Verarbeitet 32 Pixel GLEICHZEITIG in 1 CPU-Taktzyklus                  │
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
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. SQL (SQLite)                                                             │
│    REVISIONSSICHERES AUDIT-LOG & DATENSCHUTZ                                │
│    - DSGVO Art. 30 Konformität: Lokale Pseudonymisierung (ANON-<hash>)      │
│    - Speicherung von Messreihen, Parametern und Schwellenwerten             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Die Algorithmen im Detail

### 3.1 AVX2-Vektorassembler für morphologische Top-Hat-Filterung
Das morphologische Opening subtrahiert physiologische Temperaturverläufe vom Originalbild:
$$\text{TopHat}(I) = I - ((I \ominus K) \oplus K)$$
In `core/pkg/morphology/avx2_amd64.s` werden die inneren Schleifen mit AVX2-Registern (`YMM0`–`YMM2`) ausgeführt. 256-Bit-Vektoren verarbeiten jeweils 32 vorzeichenlose 8-Bit-Pixel parallel:
* `VPMINUB`: Vektorweises Minimum (Erosion).
* `VPMAXUB`: Vektorweises Maximum (Dilation).
* `VPSUBUSB`: Sättigende Subtraktion (Top-Hat-Differenz).

### 3.2 Frangi-Vesselness-Filter (Venenkartierung)
Für jede Bildskala $\sigma \in \{1.0, 2.0, 3.0\}$ wird die Hesse-Matrix berechnet:
$$\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}$$
Über die Eigenwerte $\lambda_1, \lambda_2$ (mit $|\lambda_1| \le |\lambda_2|$) werden tubuläre Gefäße isoliert:
* **Blobness:** $R_B = |\lambda_1| / |\lambda_2|$
* **Strukturstärke:** $S = \sqrt{\lambda_1^2 + \lambda_2^2}$
* **Reaktionsfunktion:**  
  $$V(\sigma) = \begin{cases} \exp\left(-\frac{R_B^2}{2\beta^2}\right) \cdot \left(1 - \exp\left(-\frac{S^2}{2c^2}\right)\right), & \text{falls } \lambda_2 < 0 \\ 0, & \text{sonst} \end{cases}$$

### 3.3 Bilateraler Seitenvergleich (Armstrong-Kriterium)
Das gespiegelte kontralaterale Bild $I_{\text{right, mirrored}}$ wird punkt- und zonenweise mit dem Primärbefund verglichen:
$$\Delta T(x, y) = |I_{\text{left}}(x, y) - I_{\text{right, mirrored}}(x, y)|$$
* $\Delta T < 1{,}0\,\text{K}$: Physiologische Normalvarianz oder beidseitige Druckbelastung (kein Herd).
* $\Delta T \ge 2{,}2\,\text{K}$: **Signifikanter pathologischer Entzündungsherd nach Armstrong et al.**

---

## 4. Benchmarks & Latenzen (1440x1080 JPEG)

Gemessen auf Standard-Desktop-Hardware (x86_64, 4 Kerne):

| Pipeline-Stufe | Implementierungssprache | Latenz |
| :--- | :--- | :--- |
| **Körper-Maskierung (Otsu + Chamfer)** | Go (Goroutinen) | 19,6 ms |
| **Top-Hat-Filter (Opening + Subtraktion)** | x86_64 AVX2 Assembler | **~500 ms** (1440x1080) / **1,4 ms** (160x120 Sensor) |
| **Statistisches Outlier-Thresholding (MAD)** | Go (O(N) Histogramm) | 4,4 ms |
| **Geometrie- & Zirkularitäts-Filter** | Go (4-Connected BFS) | 3,5 ms |
| **Frangi-Venenkartierung (3 Skalen)** | Go (2D Convolutions) | ~2000 ms (optional zuschaltbar) |
| **Longitudinaler Perfusion-Gradient** | Go | 2,0 ms |
| **Klinische Risikobewertung** | Eingebettetes Lua | < 0,1 ms |
| **GPU-Farbrendering (Ironbow)** | C# / WPF Pixel-Format | 0,0 ms (Hardware-Canvas) |
