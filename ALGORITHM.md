# Funktionsweise des IGNITE-Erkennungsalgorithmus

Der Hotspot-Erkennungsalgorithmus von **IGNITE** dient der präzisen Extraktion pathologischer Entzündungsherde (Hotspots) in thermografischen Aufnahmen. Er ist als eine fünfstufige mathematische Bildverarbeitungs-Pipeline implementiert.

Die vollständige Implementierung der Pipeline findest du im Rust-Core in [lib.rs](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L845-L993) sowie als PyTorch/Python-Wrapper in [image_processing.py](file:///d:/Downloads/JonaNoackIgnite/image_processing.py).

---

## 🧮 Die 5 Bildverarbeitungsstufen

### 1. Dynamische Kernel-Skalierung (Feature A)
Damit der Algorithmus unabhängig von der Auflösung der Wärmebildkamera (z. B. $160 \times 120$ bis $1440 \times 1080$ Pixel) konsistente Ergebnisse liefert, werden die Radien der morphologischen Operatoren proportional zur Bildbreite $W$ skaliert:
* **Berechnung:** `raw = (W * tophat_factor)` (Standardfaktor: `0.05` für 5 % der Bildbreite).
* **Ungerade-Erzwingung:** Um für morphologische Operationen ein eindeutiges Zentrum zu besitzen, wird die Kernelgröße bitweise ungerade gemacht: `odd = (raw | 1)`.
* **Grenzen:** Der Kernel wird auf mindestens $3 \times 3$ Pixel begrenzt.
* *Code-Referenz:* Siehe Funktion `compute_odd_kernel` in [lib.rs:L52-L73](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L52-L73).

---

### 2. Adaptive Körper-Segmentierung / Body-Mask (Feature B)
Bevor Statistiken berechnet werden, muss der Körper (warm) vom Hintergrund (kalt) getrennt werden, um Fehlmessungen zu vermeiden.
1. **Otsu-Binarisierung:** Der Algorithmus berechnet den optimalen globalen Schwellenwert nach Otsu (Minimierung der Intraklassen-Varianz).
2. **Schwellenwert-Begrenzung:** Um extrem kalte oder warme Extremitäten auszugleichen, wird der finale Schwellenwert auf den Bereich zwischen `otsu_min` (35) und `otsu_max` (50) des halben Otsu-Wertes begrenzt: 
   $$\text{Threshold} = \max(\text{otsu\_min}, \min(\text{otsu\_max}, \text{Otsu-Wert} / 2))$$
3. **Distanztransformation (Chamfer-L2-Metrik):** Jeder Vordergrundpixel erhält seine euklidische Distanz zum nächsten Hintergrundpixel. Dies wird über einen schnellen Zwei-Pass-Algorithmus mit Chamfer-3-4-Gewichtung angenähert.
4. **Adaptive Erosion:** Es werden nur Pixel behalten, deren Abstand zum Rand $\ge \text{dist\_erosion\_factor} \times \text{max\_dist}$ ist (Standard: 5 %). Dies eliminiert feine Ränder und Artefakte an anatomischen Übergängen (z. B. Zehenzwischenräume oder Sensorrauschen am Rand).
* *Code-Referenz:* Siehe Funktion `extract_body_mask` in [lib.rs:L438-L481](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L438-L481).

---

### 3. Morphologische Top-Hat-Transformation (Feature C)
Diese Stufe isoliert lokale Hitzeinseln (lokale Maxima) und gleicht globale Temperaturgradienten (z. B. durch ungleichmäßige Durchblutung oder Kalibrierungsfehler der Kamera) aus:
1. **Morphologisches Opening:** Das Bild wird zuerst erodiert (lokales Minimum) und anschließend dilatiert (lokales Maximum). Dadurch werden alle Strukturen, die kleiner als die Kernelgröße (aus Schritt 1) sind, herausgefiltert.
2. **Subtraktion (Top-Hat):** Das geöffnete Bild (Hintergrund-Temperaturprofil) wird vom Originalbild subtrahiert:
   $$\text{TopHat}(I) = I - \text{Opening}(I)$$
3. **Optimierung (Separierbarkeit):** Da 2D-Kernel auf großen Bildern extrem langsam sind ($O(K^2)$ Operationen pro Pixel), ist die Erosion und Dilation im Rust-Core in zwei sequentielle 1-dimensionale Pässe (horizontal und vertikal) aufgeteilt ($O(K)$). Mittels `rayon` wird dies parallel über alle CPU-Kerne berechnet.
4. **Maskierung:** Das Differenzbild wird mittels bitweisem UND mit der Body-Mask maskiert, sodass nur Differenzen auf dem Körper übrig bleiben.
* *Code-Referenz:* Siehe Funktion `morph_tophat` in [lib.rs:L259-L268](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L259-L268).

---

### 4. Statistisches Outlier-Thresholding (Feature D)
Hier wird bestimmt, ab wann eine lokale Erwärmung statistisch signifikant (also ein Entzündungsherd) ist:
1. **Statistik über Körper-Pixel:** Mittelwert $\mu_{\text{diff}}$ und Standardabweichung $\sigma_{\text{diff}}$ der Intensität des Top-Hat-Differenzbildes werden **ausschließlich** für Pixel berechnet, die innerhalb der Body-Mask liegen.
2. **Adaptiver Schwellenwert:** Ein Pixel wird vorläufig als Hotspot eingestuft, wenn seine lokale Temperaturdifferenz deutlich über dem Rauschen liegt:
   $$\text{TopHat-Wert}(x, y) > \mu_{\text{diff}} + k \cdot \sigma_{\text{diff}}$$
   (Standardmäßig ist $k = 3.0$, was bei einer Normalverteilung einem Konfidenzintervall von $99.86\%$ entspricht).
3. **Absoluthitzefilter:** Zusätzlich muss die Originaltemperatur des Pixels über der durchschnittlichen Körpertemperatur liegen ($\text{Original-Wert}(x,y) > \mu_{\text{orig}}$). Dies verhindert, dass statistische Ausreißer in ansonsten sehr kalten Bereichen (z. B. kalte Zehen) fälschlicherweise als Hotspots detektiert werden.
* *Code-Referenz:* Siehe Funktion `threshold_statistical` in [lib.rs:L536-L592](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L536-L592).

---

### 5. Geometrischer Rauschfilter (Feature E)
Zusammenhängende Hotspot-Pixel werden als isolierte Objekte geometrisch analysiert, um biologisch unplausible Formen (z. B. Sensorrauschen oder Temperaturfalten der Haut) zu filtern:
1. **Connected-Component-Analyse:** Mittels eines Two-Pass-Union-Find-Algorithmus werden benachbarte Pixel zu Clustern zusammengefasst.
2. **Relative Mindestfläche:** Pixelgruppen werden gelöscht, wenn sie kleiner als ein prozentualer Anteil der Körperoberfläche sind:
   $$\text{Fläche} < \text{min\_area\_factor} \cdot \text{Körperfläche}$$
   (Zusätzlich gilt ein absolutes Minimum von 10 Pixeln).
3. **Kreisförmigkeit (Circularity):** Zur Beurteilung der Form wird die Circularität $C$ berechnet:
   $$C = \frac{4\pi \cdot \text{Fläche}}{\text{Umfang}^2}$$
   Ein perfekter Kreis hat $C = 1.0$, dünne Linien oder Rauschen haben $C \to 0.0$. Objekte mit $C < \text{min\_circularity}$ (Standard: 0.01) werden gelöscht. Echte Entzündungen breiten sich biologisch meist kreisförmig oder oval aus, während Hautfalten oder Bildrauschen linienförmig sind.
* *Code-Referenz:* Siehe Funktion `filter_geometric` in [lib.rs:L751-L812](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L751-L812).

---

## 🚀 Hybrid-Backend-Architektur

IGNITE wählt zur Laufzeit automatisch das performanteste verfügbare System aus:

1. **GPU-Pfad (PyTorch CUDA, < 10 ms):** Verarbeitet die Daten direkt im VRAM. Ideal für Stapelverarbeitung.
2. **Rust-CPU-Pfad (`ignite_core`, ~30 ms):** Parallelisiert über Rayon. Führt die oben genannte Pipeline hocheffizient auf allen CPU-Kernen aus.
3. **Python-Fallback (OpenCV CPU, ~80 ms):** Sichert die Kompatibilität auf Systemen ohne CUDA/Rust-Compiler.
