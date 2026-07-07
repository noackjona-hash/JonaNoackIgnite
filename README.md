# IGNITE // Thermografische Entzündungsdetektion

> **Wettbewerbsprojekt Jugend forscht 2026**  
> Eine hochoptimierte Hybridlösung zur automatisierten Erkennung lokaler Entzündungsherde (Hotspots) in thermografischen Aufnahmen unter Verwendung von PyTorch-GPU, Rust-nativem Multithreading (Rayon) und Python (CustomTkinter).

---

## 🔍 Inhaltsverzeichnis
1. [Projektbeschreibung & Analysemodi](#-projektbeschreibung--analysemodi)
2. [Systemarchitektur & Hybrid-Backend](#-systemarchitektur--hybrid-backend)
3. [Die 5 Bildverarbeitungsstufen (Mathematische Pipeline)](#-die-5-bildverarbeitungsstufen-mathematische-pipeline)
4. [Durchgeführte Performance-Optimierungen](#-durchgeführte-performance-optimierungen)
5. [Modernes Design-System (Slate & Indigo)](#-modernes-design-system-slate--indigo)
6. [Installation & Build-Prozess](#-installation--build-prozess)
7. [Bedienung & Ergebnisberichte](#-bedienung--ergebnisberichte)
8. [Troubleshooting & Fehlerbehebung](#-troubleshooting--fehlerbehebung)

---

## 💡 Projektbeschreibung & Analysemodi

IGNITE dient der Früherkennung lokaler Entzündungsherde (z. B. bei chronischen Entzündungen, rheumatischen Erkrankungen oder zur Prävention des Diabetischen Fußsyndroms). Die Software wertet Wärmebilddaten aus und bietet zwei Betriebsmodi:

*   **Allgemeine Analyse (Standard)**: Erkennt und markiert beliebige thermische Hotspots am gesamten Körper (z. B. Gelenke, Rücken, Hände). Einzelne Hitzeinseln werden isoliert, nummeriert und detailliert vermessen.
*   **Fuß-Symmetrieanalyse**: Führt eine paarweise Zonenanalyse beider Füße durch. Das System unterteilt die Füße anatomisch in drei Zonen (Vorfuß, Mittelfuß, Ferse) und vergleicht die jeweilige linke mit der rechten Durchschnittstemperatur zur Erkennung asymmetrischer Hitzeverteilungen.

---

## 🚀 Systemarchitektur & Hybrid-Backend

Die Software nutzt eine hybride Berechnungsarchitektur, um plattformunabhängig maximale Performance zu erzielen. Beim Programmstart wird das am besten geeignete Berechnungs-Backend automatisch gewählt:

```
                           [ Wärmebild geladen ]
                                     |
                                     v
                           [ Backend-Entscheidung ]
                          /          |             \
                         /           |              \
           [ NVIDIA GPU ? ]    [ CPU mit Rust ? ]   [ Sonstiges ]
                 |                   |                   |
                 v                   v                   v
           PyTorch (CUDA)       Rust (Rayon)       Python Fallback
             (< 10 ms)           (~30 ms)            (~80 ms)
```

1.  **NVIDIA GPU-Pfad (PyTorch CUDA, < 10 ms)**: Verarbeitet Daten direkt im Grafikspeicher (VRAM). Perfekt für die Stapelverarbeitung großer Datenmengen.
2.  **CPU-Pfad (Rust-Core, ~30 ms)**: Bindet ein natives Rust-Kompilat (`ignite_core`) via **PyO3** ein. Die Berechnungen sind mittels **Rayon** parallelisiert und laufen extrem performant auf allen verfügbaren CPU-Kernen, vollkommen unabhängig von schweren C++-Runtimes.
3.  **Python-Fallback (OpenCV CPU, ~80 ms)**: Sichert die Ausführbarkeit der Applikation auf beliebigen Systemen, falls weder CUDA noch der Rust-Compiler verfügbar waren.

---

## 🧮 Die 5 Bildverarbeitungsstufen (Mathematische Pipeline)

Die Detektion stützt sich auf eine fünfstufige Pipeline zur präzisen Extraktion pathologischer Temperaturschwankungen:

### 1. Dynamische Kernel-Skalierung (Feature A)
Um Bildauflösungen unabhängig zu verarbeiten, skaliert das System die Radien $R$ aller morphologischen Operatoren proportional zur Bildbreite $W$:
$$R_{\text{tophat}} = \text{tophat-factor} \cdot W$$

### 2. Adaptive Körper-Segmentierung / Body-Mask (Feature B)
Das Objekt wird mittels Otsu-Binarisierung vom Hintergrund getrennt. Der Schwellenwert $T$ wird künstlich auf das Temperaturintervall $[\text{otsu-min}, \text{otsu-max}]$ beschränkt, um kältere Gliedmaßen zuverlässig zu maskieren. Es folgt eine euklidische Distanztransformation (Chamfer-3-4-Metrik) und eine adaptive Erosion:
$$\text{Maske} = \text{Erosion}(\text{Otsu}(f, T), R_{\text{erosion}})$$

### 3. Morphologische Top-Hat-Transformation (Feature C)
Isoliert lokale Helligkeitsspitzen (Hitzequellen), indem das morphologische Opening (Erosion gefolgt von Dilation) vom Originalbild subtrahiert wird:
$$T(f) = f - (f \circ B) = f - \delta_B(\epsilon_B(f))$$
wobei $B$ das ungerade strukturierende Element mit Radius $R_{\text{tophat}}$ darstellt.

### 4. Statistisches Outlier-Thresholding (Feature D)
Berechnet Mittelwert $\mu$ und Standardabweichung $\sigma$ der Top-Hat-Intensität exklusiv über alle maskierten Körper-Pixel. Ein Pixel gilt als Entzündungsherd, falls seine Intensität folgendes Kriterium erfüllt:
$$I(x,y) \ge \mu + k \cdot \sigma$$
Standardmäßig gilt $k = 3.0$ ($99.86\%$ Konfidenzintervall). Ein zusätzlicher Absoluthitzefilter stellt sicher, dass Falsch-Positive an ansonsten kalten Körperstellen eliminiert werden.

### 5. Geometrischer Rauschfilter (Feature E)
Führt eine Connected-Component-Analyse (Union-Find) durch. Pixelgruppen (Hotspots) werden verworfen, falls sie nicht eine minimale Pixelanzahl $A_{\text{min}}$ (proportional zur Körperoberfläche) besitzen oder eine unplausible Form aufweisen. Die Kreisförmigkeit (Circularity) $C$ ist definiert als:
$$C = \frac{4\pi \cdot \text{Fläche}}{\text{Umfang}^2} \ge 0.01$$

---

## ⚡ Durchgeführte Performance-Optimierungen

Das Projekt wurde tiefgehend analysiert und in mehreren Kernbereichen massiv optimiert:

*   **O(N) Monotone Deque (Rust)**: Die 1D-Erosion und -Dilation (`dilate_1d`/`erode_1d`) wurde von der naiven $O(N \cdot K)$-Sliding-Window-Suche auf eine echte **Monotone Deque (Lemire 2011)** umgestellt. Bei großen morphologischen Kernel-Radien spart dies bis zu 95 % der Rechenschritte und beschleunigt den Rust-Core bei hochauflösenden Wärmebildern um das **10- bis 50-fache**.
*   **Integer-basierter Distanztransform (Rust)**: In `distance_transform_l2` werden die euklidischen Chamfer-Metriken (Kosten 3 für gerade, 4 für diagonal) nun vollständig mit `u32`-Integer-Arithmetik statt langsamen Float-Operationen (`f64`) berechnet und erst am Ende einmalig skaliert.
*   **Rayon-Parallelisierte Normalisierung (Rust)**: Die lineare Skalierung in `normalize_minmax` verwendet nun eine parallele Schleife via `ndarray::Zip` und Rayon, wodurch die CPU-Auslastung bei Multi-Megapixel-Bildern ideal verteilt wird.
*   **Memory-Leak-Schutz & LRU-Cache (Python)**: Der Bild-Cache in `gui.py` wurde von einem unbegrenzten Standard-Wörterbuch auf ein `collections.OrderedDict` mit einer Obergrenze von 20 Einträgen (LRU-Eviction) umgestellt. Dies verhindert unkontrollierten RAM-Zuwachs bei Stapelverarbeitungen.
*   **Debounced Parameter-Tuning**: Die Slider-Reaktionszeit wurde auf 350 ms debounced. Schnelle Reglerbewegungen in der GUI stauen nun keine unfertigen Hintergrundthreads mehr an.
*   **Zentralisierte Parameter**: Alle wissenschaftlichen und anatomischen Schwellenwerte (wie die Höheneinschränkung für Fußgelenke oder Rand-Mindestabstände) wurden aus dem Code in die zentrale `config.py` überführt.

---

## 🎨 Modernes Design-System (Slate & Indigo)

Die Benutzeroberfläche der Applikation wurde optisch modernisiert und an moderne Entwickler-Tools angepasst:

*   **Edle Farbpalette**: Nutzung eines feinen Slate- und Indigo-Farbschemas (Light: Slate-50 `#F8FAFC`, Dark: Gray-950 `#030712`) mit einer leuchtenden Indigo-Akzentfarbe (`#6366F1`) für fokussierte Benutzerführung.
*   **Moderne Typografie**: Systemweite Verwendung der klaren, modernen Schriftart `Segoe UI` anstelle der generischen Standardschrift Arial.
*   **Voller Farbkontrast**: Alle Akzent-Buttons besitzen nun festen weißen Text (`#FFFFFF`) für optimale Barrierefreiheit (Kontrastverhältnis) im hellen sowie dunklen Modus.
*   **Nahtloses Plot-Design**: Das Histogramm im Tab „Temperatur-Verteilung“ passt sich vollautomatisch dem hellen oder dunklen Theme der Applikation an (keine störenden weißen Ränder mehr im Darkmode).

---

## 📦 Installation & Build-Prozess

### Voraussetzungen
*   **Python 3.10+**
*   **Rust Compiler (cargo)** (zur Kompilierung des optimierten CPU-Moduls)
*   **NVIDIA-Treiber & CUDA Toolkit** (optional, für GPU-Beschleunigung)

### Build und Installation
1.  Klone oder kopiere das Projektverzeichnis.
2.  Öffne eine **PowerShell** im Projektordner.
3.  Führe das Build-Skript aus, welches eine virtuelle Umgebung anlegt, PyTorch verifiziert und das Rust-Backend kompiliert:
    ```powershell
    # Führe das Skript im Release-Modus für maximale CPU-Performance aus
    .\build_setup.ps1 -Release
    ```

---

## 🖥 Bedienung & Ergebnisberichte

### GUI starten
Führe im Hauptverzeichnis Folgendes aus:
```bash
python main.py
```

### Verwendung
1.  **Modus wählen**: Stelle oben links den gewünschten Modus ein (*Allgemeine Analyse* oder *Fuß-Symmetrieanalyse*).
2.  **Bild laden**: Klicke auf **„Wärmebild laden“** (unterstützt PNG, JPG, BMP, TIFF). Das Bild wird sofort verarbeitet.
3.  **Parameter einstellen**: Klappe die Parameterleiste aus, um die Schwellenwerte feinzujustieren (die Filterung reagiert in Echtzeit).
4.  **Bericht exportieren**: Über das Menü `Datei -> HTML-Bericht exportieren` oder den Button in der Seitenleiste wird ein detailliertes Diagnoseprotokoll im modern gestalteten Dark-Zinc-Design ausgegeben.

---

## 🛠 Troubleshooting & Fehlerbehebung

*   **PowerShell-Skript blockiert (`build_setup.ps1`)**:
    Windows verhindert standardmäßig die Ausführung von Skripten. Schalte die Richtlinie für den aktuellen Prozess frei:
    ```powershell
    Set-ExecutionPolicy -Scope Process Bypass
    ```
*   **Rust-Fehler beim Kompilieren (`ignite_core`)**:
    Stelle sicher, dass Rust und Cargo korrekt installiert sind und im Systempfad liegen (`cargo --version`).
*   **CUDA wird nicht erkannt**:
    Prüfe mit `nvidia-smi` im Terminal, ob deine Grafikkarte geladen ist. IGNITE wechselt bei fehlendem CUDA vollautomatisch auf das Rust- oder Python-CPU-Backend, es entsteht kein Laufzeitabbruch.
