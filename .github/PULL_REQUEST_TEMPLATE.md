## 📌 Zusammenfassung der Änderungen
Eine kurze und präzise Beschreibung, was dieser PR ändert, behebt oder hinzufügt.

---

## 🏷️ Art der Änderung
- [ ] 🐛 Bugfix (Fehlerbehebung ohne Breaking Change)
- [ ] ✨ Neues Feature (Funktionale Erweiterung)
- [ ] ⚡ Performance-Optimierung (z. B. Rust-Core, Rayon, Vektor-Operationen)
- [ ] 🔬 Wissenschaftliche Validierung / Benchmarks (JuFo Datensätze, Metriken)
- [ ] 🎨 GUI / UX Anpassung (Google Material 3 Styling, Dialoge)
- [ ] 📝 Dokumentation / Paper-Aktualisierung
- [ ] 🧹 Refactoring / Code-Bereinigung

---

## 🧪 Durchgeführte Tests & Validierung
- [ ] `pytest tests/` läuft lokal ohne Fehler durch.
- [ ] Parität zwischen Python-, Rust- und GPU-Backend verifiziert (sofern relevant).
- [ ] Keine Regression bei Dice-Score oder Sensitivität auf dem Benchmark-Datensatz (`dataset_evaluator.py`).
- [ ] Manuelle Prüfung in der Benutzeroberfläche (`python main.py`).

---

## 📸 Screenshots / Benchmarks (falls relevant)
*Vorher vs. Nachher (Screenshots der GUI oder Benchmark-Ergebnisse einfügen)*

---

## 🔒 Datenschutz & Compliance
- [ ] Keine Klartext-Patientendaten in Logs oder Berichten (DSGVO SHA-256 Pseudonymisierung gewahrt).
