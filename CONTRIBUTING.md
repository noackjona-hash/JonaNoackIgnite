# Beitragen zu IGNITE Medical Imaging Suite 🔬🌡️

Vielen Dank für dein Interesse, zu **IGNITE** beizutragen! Dieses Projekt wurde als wissenschaftlicher Forschungsprototyp für den Wettbewerb **Jugend forscht 2026** (Fachgebiet Arbeitswelt) entwickelt.

Wir freuen uns über Bug-Reports, Feature-Vorschläge, Verbesserungen an den Algorithmen sowie Erweiterungen der Dokumentation.

---

## 📋 Inhaltsverzeichnis

1. [Verhaltenskodex](#verhaltenskodex)
2. [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
   - [Fehler melden (Bug Reports)](#fehler-melden-bug-reports)
   - [Neue Features vorschlagen](#neue-features-vorschlagen)
   - [Code-Beiträge einreichen (Pull Requests)](#code-beiträge-einreichen-pull-requests)
3. [Entwicklungsumgebung einrichten](#entwicklungsumgebung-einrichten)
4. [Entwicklungsrichtlinien](#entwicklungsrichtlinien)
   - [Python-Code](#python-code)
   - [Rust-Core (ignite_core)](#rust-core-ignite_core)
   - [GUI & Design (Google Material 3)](#gui--design-google-material-3)
5. [Tests & Benchmarks ausführen](#tests--benchmarks-ausführen)
6. [Pull Request Workflow](#pull-request-workflow)

---

## 🤝 Verhaltenskodex

Mit deiner Teilnahme an diesem Projekt verpflichtest du dich zur Einhaltung unseres [Code of Conduct](CODE_OF_CONDUCT.md). Bitte pflege einen respektvollen und konstruktiven Umgangston.

---

## 💡 Wie kann ich beitragen?

### Fehler melden (Bug Reports)
Wenn du einen Fehler findest, öffne bitte ein Issue mit unserem [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.md):
* Beschreibe das erwartete und das tatsächliche Verhalten.
* Gib die Schritte zur Reproduktion an.
* Nenne dein Betriebssystem, deine Python- und Rust-Version sowie Details zur Hardware (z. B. GPU-Modell).
* Füge relevante Log-Ausgaben oder Screenshots bei.

### Neue Features vorschlagen
Für neue Features oder algorithmische Erweiterungen nutze bitte das [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.md):
* Erkläre die Motivation und den wissenschaftlichen/klinischen Mehrwert.
* Beschreibe deinen Lösungsvorschlag und eventuelle Alternativen.

---

## 💻 Entwicklungsumgebung einrichten

### 1. Repository klonen
```bash
git clone https://github.com/noackjona-hash/JonaNoackIgnite.git
cd JonaNoackIgnite
```

### 2. Virtuelle Umgebung erstellen & Abhängigkeiten installieren
```bash
python -m venv venv
source venv/bin/activate  # Unter Linux/macOS
# bzw. venv\Scripts\activate unter Windows

pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Rust-Core kompilieren (optional, aber empfohlen)
```bash
maturin develop --release
```

### 4. Anwendung starten
```bash
python main.py
```

---

## 📐 Entwicklungsrichtlinien

### Python-Code
* **Code-Style:** Halte dich an PEP 8.
* **Typisierung:** Verwende Type Hints (`from typing import Optional, Any, ...`) für alle Funktionen und Methoden.
* **Datenschutz by Design:** Schreibe niemals ungehashte Patientendaten in Ausgabedateien oder Logs. Nutze stets `pseudonymize_patient()`.

### Rust-Core (`src/lib.rs`)
* **Fehlerbehandlung:** Verwende niemals `unwrap()` oder `expect()`. Alle Fehler müssen über `Result<T, String>` bzw. `PyResult<T>` an Python propagiert werden.
* **Zero-Copy:** Nutze `PyReadonlyArray2` und `PyArray2` für speichereffizienten Datenaustausch mit NumPy.
* **Parallelisierung:** Parallelisiere CPU-intensive Schleifen zeilenweise über `rayon`.

### GUI & Design (Google Material 3)
* Verwende stets die Design-Tokens und Farbkonstanten aus `gui/theme.py`.
* Trenne UI-Layout (`gui/views/`, `gui/components/`) strikt von Berechnungs- und Exportlogik (`image_processing.py`, `gui/services/`).

---

## 🧪 Tests & Benchmarks ausführen

Vor jedem Pull Request müssen alle Tests fehlerfrei durchlaufen:

```bash
# 1. Schnelle Unit- und GUI-Tests
pytest tests/

# 2. Wissenschaftliche Benchmarks & Paritätsvalidierung
python dataset_evaluator.py
```

---

## 🚀 Pull Request Workflow

1. Erstelle einen Feature-Branch von `main`:
   ```bash
   git checkout -b feature/mein-neues-feature
   ```
2. Nimm deine Änderungen vor und schreibe passende Tests in `tests/`.
3. Führe `pytest` aus und stelle sicher, dass alle Tests grün sind.
4. Erstelle einen Pull Request mit dem bereitgestellten [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
