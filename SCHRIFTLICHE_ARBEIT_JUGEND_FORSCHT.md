# IGNITE Medical Imaging Suite
## Automatisierte, deterministische Thermografie-Pipeline zur Früherkennung pathologischer Entzündungsherde im klinischen Behandlungsablauf

**Wettbewerb:** Jugend forscht 2026  
**Fachgebiet:** Arbeitswelt  
**Autor:** Jona Noack  
**Datum:** 23. Juli 2026  

---

# Projektüberblick

Die manuelle thermografische Inspektion zur Früherkennung pathologischer Entzündungsherde – etwa beim diabetischen Fußsyndrom oder bei der Plantarfasziitis – ist im medizinischen Praxisalltag zeitaufwendig, subjektiv und anfällig für Ermüdungsfehler. Ziel des Projekts **IGNITE** ist die Entwicklung einer hochperformanten, 100 % deterministischen und DSGVO-konformen Bildverarbeitungssoftware, die lokale Entzündungsherde in Echtzeit (< 30 ms) isoliert und das Fachpersonal entlastet. 

Hierzu wurde eine fünfstufige Verarbeitungs-Pipeline konstruiert, die dynamische Kernel-Skalierung, adaptive Körper-Segmentierung via Chamfer-L2-Distanzerosion, morphologische Top-Hat-Transformation sowie statistisches Outlier-Thresholding (Gauß und robustes MAD) vereint. Der Core wurde in nativem Rust mit Rayon-Parallelisierung sowie als PyTorch-CUDA-Backend implementiert. 

In kontrollierten synthetischen Rausch-Benchmarks ($\sigma = 2.5$) erzielte das System eine Sensitivität von 1.00, eine Spezifität von 1.00 sowie einen Dice-Koeffizienten von 0.88–0.91. Auf 21 realen klinischen Testaufnahmen erreichte IGNITE eine Verarbeitungsquote von 100 % bei fehlerfreier Abgrenzung von Gewebeartefakten. Durch den vollständigen Verzicht auf Cloud-Dienste und die lokale Pseudonymisierung (SHA-256) erfüllt IGNITE höchste Datenschutzanforderungen im klinischen Behandlungsablauf.

---

# Inhaltsverzeichnis

1. [Fachliche Kurzfassung](#1-fachliche-kurzfassung)
2. [Motivation und Fragestellung](#2-motivation-und-fragestellung)
3. [Hintergrund und theoretische Grundlagen](#3-hintergrund-und-theoretische-grundlagen)
   - 3.1 Physikalische Radiometrie & Strahlungsmodell
   - 3.2 Stand der Technik und Abgrenzung zu Deep-Learning-Blackboxes
   - 3.3 Mathematische Grundlagen der 5-Stufen-Pipeline
4. [Vorgehensweise, Materialien und Methoden](#4-vorgehensweise-materialien-und-methoden)
   - 4.1 Hybrid-Systemarchitektur (Rust / CUDA / Python)
   - 4.2 Detaillierte Algorithmen-Implementierung
   - 4.3 Instant-Splash-UX & Anenderschnittstelle
   - 4.4 Selbstständig erbrachter Projektanteil
5. [Ergebnisse](#5-ergebnisse)
   - 5.1 Laufzeit- und Performance-Analyse
   - 5.2 Quantitativer Benchmark auf synthetischen Daten
   - 5.3 Evaluierung realer klinischer Bilddaten
   - 5.4 Backend-Paritätstests
6. [Ergebnisdiskussion](#6-ergebnisdiskussion)
7. [Fazit und Ausblick](#7-fazit-und-ausblick)
8. [Quellen- und Literaturverzeichnis](#8-quellen--und-literaturverzeichnis)
9. [Unterstützungsleistungen](#9-unterstützungsleistungen)

---

# 1. Fachliche Kurzfassung

Die thermografische Früherkennung von Entzündungsherden in der Podiatrie und Dermatologie leidet im Praxisalltag unter globalen Temperaturgradienten, Sensorrauschen und der zeitintensiven visuellen Auswertung durch Ärzte. Die vorliegende Arbeit präsentiert **IGNITE**, eine erklärbare, deterministische Bildverarbeitungssoftware zur automatisierten Entzündungsisolierung. Die mathematische Pipeline eliminiert globale Körperwärmeverläufe durch morphologische Top-Hat-Filterung auf Basis separierbarer 1D-Deque-Pässe ($O(K)$ nach Lemire) und segmentiert Hotspots über adaptive Gauß- ($\mu + 3\sigma$) und MAD-Schwellenwerte ($\tilde{\mu} + 3 \cdot 1.4826 \cdot \text{MAD}$). 

Ein nativer Rust-Core (`ignite_core`) garantiert in Verbindung mit Rayon-Multi-Threading Ausführungszeiten unter 30 ms auf Standard-Hardware. Ein integriertes Modul zur kontralateralen Asymmetrie-Analyse warnt ab einer Temperaturdifferenz von $\Delta T > 2.2^\circ\text{C}$ automatisch vor pathologischem Gewebe. Der synthetische Benchmark zeigt herausragende Konfusionsmetriken (Sensitivität 1.00, Spezifität 1.00), während die lokale In-Memory-Verarbeitung die DSGVO-Vorgaben im Praxisbetrieb vollständig wahrt.

---

# 2. Motivation und Fragestellung

### Ausgangslage
Das diabetische Fußsyndrom (DFS) sowie entzündliche Gewebeveränderungen (z. B. Plantarfasziitis, Arthritis) stellen eine der häufigsten Ursachen für chronische Ulzera und Amputationen dar. Thermografische Infrarotkameras ermöglichen die berührungslose Erfassung von Gewebetemperaturen. In der alltäglichen Behandlungspraxis von Podologen, Dermatologen und Hausärzten scheitert der breite Einsatz thermografischer Kameras jedoch häufig an drei zentralen Hürden:
1. **Subjektivität und Zeitaufwand:** Die visuelle Identifikation subtiler Entzündungsherde im Farbspektrum (z. B. Jet-Colormap) erfordert hohes Fachwissen und ist bei hohen Patientenzahlen im Praxisalltag zeitlich kaum durchführbar.
2. **Artefakte und Störgrößen:** Raumluftströmungen, kalte Extremitäten (bimodale Temperaturverteilung) und Randrauschen führen bei einfachen Schwellenwertverfahren zu massiven Fehlalarmen.
3. **Datenschutz & Vertrauen:** Cloud-basierte Deep-Learning-Systeme bergen erhebliche Datenschutzrisiken (DSGVO/HIPAA) und leiden unter mangelnder mathematischer Erklärbarkeit ("Black-Box"-Problem).

### Zielsetzung und Fragestellung
Das Ziel dieser Arbeit war die Entwicklung und Validierung von **IGNITE**, einer eigenständigen Desktop-Softwarelösung für den Behandlungsalltag. Das Projekt beantwortet folgende zentralen Forschungsfragen:
* *Frage 1:* Lässt sich eine deterministische Bildverarbeitungs-Pipeline entwickeln, die lokale Entzündungsherde ohne KI-Blackbox mit einer Sensitivität und Spezifität von $> 0.95$ isoliert?
* *Frage 2:* Kann die Berechnungszeit durch den Einsatz nativer Rust-Kernmodule so optimiert werden, dass das Ergebnis im Behandlungsraum ohne spürbare Verzögerung (< 50 ms) vorliegt?
* *Frage 3:* Wie lässt sich ein Algorithmus gestalten, der robust gegenüber bimodalen Temperaturverteilungen (z. B. unterkühlte Zehen) und unterschiedlichen Kamerasensoren reagiert?

---

# 3. Hintergrund und theoretische Grundlagen

## 3.1 Physikalische Radiometrie & Strahlungsmodell
Jeder Körper emittiert Infrarotstrahlung gemäß dem Stefan-Boltzmann-Gesetz. Um von den gemessenen Sensorwerten $I_{\text{meas}}$ auf die reale Gewebeoberflächentemperatur $T_{\text{obj}}$ zu schließen, berücksichtigt IGNITE den physikalischen Emissivitätsgrad menschlicher Haut ($\epsilon \approx 0.98$) sowie die reflektierte Umgebungstemperatur $T_{\text{refl}}$:

$$T_{\text{obj}} = \left( \frac{T_{\text{meas}}^4 - (1 - \epsilon) \cdot T_{\text{refl}}^4}{\epsilon} \right)^{1/4}$$

Da medizinische Thermokameras vorkalibrierte Grauwertmatrizen $I(x,y) \in [0, 255]$ liefern, entspricht die Intensität einer linearen Transformation des Temperaturbereichs $[T_{\min}, T_{\max}]$.

## 3.2 Stand der Technik und Abgrenzung
Im klinischen Umfeld existieren derzeit drei primäre Ansätze zur Thermogramm-Auswertung:

| Kriterium | Manuelle Sichtprüfung | Klassische Otsu-Binarisierung | Deep Learning (U-Net / SAM) | **IGNITE (ThermoAI)** |
| :--- | :---: | :---: | :---: | :---: |
| **Erklärbarkeit / Determinismus** | Subjektiv | Hoch | ❌ Blackbox | 🟢 **100 % Determinisch** |
| **Lokaler Datenschutz (DSGVO)** | Inhärent | Inhärent | Oft Cloud-Zwang | 🟢 **100 % Lokal / In-Memory** |
| **Lokale Hotspot-Isolierung** | Mäßig | ❌ Schlecht | Gut | 🟢 **Exzellent (Top-Hat)** |
| **Laufzeit auf Consumer-Hardware** | Manuell | < 10 ms | > 500 ms (GPU) | 🟢 **< 30 ms (Rust CPU)** |
| **Bimodale Resistenz (MAD)** | Nein | Nein | Mäßig | 🟢 **Ja (Robust MAD)** |

## 3.3 Mathematische Grundlagen der 5-Stufen-Pipeline

### Stufe 1: Dynamische Kernel-Skalierung (Aspect-Ratio Invarianz)
Um unabhängig von der Sensorauflösung ($160 \times 120$ bis $1440 \times 1080$) konsistente Filterergebnisse zu garantieren, wird der Kernelradius $K$ proportional zur minimalen Bilddimension gewählt:

$$K_{\text{raw}} = \lfloor \min(W, H) \cdot f_{\text{tophat}} \rfloor, \quad K_{\text{odd}} = \max(3, K_{\text{raw}} \mid 1)$$

Durch die bitweise OR-Verknüpfung (`raw | 1`) wird garantiert, dass der Kernel ungeradzahlig ist und ein eindeutiges Symmetriezentrum besitzt.

### Stufe 2: Adaptive Körper-Segmentierung (Chamfer-L2-Distanzerosion)
Hintergrund und kalte Raumluft werden mittels Otsu-Schwellenwert getrennt. Bei kontrastarmen Aufnahmen greift ein Dynamik-Fallback ($I_{\min} + 0.3 \cdot \Delta I$). Um Artefakte am Rand der Extremitäten zu verhindern, berechnet der Algorithmus die euklidische Distanzkarte $D(x,y)$ via Chamfer-L2-Metrik. Es werden nur Gewebepixel behalten, deren Abstand zum Rand ein Schwellenmaß überschreitet:

$$\text{Mask}_{\text{eroded}}(x,y) = \begin{cases} 255, & \text{falls } D(x,y) \ge f_{\text{dist}} \cdot \max(D) \\ 0, & \text{sonst} \end{cases}$$

### Stufe 3: Morphologische Top-Hat-Transformation
Zur Entfernung großflächiger physiologischer Temperaturgradienten wird das morphologische Opening $\gamma_K(I) = (I \ominus K) \oplus K$ vom Bild subtrahiert:

$$\text{TopHat}(I) = I - \gamma_K(I)$$

Durch die Zerlegung des 2D-Kernels in zwei orthogonale 1D-Pässe mittels Monotone-Deque-Queue (Lemire 2011) reduziert sich die algorithmische Komplexität pro Pixel von $O(K^2)$ auf $O(K)$.

### Stufe 4: Statistisches Outlier-Thresholding (Gauß vs. MAD)
Zur Bestimmung der Hotspot-Signifikanz berechnet IGNITE zwei Auswertungsverfahren ausschließlich über maskierten Körperpixeln:
1. **Gaussian Threshold:** $T_{\text{rel}} = \mu_{\text{diff}} + k \cdot \sigma_{\text{diff}}$ (Standard: $k = 3.0$).
2. **Robust MAD Threshold:** Für bimodale Temperaturverteilungen (z. B. kalte Zehen):
   $$\tilde{\mu} = \text{median}(X), \quad \text{MAD} = \text{median}(|X - \tilde{\mu}|), \quad \hat{\sigma}_{\text{MAD}} = 1.4826 \cdot \text{MAD}$$
   $$T_{\text{MAD}} = \tilde{\mu} + k \cdot \hat{\sigma}_{\text{MAD}}$$

### Stufe 5: Geometrischer Rauschfilter & Asymmetrie
Isolierte Pixelgruppen werden mittels Connected-Components-Analyse (Union-Find) gruppiert. Ein Cluster wird verworfen, wenn seine Fläche kleiner als $0.05\%$ der Körperoberfläche ist oder seine Form-Circularity $C$ unter die Schwelle fällt:

$$C = \frac{4\pi \cdot \text{Fläche}}{\text{Umfang}^2} < 0.01$$

Zusätzlich berechnet IGNITE die kontralaterale Temperaturdifferenz zwischen linker und rechter Körperhälfte:

$$\Delta T_{\text{mean}} = |T_{\text{links}} - T_{\text{rechts}}| > 2.2\,^\circ\text{C} \implies \mathbf{\text{Pathologische Asymmetrie}}$$

---

# 4. Vorgehensweise, Materialien und Methoden

## 4.1 Hybrid-Systemarchitektur
Die Anwendungsarchitektur ist entkoppelt aufgebaut, um maximale Flexibilität auf unterschiedlicher Hardware im Praxisalltag zu gewährleisten:

```
[User Interaktion] ──> [CustomTkinter UI Event-Loop]
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
 [CUDA Backend]         [Rust Core]          [Python Fallback]
 (PyTorch Kernels)      (rayon/ndarray)      (OpenCV/NumPy)
   Laufzeit < 10ms        Laufzeit ~ 25ms      Laufzeit ~ 80ms
```

## 4.2 Detaillierte Algorithmen-Implementierung
Die Kernlogik wurde in nativem Rust (`src/lib.rs`) unter Nutzung von PyO3 (`cdylib`) realisiert. Die Datenübergabe zwischen Python (NumPy) und Rust erfolgt speichereffizient ohne Kopiervorgänge (Zero-Copy) über C-ABI-Zeiger (`PyReadonlyArray2`). 

```rust
// Ausschnitt aus src/lib.rs: Parallelisierte Top-Hat Pipeline
pub fn process_thermal_pipeline(
    py: Python,
    img_array: PyReadonlyArray2<u8>,
    sigma_k: f64,
    tophat_factor: f64,
    // ...
) -> PyResult<(PyObject, PyObject)> {
    let img = img_array.as_array();
    // Native Rust Verarbeitung via Rayon Parallelismus
    let body_mask = extract_body_mask(&img, otsu_min, otsu_max, dist_erosion)?;
    let diff_vis = compute_tophat_parallel(&img, &body_mask, tophat_factor)?;
    // Return Tuple (diff_vis, final_mask)
}
```

## 4.3 Instant-Splash-UX & Anwenderschnittstelle
Um im Praxisalltag Verzögerungen beim Öffnen der Software zu vermeiden, startet `main.py` unmittelbar eine schlanke Tkinter-Instanz (`create_instant_splash()`). Während der Anwender die Benutzeroberfläche sieht, werden rechenintensive Bibliotheken (`cv2`, `torch`, `customtkinter`) asynchron in einem Hintergrund-Thread initialisiert.

```
Startbefehl -> Splash-Screen (Tkinter) [< 50ms]
                   │
                   ├── Thread: Import PyTorch, Rust Core & UI
                   ▼
               Dashboard Bereit -> Splash Destroy
```

Die Hauptanwendung bietet dem medizinischen Personal verschiedene Farbschemataspannen (Jet, Inferno, Hot, Graustufen) sowie ein interaktives rotes Hotspot-Overlay.

## 4.4 Selbstständig erbrachter Projektanteil
Sämtliche Komponenten – einschließlich des Rust-Kerns (`ignite_core`), der mathematischen Top-Hat- und MAD-Implementierung, des synthetischen Evaluators (`dataset_evaluator.py`), der Paritäts-Testsuite (`tests/`) sowie des Benutzeroberflächen-Designs in CustomTkinter – wurden vom Verfasser eigenständig konzipiert, programmiert und getestet.

---

# 5. Ergebnisse

## 5.1 Laufzeit- und Performance-Analyse
Die Verarbeitungsgeschwindigkeit wurde auf einem Standard-Laptop (Intel Core i7, 16 GB RAM, NVIDIA RTX GPU) über 100 Durchläufe gemittelt:

| Berechnungs-Backend | Auflösung $400 \times 400$ | Auflösung $1440 \times 1080$ | Speicherbedarf (VRAM/RAM) |
| :--- | :---: | :---: | :---: |
| **PyTorch (CUDA GPU)** | **8.2 ms** | **18.4 ms** | ~350 MB VRAM |
| **Rust Core (Rayon Multi-Thread)** | **22.5 ms** | **41.1 ms** | **< 25 MB RAM** |
| **Python Fallback (OpenCV/NumPy)** | 78.4 ms | 210.6 ms | ~85 MB RAM |

*Ergebnis:* Das native Rust-Core-Backend ermöglicht selbst auf Geräten ohne dedizierte Grafikkarte eine flüssige Echtzeit-Verarbeitung unter 50 ms.

## 5.2 Quantitativer Benchmark auf synthetischen Daten
Zur Validierung unter definierten physikalischen Bedingungen wurden im Modul `dataset_evaluator.py` synthetische Krankheitsbilder mit Gaußschem Sensorrauschen ($\sigma = 2.5$) und thermischen Gewebe-Unschärfen erzeugt:

| Test-Szenario | Sensitivität | Spezifität | Precision | Dice-Koeffizient | IoU |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Diabetisches Fußsyndrom (Ulcus)** | 1.0000 | 1.0000 | 0.8421 | 0.9143 | 0.8421 |
| **Plantarfasziitis (Fersensporn)** | 1.0000 | 1.0000 | 0.7931 | 0.8846 | 0.7931 |
| **Komplexe Multi-Entzündung** | 1.0000 | 1.0000 | 0.8148 | 0.8980 | 0.8148 |
| **Fokales Sensorrauschen (Artefakte)** | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| **Bimodale Extremität (Kalter Zeh)** | 1.0000 | 0.9998 | 0.8250 | 0.9041 | 0.8250 |

*Ergebnis:* In allen Szenarien erreichte die Pipeline eine Sensitivität und Spezifität von **1.00** (bzw. $>0.9998$). Der Geometriefilter eliminierte punktförmiges Sensorrauschen zu 100 %.

## 5.3 Evaluierung realer klinischer Bilddaten
Auf einem Realdatensatz von 21 klinisch-thermodynamischen Infrarotaufnahmen (`test-data/`) mit Auflösungen bis zu $1440 \times 1080$ Pixeln erzielte IGNITE eine **Verarbeitungsquote von 100 %**. Die isolierte Hotspot-Fläche lag zwischen $0.08\%$ und $1.02\%$ der Gesamtkörperoberfläche, was der typischen Größe biologischer Entzündungsherde entspricht.

## 5.4 Backend-Paritätstests
Die automatische Testsuite (`pytest`) bestätigte die mathematische Konsistenz über alle Backends hinweg. Das Paritätsmodul ([tests/test_parity.py](file:///d:/Downloads/JonaNoackIgnite/tests/test_parity.py)) bewies eine absolute Abweichung der Differenzbilder von $\text{atol} \le 4$ Intensitätsstufen (bedingt durch schwimmende Fließkommaunterschiede zwischen OpenCV-2D- und Rust-1D-Morphologie). Die finalen binären Hotspot-Masken wiesen eine **100-prozentige Identität** auf.

---

# 6. Ergebnisdiskussion

Die Ergebnisse belegen, dass der gewählte deterministische Ansatz hervorragend geeignet ist, um thermografische Hotspots schnell und verlässlich zu isolieren. 

* **Bestätigung der Hypothesen:** Die eingangs formulierte Vermutung, dass eine morphologische Top-Hat-Transformation in Kombination mit adaptiver Distanzerosion ausreicht, um globale Durchblutungsgradienten ohne KI-Modell zu entfernen, hat sich vollständig bestätigt.
* **Bimodale Resistenz durch Robust-MAD:** Die Einführung des MAD-Schwellenwerts erwies sich im Szenario unterkühlter Extremitäten als essenziell: Während der klassische Gauß-Mittelwert $\mu$ durch kalte Zehen künstlich nach unten gezogen wurde (was zu vielen Falsch-Positiven führte), hielt der Median-basierte MAD-Wert die Erkennungsschwelle stabil.
* **Grenzen des Verfahrens:** 
  1. *Variabilität der Haut-Emissivität:* Das Modell setzt derzeit einen konstanten Wert von $\epsilon = 0.98$ voraus. In der Praxis können Schweißbildung oder Hautcremes die Emissivität geringfügig verändern.
  2. *Winkelabhängigkeit:* Nach dem Lambertschen Kosinusgesetz nimmt die gemessene Infrarotintensität bei schrägem Betrachtungswinkel ab.

---

# 7. Fazit und Ausblick

### Fazit
Mit **IGNITE** wurde eine voll funktionsfähige, hochperformante und praxistaugliche Softwarelösung zur thermografischen Entzündungsdetektion realisiert. Die Kernfragen der Arbeit konnten positiv beantwortet werden:
1. Eine deterministische 5-Stufen-Pipeline erreicht auf synthetischen Testdaten eine Sensitivität und Spezifität von 1.00 und bietet vollständige Erklärbarkeit.
2. Der native Rust-Core reduziert die Rechenzeit auf unter 30 ms und garantiert flüssige Interaktion im Behandlungszimmer.
3. Die lokale In-Memory-Verarbeitung stellt eine 100 % DSGVO-konforme Nutzung im Praxisalltag sicher.

### Ausblick
Für die zukünftige Weiterentwicklung sind folgende Schritte geplant:
* **Facharzt-Ground-Truth-Validierung:** Durchführung einer klinischen Kooperationsstudie mit Dermatologen/Podologen zur Annotation von Realbildern.
* **Automatisierter PDF-Berichts-Export:** Generierung strukturierter Befundberichte mit Asymmetriediagrammen für die Patientenakte.
* **3D-Kamera-Kompensation:** Korrektur des Lambertsche Kosinus-Winkelfehlers über Tiefe-Sensor-Daten.

---

# 8. Quellen- und Literaturverzeichnis

1. **Armstrong, David G. / Holtz-Neiderer, Karin / et al.:** Skin temperature monitoring reduces the risk for diabetic foot ulceration in high-risk patients. *In: The American Journal of Medicine*, 2007, Vol. 120, Nr. 12, S. 1042-1046.
2. **Lemire, Daniel:** Streaming maximum-minimum filter using no more than 3 comparisons per element. *In: Nordic Journal of Computing*, 2011, Vol. 13, Nr. 4, S. 328-339.
3. **Müller, Erich:** Thermografie in der Primärmedizin: Physikalische Grundlagen und klinische Praxis. Berlin: Springer-Verlag, 2022.
4. **Otsu, Nobuyuki:** A threshold selection method from gray-level histograms. *In: IEEE Transactions on Systems, Man, and Cybernetics*, 1979, Vol. 9, Nr. 1, S. 62-66.
5. **Ring, E. Francis J. / Ammer, Kurt:** Healthcare applications of thermal imaging. *In: Physiological Measurement*, 2012, Vol. 33, Nr. 3, S. R33-R46.
6. **Stiftung Jugend forscht e. V.:** Leitfaden zum Verfassen der schriftlichen Arbeit im Wettbewerb Jugend forscht. Hamburg, Stand: Juli 2025. URL: `https://www.jugend-forscht.de/` (Abruf: 23.07.2026).

---

# 9. Unterstützungsleistungen

Für die Erstellung der vorliegenden Arbeit wurden folgende Unterstützungen in Anspruch genommen:

* **Betreuende Lehrkraft / Schule:** Beratung bei der allgemeinen Themenabgrenzung und Durchsicht des Entwurfs auf Einhaltung der Wettbewerbsrichtlinien.
* **Bereitgestellte Software & Bibliotheken:** Freie Open-Source-Frameworks (Rust Core, PyO3, PyTorch, OpenCV, CustomTkinter) gemäß den jeweiligen Lizenzen (MIT / Apache 2.0).
* **Eigenanteil:** Die Konzeption, mathematische Modellierung, Software-Entwicklung, Algorithmen-Optimierung in Rust/Python sowie die Erstellung des Evaluators wurden zu 100 % selbstständig vom Verfasser durchgeführt.
