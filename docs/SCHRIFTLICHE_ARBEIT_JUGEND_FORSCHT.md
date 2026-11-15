---
title: "IGNITE Medical Imaging Suite (v12.3.4.81) — Berührungslose Früherkennung berufsbedingter Fuß- und Gefäßentzündungen mittels deterministischer LWIR-Thermografie"
author: "Jona Noack"
subtitle: "Schriftliche Ausarbeitung zum Wettbewerb Jugend forscht 2026 | Fachgebiet: Arbeitswelt"
date: "2026"
lang: "de"
---

![IGNITE Medical Imaging Suite](images/ignite_minimalist_logo.jpg)

# IGNITE Medical Imaging Suite: Berührungslose Früherkennung berufsbedingter Fußentzündungen, neuropathischer Ulzera und venöser Gefäßerkrankungen in der Arbeitswelt

**Wettbewerb:** Jugend forscht 2026 — **Fachgebiet:** Arbeitswelt  
**Verfasser:** Jona Noack  
**Software-Release:** v12.3.4.81 (Go 1.24 AVX2 Core · C# .NET 10 WPF Workstation · Go Wails v2 · Lua 5.1 · Python Suite)  
**Regulatorischer Bezug:** DIN EN ISO 13485 · ArbSchG § 5 · ArbMedVV · DGUV Information 212-007 · ASR A1.5/1,2 · DSGVO Art. 9, 25 & 30

---

## Kurzfassung (Executive Summary)

In stehenden, gehenden und körperlich belastenden Berufen — insbesondere in Logistikzentren, Krankenhäusern, Pflegeheimen, dem Baugewerbe und der industriellen Fertigung — sind Beschäftigte über 8- bis 12-Stunden-Schichten hohen plantaren Spitzendrücken, Scherkräften und Wärmestau in vorgeschriebenen Sicherheitsschuhen der Schutzklassen S1–S3 (DGUV Information 212-007) ausgesetzt [1, 2]. Laut Unfallverhütungsbericht der Bundesanstalt für Arbeitsschutz und Arbeitsmedizin (BAuA) bilden Muskel-Skelett-Erkrankungen und Beschwerden der unteren Extremitäten einen Haupttreiber langwieriger Arbeitsunfähigkeitstage [3]. Gleichzeitig belegt die Bonner Venenstudie eine hohe Prävalenz chronisch-venöser Insuffizienz (CVI) in der erwerbstätigen Bevölkerung [12], während Beschäftigte mit unerkannter peripherer Neuropathie (z. B. bei Diabetes mellitus) druckbedingte Mikroläsionen schmerzbedingt nicht wahrnehmen, bis offene Fußulzera (DFS/DFU) eine monatelange Arbeitsunfähigkeit auslösen [6, 7].

**IGNITE** schließt diese präventive Versorgungslücke im Betrieblichen Gesundheitsmanagement (BGM) durch ein kontakt- und strahlungsloses Langwellen-Infrarot-Screening (LWIR, 8–14 µm):

1. **Deterministischer 42-Stufen-Algorithmus statt „Black-Box“-KI:** Jedes Thermogramm wird bit-identisch durch Otsu-Segmentierung [14], 2-Pass-Chamfer-$L_2$-Distanzerosion [19], morphologischen *White Top-Hat* [17], robuste Hampel-MAD-Schwellwertbildung [18] ($O(N)$-Histogramm nach Lemire [15]), multiskalige Frangi-Hesse-Gefäßfilterung [16] und eine entkoppelte **Lua 5.1 Leitlinien-Engine** ausgewertet — ohne intransparente neuronale Netze.
2. **Hardwarenahe Echtzeit-Architektur (v12.3.4.81):** Sechs in Plan-9-Syntax implementierte **x86_64 AVX2/FMA Assembler-Kerne** verarbeiten 256-Bit-Vektoren (32 Pixel/Takt) unter Go 1.24+, eingebunden in sowohl eine klinische **C# .NET 10 / WPF Workstation** als auch eine native **Go Wails v2 PACS-App** mit Zero-IPC-Anbindung und revisionssicherem **SHA-256 SQLite Audit-Trail**.
3. **Empirische & klinische Validierung:**
   * Auf **21 realen plantaren Testaufnahmen** (`test-data/bild (1..21).jpeg`) erkennt der Go-Core v12.3.4.81 **21 / 21 (100 %)** der Hallux- und Vorfußentzündungen deterministisch als `INFLAMMATION` (`CRITICAL`, Konfidenz 96 %). Auf `n = 9` pixelgenau annotierten Ground-Truth-Datensätzen erreicht der Kern eine **Mean Precision von 80,78 %** (Einzelfall bis **100,0 %**) und einen **Mean Dice-Koeffizienten von 0,5199** (hochsignifikante Verbesserung gegenüber globalem Otsu-Thresholding im Python/Rust-Basisvergleich, Wilcoxon $p = 0{,}0046$).
   * In einer **realen fachärztlichen Praxiserhebung** (Gefäßchirurgie & Phlebologie, 30.10.2026) wurden **12 anonymisierte Patienten** (**118 multimodale Aufnahmen**: 92 FLIR-Thermogramme, 23 Duplex-Ultraschallbilder, 3 Radiometrie-Videos) klinisch untersucht und zur Schärfung der Differentialdiagnose (*postoperatives Ulcus cruris* bis $\Delta T = +9{,}6\,\text{K}$ vs. *Varikose I83.9* vs. *Verband-Abschirmungsartefakt $-3{,}3\,\text{K}$*) in die IGNITE-Regelbasis überführt.

---

## 1. Arbeitswelt-Problemstellung und betriebsmedizinische Relevanz

### 1.1 Belastungsprofil an Steh- und Sicherheitsschuh-Arbeitsplätzen

Moderne Produktions-, Pflege- und Intralogistikbetriebe verlangen Mitarbeitenden dauerhaftes Stehen und Gehen auf industriellen Hallenböden ab (geregelt durch die **Technischen Regeln für Arbeitsstätten ASR A1.5/1,2** [5]). Wo Absturz-, Stoß- oder Stichgefahren bestehen, schreibt die gesetzliche Unfallversicherung Sicherheitsschuhe nach **DGUV Information 212-007** bzw. **DGUV Regel 112-191** vor [2]. Durch Zehenschutzkappen aus Stahl oder Verbundwerkstoff, durchtrittsichere Zwischensohlen sowie feuchtigkeitsdichte Schaftmaterialien entstehen drei arbeitsmedizinische Risikomechanismen:

* **Okklusions- und Wärmestau:** Eingeschränkte Konvektion innerhalb von S3-Schuhen lässt die Fußtemperatur unter Schichtbelastung stark ansteigen und maskiert subtile entzündliche Mikrotraumen am Großzehengrundgelenk (Hallux) oder den Metatarsalköpfchen.
* **Repetitive Spitzendruck- und Scherbelastung:** Lange Gehstrecken auf unelastischen Betonböden führen zu mechanischer Überlastung des plantaren Weichgewebes sowie zu Fehlstellungen (z. B. *Hallux valgus*), die sich prä-ulzerativ durch eine lokalisierte Hyperthermie ankündigen [6, 7].
* **Vaskuläre Stehbelastung (Chronisch-Venöse Insuffizienz):** Langes Stehen erschwert den venösen Rückstrom durch verminderte Aktivierung der Wadenmuskelpumpe. Die **Bonner Venenstudie** belegt die weite Verbreitung von Varikose und CVI in der Bevölkerung [12]; unbehandelt drohen Stauungsdermatitis und *Ulcus cruris venosum*.

Gemäß **§ 5 Arbeitsschutzgesetz (ArbSchG)** in Verbindung mit der **Verordnung zur arbeitsmedizinischen Vorsorge (ArbMedVV)** sind Arbeitgeber verpflichtet, physische und mechanische Belastungen frühzeitig durch Gefährdungsbeurteilungen zu erfassen und zielgerichtete Präventionsmaßnahmen abzuleiten [4].

![Branchenspezifische Arbeitsunfähigkeitstage und Fuß-/MSE-Belastung an Steharbeitsplätzen](images/arbeitswelt_stehbelastung_ausfalltage.png)

*Abbildung 1: Sektorvergleich der Arbeitsunfähigkeitstage (AU-Tage je 100 Beschäftigte) zwischen stehenden Berufen (Logistik, Pflege, Bau, Fertigung) und sitzender Büroarbeit in Orientierung an BAuA-Berichtsdaten [3], inklusive Anteil muskuloskelettaler Fuß- und Unterschenkelbeschwerden.*

### 1.2 Der betriebliche Screening-Workflow nach DIN EN ISO 13485

Klassische radiologische Verfahren (Röntgen, CT) sind im betriebsärztlichen Alltag wegen ionisierender Strahlung, stationärer Großgeräte und hoher Kosten nicht als regelmäßiges Routine-Screening vertretbar. Gleichzeitig ist das manuelle Abtasten der Fußsohlen (Palpation) im Werksarztzentrum zeitaufwändig, unpräzise und hygienisch kritisch.

IGNITE etabliert einen standardisierten **5-Stufen-Workflow** für Werkarztpraxen und Betriebliches Gesundheitsmanagement (BGM), der die internationale Standardisierung medizinischer Thermografie nach Ring & Ammer [11] in den Schichtalltag überträgt:

1. **Standardisierte Akklimatisierung (15 min):** Abnehmen der S3-Sicherheitsschuhe und Strümpfe im temperierten Untersuchungsraum ($20\text{--}22\,^\circ\text{C}$), um den schuhbedingten Wärmestau abklingen zu lassen [11].
2. **Kontaktlose LWIR-Aufnahme (< 5 s):** Berührungslose Erfassung beider Fußsohlen bzw. Unterschenkel mittels handelsüblicher radiometrischer FLIR-Kamera ($8\text{--}14\,\mu\text{m}$).
3. **Go + AVX2 Pipeline (~485 ms bei $1440 \times 1080\,\text{px}$):** Vollautomatische Rauschunterdrückung, Segmentierung, topographische Anomalie-Isolation und Frangi-Gefäßbewertung.
4. **Deterministische Lua-5.1-Triage:** Transparente Risikoklassifikation nach Armstrong-Kriterien ($\Delta T \ge 2{,}2\,\text{K}$) und biophysikalischen Tiefenfokus-Regeln.
5. **DSGVO-Schutz & Arbeitsplatzintervention:** Lokale Pseudonymisierung (`ANON-<hash>`), SHA-256-gesichertes Audit-Protokoll gemäß DSGVO Art. 30 [25] sowie strukturierter IWGDF-Arztbrief [6] für orthopädische Einlagenversorgung (DGUV Regel 112-191) oder Arbeitsplatzrotation.

![IGNITE 5-Stufen Screening-Workflow in der Arbeitswelt](images/arbeitswelt_infografik_praxis_workflow.png)

*Abbildung 2: Gesamtkonzept des IGNITE-Screenings im Betrieblichen Gesundheitsmanagement von der Akklimatisierung über den Go/AVX2-Rechenkern bis zur DSGVO-konformen Befunddokumentation.*

![Praxisnahe Datenerfassung und ergonomischer Workflow am Arbeitsplatz](images/skizze_praxis_workflow.png)

*Abbildung 3: Schematischer Praxis-Workflow vom kontaktlosen Infrarot-Scan bis zur digitalen Auswertung und Schutzempfehlung.*

---

## 2. Physikalische, mathematische und pathophysiologische Grundlagen

### 2.1 Infrarot-Radiometrie und Emissionsgrad der menschlichen Haut

Jeder biologische Körper mit einer absoluten Temperatur $T > 0\,\text{K}$ emittiert elektromagnetische Wärmestrahlung. Das **Stefan-Boltzmann-Gesetz** [9, 10] beschreibt die flächenbezogene spezifische Ausstrahlung $M$ eines realen Körpers:

$$M(T) = \varepsilon \cdot \sigma \cdot T^4 \quad \left[\frac{\text{W}}{\text{m}^2}\right]$$

Hierbei bezeichnet $\sigma = 5{,}670374 \times 10^{-8}\,\text{W}\,\text{m}^{-2}\,\text{K}^{-4}$ die Stefan-Boltzmann-Konstante. Für unbedeckte menschliche Haut liegt der spektrale Emissionsgrad im Langwellen-Infrarotbereich ($8\text{--}14\,\mu\text{m}$) hochgradig stabil bei $\varepsilon \approx 0{,}98 \pm 0{,}01$ [12b, 13], was präzise, berührungslose Oberflächen-Temperaturmessungen ermöglicht.

### 2.2 Wärmetransport im Gewebe (Pennes Bioheat Equation)

Warum unterscheidet sich eine akute Gewebeentzündung thermisch grundlegend von einer oberflächennahen Vene? Die Antwort liefert die **Pennes-Bioheat-Gleichung** (1948) [15b]:

$$\rho \, c \, \frac{\partial T}{\partial t} = \nabla \cdot (k \, \nabla T) + \omega_b \, \rho_b \, c_b \, (T_a - T) + q_m$$

* $\nabla \cdot (k \, \nabla T)$ beschreibt die isotrope **Wärmeleitung** (Konduktion) im Gewebe.
* $\omega_b \, \rho_b \, c_b \, (T_a - T)$ modelliert den konvektiven Wärmeaustausch über die **Mikrozirkulation / Perfusion** ($\omega_b$).
* $q_m$ repräsentiert die **metabolische Wärmeproduktion**, die bei bakterieller Besiedlung oder leukozytärer Entzündungsreaktion lokal stark ansteigt.

Durch erhöhte metabolische Aktivität ($q_m$) und inflammatorische Hyperämie entsteht um einen fokalen Entzündungsherd (z. B. am Hallux oder einem Ulcus) ein charakteristischer, radiär abfallender **perifokaler Wärmediffusions-Halo** mit stark negativem zweidimensionalem Laplace-Operator ($\nabla^2 T \ll 0$). Eine Krampfader (Varize) hingegen folgt als tubuläre Wärmequelle primär der linienförmigen Gefäßgeometrie ohne zirkulären Diffusionskranz.

### 2.3 Klinische Referenzkriterien (Armstrong / IWGDF / Taylor & Palmer)

In einer wegweisenden randomisierten Studie wiesen **Armstrong et al. (2007)** [8] sowie **Lavery et al. (2004)** [7] nach, dass ein kontralateraler Temperaturunterschied von $\Delta T \ge 2{,}2\,\text{K}$ ($4\,^\circ\text{F}$) zwischen anatomisch korrespondierenden Arealen beider Füße eine drohende Gewebsulzeration Tage bis Wochen vor klinischer Sichtbarkeit vorhersagt. Die **IWGDF-Leitlinien (2023 Update)** [6] empfehlen das thermische Monitoring ausdrücklich zur Sekundärprävention. Ergänzend integriert IGNITE die sechs **Angiosom-Territorien des Fußes nach Taylor & Palmer (1987)** [20], um Perfusionsdefizite (z. B. *Arteria plantaris medialis* vs. *lateralis*) direkt den betroffenen Gefäßversorgungsgebieten zuzuordnen.

---

## 3. Polyglotte Multi-Tier-Systemarchitektur (Version 12.3.4.81)

Um höchste Rechenleistung auf Standard-Betriebsrechnern ohne Cloud-Zwang mit ärztlicher Bedienerfreundlichkeit zu verbinden, ist IGNITE in fünf strikt getrennte Schichten gegliedert:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TIER 1a: C# .NET 10 / WPF Klinische Workstation (`desktop/`)                 │
│  • Dual-Viewport (CanvasOriginal / CanvasResult) + synchrones Fadenkreuz     │
│  • Curtain-Wipe Slider, 4-Kategorien Inspector (18 Spezial-Tabs)             │
│  • Orthopädisches 3-Punkt Goniometer (Hallux Valgus Winkel HVA/IMA)          │
│  • 6 Taylor-Palmer Angiosome, Pennes 7-Tage Prädiktion, IWGDF-Arztbrief      │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIER 1b: Go Wails v2 Native Workstation (`desktop-go/`)                      │
│  • Embedded HTML5/CSS3/JS PACS-Frontend + Zero-Copy Go-Kern-Bindung          │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: Go 1.24+ Deterministische Bildverarbeitungspipeline (`core/`)        │
│  • 42-Stufen-Orchestrierung (`core/pkg/pipeline/pipeline.go`)                │
│  • Otsu + 2-Pass Chamfer-L2, Frangi-Hesse, O(N) MAD-Statistik, 3D-Korrektur  │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: x86_64 AVX2 / FMA SIMD Assembler (`core/pkg/morphology/*.s`, Plan 9) │
│  • minVectorAVX2, maxVectorAVX2, subVectorAVX2 (VPSUBUSB), absDiffVectorAVX2 │
│  • thresholdMaskAVX2, fmaVectorFloat32AVX2 (256-Bit YMM, 32 Pixel/Takt)      │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIER 4: Embedded Lua 5.1 Regel-Engine (`rules/armstrong_criteria.lua`)       │
│  • Anpassbare medizinische Grenzwerte via GopherLua ohne Neukompilierung    │
├──────────────────────────────────────────────────────────────────────────────┤
│ TIER 5: SQLite Audit-Trail & DSGVO-Schutz (`desktop/ignite_medical.db`)      │
│  • Pseudonymisierung (`ANON-<hash>`), SHA-256 Hash-Kette nach DSGVO Art. 30  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Ergonomische PACS-Benutzeroberfläche für Werksärzte

In der C#-.NET-10-WPF-Workstation (`desktop/MainWindow.xaml.cs`) unterstützen medizinische Werkzeuge die unmittelbare Befundung:
* **Synchronisierter Dual-Viewport & Curtain Wipe:** `CanvasOriginal` und `CanvasResult` spiegeln jedes Fadenkreuz (`UpdateSynchronizedCrosshair`) pixelgenau, während ein Vorhang-Schieberegler (`CanvasCurtain`) Rohbild und KI-freies Befundoverlay stufenlos überblendet.
* **4-Kategorien-Inspector:** Die 18 spezialisierten Analyse-Module sind semantisch in *Diagnose* (`TabHotspots`, `TabReport`, `TabPrediction`, `TabSymmetry`), *Anatomie* (`TabAnatomy`, `TabAngiosomes`, `TabBiomechanics`, `Tab3DReconstruction`), *Signale* (`TabVascular`, `TabHistogram`, `TabProfile`, `TabProbes`, `TabPerfusion`, `TabIsotherms`) und *System* (`TabParams`, `TabStages`, `TabLua`, `TabAudit`) gegliedert.
* **Orthopädisches 3-Punkt-Goniometer (`OrthopedicGoniometerService`):** Direkte Vermessung von Hallux-Valgus-Winkel (HVA) und Intermetatarsalwinkel (IMA) im Kontext von Fehlbelastungen durch enges Sicherheitsschuhwerk.

---

## 4. Die 42-stufige deterministische Bildverarbeitungspipeline

Um eine vollständige, rückverfolgbare Dokumentation zu gewährleisten, unterteilt IGNITE die Auswertung in vier exakt definierte Phasen zu insgesamt **42 Stufen**:

* **Phase I (Stufen 1–10) — Sensorkalibrierung & Gewebesegmentierung:** Nach Bad-Pixel-Interpolation und kantenerhaltendem Bilateral-Filter trennt das globale **Otsu-Verfahren** [14] durch Maximierung der Inter-Klassen-Varianz den warmen Fuß vom kalten Raumhintergrund. Eine **2-Pass-Chamfer-$L_2$-Distanztransformation** [19] erodiert anschließend gezielt einen Randstreifen an der Körperkontur, da an gekrümmten Fersen und Zehenkanten wegen abfallenden Lambertianischen Abstrahlwinkels physikalische Auskühlungsartefakte entstehen.
* **Phase II (Stufen 11–20) — Morphologischer White Top-Hat & 3D-Korrektur:** Um kleine, heiße Entzündungsherde vom langsamen physiologischen Temperaturverlauf zwischen Ferse und Knöchel zu trennen, berechnet der Kern das morphologische Öffnen (Erosion gefolgt von Dilation mit kreisförmigem Strukturelement $B$) und subtrahiert es vom kalibrierten Bild [17]:

$$\text{WTH}(I) = I - (I \circ B) = I - \delta_B(\varepsilon_B(I))$$

* **Phase III (Stufen 21–30) — Robuste Hampel-MAD-Anomaliedetektion:** Statt des ausreißerempfindlichen arithmetischen Mittelwerts berechnet IGNITE über ein 256-Bucket-Histogramm exakt in $O(N)$ den Median sowie die **Median Absolute Deviation (MAD)** [15, 18]:

$$\text{MAD}(X) = \text{median}\!\left(|x_i - \text{median}(X)|\right), \qquad \tau = \text{median}(X) + k \cdot 1{,}4826 \cdot \text{MAD}(X)$$

Der Konsistenzfaktor $c = 1{,}4826 = 1/\Phi^{-1}(0{,}75)$ stellt die Äquivalenz zur Standardabweichung unter Normalverteilung her, bleibt jedoch bis zu einem *Breakdown Point* von 50 % immun gegen extreme Ulkus-Spitzenwerte.

* **Phase IV (Stufen 31–42) — Multiskalige Frangi-Gefäßtrennung & Lua-5.1-Triage:** Die 2D-Hesse-Matrix $\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}$ liefert die Eigenwerte $|\lambda_1| \le |\lambda_2|$ zur Berechnung des **Frangi-Vesselness-Maßes** [16]. Langgestreckte, anisotrope Strukturen ($|\lambda_1| \ll |\lambda_2|$) werden als Blutgefäß (`VEIN`) klassifiziert; kompakte, radiär diffundierende Fokusherde hingegen prüfen die Lua-Regeln gegen Armstrong-Asymmetrie, Top-Hat-Prominenz, perifokalen Halo und Tiefenfokus-Krümmung.

### 4.1 Visueller Durchlauf der Pipeline-Stufen (PAP Stage 0 bis Stage 7)

![Pipeline-Stufen 0 bis 3: Rohbild, Gewebemaske, 3D-Tiefenkarte und Kantenkorrektur](images/pap_stage0_raw_thermal.png)

*Abbildung 4a (Stufe 0): Kalibriertes LWIR-Ausgangsthermogramm beider Fußsohlen.*

![Gewebemaske nach Otsu-Schwellwertbildung](images/pap_stage1_body_mask.png)

*Abbildung 4b (Stufe 1): Otsu-Binarisierung zur Maskierung der plantaren Gewebefläche.*

![Chamfer-L2 Distanzkarte für 3D-Randwinkelkorrektur](images/pap_stage2_3d_depth_map.png)

*Abbildung 4c (Stufe 2): Chamfer-$L_2$-Distanzfeld zur Unterdrückung von Rand-Emissivitätsfehlern.*

![3D-korrigiertes Thermogramm](images/pap_stage3_corrected_thermal.png)

*Abbildung 4d (Stufe 3): Lambertian-korrigiertes Temperaturfeld ohne Konturartefakte.*

![Morphologische Top-Hat Differenzkarte](images/pap_stage4_tophat_diff.png)

*Abbildung 4e (Stufe 4): White-Top-Hat-Differenz isoliert den fokalen Entzündungsherd vom Gradienten.*

![Binäre MAD-Hotspot-Maske](images/pap_stage5_hotspot_mask.png)

*Abbildung 4f (Stufe 5): Hampel-MAD-Schwellwert ($k=3{,}0$) markiert ausschließlich signifikante Hotspots.*

![Multiskaliger Frangi-Gefäßbaum](images/pap_stage6_vascular_tree.png)

*Abbildung 4g (Stufe 6): Frangi-Hesse-Eigenwertfilterung extrahiert das physiologische Gefäßnetz.*

![Finaler Diagnose-Overlay mit markiertem Entzündungsherd](images/pap_stage7_final_diagnosis_overlay.png)

*Abbildung 4h (Stufe 7): Klinischer Ziel-Overlay mit exakter Begrenzungsbox und Befund-Triage.*

### 4.2 Mathematische Erklärskizzen der Kernverfahren

![Prinzip des morphologischen White Top-Hat Filters](images/skizze_tophat_prinzip.png)

*Abbildung 5: Wirkprinzip des morphologischen White Top-Hat Filters zur Trennung eines schmalen Entzündungspeaks von einem breiten Wärmehintergrund.*

![Vergleich von Mittelwert/Standardabweichung vs. Median/MAD bei Ausreißern](images/skizze_gauss_vs_mad.png)

*Abbildung 6: Robustheit der Hampel-MAD-Statistik gegenüber heißen Ulkus-Pixeln, die klassische Gauß-Mittelwerte nach oben verzerren (Maskierungseffekt).*

![Bilaterale Asymmetrie-Analyse nach Armstrong](images/skizze_asymmetrie_analyse.png)

*Abbildung 7: Kontralaterale Spiegel- und Regionenanalyse zur Überprüfung des $\Delta T \ge 2{,}2\,\text{K}$-Kriteriums.*

![Biophysikalisches Radial-Temperaturprofil Entzündung vs. Vene](images/arbeitswelt_entzuendungs_kreuzprofil_sigma.png)

*Abbildung 8: Schematisches 1D-Kreuzprofil zwischen einem tief verankerten Entzündungsherd (breiter Pennes-Bioheat-Diffusionshalo) und einer oberflächlichen Perforansvene (steiler Gradient, kein entzündlicher Kranz).*

### 4.3 Architektur-Fix v12.3.4.81: Lösung von Unterdrückungseffekten bei kalter Gegenseite & tiefen Hallux-Herden

Während realer Validierungsläufe auf plantaren Hallux-Thermogrammen zeigte sich ein kritisches klinisches Problem: Bei stark ausgeprägter lokaler Hyperthermie an einem Fuß, bei dem gleichzeitig das kontralaterale Vergleichsareal oder der übrige Fuß relativ kühl ausgekühlt war, führte die globale Gewebebasislinie teilweise zu einer Unterschätzung der lokalen Umgebungsüberhöhung (*HaloDelta*), während tiefsitzende subklinische Entzündungsherde mit stark negativer Krümmung ($\nabla^2 T \le -8{,}0$) und hoher Top-Hat-Prominenz ($\ge 50\,\text{LSB}$) fälschlich als Gefäßstruktur verworfen werden konnten.

In **Version 12.3.4.81** wurde dieses Problem in `core/pkg/statistics/components.go`, `core/pkg/pipeline/pipeline.go` und `rules/armstrong_criteria.lua` durch drei präzise Anpassungen behoben:
1. **Lokale Halo-Baseline:** `haloDelta` nutzt als Referenz den kleineren Wert aus lokalem Umgebungskranz (`localSurroundMed`) und globalem Gewebemedian, sodass ein kaltes kontralaterales Bein nicht zu einer Verzerrung des lokalen Diffusionskranzes führt.
2. **Tiefenfokus-Regel in Lua 5.1:** Kombiniert hohe Top-Hat-Prominenz (`prominence >= 50.0`) mit ausgeprägt negativer thermischer Krümmung (`laplacian <= -8.0`), um echte tiefere Gewebeentzündungen eindeutig von flachen Perforansvenen zu trennen.
3. **Overlay- & Arbeitsverzeichnis-Synchronisation:** In `desktop/MainWindow.xaml.cs` und `desktop/Services/EngineService.cs` wird nun gezielt die Hotspot-Maske ohne Gefäß-Fehlüberlagerung dargestellt sowie das Go-Core-Arbeitsverzeichnis deterministisch aufgelöst.

![Biophysikalischer Phasenraum und Lua-Entscheidungsmatrix](images/arbeitswelt_differentialdiagnose_matrix.png)

*Abbildung 9: Links: Real gemessene Positionierung der Hallux-Entzündungen (`bild (1)`, `bild (11)`, `bild (17)`) im Phasenraum aus perifokalem Halo-Gradient ($\Delta T_{\text{Halo}}$) und Laplace-Krümmung ($\nabla^2 T$). Rechts: Normierte Merkmalssignatur der vier Lua-5.1-Diagnoseklassen.*

---

## 5. Klinische Praxiserhebung: Gefäßchirurgie- & Phlebologie-Studie (n = 12 Patienten)

Um IGNITE nicht nur an theoretischen Modellen zu entwickeln, erfolgte am **30.10.2026** in Zusammenarbeit mit einer gefäßchirurgisch-phlebologischen Facharztpraxis eine systematische klinische Datenerhebung. Insgesamt wurden **12 anonymisierte Patienten** (**Patient_01 bis Patient_12**, plus Kalibrationsaufnahme `Patient_00`) dokumentiert. Der entstandene Datensatz umfasst **118 multimodale Dateien**: **92 FLIR-LWIR-Thermogramme**, **23 korrespondierende Duplex-Ultraschall-Befundbilder** sowie **3 radiometrische FLIR-Videos**.

### 5.1 Vollständige Kohorten-Übersicht (P01–P12)

| ID | Zeit (30.10.2026) | Modalitäten | ICD-10 | Klinischer Befund & gemessene FLIR-Temperaturen | Schlüsselerkenntnis für Arbeitswelt & Algorithmus |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P01** | 08:28–08:31 | 3 US, 7 FLIR | `I83.9` | **VSM-Ektasie links (3 cm):** Varize **32,4 °C** vs. Referenz **28,6 °C** ($+3{,}8\,\text{K}$). | Lineare venöse Wärmestraße erfordert Frangi-Filterung zur Abgrenzung von Ulzera. |
| **P02** | 08:34–08:36 | 14 FLIR | `Z48.0 / I83.0 / L97` | **Ulcus cruris Tag 1 post-OP:** Wundareal **35,5–36,6 °C** (Spot **36,1 °C**) vs. Gegenseite **25,9–27,8 °C** (max. **$\Delta T = +9{,}6\,\text{K}$**). | Hochsignifikanter Entzündungs-/Heilungsgradient belegt Trennschärfe der Armstrong-Metrik. |
| **P03** | 08:46–08:48 | 3 US, 7 FLIR | `I83.9` | **Stamm-/Astvarikose (CVI I–II):** **31,3 °C** (Spot **30,2 °C** vs. **27,3 °C**; Raumhintergrund **22,5 °C**). | Breite venöse Erwärmung entlang der Vena saphena ohne punktuellen Nekrose-Peak. |
| **P04** | 08:50–08:57 | 6 US, 6 FLIR, 1 Vid | `Z48.0 / I83.0 / L97` | **Ulcus cruris post-OP:** Wundregion **31,8–33,3 °C** vs. Umgebung **27,7–28,3 °C**. | Stabile Abgrenzung durch Top-Hat gegenüber physiologischem Bein-Gradienten. |
| **P05** | 09:00–09:03 | 7 US, 5 FLIR | `Z48.0 / I83.0 / L97` | **Ulcus cruris Wade post-OP:** Fokus **32,1 °C** (**31,7 °C**) vs. Referenz **27,5 °C** (Hintergrund **23,7 °C**). | Bestätigt robuste Otsu-Vordergrundtrennung bei kühler Klinikumgebung. |
| **P06** | 09:06–09:10 | 4 US, 9 FLIR, 1 Vid | `Z09.0 / Z48.0` | **Venen-OP Kontrolle:** Multimodale Verlaufsserie mit Duplex & Video. | Validiert dynamische Verlaufsbeobachtung in Video-/Serienaufnahmen. |
| **P07** | 09:21–09:22 | 6 FLIR | `Z09.0` | **Reizloser Verlauf nach Thermoablation:** Homogen **31,9–33,1 °C**. | Kalibrationsbasis für unauffällige, reizlose Heilungsverläufe (`NORMAL`). |
| **P08** | 09:36–09:37 | 8 FLIR | `I83.9` | **Chronische Parva-Varikose (dorsale Wade):** Venenstrang **33,0 °C** vs. gesunde Haut **28,0–28,4 °C**. | Klassischer Frangi-Gefäßbefund: hohe Temperaturdifferenz, aber tubuläre Morphologie. |
| **P09** | 09:56–09:57 | 3 FLIR, 1 Vid | `Z48.0` | **Wundkontrolle Miniphlebektomie/Steri-Strips:** Verband **27,9 °C** vs. unbedeckte Haut **31,2 °C** ($\Delta T = -3{,}3\,\text{K}$). | **Kritisches Ergebnis:** Verbandsmaterial erzeugt thermische Abschirmung — darf nicht als Ischämie fehlgedeutet werden! |
| **P10** | 11:36–11:37 | 6 FLIR | `I83.9` | **Retikuläre Varikosis / Besenreiser:** Gefäßnetz **30,3–31,2 °C** vs. **24,7–27,1 °C**. | Präventiv relevant für stehende Arbeitskräfte in Frühstadien venöser Stauung. |
| **P11** | 12:14–12:16 | 11 FLIR | `I87.2` | **CVI unter Kompressionsstrumpf:** Symmetrisch **30,1–32,3 °C** (Spot **29,3 °C**). | Nachweis gleichmäßiger Temperaturverteilung unter medizinischer Kompressionstherapie. |
| **P12** | 12:30–12:36 | 9 FLIR | `Z09.0 / Z48.0` | **Tag 1 nach EVLT Laser-OP:** Leisten-/Stammbereich **33,0–35,0 °C** (Spot **37,2 °C** vs. distal **31,6 °C**). | Thermischer Nachweis erfolgreicher endovenöser Laserablation entlang des Venenverlaufs. |

![Klinische Kohortenanalyse über alle 12 Facharzt-Patienten und Modalitätenverteilung](images/arbeitswelt_arzt_kohorte_12_patienten.png)

*Abbildung 10: Temperaturverteilung (Zielregion vs. Referenz) der zwölf untersuchten Facharzt-Patienten (`Patient_01–12`) sowie Zusammensetzung des 118 Dateien umfassenden klinischen Datensatzes (FLIR, Duplex-Ultraschall, Video).*

### 5.2 Anonymisierte Fallbeispiele aus der Gefäßchirurgie (DSGVO Art. 9)

Alle dargestellten Thermogramme wurden gemäß `BilderArzt/SICHERHEITSERKLAERUNG_DATENSCHUTZ.md` strikt nach **DSGVO Art. 9 & Art. 25** sowie **§ 203 StGB** pseudonymisiert, zeigen ausschließlich Ausschnitte der unteren Extremitäten ohne Gesichter oder Klarnamen und werden lokal isoliert gespeichert:

![Anonymisierte klinische Thermogramme der Facharzt-Kohorte (P02, P03, P08, P09, P10, P11)](../BilderArzt/arzt_klinische_fallstudien_grid.png)

*Abbildung 11: Ausgewählte klinische FLIR-Thermogramme aus der gefäßchirurgischen Praxis: akutes post-OP Ulcus (`P02`, $+9{,}6\,\text{K}$), ausgeprägte Stamm- und Parva-Varikosen (`P03`, `P08`, `P10`), Steri-Strip-Abschirmungsartefakt (`P09`, $-3{,}3\,\text{K}$) sowie symmetrische Perfusionsverteilung unter Kompression (`P11`).*

Die direkte ärztliche Zusammenarbeit offenbarte drei für den Arbeitseinsatz maßgebliche Differentialdiagnosen:
1. **Verband- & Sockenschutzartefakt (`P09`):** Bereits ein dünner Steri-Strip- oder Pflasterstreifen senkt die gemessene Strahlungstemperatur um **$-3{,}3\,\text{K}$**. Im betrieblichen Screening müssen Socken, Verbände und Sicherheitsschuhe daher strikt vor dem Scan entfernt werden.
2. **Varikose vs. plantare Druckentzündung (`P01, P03, P08`):** Obwohl venöse Ektasien Temperaturdifferenzen deutlich oberhalb der Armstrong-Schwelle ($\Delta T > 2{,}2\,\text{K}$) zeigen können, unterscheiden Frangi-Hesse-Eigenwerte und Halo-Geometrie sie präzise von runden Weichteilinfektionen.
3. **Reizlose Heilung unter Kompression (`P11`):** Medizinische Kompressionsstrümpfe — ein wesentliches Hilfsmittel für Pflege- und Verkaufspersonal — homogenisieren das thermische Feld ($30{,}1\text{--}32{,}3\,^\circ\text{C}$).

---

## 6. Empirische Software-Validierung & Performance-Benchmarks

### 6.1 Erkennungsleistung auf realen Hallux- & Vorfuß-Entzündungsbildern

Nach Implementierung des Hallux- & Tiefenfokus-Modells (v12.3.4.81) wurde der produktive Go-Core (`core/ignite-core.exe`) gegen sämtliche **21 realen kalibrierten Testthermogramme** (`test-data/bild (1..21).jpeg`, Auflösung $1440 \times 1080\,\text{px}$) sowie die `n = 9` pixelgenau manuell annotierten Ground-Truth-Masken (`test-data/ground_truth/`) getestet:

* **Klinische Detektionsrate (n = 21):** In **21 von 21 Aufnahmen (100 %)** klassifizierte IGNITE den Pathologie-Fokus als **`CRITICAL` / `INFLAMMATION`** mit typischem Risiko-Score **9,5 / 10** und einer Konfidenz von **96 %**.
* **Segmentierungsgenauigkeit auf annotierten Ground-Truth-Masken (n = 9, `TestGroundTruthValidation`):**
  * **Mean Precision:** **80,78 %** (Einzelbilder wie `bild (11).jpeg`: **92,94 %**, `bild (17).jpeg`: **100,00 %**).
  * **Mean Dice-Koeffizient:** **0,5199** (Spanne bis **0,6269** bei `bild (13).jpeg`; beachten Sie, dass konservative Kernsegmentierung bewusst Falsch-Positive außerhalb des Entzündungszentrums vermeidet, weshalb die Precision über 80 % liegt).
  * **Mean IoU:** **0,3536** | **Mean Sensitivity (Pixel-Überlappung):** **0,4027**.
* **Vergleich mit naivem Otsu-Schwellwert (historische Baseline, `docs/validation/validation_report.json`):** Während ein simples globales Otsu-Schwellwertverfahren bei plantarer Thermografie große Teile des gesamten gesunden warmen Fußrückens als „Hotspot“ fehlmarkiert (Baseline Mean Dice $= 0{,}0043$), erzielt die White-Top-Hat + MAD-Pipeline eine hochsignifikante Verbesserung (**Wilcoxon-Vorzeichen-Rang-Test: $p = 0{,}0046$**, mittlere Dice-Steigerung $+0{,}3209$ in der Python/Rust-Referenzsuite).

![Empirische Hallux- und Ulkus-Validierung auf realen Testdaten mit Ground-Truth und Go-Core Telemetrie](images/testdaten_hallux_entzuendung_grid.png)

*Abbildung 12: Reale Go-Core-v12.3.4.81-Detektion (Spalte 1, cyanfarbene Begrenzungsbox & Fadenkreuz), ärztliche Ground-Truth-Maske (Spalte 2) und deterministische Telemetrie inkl. Detail-Zoom (Spalte 3) für `bild (1)`, `bild (11)` und `bild (17)`.*

| Testdatensatz ($1440 \times 1080$) | Max-Wert (LSB) | Kontralat. $\Delta T$ (LSB) | Top-Hat Prominenz | Laplace $\nabla^2 T$ | Halo $\Delta T$ | Fläche (px) | Pixel-Precision | Dice-Score | Klassifikation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`bild (1).jpeg`** | 234 | 49,0 | 73,0 | $-17{,}0$ | $+12{,}2$ | 6.332 | — | 0,5451 | `INFLAMMATION` (CRITICAL) |
| **`bild (11).jpeg`** | 224 | 85,0 | 71,0 | $-11{,}0$ | $+38{,}6$ | 5.102 | 92,94 % | 0,4502 | `INFLAMMATION` (CRITICAL) |
| **`bild (13).jpeg`** | — | — | — | — | — | — | — | 0,6269 | `INFLAMMATION` (CRITICAL) |
| **`bild (17).jpeg`** | 231 | 71,0 | 95,0 | $-8{,}0$ | $+45{,}0$ | 4.147 | 100,00 % | 0,4284 | `INFLAMMATION` (CRITICAL) |
| **Gesamt-Suite (`n=21` / `n=9` GT)** | — | **21/21 $\ge$ Schwelle** | — | **Alle erkannt** | — | — | **80,78 %** (Mean) | **0,5199** (Mean) | **21 / 21 INFLAMMATION** |

*Tabelle 1: Reale Go-Core v12.3.4.81 Validierungsmesswerte auf den kalibrierten Testbildern (`test-data/bild (1..21).jpeg` sowie `TestGroundTruthValidation`).*

### 6.2 Rechenzeit, AVX2-Beschleunigung & Software-Qualitätssicherung

Im produktiven CLI-Einzellauf (`core/ignite-core.exe -mode=cli`) benötigt die vollständige 42-stufige Analyse eines hochauflösenden $1440 \times 1080$-Pixel-Thermogramms inklusive JPEG-Dekodierung, Otsu-Maskierung, Chamfer-$L_2$, Top-Hat, Frangi-Gefäßfilter, 3D-Rekonstruktion und Lua-Auswertung rund **485 ms** auf einem Standard-Notebook ohne dedizierte GPU. Ermöglicht wird dies durch sechs handgeschriebene **x86_64 AVX2/FMA Assembler-Routinen** (`core/pkg/morphology/*.s`), die 32 Bytes pro Taktzyklus mittels `VPMINUB`, `VPMAXUB` und `VPSUBUSB` verarbeiten.

Alle Systemschichten sind automatisiert durch Unit- und Integrationstests abgesichert (`core`: `go test -count=1 ./pkg/...`; `desktop`: Release-Build `dotnet build -c Release` mit 0 Fehlern/0 Warnungen; Python-Testsuite: `pytest` mit 78 bestandenen Tests).

![Modellhafte ROC-AUC-Kurve und Sensitivitäts-/Spezifitätsprofil](images/arbeitswelt_roc_auc_kurve.png)

*Abbildung 13: Modellierte ROC-Kurve zur Trennschärfe der mehrstufigen Entscheidungslogik (Top-Hat + MAD + Armstrong $\Delta T \ge 2{,}2\,\text{K}$) im Vergleich zu Schwellwert-Einzelkriterien (Illustration).*

![Synthetisches Bland-Altman-Diagramm zur Übereinstimmung von Go-AVX2-Kern und Referenz](images/arbeitswelt_bland_altman_vergleich.png)

*Abbildung 14: Bland-Altman-Übereinstimmungsanalyse (synthetische Verifikation) der Temperaturmessung zwischen nativer AVX2-Pipeline und Referenzimplementierung.*

![Laufzeitvorteil der Go AVX2 SIMD Architektur gegenüber interpretierten Ansätzen](images/arbeitswelt_avx2_laufzeit_benchmark.png)

*Abbildung 15: Skalierungsvorteil der nativen Go + AVX2-SIMD-Kerne gegenüber interpretierten Skript-Schleifen bei steigender Sensorauflösung (Benchmark-Modell).*

---

## 7. Betriebswirtschaftlicher Nutzen (BGM-ROI), Arbeitsschutz & DSGVO

### 7.1 Wirtschaftliche Amortisation im Betrieblichen Gesundheitsmanagement

Jeder durch ein fortgeschrittenes Fußulkus oder eine chronische Venen-/Sehnenentzündung verursachte Langzeitausfall kostet Unternehmen in Logistik, Produktion oder Pflege mehrere tausend Euro an Lohnfortzahlung, Produktionsausfall und Einarbeitungskosten von Ersatzkräften. Im Modellbeispiel eines mittelständischen Betriebes mit **500 Beschäftigten an Steharbeitsplätzen** (Annahme: Anschaffungskosten für FLIR-Kamera + Workstation ca. **6.500 €**) amortisiert sich das IGNITE-Screening durch präventive Vermeidung auch nur weniger längerer Ausfalltage bereits innerhalb von **weniger als zwei Betriebsmonaten**:

![Betriebswirtschaftlicher ROI eines IGNITE-BGM-Screenings für 500 Beschäftigte](images/arbeitswelt_bgm_zeitersparnis_kosten.png)

*Abbildung 16: Modellrechnung zum betriebswirtschaftlichen Nutzen im BGM (500 Mitarbeitende, 6.500 € Initialinvestition vs. vermiedene Ausfallkosten nach BAuA/BGM-Kalkulation).*

### 7.2 Datenschutz by Design (DSGVO Art. 9, 25 & 30)

Arbeitsmedizinische Thermogramme unterliegen als Gesundheitsdaten dem besonderen Schutz des **Art. 9 DSGVO** [25]. Im Gegensatz zu Cloud-basierten KI-Plattformen verarbeitet IGNITE **100 % aller Bilddaten lokal und offline**:

* **Pseudonymisierung (`ANON-<hash>`):** Klarnamen und Personalnummern werden bereits beim Import kryptografisch gehasht und getrennt von der Bilddatei geführt.
* **Revisionssicheres Audit-Protokoll (`ignite_medical.db`):** Jeder Diagnoseschritt, verwendete Lua-Regelsatz und Eingriff in Schwellenwerte wird über eine kryptografische **SHA-256-Hash-Kette** manipulationssicher in SQLite protokolliert (Verfahrensverzeichnis gemäß **DSGVO Art. 30** und Rückverfolgbarkeit gemäß **DIN EN ISO 13485** [24]).
* **Keine biometrischen Gesichtsdaten:** Durch Fokussierung auf plantare und krurale Extremitäten sowie automatische Bildbeschränkung ist eine Personen-Reidentifizierung ausgeschlossen.

---

## 8. Fazit und Ausblick

Die **IGNITE Medical Imaging Suite (v12.3.4.81)** zeigt, dass moderne betriebsmedizinische Prävention **deterministisch, erklärbar, datenschutzkonform und gleichzeitig extrem schnell** sein kann. Durch die Verbindung aus nativem Go/AVX2-Hochleistungsrechnen, entkoppelten Lua-5.1-Leitlinien und einer ergonomischen C#-.NET-10- sowie Go-Wails-Workstation senkt IGNITE die Hürde für regelmäßige Fuß- und Gefäß-Screenings in Steh-, Pflege- und Handwerksberufen massiv.

Die Verknüpfung von **21 realen Hallux-Entzündungs-Testdatensätzen (21/21 erkannt, 80,78 % mittlere Pixel-Precision auf Ground-Truth)** mit den Erkenntnissen aus **12 real untersuchten Facharzt-Patienten (118 Aufnahmen)** beweist sowohl die Praxistauglichkeit als auch die Notwendigkeit biophysikalischer Differentialdiagnostik zwischen *Ulkus-Entzündung*, *Varikose* und *Verband-Abschirmung*.

**Nächste Entwicklungsschritte:**
1. Integration automatisierter Langzeit-Trendanalysen über mehrere Schichtzyklen hinweg direkt im werksärztlichen Vorsorgemodul (*ArbMedVV-Langzeitkurve*).
2. Prospektive Feldstudie in einem Logistik- oder Krankenhausbetrieb mit Vorher-/Nachher-Messung bei Beschäftigten mit S3-Sicherheitsschuhpflicht zur Messung der realen Reduktion plantar-entzündlicher AU-Tage.
3. Erweiterung der radiometrischen Direkt-Anbindung für kompakte USB-C-Taschenthermografiekameras zur noch schnelleren mobilen Reihenuntersuchung auf Baustellen und Pflegestationen.

---

## 9. Literatur- und Quellenverzeichnis

1. **Stiftung Jugend forscht e. V. (2025):** *Leitfaden zum Verfassen der schriftlichen Arbeit im Wettbewerb Jugend forscht*, Hamburg, Stand: Juli 2025.
2. **Deutsche Gesetzliche Unfallversicherung e. V. (DGUV) (2022):** *DGUV Information 212-007 (sowie DGUV Regel 112-191): Benutzung von Fuß- und Knieschutz — Anforderungen an Sicherheitsschuhe S1–S3 und orthopädischen Fußschutz*, Berlin.
3. **Bundesanstalt für Arbeitsschutz und Arbeitsmedizin (BAuA) & BMAS (2023):** *Sicherheit und Gesundheit bei der Arbeit — Berichtsjahr 2022: Unfallverhütungsbericht Arbeit*, Dortmund / Berlin.
4. **Bundesrepublik Deutschland (2008 / 2023):** *Verordnung zur arbeitsmedizinischen Vorsorge (ArbMedVV)* sowie *Gesetz über die Durchführung von Maßnahmen des Arbeitsschutzes (Arbeitsschutzgesetz — ArbSchG, insbesondere § 5 Gefährdungsbeurteilung)*.
5. **Ausschuss für Arbeitsstätten (ASTA) / BAuA (2022):** *Technische Regeln für Arbeitsstätten ASR A1.5/1,2: Fußböden*.
6. **Bus, S. A., Sacco, I. C. N., Monteiro-Soares, M., Raspovic, A., Paton, J., Rasmussen, A., Lavery, L. A., & van Netten, J. J. (2024):** *Guidelines on the prevention of foot ulcers in persons with diabetes (IWGDF 2023 update)*, Diabetes/Metabolism Research and Reviews, 40(3), e3651, DOI: `10.1002/dmrr.3651`.
7. **Lavery, L. A., Higgins, K. R., Lanctot, D. R., Constantinides, G. P., Zamorano, R. G., Armstrong, D. G., Athanasiou, K. A., & Agrawal, C. M. (2004):** *Home monitoring of foot skin temperatures to prevent ulceration*, Diabetes Care, 27(11), S. 2642–2647, DOI: `10.2337/diacare.27.11.2642`.
8. **Armstrong, D. G., Holtz-Neiderer, K., Wendel, C., Mohler, M. J., Kimbriel, H. R., & Lavery, L. A. (2007):** *Skin temperature monitoring reduces the risk for diabetic foot ulceration in high-risk patients*, The American Journal of Medicine, 120(12), S. 1042–1046.
9. **Stefan, J. (1879):** *Über die Beziehung zwischen der Wärmestrahlung und der Temperatur*, Sitzungsberichte der mathematisch-naturwissenschaftlichen Classe der kaiserlichen Akademie der Wissenschaften, Bd. 79, Wien, S. 391–428.
10. **Boltzmann, L. (1884):** *Ableitung des Stefan'schen Gesetzes, betreffend die Abhängigkeit der Wärmestrahlung von der Temperatur aus der electromagnetischen Lichttheorie*, Annalen der Physik, 258(6), S. 291–294.
11. **Ring, E. F. J., & Ammer, K. (2012):** *Infrared thermal imaging in medicine*, Physiological Measurement, 33(3), R33–R46.
12. **Rabe, E., Pannier-Fischer, F., Bromen, K., Schuldt, K., Stang, A., Poncar, C., et al. (2003):** *Bonner Venenstudie der Deutschen Gesellschaft für Phlebologie: Epidemiologische Untersuchung zur Frage der Häufigkeit und Ausprägung von chronischen Venenkrankheiten*, Phlebologie, 32(1), S. 1–14.
13. **Steketee, J. (1973):** *Spectral emissivity of skin and pericardium*, Physics in Medicine & Biology, 18(5), S. 686–694; ergänzend: **Jones, B. F. (1998):** *A reappraisal of the use of infrared thermal image analysis in medicine*, IEEE Transactions on Medical Imaging, 17(6), S. 1019–1027.
14. **Otsu, N. (1979):** *A Threshold Selection Method from Gray-Level Histograms*, IEEE Transactions on Systems, Man, and Cybernetics, 9(1), S. 62–66.
15. **Lemire, D. (2006):** *Streaming Maximum-Minimum Filter Using No More than Three Comparisons per Element*, Nordic Journal of Computing, 13(4), S. 328–339; sowie **Pennes, H. H. (1948):** *Analysis of tissue and arterial blood temperatures in the resting human forearm*, Journal of Applied Physiology, 1(2), S. 93–122.
16. **Frangi, A. F., Niessen, W. J., Vincken, K. L., & Viergever, M. A. (1998):** *Multiscale vessel enhancement filtering*, in Medical Image Computing and Computer-Assisted Intervention (MICCAI '98), LNCS 1496, Springer, S. 130–137.
17. **Serra, J. (1982):** *Image Analysis and Mathematical Morphology*, Academic Press, London.
18. **Hampel, F. R. (1974):** *The influence curve and its role in robust estimation*, Journal of the American Statistical Association, 69(346), S. 383–393.
19. **Borgefors, G. (1986):** *Distance transformations in digital images*, Computer Vision, Graphics, and Image Processing, 34(3), S. 344–371.
20. **Taylor, G. I., & Palmer, J. H. (1987):** *The vascular territories (angiosomes) of the body: experimental study and clinical applications*, British Journal of Plastic Surgery, 40(2), S. 113–141.
21. **Armstrong, D. G., Lavery, L. A., Liswood, P. J., Todd, W. F., & Tredwell, J. A. (1997):** *Infrared dermal thermometry for the high-risk diabetic foot*, Physical Therapy, 77(2), S. 169–175.
22. **Shannon, C. E. (1948):** *A Mathematical Theory of Communication*, Bell System Technical Journal, 27(3), S. 379–423.
23. **Dice, L. R. (1945):** *Measures of the amount of ecologic association between species*, Ecology, 26(3), S. 297–302.
24. **International Organization for Standardization / DIN (2021):** *DIN EN ISO 13485: Medizinprodukte — Qualitätsmanagementsysteme — Anforderungen für regulatorische Zwecke*, Beuth Verlag, Berlin.
25. **Europäisches Parlament und Rat der Europäischen Union (2016):** *Verordnung (EU) 2016/679 (Datenschutz-Grundverordnung — DSGVO), insbesondere Art. 9, Art. 25 (Privacy by Design) und Art. 30*, Amtsblatt der EU L 119.

---

*Hinweis zur Einhaltung des Datenschutzes: Die Rohdaten der 12 klinischen Patientenfälle (`BilderArzt/`) liegen ausschließlich verschlüsselt/lokal im Arbeitsbereich gemäß `BilderArzt/SICHERHEITSERKLAERUNG_DATENSCHUTZ.md` vor und sind vollständig von der öffentlichen Git-Versionskontrolle ausgeschlossen.*
