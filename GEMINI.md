# GEMINI.md — Antigravity & Gemini Agent Context

> Dieses Dokument verweist auf die zentrale Referenzdatei für alle AI-Agenten im Repository: **[AGENTS.md](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/AGENTS.md)**.

Bitte lies vor der Bearbeitung von Code in diesem Repository immer zuerst **[AGENTS.md](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/AGENTS.md)**. Es enthält:
1. **Projektübersicht & Mission:** Jugend forscht 2026, Früherkennung diabetischer Fußulzera, DIN EN ISO 13485 & Armstrong-Kriterien ($\Delta T \ge 2{,}2\,\text{K}$).
2. **Multi-Tier-Architektur:** Go (Wails v2) native Desktop-Workstation (`desktop-go/`), C# .NET 10 WPF GUI (`desktop/`), Go 1.24+ Bildverarbeitung (`core/`), 6 x86_64 AVX2 SIMD Assembler-Kernels, eingebettete Lua 5.1 Regel-Engine (`rules/`), Python 3.10+ Suite (`cli.py`, `image_processing.py`), SQLite Audit-Trail.
3. **Ordnerstruktur & Schlüsseldateien:** Vollständige Aufschlüsselung aller Ordner und Services.
4. **Klinische Algorithmen & 42-Stufen PAP:** 42-stufige Pipeline (dokumentiert in `docs/PROGRAMMABLAUFPLAN_42_STUFEN.md`), Otsu + Chamfer Distanzerosion, Morphologischer Top-Hat, MAD-Outlier Schwellwert, Frangi-Hesse Gefäßfilter, Pennes Bioheat Modell, Taylor & Palmer Angiosome, Orthopädisches Goniometer.
5. **GUI-Regeln & Inspector-Tabs:** Verbindliche Richtlinie zur Nutzung von `SelectInspectorTab(tab)` statt Integer-Indizes.
6. **Build- & Testkommandos:** Go Tests, .NET 10 Build, Go Desktop Workstation Build, Inno Setup Installer.
