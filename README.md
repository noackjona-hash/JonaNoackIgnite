# IGNITE // Thermografische Entzündungsdetektion

> **Wettbewerbsprojekt Jugend forscht 2026**  
> Eine hochoptimierte Hybridlösung zur automatisierten Erkennung lokaler Entzündungsherde (Hotspots) in thermografischen Aufnahmen unter Verwendung von PyTorch-GPU, Rust-nativem Multithreading und Python.

---

## 🔍 Inhaltsverzeichnis
1. [Projektbeschreibung & Analysemodi](#-projektbeschreibung--analysemodi)
2. [Systemarchitektur & Hybrid-Backend](#-systemarchitektur--hybrid-backend)
3. [Die 5 Bildverarbeitungsstufen (Mathematische Pipeline)](#-die-5-bildverarbeitungsstufen-mathematische-pipeline)
4. [Installation & Build-Prozess](#-installation--build-prozess)
5. [Bedienung & Ergebnisberichte](#-bedienung--ergebnisberichte)
6. [Troubleshooting & Fehlerbehebung](#-troubleshooting--fehlerbehebung)

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
$$R_{\text{tophat}} = \text{tophat\_factor} \cdot W$$

### 2. Adaptive Körper-Segmentierung / Body-Mask (Feature B)
Das Objekt wird mittels Otsu-Binarisierung vom Hintergrund getrennt. Der Schwellenwert $T$ wird künstlich auf das Temperaturintervall $[\text{otsu\_min}, \text{otsu\_max}]$ beschränkt, um kältere Gliedmaßen zuverlässig zu maskieren. Es folgt eine euklidische Distanztransformation (Chamfer-3-4-Metrik) und eine adaptive Erosion:
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

## 📦 Installation & Build-Prozess

### Voraussetzungen
*   **Python 3.10+**
*   **Rust Compiler (cargo)** (zur Kompilierung des optimierten CPU-Moduls)
*   **NVIDIA-Treiber & CUDA Toolkit** (optional, für GPU-Beschelung)

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
