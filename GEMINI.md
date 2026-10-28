# GEMINI.md — Antigravity & Gemini Agent Context

> Dieses Dokument verweist auf die zentrale Referenzdatei für alle AI-Agenten im Repository: **[AGENTS.md](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/AGENTS.md)**.

Bitte lies vor der Bearbeitung von Code in diesem Repository immer zuerst **[AGENTS.md](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/AGENTS.md)**. Es enthält:
1. **Projektübersicht & Mission:** Jugend forscht 2026, Früherkennung diabetischer Fußulzera, DIN EN ISO 13485 & Armstrong-Kriterien ($\Delta T \ge 2{,}2\,\text{K}$).
2. **Multi-Tier-Architektur:** Go (Walk / Win32) native Desktop-Workstation (`desktop/` mit echtem C++ / Qt / Win32 PACS-Flair), Go 1.24+ Bildverarbeitung (`core/`), 11 x86_64 AVX2 SIMD Assembler-Kernels, eingebettete Lua 5.1 Regel-Engine (`rules/`), Python 3.10+ Suite (`cli.py`, `image_processing.py`), SQLite Audit-Trail.
3. **Ordnerstruktur & Schlüsseldateien:** Vollständige Aufschlüsselung aller Ordner und Services.
4. **Klinische Algorithmen & 42-Stufen PAP:** 42-stufige Pipeline (dokumentiert in `docs/PROGRAMMABLAUFPLAN_42_STUFEN.md`), Otsu + Chamfer Distanzerosion, Morphologischer Top-Hat, MAD-Outlier Schwellwert, Frangi-Hesse Gefäßfilter, Pennes Bioheat Modell, Taylor & Palmer Angiosome.
5. **GUI-Regeln & Inspector-System:** Synchronisierter Dual-Viewport mit Live-Fadenkreuz, Vorhang-Split (Curtain Wipe), 4-Kategorien-Inspector (Diagnose, Anatomie, Signale, System).
6. **Build- & Testkommandos:** Go Tests, Go Desktop Workstation Build (`desktop/Ignite.exe`), Inno Setup Installer (`dist/IGNITE_Medical_Suite_v5.0.0_Setup.exe`).
