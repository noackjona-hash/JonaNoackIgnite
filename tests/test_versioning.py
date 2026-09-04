# -*- coding: utf-8 -*-
"""tests/test_versioning.py – Unit tests for automated versioning and manifest consistency."""

import os
import json
import re
from pathlib import Path
import pytest

from scripts.bump_version import (
    read_current_version,
    parse_semver,
    calculate_next_version,
    bump_all_files,
    REPO_ROOT
)
import config


def test_version_files_consistency():
    """Stellt sicher, dass alle Projekt-Manifeste exakt die gleiche Version definieren."""
    canonical_ver = read_current_version()
    assert canonical_ver != ""

    # 1. VERSION Datei
    ver_path = REPO_ROOT / "VERSION"
    assert ver_path.exists()
    assert ver_path.read_text(encoding="utf-8").strip() == canonical_ver

    # 2. pyproject.toml
    pyproject_content = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m_p = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
    assert m_p is not None
    assert m_p.group(1) == canonical_ver

    # 3. Cargo.toml
    cargo_content = (REPO_ROOT / "Cargo.toml").read_text(encoding="utf-8")
    m_c = re.search(r'\[package\][\s\S]*?version\s*=\s*"([^"]+)"', cargo_content)
    assert m_c is not None
    assert m_c.group(1) == canonical_ver

    # 4. settings.json
    settings_data = json.loads((REPO_ROOT / "settings.json").read_text(encoding="utf-8"))
    assert settings_data.get("APP_VERSION") == canonical_ver

    # 5. config.APP_VERSION
    assert config.APP_VERSION == canonical_ver
    assert config.CANONICAL_APP_VERSION == canonical_ver


def test_stale_settings_json_overwritten_by_app_version(tmp_path, monkeypatch):
    """Prüft, dass ein veralteter Versionsstring in settings.json automatisch mit der echten App-Version synchronisiert wird."""
    temp_settings = tmp_path / "settings.json"
    temp_settings.write_text(json.dumps({"APP_VERSION": "3.2.0", "DEFAULT_SIGMA_K": 3.0}), encoding="utf-8")
    
    monkeypatch.setattr(config, "SETTINGS_FILE", str(temp_settings))
    
    loaded = config.load_settings()
    assert loaded["APP_VERSION"] == config.APP_VERSION
    assert loaded["APP_VERSION"] == read_current_version()
    
    # Sicherstellen, dass die Datei auf der Festplatte auch aktualisiert wurde
    disk_data = json.loads(temp_settings.read_text(encoding="utf-8"))
    assert disk_data["APP_VERSION"] == config.APP_VERSION


def test_get_app_version_resolves_correctly(tmp_path, monkeypatch):
    """Testet die dynamische Auflösung von get_app_version aus verschiedenen Pfaden."""
    # Testfall: VERSION-Datei existiert in einem temporären Verzeichnis
    fake_ver_file = tmp_path / "VERSION"
    fake_ver_file.write_text("9.9.9\n", encoding="utf-8")
    
    # Mocke sys._MEIPASS
    monkeypatch.setattr(config.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.get_app_version() == "9.9.9"


def test_parse_semver_variants():
    assert parse_semver("3.3.0") == (3, 3, 0, "")
    assert parse_semver("v3.3.0") == (3, 3, 0, "")
    assert parse_semver("4.0.1-rc2") == (4, 0, 1, "rc2")
    assert parse_semver("10.20.30") == (10, 20, 30, "")


def test_calculate_next_version():
    assert calculate_next_version("3.3.0", "patch") == "3.3.1"
    assert calculate_next_version("3.3.0", "minor") == "3.4.0"
    assert calculate_next_version("3.3.0", "major") == "4.0.0"
    assert calculate_next_version("3.3.0", "3.3.5") == "3.3.5"
    assert calculate_next_version("3.3.0", "v3.5.0") == "3.5.0"


def test_bump_all_files_dry_run():
    curr = read_current_version()
    next_ver = calculate_next_version(curr, "minor")
    updated = bump_all_files(next_ver, curr, dry_run=True)
    assert "VERSION" in updated
    assert "pyproject.toml" in updated
    assert "Cargo.toml" in updated
    assert "settings.json" in updated
    assert "config.py" in updated
    assert "installer/ignite_installer.iss" in updated

    # Sicherstellen, dass im dry_run nichts überschrieben wurde
    assert read_current_version() == curr


def test_no_stale_hardcoded_version_in_core_modules():
    """Stellt sicher, dass keine veralteten 3.3.0 Hardcodings im UI- und Startup-Code verbleiben."""
    main_py = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
    assert "v3.3.0 · Core" not in main_py
    assert "v{config.APP_VERSION} · Core" in main_py

    dialogs_py = (REPO_ROOT / "gui" / "widgets" / "dialogs.py").read_text(encoding="utf-8")
    assert '"3.3.0"' not in dialogs_py
    assert "'3.3.0'" not in dialogs_py

