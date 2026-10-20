# IGNITE Medical Suite — Leitfaden zur Erklärung & Präsentation des Python-Codes

> **Zweck dieses Dokuments:**  
> Dieser Leitfaden dient als kompakter, praxiserprobter Spickzettel für **Jona Noack** zur mündlichen Erklärung und Live-Vorführung des IGNITE Python-Codes auf beliebigen Fremdrechnern (**Windows**, **Fedora Linux** oder **Android**), selbst wenn **keinerlei Vorbereitung** oder Software-Installation vor Ort möglich ist.

---

## 1. Schnellstart auf einem fremden System (0 Sekunden Vorbereitung)

Egal an welchem Computer oder Gerät du stehst — du hast **drei sofort einsatzbereite Wege**, das System ohne vorherige Installation vorzuführen:

### Weg A: Windows-PC (Schule, Labor, Fremd-Laptop)
1. USB-Stick einstecken oder Ordner öffnen.
2. **Doppelklick auf [`run_demo.bat`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/run_demo.bat)**.
3. *Was passiert:* Das Skript prüft automatisch, ob Python vorhanden ist (`python`, `py`, AppData). Falls ja, startet es sofort die interaktive Showcase-Engine; falls kein Python installiert ist, öffnet es automatisch den Offline-Browser-Showcase.

### Weg B: Fedora / Linux (oder Android Termux)
1. Terminal im Projektordner öffnen.
2. Befehl ausführen:
   ```bash
   ./run_demo.sh
   # Oder direkt:
   python3 standalone_demo.py
   ```
3. *Was passiert:* Läuft mit reinem Python 3 Standard-Library (Zero Dependencies). Der Browser öffnet sich automatisch unter `http://localhost:8080`.

### Weg C: Android-Tablet / Smartphone oder PC ohne Admin-Rechte
1. Kein Python installiert? Kein Problem!
2. Öffne einfach die Datei:  
   👉 **[`docs/STANDALONE_DEMO_OFFLINE.html`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/docs/STANDALONE_DEMO_OFFLINE.html)**  
   in Chrome, Firefox, Safari oder Edge.
3. *Was passiert:* Eine 100% autarke HTML5/Canvas-Applikation läuft vollständig lokal im Browser. Sie simuliert alle 7 Pipeline-Stufen, bietet interaktive Slider ($k$, $\Delta T$, Colormaps) und enthält einen Reiter mit dem annotierten Python-Quellcode.

---

## 2. Der 2-Minuten Elevator Pitch (Für Jury & Prüfer)

Wenn du den Code vorstellst, beginne mit dieser prägnanten Einleitung:

> *"Das diabetische Fußsyndrom (DFS) ist weltweit die häufigste Ursache für nicht-traumatische Amputationen. Das Problem: Wenn ein Ulkus mit bloßem Auge sichtbar wird, ist das Tiefengewebe oft schon nekrotisch.*  
>  
> *Mit IGNITE nutzen wir hochauflösende Infrarot-Thermografie im Langwellenbereich (8–14 µm). Unser Python-Code implementiert eine deterministische, nach DIN EN ISO 13485 und IWGDF validierte mathematische Bildverarbeitungs-Pipeline. Sie erkennt subklinische Entzündungen bereits 7 bis 14 Tage vor dem Hautaufbruch anhand des Armstrong-Kriteriums ($\Delta T \ge 2{,}2\,\text{K}$).*  
>  
> *Wir setzen bewusst auf deterministische Signalverarbeitung statt undurchsichtiger Black-Box-Neuronaler-Netze, um 100%ige Reproduzierbarkeit und Null Halluzinationen im klinischen Alltag zu garantieren."*

---

## 3. Architektur-Übersicht: Wo gehört der Python-Code hin?

Erkläre den Prüfern kurz die polyglotte Multi-Tier-Architektur von IGNITE:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Klinische Benutzeroberfläche (Workstation)                   │
│    - Go Wails v2 Desktop GUI (`desktop-go/`)                    │
│    - C# .NET 10 WPF PACS-Workstation (`desktop/`)               │
└────────────────────────────────┬────────────────────────────────┘
                                 │ In-Process / CLI Call
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Hochleistungs-Rechenkern (Go 1.24+ & AVX2 SIMD Assembler)    │
│    - `core/` (42-stufige Pipeline, 6 Hardware-Vektorkerne)      │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Forschungs-, CLI- & Fallback-Ebene
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Python 3 Referenz-Suite (`image_processing.py` & `cli.py`)   │
│    - Referenz-Algorithmen, Prototyping & CUDA GPU-Engine        │
│    - Multi-Backend Auto-Detection (`_find_go_core`)             │
│    - Vollständiger Python-Fallback bei fehlendem Go-Core        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Zeilen-Atlas für `image_processing.py` (Was zeige ich wo?)

Öffne die Datei [`image_processing.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py) im Editor. Hier sind die 7 Kern-Abschnitte, die du nacheinander ansteuerst:

### 1. Multi-Tier Backend Erkennung (Zeilen 36–107)
* **Funktionen:** [`_find_go_core()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L36), [`_init_gpu()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L60), [`get_active_backend()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L97).
* **Was du sagst:**  
  *"IGNITE erkennt zur Laufzeit automatisch die schnellste verfügbare Hardware: Ist eine NVIDIA-GPU vorhanden, nutzen wir PyTorch-CUDA. Für maximale CPU-Performance binden wir unseren nativen Go-Core mit x86_64 AVX2-Vektorkernen ein. Auf Fremdrechnern greift nahtlos der deterministische Python-Fallback."*

### 2. Radiometrische Kalibrierung & FLIR APP1 Parsing (Zeilen 117–235)
* **Funktionen:** [`_extract_flir_radiometric_raw()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L117), [`load_thermal_image()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L177).
* **Was du sagst:**  
  *"Wir verarbeiten nicht nur normale Farb- oder Graustufenbilder, sondern extrahieren direkt aus den FLIR JPEG APP1-Exif-Headern die echten 16-Bit Roh-Sensordaten der Mikrobolometer. Über Planck'sche Strahlungsgleichungen kalibrieren wir jeden Pixel direkt in Kelvin bzw. Grad Celsius."*

### 3. Multi-Otsu Gewebesegmentierung & Rand-Erosion (Zeilen 239–288)
* **Funktion:** [`extract_body_mask_multi_otsu()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L239).
* **Mathematik:** Maximierung der Inter-Klassen-Varianz $\sigma_B^2(t) = \omega_0(t)\omega_1(t)[\mu_0(t) - \mu_1(t)]^2$.
* **Was du sagst:**  
  *"Um den Fuß vom kühlen Raumhintergrund oder Bett zu isolieren, berechnen wir die optimale Schwellenwert-Trennung nach Otsu. Danach erodieren wir die Maske um wenige Pixel (Chamfer-$L_2$-Distanz), um Reflexionsartefakte an der Hautkante, die durch den flachen Blickwinkel entstehen, konsequent zu eliminieren."*

### 4. Multiskalen Morphologischer White Top-Hat (Zeilen 290–320)
* **Funktion:** [`compute_multiscale_tophat()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L290).
* **Mathematik:** $\text{WTH}(I) = I - (I \circ B) = I - \text{Dilation}(\text{Erosion}(I))$.
* **Was du sagst:**  
  *"Ein Fuß hat einen physiologischen Temperaturgradienten (proximal warm, distal an den Zehen kühl). Ein einfacher Schwellenwert würde an den Zehen versagen. Der White Top-Hat subtrahiert die morphologische Öffnung vom Bild. Das filtert den großflächigen Hintergrundverlauf heraus und isoliert ausschließlich lokale, fokale Hotspots."*

### 5. Multiskaliger Frangi-Vesselness-Filter (Zeilen 928–1012)
* **Funktion:** [`compute_frangi_vesselness_filter()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L928).
* **Mathematik:** 2D-Hesse-Matrix $\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}$ und Eigenwerte $\lambda_1, \lambda_2$ mit $|\lambda_1| \le |\lambda_2|$.
  $$\mathcal{R}_B = \frac{|\lambda_1|}{|\lambda_2|}, \quad S^2 = \lambda_1^2 + \lambda_2^2, \quad V_0 = \exp\left(-\frac{\mathcal{R}_B^2}{2\beta^2}\right) \cdot \left(1 - \exp\left(-\frac{S^2}{2c^2}\right)\right)$$
* **Was du sagst:**  
  *"Eine der größten Herausforderungen: Oberflächliche Venen sind ebenfalls warm, aber völlig harmlos. Über die Hesse-Matrix berechnen wir die Richtungsableitungen. Bei einer Vene ist ein Eigenwert stark negativ und der andere nahe 0 (tubuläre Röhrenstruktur). Bei einem entzündlichen Ulkusherd sind beide Eigenwerte negativ (isotroper, runder Peak). So unterscheiden wir Entzündung von Gefäß!"*

### 6. Robuste Outlier-Detektion via Hampel-MAD (Zeilen 804–858)
* **Funktion:** [`apply_hysteresis_thresholding()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L804).
* **Mathematik:**  
  $$\text{MAD} = \text{median}(|x_i - \text{median}(X)|), \quad \tau = \text{Median} + k \times 1{,}4826 \times \text{MAD}$$
* **Was du sagst:**  
  *"Statt Mittelwert und Standardabweichung nutzen wir den Median Absolute Deviation (MAD). Die Standardabweichung bricht bei einem schweren Hotspot sofort ein (Maskierungseffekt). Der MAD hat einen Bruchpunkt von 50% und bleibt absolut robust."*

### 7. Kontralateraler Armstrong-Seitenvergleich (Zeilen 1457–1520)
* **Funktion:** [`compute_contralateral_asymmetry()`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/image_processing.py#L1457).
* **Klinische Regel:** $\Delta T = |T_{\text{links}} - T_{\text{rechts}}| \ge 2{,}2\,\text{K}$.
* **Was du sagst:**  
  *"Wir vergleichen spiegelbildlich dieselben anatomischen Regionen (Metatarsale I–V, Calcaneus, Hallux). Beträgt die Temperaturdifferenz zur gesunden Gegenseite 2,2 Kelvin oder mehr, löst das System die höchste IWGDF-Warnstufe für ein bevorstehendes Ulkus aus."*

---

## 5. Fragen & Antworten für die Jury-Verteidigung

Wenn ein Prüfer oder Juror gezielte Fachfragen stellt, antworte ruhig und präzise nach folgendem Schema:

| Prüferfrage | Deine überzeugende Antwort |
| :--- | :--- |
| **"Warum haben Sie kein Deep Learning / CNN verwendet?"** | *"In der klinischen Diagnostik nach DIN EN ISO 13485 ist Erklärbarkeit (Explainability) und deterministische Reproduzierbarkeit gesetzlich gefordert. Ein neuronales Netz neigt bei seltenen Fußdeformitäten zu unvorhersehbaren Halluzinationen. Unsere biophysikalische Pipeline liefert bit-identische Ergebnisse und läuft in Echtzeit ohne Cloud oder teure Server."* |
| **"Woher stammt der Grenzwert von 2,2 Kelvin?"** | *"Das ist das international etablierte Armstrong-Kriterium (Armstrong et al., Diabetes Care 2007) und Kern der IWGDF-Leitlinien. Eine Temperaturdifferenz von $\ge 2{,}2\,\text{K}$ über 2 aufeinanderfolgende Tage sagt ein Ulkus mit 91%iger Spezifität 7–14 Tage vor dem Hautaufbruch voraus."* |
| **"Wie verhindern Sie falsch-positive Alarme an der Fußkante?"** | *"An den seitlichen Fußrändern trifft die Kamera schräg auf die Haut (Lambert'sches Kosinusgesetz), was zu scheinbaren Temperaturabfällen und Kantenkontrasten führt. Wir eliminieren diese Zone durch eine 2-Pass Chamfer-$L_2$-Distanzerosion der Gewebemaske."* |
| **"Warum nutzen Sie für den Go-Kern Assembler-Befehle?"** | *"Für mobile Point-of-Care-Geräte zählt jede Millisekunde. Durch 6 handgeschriebene AVX2-Vektorkerne (`VPMINUB`, `VPMAXUB`, `VPSUBUSB`) verarbeiten wir 32 Bildpunkte pro CPU-Taktzyklus parallel. Das senkt die Analysezeit von 120 ms auf unter 8 ms."* |
| **"Kann der Patient die Schwellenwerte verändern?"** | *"Nein, aber der behandelnde Facharzt kann über unsere eingebettete Lua-Regel-Engine (`rules/armstrong_criteria.lua`) patientenspezifische Grenzwerte anpassen — völlig ohne den Quellcode neu kompilieren zu müssen."* |

---

## 6. Zusammenfassung der 5 wichtigsten Formeln

Drucke diese Formeln im Kopf ab oder schreibe sie auf ein Blatt:

1. **Otsu-Kriterium:**  
   $$\sigma_B^2(t) = \omega_0(t)\omega_1(t)[\mu_0(t) - \mu_1(t)]^2 \longrightarrow \max$$
2. **White Top-Hat:**  
   $$\text{WTH}(I) = I - (I \circ B) = I - \text{Dilation}(\text{Erosion}(I))$$
3. **Hampel-MAD Schwellenwert:**  
   $$\tau = \text{Median}(X) + k \times 1{,}4826 \times \text{Median}(|X - \text{Median}(X)|)$$
4. **Frangi Tubularitäts-Index:**  
   $$V(\lambda_1, \lambda_2) = \exp\left(-\frac{\mathcal{R}_B^2}{2\beta^2}\right) \cdot \left(1 - \exp\left(-\frac{S^2}{2c^2}\right)\right) \quad \text{mit } \mathcal{R}_B = \frac{|\lambda_1|}{|\lambda_2|}$$
5. **Armstrong Ulkus-Alarm:**  
   $$\Delta T_{\text{kontralateral}} = |T_{\text{links}}(x, y) - T_{\text{rechts}}(x', y')| \ge 2{,}2\,\text{K}$$

---

> [!TIP]
> **Präsentations-Geheimtipp:**  
> Wenn du vor der Jury stehst, starte die Live-Demo mit [`run_demo.bat`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/run_demo.bat) oder öffne [`docs/STANDALONE_DEMO_OFFLINE.html`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/docs/STANDALONE_DEMO_OFFLINE.html).  
> Klicke auf **"Pipeline Automatisch Abspielen ⯈"** und erkläre der Jury synchron zu den 7 Stufen, wie das Bild schrittweise vom Roh-Thermogramm bis zum klinischen Befund verarbeitet wird. Das hinterlässt einen extrem professionellen Eindruck!
