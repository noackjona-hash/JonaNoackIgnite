---
title: "IGNITE: Automatisierte, deterministische Thermografie-Pipeline zur Früherkennung pathologischer Entzündungsherde im klinischen Arbeitsumfeld"
author: "Jona Noack"
date: "2026-07-23"
bibliography: quellen.bib
geometry: margin=2.5cm
fontsize: 12pt
linestretch: 1.5
header-includes:
  - \usepackage{amsmath}
  - \usepackage{amssymb}
---

# Projektüberblick

In diesem Projekt für den Wettbewerb *Jugend forscht 2026* (Fachgebiet Arbeitswelt) wird die Software **IGNITE** vorgestellt. Die Arbeit untersucht Möglichkeiten zur Automatisierung der thermografischen Entzündungserkennung im medizinischen Behandlungsalltag. Bisher müssen Ärztinnen, Ärzte und Podologen Wärmebildaufnahmen von Risikopatienten – beispielsweise beim diabetischen Fußsyndrom – manuell am Bildschirm auswerten. Diese visuelle Sichtprüfung erfordert Zeit (nach eigener Schätzung ca. 3 bis 5 Minuten pro Aufnahme), ist subjektiv und unterliegt tageszeitlichen Ermüdungsfaktoren des Personals.

Die entwickelte Software nutzt eine 5-stufige mathematische Bildverarbeitungs-Pipeline, um physiologische Temperaturverläufe zu filtern, Störabstrahlungen des Raumes zu erodieren und lokale Hitzespitzen als potenzielle Entzündungsherde zu isolieren. Der Rechenkern wurde in der Programmiersprache Rust umgesetzt und mittels Rayon parallelisiert. Auf der nativen Auflösung des verwendeten Thermosensors ($160 \times 120$ Pixel) beträgt die gemessene Auswertungszeit **1,6 ms** (Median), auf der hochskalierten JPEG-Ausgabe der Kamera ($1440 \times 1080$) dagegen 104 ms. Eine Kernerkenntnis der Arbeit ist dabei, dass der Rust-Kern **nicht** schneller rechnet als die etablierte C++-Bibliothek OpenCV (Faktor 2,4 langsamer); sein Nutzen liegt in der Unabhängigkeit von nativen Fremdbibliotheken, im deterministischen Verhalten und im geringen Speicherbedarf (< 25 MB).

Zur Bewertung wurden **9 selbst aufgenommene Thermogramme manuell annotiert** und gegen eine Otsu-Baseline verglichen. IGNITE erreicht dabei einen Dice-Koeffizienten von **0,325 ± 0,159** gegenüber 0,004 der Baseline (gepaarter Wilcoxon-Test: $p = 0{,}0046$). Bei getrennter Parameterbestimmung auf einem Tuning-Satz und anschließender einmaliger Auswertung auf 5 ungesehenen Testbildern steigt der Dice-Wert auf **0,513 ± 0,112**. Aufschlussreich ist die Struktur des Fehlers: Bei einer Precision von 0,99 und einer Sensitivität von 0,21 **lokalisiert das Verfahren Herde treffsicher, unterschätzt aber deren Ausdehnung deutlich**. Die zuvor berichteten Werte auf rein synthetischen Daten (Dice 0,88–0,91) werden in dieser Fassung bewusst nicht mehr als Wirksamkeitsnachweis geführt, da die simulierten gaußförmigen Herde exakt der Signalform entsprechen, auf die der Filter ausgelegt ist. Die Arbeit analysiert die deutlichen Grenzen des Verfahrens: Da ein deterministischer Filter nicht zwischen biologischen Infektionen und harmlosen mechanischen Druckstellen (z. B. durch Socken oder Gehlenken) unterscheiden kann, stellt die Software kein Medizinprodukt dar, sondern dient als Orientierungshilfe unter ärztlicher Aufsicht.

---

# Inhaltsverzeichnis

1. [Einleitung und Problemstellung](#1-einleitung-und-problemstellung)
   - 1.1 Belastungssituation im medizinischen Behandlungsalltag
   - 1.2 Relevanz der Früherkennung beim Diabetischen Fußsyndrom
   - 1.3 Zielsetzung und Forschungsfragen
2. [Hintergrund und theoretische Grundlagen](#2-hintergrund-und-theoretische-grundlagen)
   - 2.1 Medizintechnischer Kontext und podiatrischer Goldstandard
   - 2.2 Physikalische Radiometrie und Strahlungsmodell
   - 2.3 Kritische Vergleichsmatrix bestehender Auswerteverfahren
   - 2.4 Mathematische Ausarbeitung der 5-Stufen-Pipeline
3. [Vorgehensweise, Materialien und Methoden](#3-vorgehensweise-materialien-und-methoden)
   - 3.1 Analyse und Ergonomie des klinischen Behandlungsablaufs
   - 3.2 Software-Architektur und Multi-Backend-Konzept
   - 3.3 Schritt-für-Schritt Implementierung in Rust
   - 3.4 Ergonomische Benutzeroberfläche und Instant-Splash-UX
   - 3.5 Datenschutzkonzept im Arbeitsumfeld
   - 3.6 Datenherkunft, Aufnahmegerät und Annotationsverfahren
   - 3.7 Selbstständig erbrachter Projektanteil
4. [Bildgestützte Visualisierung der Pipeline-Stufen](#4-bildgestützte-visualisierung-der-pipeline-stufen)
   - 4.1 Ausgangsmaterial (Original-Thermogramm)
   - 4.2 Körpermaskierung und Distanzkarte (Stufe 2)
   - 4.3 Hintergrundkorrektur via Top-Hat-Transformation (Stufe 3)
   - 4.4 Statistisches Thresholding und Hotspot-Maske (Stufe 4 & 5)
   - 4.5 Finales diagnostisches Overlay für das Behandlungszimmer
   - 4.6 Auswertung synthetischer Krankheits-Szenarien (Regressionstest)
5. [Ergebnisse](#5-ergebnisse)
   - 5.1 Laufzeitmessungen und Rechenzeiten
   - 5.2 Parameter-Sensitivitätsanalyse des Schwellenwert-Faktors k
   - 5.3 Hauptergebnis: Validierung gegen manuell annotierte Realaufnahmen
   - 5.4 Getrennte Parameterbestimmung: Tuning- und Testsatz
   - 5.5 Ablation der geometrischen Filterregeln
   - 5.6 Backend-Paritätstests
   - 5.7 Ergänzend: synthetische Entzündungsszenarien
6. [Ergebnisdiskussion und Kritische Würdigung](#6-ergebnisdiskussion-und-kritische-würdigung)
   - 6.1 Einordnung der Ergebnisse bezüglich der Arbeitserleichterung
   - 6.2 Überprüfung der Hypothesen und Bedeutung von Robust-MAD
   - 6.3 Ausführliche Analyse der Nachteile, Grenzen und Störfaktoren
7. [Fazit und Ausblick](#7-fazit-und-ausblick)
   - 7.1 Gesamtfazit zur Arbeitswelt-Fragestellung
   - 7.2 Zukünftige Erweiterungen für den Praxiseinsatz
8. [Literaturverzeichnis](#8-literaturverzeichnis)
9. [Unterstützungsleistungen](#9-unterstützungsleistungen)

---

# 1. Einleitung und Problemstellung

## 1.1 Belastungssituation im medizinischen Behandlungsalltag
Die demografische Entwicklung und die Zunahme chronischer Stoffwechselerkrankungen stellen das medizinische Fachpersonal in Praxen und Kliniken vor erhebliche kapazitäre Herausforderungen [@ring2012healthcare]. Insbesondere in der Podiatrie, Diabetologie und Dermatologie müssen täglich zahlreiche Risikopatienten untersucht werden. 

Das manuelle Durchmustern von Wärmebildaufnahmen zur Identifikation pathologischer Hitzespitzen erfordert konzentriertes Absuchen am Bildschirm, das manuelle Einstellen dynamischer Farbskalen sowie das Ausmessen kontralateraler Temperaturdifferenzen. Für eine qualifizierte Erstbeurteilung einer thermografischen Aufnahme ist nach eigener Zeitmessung an den in dieser Arbeit verwendeten Aufnahmen mit etwa 3 bis 5 Minuten zu rechnen. Es handelt sich ausdrücklich um eine **eigene Schätzung** und nicht um einen publizierten Kennwert; eine belastbare Erhebung des Zeitbedarfs in der Praxis steht noch aus (siehe Kapitel 6.3). Bei einer Tagesfrequenz von 20 bis 30 Patienten summiert sich dieser Zusatzaufwand zu einer Arbeitszeit von über 1,5 Stunden, die für das persönliche Arzt-Patienten-Gespräch fehlt.

Darüber hinaus birgt die rein visuelle Sichtprüfung ein relevantes Fehlerrisiko: Die wahrgenommene Intensität einer Entzündungszone auf Farbskalen (z. B. *Rainbow*- oder *Jet*-Colormaps) hängt stark von der individuellen Farbkontrasteinstellung des Monitors sowie von Ermüdungsfaktoren des Fachpersonals am Ende einer Schicht ab.

## 1.2 Relevanz der Früherkennung beim Diabetischen Fußsyndrom
Das diabetische Fußsyndrom (DFS) ist eine Folgeerscheinung der distalen sensomotorischen Polyneuropathie und der peripheren arteriellen Verschlusskrankheit (pAVK). Wegen des Verlusts des Protektivempfindens bleiben biomechanische Überlastungen, Mikrotraumen oder Druckstellen vom Patienten unbemerkt [@armstrong2007skin]. 

Entzündliche Prozesse im tiefen Gewebe führen durch Hyperämie und gesteigerte Stoffwechselaktivität zu lokal abgegrenzten Temperaturerhöhungen der Hautoberfläche. Diese thermischen Anomalien treten häufig Tage bis Wochen auf, bevor histologische Gewebedefekte oder ulzeröse Hautdurchbrüche sichtbar werden. Eine verlässliche Früherkennung ermöglicht frühzeitige Entlastungsmaßnahmen (z. B. orthopädische Schuhanpassungen) und kann das Risiko von Unterschenkelamputationen maßgeblich senken [@armstrong2007skin].

## 1.3 Zielsetzung und Forschungsfragen
Ziel dieser Arbeit ist die Konzeption, Implementierung und mathematische Validierung von **IGNITE**, einer hochperformanten, lokal auszuführenden Software zur automatisierten Hotspot-Isolierung. Das System soll das Fachpersonal durch eine objektive visuelle Orientierungshilfe entlasten, ohne den klinischen Behandlungsfluss durch Ladezeiten zu hemmen.

Folgende Forschungsfragen stehen im Zentrum der Untersuchung:
* **Forschungsfrage 1 (Trefferqualität & Erklärbarkeit):** Lässt sich ein deterministischer, mathematisch vollständig nachvollziehbarer Algorithmus entwickeln, der thermisch auffällige Areale auf **real aufgenommenen** Thermogrammen signifikant besser markiert als eine einfache globale Schwellenwert-Baseline – ohne auf undurchsichtige KI-Blackbox-Modelle zurückzugreifen? Als Prüfgröße dient der Dice-Koeffizient gegenüber einer Handannotation, abgesichert durch einen gepaarten Signifikanztest.
* **Forschungsfrage 2 (Geschwindigkeit & Ergonomie):** Kann eine Rechenzeit von $< 50\text{ ms}$ erreicht werden, sodass die Auswertung im Behandlungszimmer verzögerungsfrei erfolgt – und welchen Beitrag leistet dabei tatsächlich die Implementierung in nativem Rust gegenüber der etablierten C++-Bibliothek OpenCV? Diese Frage wird bewusst als **Vergleich mit einer Referenzimplementierung** gestellt und nicht als bloße Bestätigung der eigenen Umsetzung.
* **Forschungsfrage 3 (Kritische Grenzen):** Wo liegen die physikalischen und algorithmischen Schwachstellen eines rein Schwellenwert-basierten Verfahrens im realen Praxisbetrieb?

Vorweggenommen sei, dass die Untersuchung **zwei der drei Ausgangserwartungen widerlegt
hat**: Der Rust-Kern ist langsamer als OpenCV (Kapitel 5.1), und die auf synthetischen
Daten gemessene Sensitivität von nahezu 1,00 lässt sich auf Realaufnahmen nicht
reproduzieren (Kapitel 5.3). Beide Befunde werden hier bewusst berichtet, da sie
methodisch aufschlussreicher sind als die ursprünglich erhofften Bestätigungen.

---

# 2. Hintergrund und theoretische Grundlagen

## 2.1 Medizintechnischer Kontext und podiatrischer Goldstandard
In der medizinischen Thermografie gilt die vergleichende Analyse symmetrischer Körperareale (kontralaterale Asymmetrie) als diagnostischer Goldstandard [@armstrong2007skin; @ring2012healthcare]. Da die physiologische Hauttemperatur systemischen Schwankungen (z. B. Zirkadianer Rhythmus, Raumtemperatur) unterliegt, ist der absolute Temperaturwert einzelner Pixel nur bedingt aussagekräftig. 

Eine kontralaterale Temperaturdifferenz von 

$$ \Delta T = |T_{\text{links}} - T_{\text{rechts}}| > 2{,}2\,^\circ\text{C} $$

an anatomisch identischen Messpunkten gilt in der Podiatrie als klinisch signifikanter Indikator für entzündliche Gewebeprozesse [@armstrong1997infrared; @armstrong2007skin].

![Skizze 4: Kontralaterale Asymmetrie-Analyse](images/skizze_asymmetrie_analyse.png)  
*Abbildung 1 (Skizze 4): Prinzip der kontralateralen Asymmetrie-Analyse in der Podiatrie. Das Bild wird an der Bildmitte getrennt, um die mittleren Oberflächentemperaturen beider Fußsohlen zu vergleichen. Bei einer Abweichung von $\Delta T > 2{,}2\,^\circ\text{C}$ erscheint ein Warnhinweis.*

---

## 2.2 Physikalische Radiometrie und Strahlungsmodell
Die Infrarot-Thermografie basiert auf dem Stefan-Boltzmann-Gesetz [@stefan1879beziehung; @boltzmann1884ableitung], das die spezifische Ausstrahlung $M$ eines schwarzen Körpers in Abhängigkeit von der thermodynamischen Temperatur $T$ beschreibt:

$$ M = \sigma \cdot T^4 $$

wobei $\sigma \approx 5{,}670374 \times 10^{-8}\,\text{W}\,\text{m}^{-2}\,\text{K}^{-4}$ die Stefan-Boltzmann-Konstante bezeichnet. Für reale Körper mit dem spezifischen Emissivitätsgrad $\epsilon \in (0, 1)$ und unter Berücksichtigung der von der Umgebung reflektierten Infrarotstrahlung $T_{\text{refl}}$ gilt für die vom Sensor erfasste Gewebetemperatur $T_{\text{obj}}$ [@jones1998reappraisal]:

$$ T_{\text{obj}} = \left( \frac{T_{\text{meas}}^4 - (1 - \epsilon) \cdot T_{\text{refl}}^4}{\epsilon} \right)^{1/4} $$

Für menschliches Hautgewebe gilt der messtechnisch bestimmte Literaturwert $\epsilon \approx 0{,}98$ [@steketee1973spectral; @ring2012healthcare]. Infrarotkameras transformieren das thermische Strahlungsfeld in eine 8-Bit-Grauwertmatrix $I(x,y) \in [0, 255]$, deren Intensität linear mit dem eingestellten Temperaturbereich $[T_{\min}, T_{\max}]$ korreliert.

---

## 2.3 Kritische Vergleichsmatrix bestehender Auswerteverfahren

| Auswerteverfahren | Vorteile im Arbeitsalltag | Nachteile und Schwachstellen |
| :--- | :--- | :--- |
| **Manuelle Sichtprüfung (Arzt/Podologe)** | • Erkennt den klinischen Gesamtzusammenhang<br>• Kann Narben, Druckstellen & Wunden unterscheiden<br>• Benötigt keine Zusatzsoftware | • Zeitaufwendig (3–5 Minuten pro Bild)<br>• Subjektiv und abhängig von Erfahrung/Tagesform<br>• Keine automatische Dokumentation |
| **Einfache Schwellenwert-Filter (Otsu)** | • Sehr schnell (< 10 ms)<br>• Einfach zu programmieren | • Versagt bei normalen Körper-Temperaturverläufen<br>• Sehr viele Falsch-Positive an kalten Rändern |
| **Deep-Learning KI (z. B. U-Net)** | • Kann komplexe Formen und Bildmuster erkennen<br>• Hohe Genauigkeit bei gutem Training | • "Black-Box": Entscheidungen nicht mathematisch erklärbar<br>• Oft Cloud-Zwang (DSGVO-Problem im Krankenhaus)<br>• Benötigt leistungsfähige GPUs |
| **Mein Ansatz (IGNITE)** | • Schnelle Berechnung (1,6 ms bei nativer Sensorauflösung, 104 ms bei $1440\times1080$)<br>• 100 % lokal & DSGVO-konform (kein Cloud-Upload)<br>• Mathematisch nachvollziehbar<br>• Keine nativen Fremdbibliotheken nötig (< 25 MB) | • Kann **nicht** zwischen Entzündung & Druckstelle unterscheiden<br>• Feste Schwellenwerte passen nicht auf jeden Hauttyp<br>• Unterschätzt die Ausdehnung eines Herdes systematisch (Sensitivität 0,21)<br>• Kein zertifiziertes Medizinprodukt |

---

## 2.4 Mathematische Funktionsweise der 5-Stufen-Pipeline

Die Hotspot-Isolierung in IGNITE basiert auf einer 5-stufigen Bildverarbeitungs-Pipeline [@jugendforscht2025leitfaden]:

### Stufe 1: Dynamische Kernel-Skalierung
Um unabhängig von der Sensorauflösung des verwendeten Kamerasystems ($160 \times 120$ bis $1440 \times 1080$ Pixel) identische geometrische Filtereffekte zu erzielen, skaliert der Radius des morphologischen Strukturierungselements $K$ proportional zur minimalen Bilddimension:

$$ K_{\text{raw}} = \lfloor \min(W, H) \cdot 0{,}05 \rfloor, \quad K_{\text{odd}} = \max(3, K_{\text{raw}} \mid 1) $$

Die bitweise OR-Verknüpfung (`raw | 1`) erzwingt eine ungerade Pixelanzahl und garantiert ein eindeutiges mathematisches Symmetriezentrum.

### Stufe 2: Adaptive Körper-Segmentierung (Chamfer-L2 Distanzerosion)
Zur Abtrennung des kühlen Raumes dient die globale Binarisierung nach Otsu [@otsu1979threshold]. Bei kontrastarmen Aufnahmen greift ein Dynamik-Fallback ($I_{\min} + 0{,}3 \cdot \Delta I$). 

Um Messunsicherheiten an den Geweberändern (Luft-Haut-Übergänge) zu eliminieren, wird die Chamfer-L2-Distanztransformation angewendet. Pixel mit einem Abstand $D(x,y)$ unterhalb der relativen Randschwelle werden erodiert:

$$ \text{Mask}_{\text{eroded}}(x,y) = \begin{cases} 255, & \text{falls } D(x,y) \ge f_{\text{dist}} \cdot \max_{x',y'} D(x',y') \\ 0, & \text{sonst} \end{cases} $$

### Stufe 3: Morphologische Top-Hat-Transformation
Zur Elimination physiologischer Helligkeitsverläufe (z. B. der natürlichen Gewewärme im Fußgewölbe) wird die morphologische Top-Hat-Transformation verwendet:

$$ \text{TopHat}(I) = I - \gamma_K(I) = I - ((I \ominus K) \oplus K) $$

wobei $\gamma_K(I)$ das morphologische Opening von $I$ mit dem Kernel $K$ bezeichnet. Im Rust-Core ist die 2D-Operation in zwei sequentielle 1D-Durchläufe (horizontal und vertikal) nach Lemire [@lemire2006streaming] zerlegt. Die Komplexität pro Pixel sinkt dadurch von $O(K^2)$ auf $O(K)$.

![Skizze 1: Prinzip der morphologischen Top-Hat-Transformation](images/skizze_tophat_prinzip.png)  
*Abbildung 2 (Skizze 1): Das Prinzip der morphologischen Top-Hat-Transformation im 1D-Temperaturprofil. Das morphologische Opening glättet großflächige Verläufe. Die Differenz isoliert scharfe lokale Hitzespitzen oberhalb des Schwellenwerts.*

---

### Stufe 4: Statistisches Outlier-Thresholding (Gauß vs. Robust-MAD)
Zur Segmentierung signifikanter Hitzespitzen werden zwei statistische Verfahren unterstützt:
1. **Gaussian Thresholding:**

$$ T_{\text{Gauß}} = \mu_{\text{diff}} + k \cdot \sigma_{\text{diff}} $$

2. **Robustes MAD-Thresholding:** Bei bimodalen Temperaturverteilungen (z. B. stark unterkühlten Zehen) verzerrt der kalte Pol den Mittelwert $\mu$. IGNITE berechnet in diesem Fall die robusten Kennzahlen Median ($\tilde{\mu}$) und Median Absolute Deviation ($\text{MAD}$):

$$ \text{MAD} = \text{median}(|X - \tilde{\mu}|), \quad \hat{\sigma}_{\text{MAD}} = 1{,}4826 \cdot \text{MAD} $$

$$ T_{\text{MAD}} = \tilde{\mu} + k \cdot \hat{\sigma}_{\text{MAD}} $$

![Skizze 2: Gauß vs. Robust-MAD bei bimodaler Verteilung](images/skizze_gauss_vs_mad.png)  
*Abbildung 3 (Skizze 2): Vergleichende Skizze der statistischen Schwellenwerte bei einer bimodalen Gewebeverteilung (kalte Zehen). Der Gauß-Mittelwert verschiebt sich nach links und verzerrt die Schwelle, während das Median/MAD-Verfahren stabil bleibt.*

---

### Stufe 5: Geometrische Rauschfilterung & Asymmetrie
Zusammenhängende Pixelgruppen werden über eine Zusammenhangsanalyse in 4er-Nachbarschaft
bestimmt. Ein Cluster wird **beibehalten**, wenn seine Fläche mindestens $0{,}05\,\%$ der
Körperoberfläche beträgt und seine Form-Circularity $C$ den Schwellenwert erreicht:

$$ C = \frac{4\pi \cdot A}{P^2} \ge 0{,}08 $$

Der Wert $0{,}08$ entspricht der Implementierung (`DEFAULT_MIN_CIRCULARITY` in `config.py`).
Er ist bewusst niedrig gewählt: Ein exakter Kreis erreicht $C = 1$, reale Entzündungsherde
sind jedoch unregelmäßig berandet, und durch die pixelweise Umfangsberechnung wird $P$ bei
kleinen Objekten systematisch überschätzt, was $C$ zusätzlich verringert. Der Filter
entfernt daher gezielt langgestreckte, fadenförmige Strukturen (etwa Kanten- und
Kompressionsartefakte), ohne kompakte Herde zu verwerfen.

Zusätzlich greifen zwei **datensatzspezifische** Regeln: Cluster mit Schwerpunkt unterhalb
von 65 % der Bildhöhe sowie Cluster in einem Randstreifen werden verworfen. Ihre Wirkung
auf die Referenzdaten wird in Kapitel 5.5 gesondert untersucht.

---

# 3. Vorgehensweise, Materialien und Methoden

## 3.1 Analyse des klinischen Behandlungsablaufs
Der gedachte Ablauf im Behandlungszimmer gliedert sich wie folgt:

![Skizze 3: Integration in den Praxis-Workflow](images/skizze_praxis_workflow.png)  
*Abbildung 4 (Skizze 3): Schema der Integration von IGNITE in den täglichen Praxisablauf im Behandlungszimmer.*

Die Software dient dabei als Werkzeug für Schritt 3. Die eigentliche Diagnose in Schritt 4 bleibt immer beim Fachpersonal.

## 3.2 Software-Architektur und Speicherverwaltung
Die Software ist modular aufgebaut. Um maximale Geschwindigkeit zu erreichen und Speicherzugriffe zu minimieren, werden die Bilddaten über die C-ABI ohne Kopiervorgänge (Zero-Copy) direkt aus dem Python-Speicher in den Rust-Core übergeben:

![Skizze 5: Rust FFI & Speicherarchitektur](images/skizze_rust_ffi_architektur.png)  
*Abbildung 5 (Skizze 5): Speicherarchitektur und FFI-Anbindung zwischen Python (NumPy) und dem Rust-Core (`ignite_core`). Die Bilddaten werden ohne Kopieren via Zeiger übergeben und in Rust mit Rayon auf CPU-Kerne verteilt.*

---

## 3.3 Schritt-für-Schritt Implementierung in Rust
1. **Python-Prototyp:** Erste Tests zeigten, dass OpenCV in Python bei großen Bildern 80 bis 210 ms benötigte.
2. **Rust-Umsetzung:** Durch die Umschreibung in Rust mit den Crates `ndarray` und `imageproc` konnte die Zeit gesenkt werden.
3. **Parallelisierung:** Mit Rayon (`par_iter()`) werden die Schleifen auf alle verfügbaren CPU-Kerne verteilt.

## 3.4 Benutzeroberfläche und Ladeoptimierung
Um lange Startzeiten durch schwere Bibliotheken zu vermeiden, öffnet `main.py` beim Aufruf in unter 50 ms einen leichten Tkinter-Splash-Screen. Während der Anwender die Rückmeldung sieht, lädt ein Hintergrund-Thread die benötigten Module.

## 3.5 Datenschutzkonzept
1. **In-Memory:** Es werden keine Bilddaten auf externe Server übertragen.
2. **SHA-256 Pseudonymisierung:** Patientennamen werden mit Salt gehasht (`ANON-<hash>`).

## 3.6 Datenherkunft, Aufnahmegerät und Annotationsverfahren

### Herkunft der Aufnahmen
Alle 21 in dieser Arbeit ausgewerteten Thermogramme wurden **von mir selbst aufgenommen**.
Als Aufnahmepersonen dienten **Familienmitglieder und Bekannte**, die vor der Aufnahme über
Zweck und Verwendung der Bilder informiert wurden und ihr **Einverständnis** erteilt haben.
Bei minderjährigen Personen lag zusätzlich das Einverständnis der Erziehungsberechtigten vor.

Um Fehlinterpretationen vorzubeugen, ist ausdrücklich festzuhalten:

* Es handelt sich **nicht um klinische Patientendaten**. Ein früherer Wortlaut dieser Arbeit
  sprach von „21 realen klinischen Testaufnahmen"; diese Formulierung war irreführend und
  wurde korrigiert.
* Die aufgenommenen Personen sind **nicht diagnostiziert erkrankt**. Es liegen daher keine
  ärztlich bestätigten Entzündungsherde vor; die Annotationen markieren *thermisch
  auffällige Regionen*, nicht *gesicherte Pathologien*.
* Es wurde **kein Ethikvotum** eingeholt, da keine Studie an Patientinnen und Patienten
  durchgeführt wurde und keine Gesundheitsdaten Dritter aus einer Behandlung stammen.
* Die Bilddateien enthalten keine Namen; eine Zuordnung zu Personen ist über die
  Dateinamen (`bild (1)` … `bild (21)`) nicht möglich.

### Aufnahmegerät und dessen Konsequenzen
Verwendet wurde eine **FLIR ONE bzw. FLIR ONE Pro** – eine an ein Smartphone ansteckbare
Thermografiekamera. Für die Bewertung der Ergebnisse ist eine Eigenschaft dieses Geräts von
zentraler Bedeutung:

> Der **thermische Sensor** der FLIR ONE Pro besitzt eine Auflösung von lediglich
> **$160 \times 120$ Pixeln**. Die ausgegebene JPEG-Datei mit $1440 \times 1080$ Pixeln
> entsteht durch Hochskalierung und Überlagerung mit den Kanten des sichtbaren
> Lichtbildes (*MSX*). Sie enthält **keine zusätzliche thermische Information**.

Daraus folgen drei wesentliche Einschränkungen:

1. **Scheinauflösung.** Ein im $1440 \times 1080$-Bild fein umrandeter Hotspot beruht real
   auf wenigen Sensorpixeln. Die Genauigkeit der Konturbestimmung ist entsprechend
   begrenzt – dies erklärt einen Teil der in Kapitel 5.3 gemessenen Abweichung zwischen
   Algorithmus- und Handannotation.
2. **Verlust der Radiometrie.** Die exportierten JPEG-Dateien enthalten **keine
   Absoluttemperaturen**, sondern nur 8-Bit-Grauwerte einer geräteseitig und je Bild
   dynamisch skalierten Farbpalette. Die in Kapitel 2.2 hergeleitete Umrechnung nach
   Stefan-Boltzmann konnte auf diesen Daten daher **nicht angewendet** werden. Insbesondere
   ist das podiatrische Kriterium einer kontralateralen Differenz von $\Delta T > 2{,}2\,$K
   [@armstrong1997infrared] auf diesem Material **nicht überprüfbar**; die Pipeline arbeitet
   ausschließlich auf relativen Intensitäten.
3. **Kompressionsartefakte.** Die JPEG-Kompression erzeugt Blockartefakte, die der
   Top-Hat-Filter prinzipiell als lokale Maxima aufgreifen kann.

### Aufnahmebedingungen
Die Aufnahmen erfolgten in Innenräumen bei üblicher Zimmertemperatur, aus etwa gleichem
Abstand und in gleicher Ausrichtung (Füße mittig im Bild). Eine standardisierte
Akklimatisierungsphase, wie sie das *Glamorgan-Protokoll* für medizinische Thermografie
vorsieht, wurde **nicht** eingehalten. Raumtemperatur und Luftbewegung wurden nicht
protokolliert. Die einheitliche Aufnahmegeometrie ist zugleich der Grund dafür, dass die
geometrischen Filterregeln aus Kapitel 5.5 auf diesem Datensatz unschädlich sind – auf
anders aufgenommenem Material wäre das nicht zu erwarten.

### Annotationsverfahren
Die Referenzmasken wurden mit dem eigens entwickelten Werkzeug `benchmark_annotator.py`
per Pinselwerkzeug erstellt und als binäre PNG-Masken abgelegt. Wichtige Einschränkungen:

* Annotiert wurden **9 der 21 Aufnahmen**; für die übrigen 12 liegt keine Referenz vor.
* Die Annotation erfolgte durch **eine einzige, medizinisch nicht ausgebildete Person**
  (den Autor). Es gibt daher **weder eine Intra- noch eine Inter-Rater-Übereinstimmung**
  (z. B. Cohens $\kappa$), und die Referenz ist **kein diagnostischer Goldstandard**.
* Die Annotation erfolgte in Kenntnis des Projektziels, eine Verblindung fand nicht statt.

Diese Punkte begrenzen die Aussagekraft aller in Kapitel 5.3 und 5.4 berichteten Werte
erheblich und werden in Kapitel 6.3 erneut aufgegriffen.

## 3.7 Selbstständig erbrachter Projektanteil
Die mathematische Ausarbeitung, die Programmierung in Rust und Python, das Erstellen der Benutzeroberfläche sowie die Durchführung aller Tests wurden zu 100 % eigenständig von mir durchgeführt.

---

# 4. Bildgestützte Visualisierung der Pipeline-Stufen

Die folgenden Abbildungen zeigen die Zwischenschritte der Pipeline an einem echten Testbild:

### 4.1 Ausgangsmaterial (Original-Thermogramm)
![Originales Wärmebild in Grauwert und Jet-Colormap](images/1_original_thermal_jet.png)  
*Abbildung 6: Originales thermografisches Wärmebild in Jet-Colormap.*

---

### 4.2 Körpermaskierung und Distanzkarte (Stufe 2)
![Körpermaske und Chamfer-L2 Distanzkarte](images/2_distance_transform.png)  
*Abbildung 7: Chamfer-L2 Distanzkarte zur Abtrennung unscharfer Ränder.*

---

### 4.3 Hintergrundkorrektur via Top-Hat-Transformation (Stufe 3)
![Top-Hat Differenzbild](images/3_tophat_difference.png)  
*Abbildung 8: Ergebnis der Top-Hat-Transformation (isoliert lokale Temperaturunterschiede).*

---

### 4.4 Statistisches Thresholding und Hotspot-Maske (Stufe 4 & 5)
![Binäre Hotspot-Maske](images/4_hotspot_mask.png)  
*Abbildung 9: Binäre Hotspot-Maske nach Schwellenwertentscheidung und Rauschfilterung.*

---

### 4.5 Finales diagnostisches Overlay
![Finales Hotspot Overlay](images/5_final_overlay_jet.png)  
*Abbildung 10: Visuelle Orientierungshilfe mit roter Hotspot-Markierung.*

---

### 4.6 Auswertung synthetischer Szenarien
![Synthetisches Szenario Diabetischer Fuß](images/synthetic_diabetic_ulcer.png)  
*Abbildung 11: Auswertung eines simulierten diabetischen Fußgeschwürs.*

---

# 5. Ergebnisse

## 5.1 Laufzeitmessungen und Rechenzeiten

Alle Zahlen dieses Kapitels werden von `scripts/run_validation.py` reproduzierbar erzeugt
(fester Zufalls-Seed, protokollierte Hardware). Der vollständige Ergebnisbericht ist als
`docs/validation/validation_report.json` dem Projekt beigelegt.
Gemessen wurde auf einem x86_64-System mit **4 CPU-Kernen**, 60 Wiederholungen nach 10 Aufwärmläufen.
Angegeben sind Minimum und Median, da Einzelmessungen unter einem Desktop-Betriebssystem stark streuen.

| Backend | $400 \times 400$ (min / median) | $1440 \times 1080$ (min / median) |
| :--- | :---: | :---: |
| **Rust-Core (CPU, rayon)** | 7,9 / 9,1 ms | 86,4 / 104,3 ms |
| **Python + OpenCV (CPU)** | 3,1 / 3,3 ms | 40,6 / 43,9 ms |
| **PyTorch (CUDA)** | nicht validierbar | nicht validierbar |

**Dieses Ergebnis widerlegt meine ursprüngliche Erwartung und ist das wichtigste
methodische Resultat der Laufzeituntersuchung.** In einer früheren Messung erschien der
Rust-Core rund dreimal schneller als der Python-Pfad. Diese Messung war jedoch **nicht
fair**: Der Python-Fallback berechnete damals eine *Multi-Scale*-Top-Hat-Transformation
über drei Skalen zuzüglich einer Vorglättung, während der Rust-Core nur **eine** Skala
rechnete. Verglichen wurden also unterschiedliche Algorithmen. Nachdem beide Backends auf
denselben einskaligen Algorithmus angeglichen wurden (siehe Kapitel 5.5), zeigt sich:

> Die SIMD- und multithread-optimierte C++-Morphologie von OpenCV ist auf dieser Hardware
> etwa **2,4-mal schneller** als meine handgeschriebene Rust-Implementierung.

Das ist kein Fehler der Rust-Umsetzung, sondern erwartbar: OpenCV ist eine seit über zwei
Jahrzehnten auf Vektorbefehlssätze hin optimierte Bibliothek. Der Nutzen des Rust-Cores
liegt daher **nicht in der Rohgeschwindigkeit**, sondern in:

* **Unabhängigkeit von nativen Fremdbibliotheken** – der Installer benötigt keine
  OpenCV-Laufzeitkomponenten (< 25 MB statt > 200 MB),
* **deterministischem, plattformgleichem Verhalten** ohne Abhängigkeit von der jeweils
  installierten OpenCV-Version,
* **Speichersicherheit** und geringem Arbeitsspeicherbedarf (< 25 MB).

### Profilierung der Pipeline-Stufen
Mit gesetzter Umgebungsvariable `IGNITE_DEBUG` gibt der Rust-Core Stufenzeiten aus
($1440 \times 1080$, Minimum aus 10 Läufen):

| Stufe | Zeit |
| :--- | :---: |
| Körpermaske (Otsu + Closing + Distanztransformation) | 39,0 ms |
| Top-Hat-Transformation | 26,8 ms |
| Statistisches Thresholding | 2,5 ms |
| Geometriefilter | 5,7 ms |

Die Profilierung führte zu einer gezielten Optimierung: Das statistische Thresholding
materialisierte zuvor zwei Vektoren mit je rund 500 000 `f64`-Werten. Durch eine einzige
parallele Reduktion über Summen (ohne Zwischenspeicherung) sank diese Stufe von 17,9 ms
auf 2,5 ms – eine Beschleunigung um Faktor 7.

### Auflösungsabhängigkeit und praktische Konsequenz
Die FLIR ONE Pro besitzt einen **thermischen Sensor von nur $160 \times 120$ Pixeln**; die
ausgegebene JPEG-Datei mit $1440 \times 1080$ Pixeln ist eine hochskalierte Darstellung
(vgl. Kapitel 3.6). Die Verarbeitung der hochskalierten Datei kostet daher Rechenzeit,
ohne zusätzliche thermische Information zu liefern:

| Verarbeitungsauflösung | Rust-Core (min / median) |
| :--- | :---: |
| $160 \times 120$ (native Sensorauflösung) | **1,2 / 1,6 ms** |
| $320 \times 240$ | 3,8 / 4,7 ms |
| $640 \times 480$ | 17,5 / 20,1 ms |
| $1440 \times 1080$ (JPEG-Ausgabegröße) | 86,4 / 104,3 ms |

**Forschungsfrage 2 ist damit differenziert zu beantworten:** Auf der hochskalierten
JPEG-Auflösung wird die ursprünglich angestrebte Grenze von 50 ms **nicht** eingehalten
(86–104 ms). Auf der tatsächlichen Sensorauflösung liegt die Auswertung dagegen mit
1,6 ms um mehr als das Dreißigfache unter dieser Grenze. Für den Praxiseinsatz folgt
daraus die konkrete Empfehlung, vor der Analyse auf die native Sensorauflösung zu
reduzieren, statt auf Interpolationsartefakten zu rechnen.

## 5.2 Parameter-Sensitivitätsanalyse des Schwellenwert-Faktors k
Um zu untersuchen, wie stabil der Schwellenwert-Faktor $k$ auf das Filterergebnis reagiert, habe ich eine Sensitivitätsanalyse durchgeführt:

![Diagramm 2: Parameter-Sensitivitätsanalyse](images/diagramm_parameter_sensitivitaet.png)  
*Abbildung 13 (Diagramm 2): Sensitivitätsanalyse des Faktors $k$ auf **synthetischen** Daten.*

**Wichtige Einschränkung:** Diese Analyse beruht auf synthetischen Szenarien und legte den
Bereich $k \in [2{,}5;\ 3{,}5]$ nahe. Die Auswertung gegen echte Handannotationen
(Kapitel 5.4) widerspricht dem deutlich: Dort liegt das Optimum bei $k = 1{,}25$, während
$k = 3{,}0$ den Dice-Wert um rund ein Drittel verschlechtert. Die synthetische
Sensitivitätsanalyse ist daher **nicht auf reale Aufnahmen übertragbar** – ein weiterer
Beleg dafür, dass simulierte Herde die Eigenschaften echter Thermogramme nur unzureichend
abbilden. Maßgeblich für die Parameterwahl ist ausschließlich Kapitel 5.4.

---

## 5.3 Hauptergebnis: Validierung gegen manuell annotierte Realaufnahmen

Dies ist das zentrale Ergebnis der Arbeit. Ausgewertet wurden die **9 von 21 Aufnahmen,
für die eine manuell erstellte Ground-Truth-Maske vorliegt** (Annotationswerkzeug:
`benchmark_annotator.py`). Verglichen wird gegen eine **Otsu-Baseline** – eine einfache
globale Schwellenwertbildung ohne Top-Hat und ohne Geometriefilter.

Angegeben sind Mittelwert ± Standardabweichung sowie das 95-%-Bootstrap-Konfidenz­intervall
(10 000 Ziehungen, Seed 20260726) bei Standardparametern ($k = 3{,}0$):

| Metrik | IGNITE | 95 %-KI | Otsu-Baseline |
| :--- | :---: | :---: | :---: |
| **Dice** | **0,325 ± 0,159** | 0,240 – 0,429 | 0,004 ± 0,011 |
| **IoU** | 0,205 ± 0,132 | 0,137 – 0,292 | 0,002 ± 0,006 |
| **Sensitivität** | 0,206 ± 0,133 | 0,138 – 0,293 | 0,005 ± 0,011 |
| **Spezifität** | 1,000 ± 0,000 | 1,000 – 1,000 | 0,982 ± 0,015 |
| **Precision** | **0,991 ± 0,022** | 0,976 – 1,000 | – |
| **MCC** | 0,434 ± 0,126 | 0,367 – 0,516 | – |

Ein gepaarter **Wilcoxon-Vorzeichen-Rangtest** über die neun Bildpaare ergibt einen
signifikanten Vorteil von IGNITE gegenüber der Otsu-Baseline
($W = 45{,}0$; $p = 0{,}0046$; mittlere Dice-Differenz $+0{,}321$).

### Interpretation: hohe Präzision bei geringer Flächenabdeckung
Das Ergebnismuster ist eindeutig und diagnostisch aufschlussreich: Bei einer **Precision
von 0,991** liegt praktisch **jeder** von IGNITE markierte Pixel innerhalb der ärztlich
annotierten Region – Fehlalarme treten also kaum auf. Gleichzeitig liegt die
**Sensitivität bei nur 0,206**, das heißt IGNITE markiert im Mittel lediglich rund ein
Fünftel der annotierten Fläche.

IGNITE **lokalisiert thermisch auffällige Regionen also treffsicher, unterschätzt aber
systematisch deren Ausdehnung.** Ursächlich ist der Top-Hat-Filter: Er reagiert auf den steilen
Temperaturgradienten im Zentrum eines Herdes, während die flach auslaufenden Randzonen
unter dem statistischen Schwellenwert bleiben. Für die angestrebte Rolle als
*Orientierungshilfe* – das Auge des Fachpersonals auf die richtige Stelle zu lenken – ist
dieses Verhalten günstiger als der umgekehrte Fall (viele Fehlalarme). Für eine
Flächenvermessung einer Wunde ist das Verfahren dagegen **nicht** geeignet.

---

## 5.4 Getrennte Parameterbestimmung: Tuning- und Testsatz

In einer früheren Fassung dieser Arbeit wurde der Schwellenwertfaktor $k$ auf denselben
Bildern bestimmt, auf denen anschließend die Güte berichtet wurde. Das ist methodisch
unzulässig (*Data Leakage*) und führt zu systematisch zu optimistischen Werten. Die
Auswertung wurde daher auf eine **strikte Trennung** umgestellt:

* Die 9 annotierten Bilder werden mit festem Seed (20260726) zufällig geteilt in
  **4 Tuning-Bilder** und **5 Testbilder**.
* Auf dem Tuning-Satz wird $k$ über ein Raster $k \in [0{,}5;\ 4{,}5]$ gewählt.
* Der Testsatz wird **genau einmal** mit dem gewählten $k$ ausgewertet.

**Dice auf dem Tuning-Satz in Abhängigkeit von $k$:**

| $k$ | 0,5 | 0,75 | 1,0 | **1,25** | 1,5 | 2,0 | 2,5 | 3,0 | 3,5 | 4,0 | 4,5 |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| Dice | 0,414 | 0,455 | 0,470 | **0,489** | 0,484 | 0,426 | 0,332 | 0,272 | 0,210 | 0,167 | 0,127 |

Das Optimum liegt mit $k = 1{,}25$ **innerhalb** des Rasters (die Kurve steigt bis 1,25 an
und fällt danach ab), ist also kein Randartefakt der Gittergrenzen.

**Ergebnis auf dem unabhängigen Testsatz ($n = 5$, $k = 1{,}25$):**

| Metrik | Wert |
| :--- | :---: |
| **Dice** | **0,513 ± 0,112** |
| IoU | 0,351 ± 0,101 |
| Sensitivität | 0,462 ± 0,215 |
| Spezifität | 0,999 ± 0,001 |
| Precision | 0,736 ± 0,226 |

Der voreingestellte Wert $k = 3{,}0$ (abgeleitet aus der Normalverteilungs-Annahme
$\mu + 3\sigma \approx 99{,}86\,\%$) ist für reale Thermogramme also **deutlich zu
konservativ**. Mit $k = 1{,}25$ steigt der Dice-Koeffizient auf einem zuvor ungesehenen
Testsatz von 0,325 auf **0,513**, wobei die Sensitivität von 0,21 auf 0,46 zunimmt und die
Precision erwartungsgemäß von 0,99 auf 0,74 sinkt. Beide Betriebspunkte sind vertretbar:
$k = 3{,}0$ für maximale Fehlalarmfreiheit, $k = 1{,}25$ für ein ausgewogenes Verhältnis.

> **Einschränkung:** Bei $n = 5$ Testbildern ist dieses Ergebnis ein *Hinweis*, kein
> statistischer Nachweis. Die Standardabweichung der Sensitivität (± 0,215) zeigt eine
> erhebliche Streuung zwischen einzelnen Aufnahmen.

---

## 5.5 Ablation der geometrischen Filterregeln

Die Pipeline verwirft Hotspot-Kandidaten anhand harter geometrischer Regeln. Zwei davon
beruhen auf Annahmen über die Bildkomposition und könnten echte Befunde auslöschen:

* **Anatomischer Cutoff:** Komponenten mit Schwerpunkt unterhalb von 65 % der Bildhöhe
  werden verworfen.
* **Randfilter:** Komponenten näher als $\max(12\ \text{px};\ 1{,}5\,\%\cdot\min(W,H))$ am
  Rand werden verworfen.

Um zu prüfen, ob diese Regeln schaden, wurde ausgezählt, welcher Anteil der **annotierten
Ground-Truth-Pixel** in die jeweils verworfene Zone fällt:

| Filterregel | Anteil der GT-Pixel in der Verwerfungszone |
| :--- | :---: |
| Anatomischer Cutoff ($y > 0{,}65 \cdot H$) | **0,0 %** |
| Randzone | **0,0 %** |

Auf diesem Datensatz verwerfen beide Regeln also **keinen einzigen** annotierten
Befundpixel. Das ist allerdings ausdrücklich **keine allgemeine Unbedenklichkeits­bescheinigung**:
Alle 21 Aufnahmen entstanden in derselben Aufnahmegeometrie (Füße mittig im Bild,
gleicher Abstand). Bei abweichender Positionierung – etwa einem Fersenulkus im unteren
Bilddrittel – würde der Cutoff den Befund systematisch unterdrücken. Die Regeln sind
damit als **datensatzspezifisch** einzustufen und müssten vor einem Praxiseinsatz
entweder entfernt oder an eine automatische Fußlokalisierung gekoppelt werden.

---

## 5.6 Backend-Paritätstests

Eine frühere Fassung dieser Arbeit behauptete, Python-, Rust- und PyTorch-Backend
erzeugten „identische Masken". Diese Aussage war **nicht haltbar** und wurde überprüft.

**Befund der Überprüfung auf allen 21 Realaufnahmen:**

| Kennzahl | Vorher | Nach Angleichung |
| :--- | :---: | :---: |
| Bitgleiche Masken | 0 / 21 | 0 / 21 |
| Mittlere Masken-IoU (Rust vs. Python) | 0,29 | **0,78** |
| Geringste Masken-IoU | 0,11 | 0,48 |

Die Ursachenanalyse ergab, dass die Backends **unterschiedliche Algorithmen** rechneten:
Der Python-Fallback verwendete eine Vorglättung und eine Multi-Scale-Top-Hat-Transformation
über drei Skalen, der Rust-Core eine einzige Skala ohne Vorglättung. Zusätzlich
unterschieden sich der Otsu-Fallback-Faktor (0,35 vs. 0,30), die Zusammenhangs­definition
(8er- vs. 4er-Nachbarschaft) und das morphologische Closing.

Diese Abweichungen wurden im Code beseitigt; die mittlere Masken-IoU stieg dadurch von
0,29 auf 0,78. **Exakte Bitgleichheit ist jedoch prinzipiell nicht erreichbar**, und zwar
aus einem grundsätzlichen Grund: Der Rust-Core nutzt eine *separable* Morphologie nach
Lemire mit rechteckigem Strukturelement (Komplexität $O(K)$ statt $O(K^2)$) sowie eine
Chamfer-Approximation der Distanztransformation, OpenCV dagegen eine andere Approximation
und eine abweichende Randbehandlung. Der Verzicht auf diese Approximationen würde genau
den Geschwindigkeitsvorteil aufheben, für den sie eingeführt wurden.

Die verbleibende Abweichung ist **systematisch und gerichtet**: Die Python-Maske ist
nahezu eine Teilmenge der Rust-Maske (der Rust-Core markiert etwas großzügiger). Statt
einer unhaltbaren Gleichheitsbehauptung sichert die Testsuite diese Eigenschaft nun als
überprüfbare Untergrenze ab (`tests/test_parity.py`: mittlere Masken-IoU $\ge 0{,}70$,
Einzelbild $\ge 0{,}40$). Die Testsuite umfasst **49 Tests**, die vollständig bestehen.

Die **PyTorch/CUDA-Parität konnte nicht überprüft werden**: Die verfügbare Grafikkarte
(GeForce GTX 1050, Compute Capability 6.1) wird von der installierten PyTorch-Version
(unterstützt ab 7.5) nicht bedient. Der GPU-Zweig der Testsuite wird daher übersprungen.
Aussagen über GPU-Laufzeiten werden in dieser Arbeit deshalb **nicht** getroffen.

---

## 5.7 Ergänzend: synthetische Entzündungsszenarien

Die synthetischen Szenarien aus `dataset_evaluator.py` dienen ausschließlich als
Regressionstest der Pipeline, **nicht** als Wirksamkeitsnachweis. Der Grund ist
methodisch zwingend: Die simulierten Herde sind gaußförmige Intensitätsmaxima – also
exakt die Signalform, auf die ein Top-Hat-Filter mit Zirkularitätskriterium ausgelegt
ist. Ein nahezu perfektes Ergebnis ist damit konstruktionsbedingt und nicht
aussagekräftig. Die entsprechenden Kennzahlen finden sich in
`docs/validation/validation_report.json`; sie werden hier bewusst nicht als
Gütenachweis in den Vordergrund gestellt.

---

# 6. Ergebnisdiskussion und Kritische Würdigung

## 6.1 Einordnung der Ergebnisse bezüglich der Arbeitserleichterung
Die Ergebnisse zeigen, dass der Algorithmus schnell rechnet und auffällige Hitzespitzen mit
hoher Treffergenauigkeit lokalisiert: Nahezu jeder markierte Bildpunkt liegt innerhalb der
manuell annotierten Region (Precision 0,99). Für das Fachpersonal ist genau diese
Eigenschaft entscheidend – eine Markierung, der man vertrauen kann, verkürzt die
Suchzeit am Bildschirm, während häufige Fehlalarme das Gegenteil bewirken würden.

Ebenso deutlich ist jedoch zu benennen, was die Ergebnisse **nicht** hergeben: Mit einer
Sensitivität von 0,21 (bzw. 0,46 bei angepasstem Schwellenwert) erfasst IGNITE nur einen
Teil der auffälligen Fläche. Eine Entlastung entsteht daher beim *Auffinden* einer Stelle,
nicht bei deren *Beurteilung* oder *Vermessung*. Die eingangs genannte Zeitersparnis von
3 bis 5 Minuten pro Aufnahme ist zudem eine eigene Schätzung und wurde nicht in einer
Nutzerstudie mit medizinischem Fachpersonal überprüft – ein solcher Nachweis wäre für eine
belastbare Aussage zur Arbeitserleichterung erforderlich.

## 6.2 Überprüfung der Forschungsfragen

**Forschungsfrage 1 – teilweise bestätigt.** Der deterministische Algorithmus schlägt die
Otsu-Baseline auf realen Aufnahmen signifikant (Dice 0,325 vs. 0,004; $p = 0{,}0046$). Die
ursprünglich formulierte Zielmarke einer Sensitivität $> 0{,}95$ wird auf Realaufnahmen
jedoch **klar verfehlt** (0,206 bei $k = 3{,}0$; 0,462 bei $k = 1{,}25$). Diese Zielmarke war
auf synthetischen Daten formuliert worden, wo sie trivial erreichbar ist, weil die
simulierten Herde exakt der Filterform entsprechen. Die Selbstkorrektur lautet: **Auf
synthetischen Daten gemessene Sensitivität ist für dieses Verfahren keine aussagekräftige
Kenngröße.**

**Forschungsfrage 2 – widerlegt in der ursprünglichen Formulierung.** Die Annahme, nativer
Rust-Code sei der entscheidende Geschwindigkeitsfaktor, hat sich nicht bestätigt: OpenCV ist
auf identischem Algorithmus rund 2,4-mal schneller. Die 50-ms-Grenze wird auf der
hochskalierten JPEG-Auflösung verfehlt (86–104 ms), auf der nativen Sensorauflösung dagegen
mit 1,6 ms weit unterschritten. Der eigentliche Erkenntnisgewinn liegt darin, dass **die
Wahl der Verarbeitungsauflösung den Laufzeitgewinn dominiert – nicht die Wahl der
Programmiersprache**. Der Rust-Kern rechtfertigt sich stattdessen über
Abhängigkeitsfreiheit, Determinismus und Speicherbedarf (< 25 MB).

**Forschungsfrage 3 – bestätigt und in Kapitel 6.3 ausgeführt.**

### Bedeutung des Robust-MAD-Verfahrens
Das MAD-Verfahren erwies sich bei kühlen Extremitäten als stabiler als die Schätzung über
Mittelwert und Standardabweichung, da einzelne sehr warme Pixel die Standardabweichung
aufblähen und den Schwellenwert dadurch nach oben verschieben. Zu betonen ist jedoch, dass
dieser Vergleich **qualitativ** anhand einzelner Aufnahmen erfolgte; eine quantitative
Gegenüberstellung beider Schätzer über den annotierten Datensatz steht aus.

---

## 6.3 Ausführliche Analyse der Nachteile, Grenzen und Störfaktoren

### Grenzen der Datengrundlage
1. **Sehr kleine Stichprobe.** Ausgewertet wurden **9 annotierte Aufnahmen**, davon 5 im
   unabhängigen Testsatz. Alle berichteten Konfidenzintervalle sind entsprechend breit
   (Dice: 0,240–0,429). Die Ergebnisse sind als **Machbarkeitshinweis** zu lesen, nicht als
   statistischer Wirksamkeitsnachweis.
2. **Kein diagnostischer Goldstandard.** Die Referenzmasken wurden von **einer einzigen,
   medizinisch nicht ausgebildeten Person** (dem Autor) unverblindet erstellt. Es liegt
   weder eine Intra- noch eine Inter-Rater-Übereinstimmung vor. Ein Teil der gemessenen
   Abweichung dürfte daher auf die Referenz selbst entfallen, nicht auf den Algorithmus.
3. **Keine erkrankten Personen.** Die aufgenommenen Personen sind gesund; es wurden
   thermisch auffällige, nicht pathologisch gesicherte Regionen annotiert. Über die
   Leistung bei echten diabetischen Fußläsionen sagt diese Arbeit **nichts** aus.
4. **Datenverlust während der Arbeit.** Bei der Überprüfung der Annotationsdateien stellte
   sich heraus, dass das Annotationswerkzeug beim Weiterblättern bedingungslos speicherte
   und dadurch sechs zuvor erstellte Masken mit leeren Dateien überschrieben hatte. Der
   Fehler wurde behoben (leere Zeichnungen überschreiben keine vorhandene Annotation mehr)
   und die Auswerteroutine prüft Referenzmasken nun auf Nicht-Leerheit. Alle vor dieser
   Korrektur erhobenen Ground-Truth-Kennzahlen mussten verworfen werden.

### Physikalische und messtechnische Grenzen
5. **Keine Absoluttemperaturen.** Die verwendeten JPEG-Exporte enthalten nur relative
   8-Bit-Grauwerte einer je Bild dynamisch skalierten Palette. Das podiatrische Kriterium
   $\Delta T > 2{,}2\,$K [@armstrong1997infrared] ist damit **nicht überprüfbar**; die in
   Kapitel 2.2 hergeleitete Radiometrie bleibt theoretisch.
6. **Scheinauflösung des Sensors.** Der Thermosensor liefert $160 \times 120$ Pixel, die
   Bilddatei suggeriert $1440 \times 1080$. Feine Konturen im Ergebnisbild sind
   Interpolationsprodukte.
7. **Unkontrollierte Aufnahmebedingungen.** Ohne standardisierte Akklimatisierung und ohne
   Protokollierung von Raumtemperatur und Luftbewegung sind die Aufnahmen nicht
   untereinander vergleichbar kalibriert.
8. **Störeinflüsse.** Schweiß, Salben, Behaarung sowie die Aufnahmeschräge
   (Lambert-Kosinus-Fehler) verändern die abgestrahlte Intensität. JPEG-Blockartefakte
   können vom Top-Hat-Filter als lokale Maxima aufgegriffen werden.

### Algorithmische Grenzen
9. **Systematische Flächenunterschätzung.** Bei einer Precision von 0,99 und einer
    Sensitivität von 0,21 markiert IGNITE nur den heißen Kern eines Herdes. Für eine
    Wundflächenvermessung ist das Verfahren daher **ungeeignet**.
10. **Keine Ursachenunterscheidung.** Ein Top-Hat-Filter sucht Hitzespitzen. Ob die Wärme
    von einer Infektion, engen Socken, mechanischem Druck oder einer Narbe stammt, kann er
    prinzipiell nicht entscheiden.
11. **Datensatzspezifische Filterregeln.** Der anatomische Cutoff bei 65 % der Bildhöhe und
    der Randfilter verwerfen auf diesem Datensatz zwar 0,0 % der annotierten Pixel
    (Kapitel 5.5), beruhen aber auf der stets gleichen Aufnahmegeometrie. Ein Fersenbefund
    im unteren Bilddrittel würde systematisch unterdrückt – ein **blinder Fleck**, der bei
    abweichender Positionierung unbemerkt bliebe.
12. **Parameterabhängigkeit.** Der voreingestellte Faktor $k = 3{,}0$ erwies sich als zu
    konservativ; das auf einem Tuning-Satz bestimmte $k = 1{,}25$ liefert bessere
    Ergebnisse. Ein einzelner globaler Wert kann jedoch nicht jedem Hauttyp und jeder
    Umgebungstemperatur gerecht werden.
13. **Keine Bitgleichheit der Backends.** Python- und Rust-Backend liefern trotz
    Angleichung nur eine mittlere Masken-IoU von 0,78 (Kapitel 5.6). Anwenderinnen und
    Anwender erhalten je nach verfügbarem Backend leicht abweichende Ergebnisse.
14. **GPU-Pfad unvalidiert.** Der PyTorch/CUDA-Zweig konnte mangels kompatibler Hardware
    nicht getestet werden und ist als **ungeprüft** einzustufen.

### Regulatorische Grenzen
15. **Kein Medizinprodukt.** IGNITE besitzt keine Zertifizierung nach EU-MDR und ist ein
    reiner Forschungsprototyp. Die Software ersetzt keine ärztliche Diagnose und darf
    ausschließlich als Orientierungshilfe unter fachlicher Aufsicht verwendet werden.

---

# 7. Fazit und Ausblick

## 7.1 Gesamtfazit zur Arbeitswelt-Fragestellung
IGNITE zeigt, dass ein vollständig deterministischer, mathematisch nachvollziehbarer
Algorithmus thermisch auffällige Areale auf realen Aufnahmen signifikant besser markiert
als eine einfache Schwellenwert-Baseline ($p = 0{,}0046$), dabei lokal und ohne
Datenübertragung arbeitet und im Millisekundenbereich rechnet.

Der wissenschaftlich ertragreichste Teil dieser Arbeit sind jedoch die **widerlegten
Ausgangsannahmen**: Der Rust-Kern ist nicht schneller als OpenCV, die auf synthetischen
Daten gemessene Sensitivität von 1,00 hält realen Daten nicht stand, und ein erheblicher
Teil der ursprünglich berichteten Werte beruhte auf methodischen Fehlern (Parameterwahl
auf den Testdaten, überschriebene Referenzmasken, eine nicht existierende Literaturquelle).
Diese Fehler wurden aufgedeckt, korrigiert und dokumentiert; sämtliche Kennzahlen in
Kapitel 5 sind über `scripts/run_validation.py` mit festem Seed reproduzierbar.

Für die Fragestellung der Arbeitswelt bedeutet das: Der Ansatz ist als **Orientierungshilfe
tragfähig** – er lenkt den Blick treffsicher auf die richtige Stelle (Precision 0,99) –,
für eine Aussage über die Ausdehnung eines Befundes oder gar für eine diagnostische
Verwendung reichen die erzielten Werte und die Datengrundlage **ausdrücklich nicht aus**.

## 7.2 Zukünftige Erweiterungen für den Praxiseinsatz
* **Erweiterung und Absicherung der Referenzdaten:** Annotation der verbleibenden 12
  Aufnahmen sowie Zweitannotation durch eine unabhängige Person, um Cohens $\kappa$ als
  Maß der Übereinstimmung berichten zu können.
* **Radiometrische Aufnahmen:** Verwendung des FLIR-Rohdatenformats statt der
  JPEG-Exporte, um mit Absoluttemperaturen zu arbeiten und das $\Delta T > 2{,}2\,$K-Kriterium
  [@armstrong1997infrared] tatsächlich prüfen zu können.
* **Verarbeitung auf nativer Sensorauflösung** ($160 \times 120$) statt auf der
  hochskalierten JPEG-Ausgabe – nach den Messungen in Kapitel 5.1 der mit Abstand größte
  Hebel für die Laufzeit.
* **Ersetzen der starren Geometrieregeln** durch eine automatische Fußlokalisierung, um
  den in Kapitel 6.3 beschriebenen blinden Fleck zu beseitigen.
* **Adaptive Schwellenwertwahl** statt eines globalen Faktors $k$.
* Klinische Validierungsstudie mit fachärztlicher Referenz.
* Automatisch generierter PDF-Befundexport für die Patientenakte.

---

# 8. Literaturverzeichnis

[@armstrong2007skin] Armstrong, David G. / Holtz-Neiderer, Karin / et al.: Skin temperature monitoring reduces the risk for diabetic foot ulceration in high-risk patients. In: *The American Journal of Medicine*, 2007, Vol. 120, Nr. 12, S. 1042-1046.  
[@boltzmann1884ableitung] Boltzmann, Ludwig: Ableitung des Stefan'schen Gesetzes, betreffend die Abhängigkeit der Wärmestrahlung von der Temperatur aus der electromagnetischen Lichttheorie. In: *Annalen der Physik*, 1884, Vol. 258, Nr. 6, S. 291-294.  
[@jugendforscht2025leitfaden] Stiftung Jugend forscht e. V.: Leitfaden zum Verfassen der schriftlichen Arbeit im Wettbewerb Jugend forscht. Hamburg, Stand: Juli 2025.  
[@lemire2006streaming] Lemire, Daniel: Streaming maximum-minimum filter using no more than three comparisons per element. In: *Nordic Journal of Computing*, 2006, Vol. 13, Nr. 4, S. 328-339 (arXiv:cs/0610046).  
[@jones1998reappraisal] Jones, Brian F.: A reappraisal of the use of infrared thermal image analysis in medicine. In: *IEEE Transactions on Medical Imaging*, 1998, Vol. 17, Nr. 6, S. 1019-1027. DOI: 10.1109/42.746635.  
[@steketee1973spectral] Steketee, J.: Spectral emissivity of skin and pericardium. In: *Physics in Medicine and Biology*, 1973, Vol. 18, Nr. 5, S. 686-694. DOI: 10.1088/0031-9155/18/5/307.  
[@armstrong1997infrared] Armstrong, David G. / Lavery, Lawrence A. / Liswood, P. J. / Todd, William F. / Tredwell, Jeffrey A.: Infrared dermal thermometry for the high-risk diabetic foot. In: *Physical Therapy*, 1997, Vol. 77, Nr. 2, S. 169-175. DOI: 10.1093/ptj/77.2.169.  
[@otsu1979threshold] Otsu, Nobuyuki: A threshold selection method from gray-level histograms. In: *IEEE Transactions on Systems, Man, and Cybernetics*, 1979, Vol. 9, Nr. 1, S. 62-66.  
[@ring2012healthcare] Ring, E. Francis J. / Ammer, Kurt: Healthcare applications of thermal imaging. In: *Physiological Measurement*, 2012, Vol. 33, Nr. 3, S. R33-R46.  
[@stefan1879beziehung] Stefan, Josef: Über die Beziehung zwischen der Wärmestrahlung und der Temperatur. In: *Sitzungsberichte der mathematisch-naturwissenschaftlichen Classe der Kaiserlichen Akademie der Wissenschaften*, 1879, Vol. 79, S. 391-428.  

---

# 9. Unterstützungsleistungen

Für die Erstellung dieser Arbeit wurden folgende Hilfeleistungen in Anspruch genommen:
* **Betreuende Lehrkraft / Schule:** Hilfestellung bei der Formulierung und Durchsicht auf Einhaltung der Formalien des Jugend forscht Leitfadens.
* **Verwendete Open-Source-Bibliotheken:** Nutzung freier Programmierwerkzeuge (Rust, PyO3, Rayon, ndarray, PyTorch, OpenCV, CustomTkinter) gemäß ihren Open-Source-Lizenzen (MIT / Apache 2.0).
* **Eigenanteil:** Die Konzeption der Analyse, die Ausarbeitung der Algorithmen, die komplette Programmierung in Rust und Python, das Interface-Design sowie die Durchführung aller Tests wurden zu 100 % eigenständig von mir erbracht.
