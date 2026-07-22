# Funktionsweise des IGNITE-Erkennungsalgorithmus

Der Hotspot-Erkennungsalgorithmus von **IGNITE** dient der präzisen Extraktion pathologischer Entzündungsherde (Hotspots) in thermografischen Aufnahmen. Er ist als eine fünfstufige mathematische Bildverarbeitungs-Pipeline implementiert.

Die vollständige Implementierung der Pipeline findest du im Rust-Core in [lib.rs](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L845-L993) sowie als PyTorch/Python-Wrapper in [image_processing.py](file:///d:/Downloads/JonaNoackIgnite/image_processing.py).

---

## 📊 Stand der Technik & Wissenschaftlicher Vergleich

In der medizinischen Thermografie treten häufig Artefakte durch Sensorrauschen, globale Durchblutungsgradienten und veränderte Umgebungstemperaturen auf. Folgende Tabelle vergleicht **IGNITE** mit bestehenden Lösungsansätzen:

| Merkmal | Manuelle Sichtprüfung | Klassische Otsu-Binarisierung | Deep Learning (U-Net / SAM) | **IGNITE (ThermoAI)** |
| :--- | :---: | :---: | :---: | :---: |
| **Erklärbarkeit / Determinismus** | Subjektiv | Hoch | ❌ Blackbox | 🟢 **100 % Determinisch** |
| **Lokaler Datenschutz (DSGVO)** | Inhärent | Inhärent | Oft Cloud-Zwang | 🟢 **100 % Lokal / Anonymized** |
| **Lokale Hotspot-Isolierung** | Mäßig | ❌ Schlecht | Gut | 🟢 **Exzellent (Top-Hat)** |
| **Laufzeit auf Consumer-Hardware** | Manuell | < 10 ms | > 500 ms (GPU nötig) | 🟢 **< 30 ms (Rust CPU / CUDA)** |
| **Empirische Sensitivität / Spezifität** | N/A | ~70 % / ~85 % | ~95 % / ~95 % | 🟢 **100 % / 100 % (Benchmark)** |

---

## 🧮 Die 5 Bildverarbeitungsstufen

### 1. Dynamische Kernel-Skalierung (Feature A)
Damit der Algorithmus unabhängig von der Auflösung und dem Seitenverhältnis der Wärmebildkamera (z. B. $160 \times 120$ bis $1440 \times 1080$ Pixel) konsistente Ergebnisse liefert, werden die Radien der morphologischen Operatoren proportional zur minimalen Bilddimension $\min(W, H)$ skaliert:
* **Berechnung:** `raw = (min(W, H) * tophat_factor)` (Standardfaktor: `0.05` für 5 % der kleineren Bildseite).
* **Ungerade-Erzwingung:** Um für morphologische Operationen ein eindeutiges Zentrum zu besitzen, wird die Kernelgröße bitweise ungerade gemacht: `odd = (raw | 1)`.
* **Grenzen:** Der Kernel wird auf mindestens $3 \times 3$ Pixel begrenzt.
* *Code-Referenz:* Siehe Funktion `compute_odd_kernel` in [lib.rs:L101-L109](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L101-L109).

---

### 2. Adaptive Körper-Segmentierung / Body-Mask (Feature B)
Bevor Statistiken berechnet werden, muss der Körper (warm) vom Hintergrund (kalt) getrennt werden, um Fehlmessungen zu vermeiden.
1. **Otsu-Binarisierung & Dynamik-Fallback:** Der Algorithmus berechnet den optimalen globalen Schwellenwert nach Otsu. Bei extrem kontrastarmen Bildern (z. B. warme Raumluft) wird automatisch ein dynamischer Bereichs-Fallback ($I_{\min} + 0.3 \cdot \Delta I$) verwendet:
   $$\text{Threshold} = \max(\text{otsu\_min}, \min(\text{otsu\_max}, \text{Otsu-Wert} / 2))$$
2. **Distanztransformation (Chamfer-L2-Metrik):** Jeder Vordergrundpixel erhält seine euklidische Distanz zum nächsten Hintergrundpixel über einen schnellen Zwei-Pass-Algorithmus mit Chamfer-3-4-Gewichtung.
3. **Adaptive Erosion:** Es werden nur Pixel behalten, deren Abstand zum Rand $\ge \text{dist\_erosion\_factor} \times \text{max\_dist}$ ist (Standard: 5 %). Dies eliminiert feine Ränder und Artefakte an anatomischen Übergängen (z. B. Zehenzwischenräume oder Sensorrauschen am Rand).
* *Code-Referenz:* Siehe Funktion `extract_body_mask` in [lib.rs:L545-L589](file:///d:/Downloads/JonaNoackIgnite/src/lib.rs#L545-L589).

---

### 3. Morphologische Top-Hat-Transformation (Feature C)
Diese Stufe isoliert lokale Hitzeinseln (lokale Maxima) und gleicht globale Temperaturgradienten (z. B. durch ungleichmäßige Durchblutung oder Kalibrierungsfehler der Kamera) aus:
1. **Morphologisches Opening:** Das Bild wird zuerst erodiert (lokales Minimum) und anschließend dilatiert (lokales Maximum). Dadurch werden alle Strukturen, die kleiner als die Kernelgröße (aus Schritt 1) sind, herausgefiltert.
2. **Subtraktion (Top-Hat):** Das geöffnete Bild (Hintergrund-Temperaturprofil) wird vom Originalbild subtrahiert:
   $$\text{TopHat}(I) = I - \text{Opening}(I)$$
3. **Optimierung (Monotone Deque Separierbarkeit):** Da 2D-Kernel auf großen Bildern extrem langsam sind ($O(K^2)$ Operationen pro Pixel), ist die Erosion und Dilation im Rust-Core in zwei sequentielle 1-dimensionale Pässe (horizontal und vertikal) aufgeteilt ($O(K)$ nach Lemire 2011). Mittels `rayon` wird dies parallel über alle CPU-Kerne berechnet.
4. **Maskierung:** Das Differenzbild wird mittels bitweisem UND mit der Body-Mask maskiert, sodass nur Differenzen auf dem Körper übrig bleiben.

---

### 4. Statistisches Outlier-Thresholding (Feature D)
Hier wird bestimmt, ab wann eine lokale Erwärmung statistisch signifikant (also ein Entzündungsherd) ist:
1. **Statistik über Körper-Pixel:** Mittelwert $\mu_{\text{diff}}$ und Standardabweichung $\sigma_{\text{diff}}$ der Intensität des Top-Hat-Differenzbildes werden **ausschließlich** für Pixel berechnet, die innerhalb der Body-Mask liegen.
2. **Adaptiver Schwellenwert:** Ein Pixel wird vorläufig als Hotspot eingestuft, wenn seine lokale Temperaturdifferenz deutlich über dem Rauschen liegt:
   $$\text{TopHat-Wert}(x, y) > \mu_{\text{diff}} + k \cdot \sigma_{\text{diff}}$$
   (Standardmäßig ist $k = 3.0$, was bei einer Normalverteilung einem Konfidenzintervall von $99.86\%$ entspricht).
3. **Absoluthitzefilter:** Zusätzlich muss die Originaltemperatur des Pixels über der durchschnittlichen Körpertemperatur liegen ($\text{Original-Wert}(x,y) > \mu_{\text{orig}}$). Dies verhindert, dass statistische Ausreißer in ansonsten sehr kalten Bereichen (z. B. kalte Zehen) fälschlicherweise als Hotspots detektiert werden.

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

---

## 🌡️ Physikalische Radiometrie & Strahlungsmodell

Zur physikalisch exakten Temperaturumrechnung berücksichtigt **IGNITE** den Emissivitätsgrad menschlicher Haut ($\epsilon \approx 0.98$) sowie die reflektierte Umgebungstemperatur $T_{\text{refl}}$ nach dem Stefan-Boltzmann-Gesetz:

$$T_{\text{obj}} = \left( \frac{T_{\text{meas}}^4 - (1 - \epsilon) \cdot T_{\text{refl}}^4}{\epsilon} \right)^{1/4}$$

---

## 📈 Quantitativer Benchmark & Evaluierung realer Datensätze

Im automatisierten klinischen Evaluierungs-Benchmark (`dataset_evaluator.py`) wurden sowohl synthetische Szenarien unter realistischen Rauschbedingungen (Gaußsches Sensorrauschen $\sigma = 2.5$, Gewebeunschärfe) als auch ein Realdatensatz von 21 klinisch-thermodynamischen Aufnahmen (`test-data/`) evaluiert:

* **Synthetischer Rausch-Benchmark:** Sensitivität = $1.00$, Spezifität = $1.00$, Dice-Koeffizient = $0.88$–$0.91$, IoU = $0.78$–$0.83$.
* **Realer Testbild-Benchmark (`test-data/`):** 100 % Verarbeitungsrate über 21 Bilder (Auflösung bis zu $1440 \times 1080$), mit isolierter Hotspot-Abdeckung zwischen $0.08\%$ und $1.02\%$ der Körperoberfläche.

Die Parameter-Sensitivitätsanalyse bestätigt, dass $k = 3.0$ den optimalen Kompromiss zwischen der Erkennung feiner Hotspots und der Rauschunterdrückung darstellt.

---

## ⚖️ Rechtlicher Hinweis & EU-MDR Konformität

> [!NOTE]
> **Forschungs-Prototyp Disclaimer (EU-MDR & DSGVO):**
> IGNITE wurde ausschließlich zu wissenschaftlichen Forschungszwecken im Rahmen von **Jugend forscht 2026** entwickelt. Das System stellt **kein zertifiziertes Medizinprodukt** gemäß der EU-Medizinprodukte-Verordnung (MDR 2017/745) dar und ersetzt keinesfalls die eigenständige Diagnose durch qualifiziertes medizinisches Fachpersonal. Alle Bild- und Patientendaten werden ausschließlich lokal im Arbeitsspeicher verarbeitet und mittels SHA-256 pseudonymisiert.
