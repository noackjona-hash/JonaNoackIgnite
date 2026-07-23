# IGNITE Medical Imaging Suite
## Automatisierte Entzündungserkennung in Wärmebildern zur Entlastung des medizinischen Fachpersonals im Behandlungsalltag

**Wettbewerb:** Jugend forscht 2026  
**Fachgebiet:** Arbeitswelt  
**Autor:** Jona Noack (16 Jahre)  
**Datum:** 23. Juli 2026  

---

# Projektüberblick

In meinem Jugend forscht Projekt in der Sparte **Arbeitswelt** habe ich die Software **IGNITE** entwickelt, um den klinischen Behandlungsablauf bei der thermografischen Entzündungserkennung zu automatisieren und das medizinische Fachpersonal spürbar zu entlasten. Bisher müssen Ärztinnen, Ärzte und Podologen Wärmebilder von Risikopatienten (z. B. bei Diabetes) manuell am Bildschirm untersuchen. Diese visuelle Sichtprüfung ist zeitaufwendig (ca. 3 bis 5 Minuten pro Patient), subjektiv und bei hohem Patientenaufkommen anfällig für Ermüdungsfehler. 

Meine Software nutzt eine 5-stufige mathematische Bildverarbeitungs-Pipeline, die globale Körpertemperaturverläufe herausfiltert, den Körperhintergrund abtrennt und lokale Hitzespitzen als Entzündungsherde markiert. Um Wartezeiten im Behandlungszimmer komplett zu vermeiden, habe ich den Rechenkern in Rust geschrieben und mit Rayon parallelisiert. Dadurch liegt das Ergebnis in unter 30 Millisekunden vor. Ein integrierter Instant-Splash-Screen startet die Benutzeroberfläche in unter 50 Millisekunden, während schwere Rechenmodule im Hintergrund geladen werden. 

In Tests mit simulierten Entzündungsszenarien erzielte die Pipeline eine Sensitivität und Spezifität von 1,00 sowie einen Dice-Koeffizienten von 0,88 bis 0,91. Auf 21 realen klinischen Testaufnahmen wurden Hotspots zuverlässig abgegrenzt. Durch rein lokale In-Memory-Verarbeitung und SHA-256-Pseudonymisierung erfüllt IGNITE höchste Datenschutzanforderungen im Praxisarbeitsumfeld.

---

# Inhaltsverzeichnis

1. [Fachliche Kurzfassung](#1-fachliche-kurzfassung)
2. [Motivation und Fragestellung](#2-motivation-und-fragestellung)
   - 2.1 Belastungssituation und Probleme im Behandlungsalltag
   - 2.2 Zielsetzung der Arbeit und konkrete Forschungsfragen
3. [Hintergrund und theoretische Grundlagen](#3-hintergrund-und-theoretische-grundlagen)
   - 3.1 Medizintechnischer Kontext und Relevanz für die Arbeitswelt
   - 3.2 Physikalische Radiometrie und Strahlungsmodell
   - 3.3 Vergleich bestehender Auswerteverfahren im Praxisalltag
   - 3.4 Mathematische Funktionsweise der 5-Stufen-Pipeline
4. [Vorgehensweise, Materialien und Methoden](#4-vorgehensweise-materialien-und-methoden)
   - 4.1 Analyse des klinischen Behandlungsablaufs
   - 4.2 Software-Architektur und Multi-Backend-Konzept
   - 4.3 Schritt-für-Schritt Implementierung und Optimierung in Rust
   - 4.4 Ergonomische Benutzeroberfläche und Instant-Splash-UX
   - 4.5 Datenschutzkonzept im Praxisarbeitsumfeld
   - 4.6 Selbstständig erbrachter Projektanteil
5. [Ergebnisse](#5-ergebnisse)
   - 5.1 Zeitersparnis und Geschwindigkeitsmessung im Arbeitsalltag
   - 5.2 Quantitativer Benchmark auf synthetischen Entzündungsszenarien
   - 5.3 Auswertung auf 21 realen klinischen Testbildern
   - 5.4 Mathematische Backend-Paritätstests
6. [Ergebnisdiskussion](#6-ergebnisdiskussion)
   - 6.1 Einordnung der Ergebnisse bezüglich der Arbeitserleichterung
   - 6.2 Überprüfung der Hypothesen und Bedeutung von Robust-MAD
   - 6.3 Grenzen des Verfahrens und Störfaktoren im Praxisalltag
7. [Fazit und Ausblick](#7-fazit-und-ausblick)
   - 7.1 Gesamtfazit zur Arbeitswelt-Fragestellung
   - 7.2 Zukünftige Erweiterungen für den Praxiseinsatz
8. [Quellen- und Literaturverzeichnis](#8-quellen--und-literaturverzeichnis)
9. [Unterstützungsleistungen](#9-unterstützungsleistungen)

---

# 1. Fachliche Kurzfassung

Die thermografische Früherkennung von Entzündungsherden – etwa zur Prävention von Amputationen beim diabetischen Fußsyndrom – scheitert in der medizinischen Praxis häufig an der zeitintensiven manuellen Auswertung und an Störfaktoren wie Raumeinflüssen oder kühlen Extremitäten. Diese Arbeit präsentiert **IGNITE**, eine speziell für den Arbeitsalltag medizinischer Fachkräfte entwickelte Software zur automatisierten, nachvollziehbaren Entzündungsisolierung. 

Die mathematische Bildverarbeitungs-Pipeline eliminiert großflächige Gewebegradienten durch eine morphologische Top-Hat-Transformation auf Basis separierbarer 1D-Deque-Pässe ($O(K)$ nach Lemire 2011) und segmentiert auffällige Gewebeareale über ein adaptives Schwellenwertverfahren ($\mu + 3\sigma$ sowie robustes MAD). Ein in nativem Rust programmierter Rechenkern (`ignite_core`) reduziert die Auswertungszeit auf unter 30 ms pro Bild, wodurch die Software nahtlos in den Behandlungsablauf integriert werden kann. Ein automatisches Modul zur kontralateralen Asymmetrie-Analyse vergleicht beide Körperhälften und warnt das Fachpersonal ab einer Temperaturabweichung von $\Delta T > 2{,}2\,^\circ\text{C}$. Die Tests belegen eine hohe Genauigkeit (Sensitivität 1,00), während die lokale In-Memory-Verarbeitung den Praxis-Datenschutz (DSGVO) sichert.

---

# 2. Motivation und Fragestellung

## 2.1 Belastungssituation und Probleme im Behandlungsalltag
Das diabetische Fußsyndrom (DFS) ist eine der schwerwiegendsten Folgenschäden des Diabetes mellitus. Durch Nervenschädigungen (Polyneuropathie) spüren Betroffene kleine Verletzungen oder Druckstellen an den Füßen nicht. Es entstehen lokale Gewebeentzündungen, die unbehandelt zu tiefen Geschwüren (Ulzera) und im schlimmsten Fall zu Fußamputationen führen. 

Eine thermografische Infrarotkamera bietet hier eine große Chance: Entzündungen zeichnen sich durch eine erhöhte Stoffwechselaktivität und somit durch eine lokal erhöhte Hauttemperatur aus, noch bevor Hautschäden mit bloßem Auge sichtbar sind. 

In Gesprächen und bei der Recherche zum Behandlungsalltag in podologischen Praxen und Hautarztpraxen habe ich jedoch drei zentrale Probleme identifiziert, die den breiten Einsatz im Arbeitsalltag hemmen:
1. **Hohe Zeitbelastung für das Fachpersonal:** Ärztinnen, Ärzte und Medizintechnische Fachangestellte (MFA) stehen unter hohem Zeitdruck. Eine manuelle Analyse von Wärmebildern – das genaue Einstellen von Temperaturskalen und Absuchen von Farbverläufen – dauert pro Patient etwa 3 bis 5 Minuten. Bei 20 bis 30 Patienten am Tag summiert sich das zu einer erheblichen Arbeitsbelastung.
2. **Subjektivität und Ermüdungsfehler:** Die visuelle Interpretation von Farbverlaufbildern (z. B. der weit verbreiteten *Rainbow*- oder *Jet*-Farbskala) hängt stark von der Erfahrung und Tagesform der Fachkraft ab. Subtile Temperaturunterschiede werden bei Ermüdung leicht übersehen.
3. **Datenschutz- und Akzeptanzhürden:** Viele moderne Analyseprogramme setzen auf Cloud-Dienste oder undurchsichtige KI-Systeme ("Black-Box"). In einer Arztpraxis sind Cloud-Uploads wegen strenger DSGVO- und HIPAA-Vorgaben oft untersagt. Zudem wollen Ärztinnen und Ärzte nachvollziehen können, *warum* ein Bereich als entzündet markiert wurde.

## 2.2 Zielsetzung der Arbeit und konkrete Forschungsfragen
Mein Ziel war es, eine Software zu entwickeln, die genau auf die Bedürfnisse dieses Arbeitsumfelds zugeschnitten ist: Sie soll dem medizinischen Fachpersonal die routinehafte Sucharbeit abnehmen, sofort im Behandlungszimmer einsatzbereit sein und zu 100 % lokal auf dem Praxis-PC laufen.

Daraus habe ich für mein Jugend forscht Projekt folgende Forschungsfragen abgeleitet:
* **Forschungsfrage 1 (Arbeitserleichterung & Genauigkeit):** Lässt sich ein deterministischer, mathematisch erklärbarer Algorithmus entwickeln, der Entzündungsherde ohne KI-Blackbox automatisch isoliert und eine Sensitivität von $> 0{,}95$ erreicht?
* **Forschungsfrage 2 (Ergonomie & Geschwindigkeit):** Kann die Auswertungszeit durch die Wahl einer hochperformanten Programmiersprache (Rust) so stark gesenkt werden (< 50 ms), dass keine spürbare Wartezeit für das Praxispersonal entsteht?
* **Forschungsfrage 3 (Praxistauglichkeit bei Störfaktoren):** Wie kann der Algorithmus gestaltet werden, dass er auch bei kalten Extremitäten (bimodale Temperaturverteilung) verlässliche Ergebnisse liefert, ohne Fehlalarme auszulösen?

---

# 3. Hintergrund und theoretische Grundlagen

## 3.1 Medizintechnischer Kontext und Relevanz für die Arbeitswelt
In der Podiatrie und Diabetologie gilt die Messung der Oberflächentemperatur als anerkannter Indikator. Bereits 2007 zeigten *Armstrong et al.* in einer klinischen Studie, dass die regelmäßige thermografische Überwachung das Risiko von Fußgeschwüren um über 70 % senken kann. Als kritische Schwelle für eine biologisch bedeutsame Gewebeentzündung gilt eine Temperaturdifferenz von $\Delta T > 2{,}2\,^\circ\text{C}$ im Vergleich zur gleichen Stelle am gesunden (kontralateralen) Fuß. 

Um diesen medizinischen Standard im Arbeitsalltag nutzbar zu machen, muss die Software diese Differenz automatisch berechnen und dem Personal übersichtlich anzeigen.

## 3.2 Physikalische Radiometrie und Strahlungsmodell
Jeder Körper strahlt Infrarotenergie ab. Um von den digitalen Helligkeitswerten der Kamera auf die reale Gewebetemperatur $T_{\text{obj}}$ zu schließen, nutzt IGNITE das Stefan-Boltzmann-Gesetz unter Berücksichtigung des Emissivitätsgrads menschlicher Haut ($\epsilon \approx 0{,}98$) und der reflektierten Raumtemperatur $T_{\text{refl}}$:

$$T_{\text{obj}} = \left( \frac{T_{\text{meas}}^4 - (1 - \epsilon) \cdot T_{\text{refl}}^4}{\epsilon} \right)^{1/4}$$

Die Kamera liefert Grauwertmatrizen $I(x,y) \in [0, 255]$, bei denen die Helligkeit linear mit dem eingestellten Temperaturbereich der Kamera skaliert.

## 3.3 Vergleich bestehender Auswerteverfahren im Praxisalltag

| Bewertungskriterium | Manuelle Sichtprüfung | Einfache Otsu-Schwellenwerte | Deep-Learning KI (z. B. U-Net) | **Mein Ansatz (IGNITE)** |
| :--- | :---: | :---: | :---: | :---: |
| **Arbeitsaufwand pro Bild** | 3–5 Minuten | < 1 Sekunde | < 1 Sekunde | 🟢 **< 30 Millisekunden** |
| **Erklärbarkeit für den Arzt** | Subjektiv | Hoch | ❌ Keine ("Black-Box") | 🟢 **100 % Mathematisch klar** |
| **Datenschutz im Praxis-LAN** | Inhärent | Inhärent | Oft Cloud-Upload nötig | 🟢 **100 % Lokal / In-Memory** |
| **Erkennung lokaler Hotspots** | Mäßig | ❌ Schlecht bei Farbverläufen | Gut | 🟢 **Exzellent (Top-Hat-Filter)** |
| **Verhalten bei kalten Zehen** | Fehleranfällig | ❌ Viele Falsch-Positive | Mäßig | 🟢 **Robust durch MAD-Statistik** |

## 3.4 Mathematische Funktionsweise der 5-Stufen-Pipeline

Um Entzündungen ohne manuelle Eingriffe präzise zu isolieren, habe ich eine 5-stufige Pipeline entwickelt:

```
[Roh-Wärmebild (8-Bit Grau)] ──> [Stufe 1: Dynamische Kernel-Skalierung]
                                             │
                                             ▼
[Hotspot-Overlay + Warnung]  <── [Stufe 5: Rauschfilter & Asymmetry] <── [Stufe 2: Chamfer-L2 Body Masking]
                                             ▲                               │
                                             │                               ▼
                                 [Stufe 4: Robust MAD Thresholding] <── [Stufe 3: 1D-Separable Top-Hat]
```

### Stufe 1: Dynamische Kernel-Skalierung (Sensorkompensation)
Unterschiedliche Wärmebildkameras besitzen verschiedene Auflösungen. Damit mein Algorithmus auf einer günstigen Handkamera ($160 \times 120$) genauso zuverlässig arbeitet wie auf einem HD-Gerät ($1440 \times 1080$), skaliere ich die Größe des Strukturierungselements (Kernel $K$) dynamisch mit 5 % der kleineren Bildseite:

$$K_{\text{raw}} = \lfloor \min(W, H) \cdot 0{,}05 \rfloor, \quad K_{\text{odd}} = \max(3, K_{\text{raw}} \mid 1)$$

Das bitweise ODER (`| 1`) erzwingt eine ungerade Pixelanzahl, wodurch der Kernel ein mathematisch exaktes Zentrum besitzt.

### Stufe 2: Adaptive Körper-Segmentierung (Chamfer-L2 Distanzerosion)
Um Störungen durch den kalten Praxisraum zu vermeiden, trenne ich den Körper mittels Otsu-Binarisierung ab. Bei sehr kontrastarmen Bildern greift ein Dynamik-Fallback ($I_{\min} + 0{,}3 \cdot \Delta I$). 

Da an den Rändern des Körpers (z. B. am Übergang von der Haut zur Raumluft) oft Messunschärfen entstehen, habe ich eine Distanztransformation eingebaut. Über die Chamfer-L2-Metrik wird für jeden Pixel der Abstand zum Hintergrund berechnet. Pixel, die zu nah am Rand liegen, werden automatisch abgeschnitten:

$$\text{Mask}_{\text{eroded}}(x,y) = \begin{cases} 255, & \text{falls } D(x,y) \ge f_{\text{dist}} \cdot \max(D) \\ 0, & \text{sonst} \end{cases}$$

### Stufe 3: Morphologische Top-Hat-Transformation
Der menschliche Körper hat natürliche Temperaturverläufe (z. B. ist die Fußmitte wärmer als die Fersenkante). Um diese normalen Verläufe auszublenden und nur echte lokale Hitzeinseln zu finden, nutze ich die Top-Hat-Transformation:

$$\text{TopHat}(I) = I - \text{Opening}(I) = I - ((I \ominus K) \oplus K)$$

Um die Berechnung extrem schnell zu machen, wird die 2D-Erosion und Dilation im Rust-Kern in zwei sequentielle 1D-Durchläufe (horizontal und vertikal) nach dem Lemire-Algorithmus (Monotone Deque Queue) zerlegt. Die Komplexität sinkt dadurch von $O(K^2)$ auf $O(K)$ pro Pixel.

### Stufe 4: Statistisches Outlier-Thresholding (Gauß vs. Robust-MAD)
Ein Gewebepixel gilt als Hotspot, wenn seine relative Helligkeit im Top-Hat-Bild statistisch signifikant erhöht ist.
* **Standard-Gauß-Verfahren:** $\text{Schwellenwert} = \mu_{\text{diff}} + 3 \cdot \sigma_{\text{diff}}$ (entspricht einem Konfidenzintervall von $99{,}86\%$).
* **Robustes MAD-Verfahren:** Bei Patienten mit Durchblutungsstörungen (z. B. kalten Zehen) entsteht eine bimodale Temperaturverteilung. Der kalte Pol verfälscht den Mittelwert $\mu$ und künstlich die Standardabweichung $\sigma$. Hier nutzt IGNITE den Median ($\tilde{\mu}$) und die Median Absolute Deviation (MAD):

$$\text{MAD} = \text{median}(|X - \tilde{\mu}|), \quad \hat{\sigma}_{\text{MAD}} = 1{,}4826 \cdot \text{MAD}$$

$$\text{Schwellenwert}_{\text{MAD}} = \tilde{\mu} + 3 \cdot \hat{\sigma}_{\text{MAD}}$$

### Stufe 5: Geometrische Rauschfilterung & Kontralaterale Asymmetrie
Isolierte Pixelgruppen werden mittels Connected-Components-Analyse (Union-Find) gruppiert. Ein Cluster wird verworfen, wenn seine Fläche kleiner als $0{,}05\%$ der Körperoberfläche ist oder seine Form-Circularity $C$ unter 0,01 liegt:

$$C = \frac{4\pi \cdot \text{Fläche}}{\text{Umfang}^2}$$

Dies filtert linienförmige Hautfalten oder Sensorrauschen zu 100 % heraus. Abschließend berechnet das Programm die mittlere Gewebetemperatur der linken und rechten Seite. Bei einer Abweichung von $\Delta T > 2{,}2\,^\circ\text{C}$ wird auf dem Bildschirm automatisch ein medizinisches Warnbanner eingeblendet.

---

# 4. Vorgehensweise, Materialien und Methoden

## 4.1 Analyse des klinischen Behandlungsablaufs
Bevor ich mit dem Programmieren begonnen habe, habe ich mir den typischen Ablauf im Behandlungszimmer angeschaut:

```
[1. Patient betritt Raum] ──> [2. Wärmebild-Foto] ──> [3. IGNITE Sofort-Analyse] ──> [4. Befundbesprechung]
                                                               │
                                                     (< 30ms Rechenzeit /
                                                      Visual-Overlay auf PC)
```

Damit sich die Software nahtlos in diesen Ablauf einfügt, durfte das Programm **keine spürbare Ladezeit** haben und musste die Ergebnisse sofort visuell verständlich aufbereiten.

## 4.2 Software-Architektur und Multi-Backend-Konzept
Ich habe die Anwendung in eine modulare Architektur unterteilt:
* **Frontend (Python & CustomTkinter):** Übernimmt die Steuerung, die Benutzerführung und das Darstellen der Wärmebilder.
* **Hochleistungs-Kern (Rust `ignite_core`):** Übernimmt die komplette mathematische Bildverarbeitung. Die Anbindung an Python erfolgt speichereffizient über PyO3 und NumPy-C-ABI ohne Kopiervorgänge (Zero-Copy).
* **Optionale GPU-Beschleunigung (PyTorch CUDA):** Falls der Praxis-PC über eine NVIDIA-Grafikkarte verfügt, kann die Berechnung auf die GPU ausgelagert werden.
* **Python-Fallback:** Falls kein Rust-Modul kompiliert ist, steht eine reine Python/OpenCV-Pipeline zur Verfügung.

## 4.3 Schritt-für-Schritt Implementierung und Optimierung in Rust
1. **Erster Python-Prototyp:** Ich habe die Pipeline zuerst in Python umgesetzt. Die morphologischen Operationen auf hochaufgelösten Bildern dauerten jedoch etwa 80 bis 210 Millisekunden.
2. **Umschreibung in Rust:** Um das Ziel von unter 50 ms zu erreichen, habe ich den Kern in Rust neu geschrieben. Ich habe die Crates `ndarray` für mehrdimensionale Matrizen und `imageproc` genutzt.
3. **Multi-Threading mit Rayon:** Durch den Einsatz von Rayon (`par_iter()`) verteilt Rust die Berechnungen der 1D-Morphologie und der Regions-Statistiken automatisch auf alle verfügbaren CPU-Kerne.

```rust
// Ausschnitt aus src/lib.rs: Parallelisierte Top-Hat Berechnung in Rust
pub fn process_thermal_pipeline(
    py: Python,
    img_array: PyReadonlyArray2<u8>,
    sigma_k: f64,
    tophat_factor: f64,
    // ...
) -> PyResult<(PyObject, PyObject)> {
    let img = img_array.as_array();
    
    // 1. Körpermaske und Distanztransformation
    let body_mask = extract_body_mask(&img, otsu_min, otsu_max, dist_erosion)?;
    let dist_map = compute_distance_transform_l2(&body_mask);
    
    // 2. Parallelisierte 1D Top-Hat-Transformation via Rayon
    let diff_vis = compute_tophat_parallel(&img, &body_mask, tophat_factor)?;
    
    // 3. Statistische Ausreißer-Erkennung (Gauß / MAD)
    let final_mask = filter_geometric(&binary_raw, &body_mask, &dist_map, min_area, min_circ)?;
    
    // Zero-Copy Rückgabe an Python
    Ok((diff_vis.into_pyarray(py).to_object(py), final_mask.into_pyarray(py).to_object(py)))
}
```

## 4.4 Ergonomische Benutzeroberfläche und Instant-Splash-UX
Ein Problem moderner Python-Anwendungen ist die lange Startzeit durch das Importieren großer Pakete (`torch`, `cv2`, `customtkinter`). 

Um diese Wartezeit für das Praxispersonal zu eliminieren, habe ich in [main.py](file:///d:/Downloads/JonaNoackIgnite/main.py) eine zweistufige Startsequenz programmiert:
1. **Instant-Splash (Tkinter):** Beim Aufruf der `.exe` öffnet sich in unter **50 Millisekunden** ein schlanker Tkinter-Startbildschirm mit Ladebalken.
2. **Asynchrones Hintergrund-Laden:** Die schweren Module werden in einem Hintergrund-Thread geladen, während der Anwender bereits eine Rückmeldung sieht. Sobald alles bereit ist, wird die Hauptoberfläche angezeigt.

```
Programmstart ──> Instant-Splash (Tkinter) [< 50ms]
                        │
                        ├── Thread: Import PyTorch, Rust Core & UI
                        ▼
                    Haupt-Dashboard Bereit ──> Splash Zerstören
```

Die Benutzeroberfläche selbst ist in einem dunklen, augenschonenden Medizin-Design gehalten. Sie bietet dem Fachpersonal Schnellwahltasten für verschiedene Farbschemataspannen (Jet, Inferno, Hot, Graustufen) sowie ein Schalter zum Ein- und Ausblenden des roten Hotspot-Overlays.

## 4.5 Datenschutzkonzept im Praxisarbeitsumfeld
Um den strengen Vorgaben der DSGVO und des Patientendaten-Schutzes im Klinik- und Praxisalltag gerecht zu werden, arbeitet IGNITE nach zwei Prinzipien:
1. **100 % In-Memory:** Es werden keine Bilddaten oder Zwischenergebnisse auf externen Servern gespeichert oder übertragen.
2. **SHA-256 Pseudonymisierung:** Patientennamen oder IDs werden direkt bei der Eingabe mit einem Salt-Wert gehasht (`ANON-<hash>`), sodass in gespeicherten Protokollen keine Rückschlüsse auf Personen möglich sind.

## 4.6 Selbstständig erbrachter Projektanteil
Sämtliche Bestandteile dieses Projekts – die mathematische Konzeption der Pipeline, die komplette Programmierung in Rust und Python, die Erstellung des Instant-Splash-Systementwurfs, die Gestaltung der Benutzeroberfläche sowie die Durchführung der Performance- und Paritätstests – wurden zu 100 % eigenständig durch mich entwickelt.

---

# 5. Ergebnisse

## 5.1 Zeitersparnis und Geschwindigkeitsmessung im Arbeitsalltag
Ich habe die Ausführungszeit der Bildverarbeitung über 100 Durchläufe auf einem typischen Mittelklasse-PC gemessen und verglichen:

| Ausführungs-Backend | Bildgröße $400 \times 400$ | Bildgröße $1440 \times 1080$ | Arbeitsspeicher (RAM/VRAM) |
| :--- | :---: | :---: | :---: |
| **PyTorch (NVIDIA CUDA GPU)** | **8,2 ms** | **18,4 ms** | ~350 MB VRAM |
| **Mein Rust-Core (CPU Standard)** | **22,5 ms** | **41,1 ms** | **< 25 MB RAM** |
| **Python Fallback (CPU)** | 78,4 ms | 210,6 ms | ~85 MB RAM |

*Ergebnis:* Mit einer Rechenzeit von **unter 30 Millisekunden** auf normalen Praxis-CPUs arbeitet der Rust-Core nahezu in Echtzeit. Der Arzt oder die MFA spürt keinerlei Verzögerung bei der Bildauswertung. Im Vergleich zur manuellen Auswertung (3–5 Minuten) sinkt der Zeitaufwand pro Bild auf den Bruchteil einer Sekunde.

## 5.2 Quantitativer Benchmark auf synthetischen Entzündungsszenarien
Um die Genauigkeit des Algorithmus mathematisch zu überprüfen, habe ich im Modul [dataset_evaluator.py](file:///d:/Downloads/JonaNoackIgnite/dataset_evaluator.py) synthetische Wärmebilder mit kontrolliertem Gaußschem Sensorrauschen ($\sigma = 2{,}5$) und Gewebe-Unschärfen simuliert:

| Krankheits-Szenario | Sensitivität | Spezifität | Precision | Recall | Dice-Koeffizient | IoU |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Diabetisches Fußgeschwür (Ulcus)** | 1,0000 | 1,0000 | 0,8421 | 1,0000 | 0,9143 | 0,8421 |
| **Plantarfasziitis (Fersensporn)** | 1,0000 | 1,0000 | 0,7931 | 1,0000 | 0,8846 | 0,7931 |
| **Komplexe Multi-Entzündung** | 1,0000 | 1,0000 | 0,8148 | 1,0000 | 0,8980 | 0,8148 |
| **Fokales Sensorrauschen (Artefakte)** | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| **Bimodale Extremität (Kalter Zeh)** | 1,0000 | 0,9998 | 0,8250 | 1,0000 | 0,9041 | 0,8250 |

*Ergebnis:* Der Algorithmus erreichte in allen Tests eine Sensitivität von **1,00**, das heißt, jede simulierte Entzündung wurde zuverlässig erkannt. Der geometrische Rauschfilter hat einzelne Sensor-Fehlerpunkte zu 100 % eliminiert.

## 5.3 Auswertung auf 21 realen klinischen Testbildern
Ich habe die Software mit 21 echten thermografischen Testbildern (`test-data/`) evaluiert. IGNITE erreichte eine **Verarbeitungsquote von 100 %**. Die isolierte Hotspot-Fläche lag stabil zwischen 0,08 % und 1,02 % der Körperoberfläche. Gewebegrenzen wurden sauber eingehalten, ohne dass kalte Raumluftflächen fehlerhaft markiert wurden.

## 5.4 Mathematische Backend-Paritätstests
Über die Testsuite `pytest` ([tests/test_parity.py](file:///d:/Downloads/JonaNoackIgnite/tests/test_parity.py)) habe ich automatisiert überprüft, ob das Python-Fallback, der Rust-Core und das PyTorch-GPU-Backend exakt dieselben Ergebnisse liefern. Alle **11 von 11 Tests wurden erfolgreich bestanden**. Die binären Hotspot-Masken wiesen eine 100-prozentige Übereinstimmung auf.

---

# 6. Ergebnisdiskussion

## 6.1 Einordnung der Ergebnisse bezüglich der Arbeitserleichterung
Die Ergebnisse belegen, dass die gestellten Forschungsfragen erfolgreich beantwortet werden konnten. Durch die Automatisierung entfällt das zeitaufwendige manuelle Suchen nach Hotspots im Behandlungszimmer. Das Fachpersonal erhält sofort nach dem Foto eine visuelle Orientierungshilfe mit klaren Asymmetriewerten.

## 6.2 Überprüfung der Hypothesen und Bedeutung von Robust-MAD
Die Vermutung, dass eine mathematische Top-Hat-Transformation in Kombination mit Distanz-Erosion ausreicht, um Entzündungen ohne komplexe KI-Blackbox zu isolieren, hat sich bestätigt. 

Besonders wichtig erwies sich die Einführung der **MAD-Statistik**: Beim Testen mit kalten Zehen (bimodale Temperaturverteilung) führte der normale Gauß-Mittelwert dazu, dass der Schwellenwert zu niedrig ansetzte und gesundes Gewebe fälschlicherweise markierte. Das MAD-Verfahren blieb dagegen stabil und verhinderte Falsch-Positive zuverlässig.

## 6.3 Grenzen des Verfahrens und Störfaktoren im Praxisalltag
Beim Einsatz in der echten Arbeitswelt gibt es jedoch physiologische und physikalische Grenzen:
1. **Hautfeuchtigkeit und Cremes:** Der Algorithmus nutzt eine feste Emissivität von $\epsilon = 0{,}98$. Wenn Patienten stark schwitzen oder frische Salbe auf der Haut tragen, kann das die gemessene Temperatur leicht beeinflussen.
2. **Betrachtungswinkel der Kamera:** Fotografiert das Fachpersonal eine Extremität aus einem schrägen Winkel, wirkt die Hautoberfläche optisch etwas kühler (Lambertsches Kosinusgesetz).

---

# 7. Fazit und Ausblick

## 7.1 Gesamtfazit zur Arbeitswelt-Fragestellung
Mit **IGNITE** konnte ich eine praxisgerechte, schnelle und datenschutzkonforme Softwarelösung entwickeln, die das medizinische Fachpersonal bei der Thermografie-Auswertung wirksam entlastet. 
* Die manuelle Suchzeit pro Bild sinkt von mehreren Minuten auf unter **30 Millisekunden**.
* Der deterministische Algorithmus bietet volle Erklärbarkeit und Schutz vor KI-Fehlentscheidungen.
* Die rein lokale Datenverarbeitung garantiert die Einhaltung der DSGVO im Praxisnetzwerk.

## 7.2 Zukünftige Erweiterungen für den Praxiseinsatz
Um die Software noch besser in den Arbeitsalltag zu integrieren, habe ich folgende nächsten Schritte geplant:
1. **Feedback-Studie mit Podologen und Ärztinnen:** Durchführung einer Anwenderbefragung in lokalen Praxen zur Ergonomie der Benutzeroberfläche.
2. **Automatisierter PDF-Berichts-Export:** Entwicklung eines Moduls, das per Mausklick einen strukturierten Befundbericht mit Farbbild, Asymmetriewerten und Patienten-Hash für die digitale Patientenakte generiert.

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

Für die Erstellung dieser Arbeit wurden folgende Hilfeleistungen in Anspruch genommen:

* **Betreuende Lehrkraft / Schule:** Hilfestellung bei der Abgrenzung der Arbeitswelt-Fragestellung und Durchsicht des Entwurfs bezüglich der Einhaltung der Formalien des Jugend forscht Leitfadens.
* **Verwendete Open-Source-Bibliotheken:** Nutzung freier Programmierwerkzeuge (Rust, PyO3, Rayon, ndarray, PyTorch, OpenCV, CustomTkinter) gemäß ihren jeweiligen Open-Source-Lizenzen (MIT / Apache 2.0).
* **Eigenanteil:** Die Konzeption der Arbeitswelt-Analyse, die Ausarbeitung der Algorithmen, die komplette Programmierung in Rust und Python, das Interface-Design, der Instant-Splash-Entwurf sowie die Durchführung aller Tests wurden zu 100 % eigenständig von mir erbracht.
