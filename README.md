# Ignite – Entzündungsdetektion via Thermografie

Dieses Projekt ist eine hochoptimierte, hardwarebeschleunigte Softwarelösung zur automatisierten **Entzündungsdetektion (Hotspot-Erkennung)** in thermografischen Fußaufnahmen, entwickelt im Rahmen von **Jugend forscht**.

Die Software kombiniert ein benutzerfreundliches Python-Frontend mit einer extrem schnellen, hybriden Bildverarbeitungs-Pipeline auf Basis von **GPU (CUDA / PyTorch)** und **CPU (Rust-native Multithreading)**.

---

## 🚀 Systemarchitektur & Hybrid-Backend

Die Pipeline wählt beim Start vollautomatisch den schnellsten verfügbaren Hardware-Pfad:

1. **GPU-Pfad (Standard bei NVIDIA-GPUs, < 10 ms)**
   - Nutzt **PyTorch CUDA** auf der Grafikkarte für massiv parallele mathematische Operationen.
   - Berechnet die morphologische Top-Hat-Transformation und die statistische Schwellenwert-Filterung direkt im VRAM.
2. **CPU-Pfad (Rust-Core, ~50 ms)**
   - Nutzt ein natives, selbstgeschriebenes Rust-Erweiterungsmodul (`ignite_core`) via **PyO3**.
   - Parallelisiert alle Rechenoperationen mittels **Rayon** über alle verfügbaren CPU-Kerne.
   - Komplett frei von externen C++-Abhängigkeiten wie OpenCV.
3. **CPU-Fallback (Python)**
   - Rein in Python geschriebener Fallback-Pfad für maximale Kompatibilität auf fremden Endgeräten.

---

## 🛠 Die 5 Pipeline-Stufen (Features A–E)

Die mathematische Erkennung basiert auf fünf aufeinander abgestimmten Stufen:

- **Feature A – Dynamische Kernel**: Berechnet ungerade Strukturierungselemente basierend auf der Bildbreite (Standard: 5 % für Top-Hat, 2 % für Geometriefilter).
- **Feature B – Adaptive Body-Mask**: 
  - Otsu-Binarisierung mit Sicherheits-Schwellenwert-Eingrenzung auf den Bereich `[35, 50]`, um auch kältere Extremitäten (Zehen) zuverlässig zu erfassen.
  - Euklidische Distanztransformation (Chamfer-3-4-Metrik).
  - 5% adaptive Erosion zur Eliminierung von Randrauschen und Text-Logos der Kamera.
- **Feature C – Top-Hat-Transformation**: Führt ein morphologisches Opening durch und subtrahiert dieses vom Originalbild, um lokale Helligkeitsspitzen präzise zu isolieren.
- **Feature D – Statistischer Schwellenwert (µ + 3σ + Absoluthitze-Filter)**:
  - Berechnet Mittelwert $\mu$ and Standardabweichung $\sigma$ der Top-Hat-Differenz exklusiv über Körper-Pixel.
  - Filtert mit einem strengen Ausreißer-Schwellenwert von $\mu + 3.0\sigma$ (99.86% Konfidenz).
  - Verlangt zusätzlich, dass die absolute Helligkeit über der durchschnittlichen Fußtemperatur liegt. Dies **eliminiert Falsch-Positive an gesunden (kalten) Zehen vollständig**.
- **Feature E – Geometrischer Rauschfilter**: Führt eine Connected-Component-Analyse (Union-Find) durch. Filtert Komponenten nach Mindestfläche ($0.05\ \%$ der Körperoberfläche) und Circularity ($C = 4\pi A / P^2 \ge 0.01$) zur Entfernung von Rauschen und Linienartefakten.

---

## 📦 Voraussetzungen & Installation

### Voraussetzungen
- **Python 3.10+**
- **NVIDIA GPU** mit installiertem CUDA-Treiber (optional, für GPU-Beschleunigung)
- **Rust-Toolchain** (optional, falls das CPU-Backend neu kompiliert werden soll)

### Installation
1. Öffne ein PowerShell-Terminal im Projektordner.
2. Führe das Setup-Skript aus, um das Rust-Backend zu bauen, Abhängigkeiten (wie PyTorch) zu verifizieren und das Modul zu installieren:
   ```powershell
   # Release-Build (empfohlen für maximale CPU-Performance)
   .\build_setup.ps1 -Release
   ```
   *(Falls PowerShell-Skripte durch Ausführungsrichtlinien blockiert sind, führe vorher `Set-ExecutionPolicy -Scope Process Bypass` aus.)*

---

## 🖥 Bedienung & Verwendung

Starte die grafische Benutzeroberfläche (GUI) mit:
```bash
python main.py
```

1. Klicke auf **„Wärmebild laden“** und wähle eine thermografische Aufnahme aus (unterstützt PNG, JPEG, BMP, TIFF).
2. Die Software verarbeitet das Bild in Echtzeit und zeigt die vier Zwischenschritte in den Panels an.
3. Die erkannten Entzündungsherde (Hotspots) werden in Panel 4 **leuchtend rot markiert**.
4. Alle Zwischenschritte werden automatisch für die Jury-Dokumentation im Ordner `ignite_steps_output` als Bild und NumPy-Array gesichert.
