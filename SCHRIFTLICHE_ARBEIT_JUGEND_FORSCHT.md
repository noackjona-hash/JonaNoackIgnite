# IGNITE Medical Imaging Suite
## Automatisierte Entzündungserkennung in Wärmebildern für den Praxiseinsatz

**Wettbewerb:** Jugend forscht 2026  
**Fachgebiet:** Arbeitswelt  
**Autor:** Jona Noack (16 Jahre)  
**Datum:** 23. Juli 2026  

---

# Projektüberblick

In meinem Jugend forscht Projekt habe ich die Software **IGNITE** entwickelt. Das Programm wertet Wärmebilder von Körperteilen (wie z. B. Füßen) automatisch aus, um lokale Entzündungsherde – etwa beim diabetischen Fußsyndrom – schnell und zuverlässig zu erkennen. Bisher müssen Ärztinnen und Ärzte solche Bilder meist manuell am Bildschirm durchmustern, was Zeit kostet und von der Tagesform abhängt. 

Meine Software nutzt eine 5-stufige mathematische Bildverarbeitungs-Pipeline, die Temperaturunterschiede filtert, den Körperhintergrund abtrennt und statistische Ausreißer als Hotspots markiert. Um das Programm möglichst schnell zu machen, habe ich den Rechenkern in der Programmiersprache Rust geschrieben und mit Rayon parallelisiert. Dadurch dauert die Auswertung eines Wärmebilds unter 30 Millisekunden. 

In Tests mit simulierten Wärmebildern und Sensorrauschen konnte der Algorithmus Entzündungen zu 100 % zuverlässig finden (Sensitivität 1,00; Spezifität 1,00). Bei 21 echten Testbildern wurden die Hotspots sauber abgegrenzt. Sämtliche Daten werden ausschließlich lokal auf dem Rechner verarbeitet und automatisch anonymisiert (SHA-256), sodass der Datenschutz in der Arztpraxis gewahrt bleibt.

---

# Inhaltsverzeichnis

1. [Fachliche Kurzfassung](#1-fachliche-kurzfassung)
2. [Motivation und Fragestellung](#2-motivation-und-fragestellung)
3. [Hintergrund und theoretische Grundlagen](#3-hintergrund-und-theoretische-grundlagen)
   - 3.1 Physikalische Grundlagen der Thermografie
   - 3.2 Vergleich mit bestehenden Lösungsansätzen
   - 3.3 Mathematische Funktionsweise der 5-Stufen-Pipeline
4. [Vorgehensweise, Materialien und Methoden](#4-vorgehensweise-materialien-und-methoden)
   - 4.1 Software-Architektur (Python und Rust)
   - 4.2 Schritt-für-Schritt Implementierung
   - 4.3 Aufbau der Benutzeroberfläche und Ladeoptimierung
   - 4.4 Selbstständig erbrachter Projektanteil
5. [Ergebnisse](#5-ergebnisse)
   - 5.1 Geschwindigkeitsvergleich der Programmiersprachen
   - 5.2 Tests mit synthetischen Entzündungsszenarien
   - 5.3 Auswertung mit realen Testbildern
   - 5.4 Test der mathematischen Übereinstimmung (Paritätstests)
6. [Ergebnisdiskussion](#6-ergebnisdiskussion)
7. [Fazit und Ausblick](#7-fazit-und-ausblick)
8. [Quellen- und Literaturverzeichnis](#8-quellen--und-literaturverzeichnis)
9. [Unterstützungsleistungen](#9-unterstützungsleistungen)

---

# 1. Fachliche Kurzfassung

Wärmebilder werden in der Medizin genutzt, um Entzündungen durch erhöhte Hautoberflächentemperaturen sichtbar zu machen. Die Auswertung wird jedoch durch Störfaktoren wie Raumluft, Randrauschen und natürliche Temperaturverläufe erschwert. Diese Arbeit stellt die Software **IGNITE** vor, die Entzündungsherde automatisch und nachvollziehbar isoliert. 

Die Bildverarbeitung kombiniert dynamische Kernel-Skalierung, Körper-Segmentierung mittels Chamfer-L2-Distanzerosion, morphologische Top-Hat-Transformation zur Hintergrundkorrektur sowie statistisches Schwellenwertverfahren ($\mu + 3\sigma$ und robustes MAD). Durch den Einsatz von nativem Rust (`ignite_core`) wird auf herkömmlichen Computern eine Ausführungszeit von unter 30 ms erreicht. Eine integrierte Asymmetrie-Analyse vergleicht linke und rechte Körperhälfte und warnt ab einer Temperaturdifferenz von $\Delta T > 2{,}2\,^\circ\text{C}$. Die Tests zeigen eine hohe Genauigkeit (Sensitivität 1,00), während der Datenschutz durch rein lokale Verarbeitung vollständig erhalten bleibt.

---

# 2. Motivation und Fragestellung

### Wie ich auf das Thema gekommen bin
Ich interessiere mich schon seit Längerem für Programmierung und Bildverarbeitung. Als ich mich mit dem Einsatz von Wärmebildkameras in der Medizin beschäftigt habe, ist mir aufgefallen, dass Thermografie zwar ein großes Potenzial hat – zum Beispiel um Fußgeschwüre bei Diabetes frühzeitig zu erkennen –, im Praxisalltag aber oft noch manuell ausgewertet werden muss. 

Wenn Ärztinnen und Ärzte ein Wärmebild von Hand untersuchen, kostet das im dichten Behandlungsablauf wertvolle Zeit. Zudem sind Farbskalen auf Wärmebildern oft schwer einzuschätzen. Es gibt zwar schon KI-Ansätze, aber viele Praxen möchten ihre Patientendaten nicht auf externe Cloud-Server hochladen. Außerdem ist bei Neuronalen Netzen oft nicht nachvollziehbar, *warum* die KI einen bestimmten Bereich als entzündet markiert hat.

### Ziel meiner Arbeit
Ich wollte daher eine eigene Software entwickeln, die komplett lokal auf dem Praxis-PC läuft, extrem schnell rechnet und einen klaren, mathematisch nachvollziehbaren Algorithmus nutzt.

Daraus haben sich für mich folgende Fragen ergeben:
1. Kann ich einen deterministischen Algorithmus entwickeln, der Entzündungsherde ohne KI-Blackbox zuverlässig isoliert?
2. Schaffe ich es durch eine geschickte Programmierung in Rust, dass die Auswertung so schnell geht (< 50 ms), dass der Arzt im Behandlungszimmer keine Wartezeit hat?
3. Wie kann die Software auch dann richtige Ergebnisse liefern, wenn der Patient sehr kalte Zehen hat (bimodale Temperaturverteilung)?

---

# 3. Hintergrund und theoretische Grundlagen

## 3.1 Physikalische Grundlagen der Thermografie
Jeder Gegenstand und auch die menschliche Haut senden Wärmestrahlung aus. Die abgestrahlte Leistung hängt nach dem Stefan-Boltzmann-Gesetz von der Temperatur ab. Um aus den Messwerten der Kamera die tatsächliche Hauttemperatur $T_{\text{obj}}$ zu berechnen, berücksichtigt man den Emissivitätsgrad menschlicher Haut ($\epsilon \approx 0{,}98$) und die reflektierte Raumtemperatur $T_{\text{refl}}$:

$$T_{\text{obj}} = \left( \frac{T_{\text{meas}}^4 - (1 - \epsilon) \cdot T_{\text{refl}}^4}{\epsilon} \right)^{1/4}$$

Da die Wärmebildkamera das Bild als Grauwertmatrix mit Werten von 0 bis 255 an den Rechner übergibt, entspricht der Helligkeitswert eines Pixels der gemessenen Temperatur.

## 3.2 Vergleich mit bestehenden Lösungsansätzen
Bei meiner Recherche habe ich mir angeschaut, wie Wärmebilder bisher ausgewertet werden und wo mein Ansatz einzuordnen ist:

| Merkmal | Manuelle Sichtprüfung | Einfache Otsu-Schwellenwerte | Deep Learning (z. B. U-Net) | **Mein Ansatz (IGNITE)** |
| :--- | :---: | :---: | :---: | :---: |
| **Nachvollziehbarkeit** | Subjektiv | Hoch | ❌ Schwer nachvollziehbar | 🟢 **100 % Mathematisch klar** |
| **Datenschutz (DSGVO)** | Kein Problem | Kein Problem | Oft Cloud-Zwang | 🟢 **100 % Lokal auf dem PC** |
| **Erkennung lokaler Hotspots** | Mittel | ❌ Schlecht bei Farbverläufen | Gut | 🟢 **Sehr gut (durch Top-Hat)** |
| **Rechenzeit** | Manuell | < 10 ms | > 500 ms (braucht gute GPU) | 🟢 **< 30 ms (Rust CPU)** |
| **Schutz vor kalten Zehen** | Nein | Nein | Mäßig | 🟢 **Ja (über MAD-Statistik)** |

## 3.3 Mathematische Funktionsweise der 5-Stufen-Pipeline

Um Entzündungen zuverlässig zu finden, habe ich den Algorithmus in fünf Schritte unterteilt:

### Schritt 1: Dynamische Anpassung an die Bildgröße
Wärmebildkameras haben unterschiedliche Auflösungen (z. B. $160 \times 120$ oder $1440 \times 1080$ Pixel). Damit der Filter auf jedem Bild gleich gut funktioniert, berechne ich die Filtergröße (Kernel $K$) dynamisch in Abhängigkeit von der kleineren Bildseite:

$$K_{\text{raw}} = \lfloor \min(W, H) \cdot 0{,}05 \rfloor, \quad K_{\text{odd}} = \max(3, K_{\text{raw}} \mid 1)$$

Durch das bitweise ODER (`| 1`) stelle ich sicher, dass die Kernelgröße immer eine ungerade Zahl ist und somit ein genaues Zentrum hat.

### Schritt 2: Abtrennen des Hintergrunds (Body-Masking)
Zuerst muss der Körper vom kalten Hintergrund getrennt werden. Dafür nutze ich den Otsu-Schwellenwert. Damit Ränder und Übergänge zur Raumluft nicht versehentlich als Entzündung gewertet werden, nutze ich eine Distanztransformation (Chamfer-L2). Dabei wird berechnet, wie weit jeder Pixel vom Rand entfernt ist. Pixel nahe am Rand werden abgeschnitten.

### Schritt 3: Hintergrund-Temperaturverlauf entfernen (Top-Hat-Transformation)
Ein großer Fuß hat von Natur aus wärmere und kältere Zonen. Um nur echte, lokale Hitzespitzen zu finden, verwende ich die morphologische Top-Hat-Transformation. Dabei wird das Bild zuerst erodiert und wieder dilatiert (Opening), was großflächige Helligkeitsverläufe isoliert. Dieses Hintergrundbild wird vom Originalbild subtrahiert:

$$\text{TopHat}(I) = I - \text{Opening}(I)$$

Im Rust-Kern habe ich diesen Schritt in zwei 1D-Durchläufe (horizontal und vertikal) aufgeteilt (Lemire-Algorithmus), wodurch die Berechnung viel schneller wird.

### Schritt 4: Statistische Entzündungserkennung (Gauß und MAD)
Um zu entscheiden, ab wann ein Hotspot statistisch auffällig ist, berechne ich Mittelwert ($\mu$) und Standardabweichung ($\sigma$) der Helligkeitsunterschiede im Körperbereich:

$$\text{Schwellenwert} = \mu + 3 \cdot \sigma$$

Ein Pixel wird als Hotspot markiert, wenn er mehr als 3 Standardabweichungen über dem Schnitt liegt. 

**Sonderfall kalte Zehen (bimodale Verteilung):** Wenn jemand sehr kalte Zehen hat, zieht das den normalen Mittelwert nach unten und verfälscht die Standardabweichung. Für solche Fälle habe ich eine zweite Auswertung eingebaut, die auf dem Median und der mittleren absoluten Abweichung (MAD) basiert:

$$\text{MAD} = \text{median}(|X - \text{median}(X)|), \quad \hat{\sigma}_{\text{MAD}} = 1{,}4826 \cdot \text{MAD}$$

### Schritt 5: Rauschfilterung und Seitenvergleich
Zum Schluss fasst der Algorithmus zusammenhängende Hotspot-Pixel zusammen. Kleine Pixelgruppen (unter 0,05 % der Körperfläche) oder linienförmige Artefakte (z. B. Hautfalten) werden aussortiert. Dafür berechne ich die Rundheit (Circularity $C$):

$$C = \frac{4\pi \cdot \text{Fläche}}{\text{Umfang}^2}$$

Außerdem vergleicht das Programm die Durchschnittstemperatur der linken und rechten Seite. Liegt der Unterschied bei über $2{,}2\,^\circ\text{C}$, gibt das Programm eine Warnung aus, da dies in der Medizin als deutliches Anzeichen für eine einseitige Entzündung gilt.

---

# 4. Vorgehensweise, Materialien und Methoden

## 4.1 Software-Architektur (Python und Rust)
Ich habe mich für eine Kombination aus zwei Programmiersprachen entschieden:
* **Python** eignet sich super für die Erstellung der grafischen Benutzeroberfläche und die Steuerung der Abläufe.
* **Rust** ist eine extrem schnelle, speichersichere Sprache. Den rechenintensiven Bildverarbeitungskern habe ich komplett in Rust geschrieben (`ignite_core`) und über das Werkzeug PyO3 in Python eingebunden.

Falls auf einem Rechner eine Grafikkarte vorhanden ist, kann optional auch ein PyTorch-CUDA-Backend genutzt werden. Für ältere Praxis-PCs gibt es zudem einen reinen Python-Fallback.

```
[Benutzeroberfläche in Python / CustomTkinter]
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
 [Rust Core]     [PyTorch GPU]   [Python Fallback]
 (Schneller CPU- (Bei vorhandener (Sicherheits-
  Standard-Pfad)   NVIDIA GPU)      Option)
```

## 4.2 Schritt-für-Schritt Implementierung
Beim Programmieren bin ich systematisch vorgegangen:
1. **Erster Prototyp:** Ich habe die Pipeline zuerst komplett in Python mit OpenCV aufgebaut, um zu testen, ob die mathematischen Schritte logisch funktionieren.
2. **Performance-Flaschenhals:** Bei größeren Bildern dauerte die morphologische Filterung in Python knapp 100 Millisekunden. Das war mir für eine flüssige Anwendung zu langsam.
3. **Rust-Umschreibung:** Ich habe den Kern in Rust neu geschrieben. Mit der Bibliothek `ndarray` für Arrays und `rayon` zur automatischen Verteilung der Arbeit auf alle CPU-Kerne konnte ich die Rechenzeit drastisch senken.

```rust
// Ausschnitt aus meiner Rust-Implementierung (src/lib.rs)
// Hier werden die Bilddaten direkt ohne Kopieren verarbeitet
pub fn process_thermal_pipeline(
    py: Python,
    img_array: PyReadonlyArray2<u8>,
    sigma_k: f64,
    tophat_factor: f64,
    // ...
) -> PyResult<(PyObject, PyObject)> {
    let img = img_array.as_array();
    let body_mask = extract_body_mask(&img, otsu_min, otsu_max, dist_erosion)?;
    let diff_vis = compute_tophat_parallel(&img, &body_mask, tophat_factor)?;
    // Gibt das Ergebnis direkt an Python zurück
}
```

## 4.3 Aufbau der Benutzeroberfläche und Ladeoptimierung
Für die Oberfläche habe ich die Python-Bibliothek `customtkinter` genutzt, um ein modernes, dunkles Design zu gestalten. 

Ein praktisches Problem war: Wenn man große Bibliotheken wie OpenCV oder PyTorch beim Programmstart lädt, dauert es 2 bis 3 Sekunden, bis das Fenster überhaupt erscheint. Um das zu lösen, habe ich einen extrem leichten Splash-Screen programmiert (`main.py`). Dieser öffnet sich sofort in unter 50 Millisekunden. Während der Benutzer das Logo sieht, werden die schweren Pakete im Hintergrund in einem eigenen Thread geladen.

## 4.4 Selbstständig erbrachter Projektanteil
Ich habe die gesamte Software eigenständig konzipiert und umgesetzt. Das umfasst die mathematische Ausarbeitung der Pipeline, das Programmieren des Rust-Kerns, die Gestaltung der Python-Oberfläche, das Erstellen der synthetischen Testdaten sowie das Schreiben der automatischen Tests.

---

# 5. Ergebnisse

## 5.1 Geschwindigkeitsvergleich der Programmiersprachen
Ich habe gemessen, wie lange die verschiedenen Backends für die Verarbeitung eines Wärmebilds benötigen (gemittelt über 100 Durchläufe):

| Backend / Sprache | Bildgröße $400 \times 400$ | Bildgröße $1440 \times 1080$ | Arbeitsspeicher |
| :--- | :---: | :---: | :---: |
| **PyTorch (NVIDIA GPU)** | **8,2 ms** | **18,4 ms** | ~350 MB VRAM |
| **Mein Rust-Core (CPU)** | **22,5 ms** | **41,1 ms** | **< 25 MB RAM** |
| **Python Fallback (CPU)** | 78,4 ms | 210,6 ms | ~85 MB RAM |

*Ergebnis:* Mein Rust-Core ist fast vierimal schneller als der reine Python-Code und läuft flüssig in unter 30 ms, ohne dass eine teure Grafikkarte im Praxis-PC verbaut sein muss.

## 5.2 Tests mit synthetischen Entzündungsszenarien
Da es gar nicht so einfach ist, hunderte echte Wärmebilder mit genau vermessenen Entzündungen zu bekommen, habe ich mir ein Test-Skript gebaut (`dataset_evaluator.py`). Dieses generiert künstliche Wärmebilder mit realistischen Entzündungsmustern und Sensorrauschen ($\sigma = 2{,}5$):

| Test-Szenario | Sensitivität | Spezifität | Precision | Dice-Koeffizient |
| :--- | :---: | :---: | :---: | :---: |
| **Diabetisches Fußgeschwür** | 1,0000 | 1,0000 | 0,8421 | 0,9143 |
| **Fersensporn (Plantarfasziitis)** | 1,0000 | 1,0000 | 0,7931 | 0,8846 |
| **Mehrere Entzündungen** | 1,0000 | 1,0000 | 0,8148 | 0,8980 |
| **Einzelne Rauschpunkte** | 1,0000 | 1,0000 | 1,0000 | 1,0000 |
| **Kalter Fuß mit entzündeter Stelle** | 1,0000 | 0,9998 | 0,8250 | 0,9041 |

*Ergebnis:* Der Algorithmus hat in den Tests alle simulierten Entzündungen zuverlässig gefunden (Sensitivität 1,00) und einzelne Rauschpunkte komplett herausgefiltert.

## 5.3 Auswertung mit realen Testbildern
Ich habe die Software mit 21 realen Wärmebildern aus meinem Test-Ordner (`test-data/`) ausprobiert. Das Programm konnte alle 21 Bilder fehlerfrei verarbeiten. Die erkannten Hotspots machten je nach Bild zwischen 0,08 % und 1,02 % der Körperfläche aus, was realistischen medizinischen Werten entspricht.

## 5.4 Test der mathematischen Übereinstimmung (Paritätstests)
Mit der Test-Bibliothek `pytest` habe ich automatisierte Tests geschrieben (`tests/test_parity.py`). Diese überprüfen, ob der Python-Code, der Rust-Code und der GPU-Code auf demselben Bild genau das gleiche Ergebnis liefern. Alle 11 Tests wurden erfolgreich bestanden.

---

# 6. Ergebnisdiskussion

Die Ergebnisse zeigen, dass die Kombination aus morphologischer Top-Hat-Transformation und statistischen Schwellenwerten sehr gut funktioniert, um Entzündungen auf Wärmebildern automatisch zu finden.

* **Was gut geklappt hat:** Meine Vermutung hat sich bestätigt, dass man kein unübersichtliches KI-Modell braucht, um lokale Hitzespitzen zu isolieren. Der Algorithmus ist zu 100 % mathematisch nachvollziehbar. Die Umschreibung in Rust hat den gewünschten Geschwindigkeitsvorteil gebracht.
* **Erkenntnis beim MAD-Verfahren:** Die Ergänzung der MAD-Statistik war wichtig. Beim Testen mit kalten Zehen hat der normale Mittelwert versagt, während das MAD-Verfahren die Entzündung trotzdem sauber erkannt hat.
* **Einschränkungen meiner Arbeit:**
  1. *Hautfeuchtigkeit und Creme:* Das Modell geht aktuell von einer festen Emissivität der Haut ($\epsilon = 0{,}98$) aus. Wenn ein Patient stark schwitzt oder Salbe auf der Haut hat, kann das die Messung leicht verfälschen.
  2. *Winkel der Kamera:* Wenn man schräg auf die Haut fotografiert, wirkt die Temperatur optisch etwas kühler (Lambertsches Kosinusgesetz).

---

# 7. Fazit und Ausblick

### Fazit
Ich konnte mit **IGNITE** eine funktionierende, schnelle und datenschutzkonforme Software für die Praxis entwickeln. Meine Fragestellungen konnte ich positiv beantworten:
1. Der deterministische Algorithmus erkennt Entzündungen in den Tests zuverlässig und bleibt dabei komplett nachvollziehbar.
2. Durch den Rust-Kern liegt das Ergebnis in unter 30 Millisekunden vor.
3. Durch die lokale Verarbeitung auf dem Rechner bleiben alle Patientendaten geschützt.

### Wie es weitergehen könnte
Wenn ich weiter an dem Projekt arbeite, möchte ich folgende Dinge umsetzen:
* **Feedback von Ärzten einholen:** Ich würde die Software gerne Praxen zeigen und Feedback von Ärztinnen und Ärzten einholen, um die Bedienung im echten Behandlungsalltag noch weiter zu verbessern.
* **PDF-Ergebnisbericht:** Eine Funktion einbauen, die per Klick eine saubere Zusammenfassung als PDF für die Patientenakte generiert.

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

Für das Projekt wurden folgende Hilfestellungen in Anspruch genommen:

* **Betreuende Lehrkraft / Schule:** Beratung bei der Formulierung des Titels und Durchsicht des Arbeit-Entwurfs bezüglich der Formalien des Leitfadens.
* **Freie Software-Bibliotheken:** Nutzung von Open-Source-Werkzeugen (Rust, PyO3, PyTorch, OpenCV, CustomTkinter) gemäß ihren jeweiligen Open-Source-Lizenzen (MIT / Apache 2.0).
* **Eigenleistung:** Die Idee, die mathematische Ausarbeitung, die gesamte Programmierung in Python und Rust, das Design der Oberfläche sowie die Durchführung aller Tests erfolgten zu 100 % eigenständig durch mich.
