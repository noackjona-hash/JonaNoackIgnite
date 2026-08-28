# -*- coding: utf-8 -*-
"""scripts/bump_version.py – Centralized Version Automation Tool for IGNITE.

Usage:
    python scripts/bump_version.py patch          # 3.3.0 -> 3.3.1
    python scripts/bump_version.py minor          # 3.3.0 -> 3.4.0
    python scripts/bump_version.py major          # 3.3.0 -> 4.0.0
    python scripts/bump_version.py 3.5.0          # Explicit version
    python scripts/bump_version.py patch --dry-run
    python scripts/bump_version.py minor --git    # Updates files, creates git commit & tag
"""

from __future__ import annotations
import os
import sys
import re
import json
import argparse
import subprocess
from pathlib import Path
from typing import Tuple, List

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_current_version() -> str:
    """Liest die kanonische Version aus der VERSION-Datei oder pyproject.toml."""
    ver_file = REPO_ROOT / "VERSION"
    if ver_file.exists():
        v = ver_file.read_text(encoding="utf-8").strip()
        if v:
            return v

    pyproject_file = REPO_ROOT / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text(encoding="utf-8")
        m = re.search(r'version\s*=\s*"([^"]+)"', content)
        if m:
            return m.group(1)

    return "3.3.0"


def parse_semver(ver_str: str) -> Tuple[int, int, int, str]:
    """Zerlegt einen SemVer-String in (major, minor, patch, prerelease)."""
    cleaned = ver_str.strip().lstrip("vV")
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-.]([a-zA-Z0-9.]+))?$", cleaned)
    if not m:
        nums = [int(n) for n in re.findall(r"\d+", cleaned)]
        while len(nums) < 3:
            nums.append(0)
        return (nums[0], nums[1], nums[2], "")
    
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4) or ""


def calculate_next_version(current: str, action: str) -> str:
    """Berechnet die nächste Versionsnummer basierend auf der Aktion."""
    major, minor, patch, _ = parse_semver(current)
    act = action.lower().strip()

    if act == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif act == "minor":
        return f"{major}.{minor + 1}.0"
    elif act == "major":
        return f"{major + 1}.0.0"
    else:
        # Explizite Version übergeben
        new_v = action.strip().lstrip("vV")
        # Validieren
        parse_semver(new_v)
        return new_v


def update_file_regex(file_path: Path, pattern: str, replacement: str, dry_run: bool = False) -> bool:
    """Ersetzt Text in einer Datei mittels Regex und gibt True zurück, wenn Änderungen vorgenommen wurden."""
    if not file_path.exists():
        return False

    content = file_path.read_text(encoding="utf-8")
    new_content, count = re.subn(pattern, replacement, content)
    if count > 0 and new_content != content:
        if not dry_run:
            file_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def bump_all_files(new_version: str, old_version: str, dry_run: bool = False) -> List[str]:
    """Aktualisiert alle Projekt-Manifeste auf die neue Version."""
    updated: List[str] = []

    # 1. VERSION (SSOT)
    ver_file = REPO_ROOT / "VERSION"
    if not dry_run:
        ver_file.write_text(f"{new_version}\n", encoding="utf-8")
    updated.append("VERSION")

    # 2. pyproject.toml
    if update_file_regex(
        REPO_ROOT / "pyproject.toml",
        r'(version\s*=\s*")[^"]+(")',
        rf'\g<1>{new_version}\g<2>',
        dry_run
    ):
        updated.append("pyproject.toml")

    # 3. Cargo.toml
    if update_file_regex(
        REPO_ROOT / "Cargo.toml",
        r'(\[package\][\s\S]*?version\s*=\s*")[^"]+(")',
        rf'\g<1>{new_version}\g<2>',
        dry_run
    ):
        updated.append("Cargo.toml")

    # 4. settings.json
    settings_file = REPO_ROOT / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
            data["APP_VERSION"] = new_version
            if not dry_run:
                settings_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
            updated.append("settings.json")
        except Exception:
            pass

    # 5. config.py
    if update_file_regex(
        REPO_ROOT / "config.py",
        r'("APP_VERSION":\s*")[^"]+(")',
        rf'\g<1>{new_version}\g<2>',
        dry_run
    ):
        updated.append("config.py")

    # 6. installer/ignite_installer.iss
    iss_file = REPO_ROOT / "installer" / "ignite_installer.iss"
    if iss_file.exists():
        update_file_regex(
            iss_file,
            r'(#define AppVersion\s*")[^"]+(")',
            rf'\g<1>{new_version}\g<2>',
            dry_run
        )
        update_file_regex(
            iss_file,
            r'(AppVersion\s*=\s*)[^\r\n]+',
            rf'\g<1>{new_version}',
            dry_run
        )
        update_file_regex(
            iss_file,
            r'(VersionInfoVersion\s*=\s*)[^\r\n]+',
            rf'\g<1>{new_version}',
            dry_run
        )
        update_file_regex(
            iss_file,
            r'(VersionInfoProductVersion\s*=\s*)[^\r\n]+',
            rf'\g<1>{new_version}',
            dry_run
        )
        update_file_regex(
            iss_file,
            r'(OutputBaseFilename\s*=\s*IGNITE_Setup_v)[^\r\n]+',
            rf'\g<1>{new_version}',
            dry_run
        )
        updated.append("installer/ignite_installer.iss")

    # 7. LICENSE
    if update_file_regex(
        REPO_ROOT / "LICENSE",
        r'(Version\s*)[0-9.]+(\s*\(Institutional)',
        rf'\g<1>{new_version}\g<2>',
        dry_run
    ):
        updated.append("LICENSE")

    # 8. scripts/build_setup.ps1
    if update_file_regex(
        REPO_ROOT / "scripts" / "build_setup.ps1",
        r'(IGNITE Core v)[0-9.]+(\s*–\s*Rust Build)',
        rf'\g<1>{new_version}\g<2>',
        dry_run
    ):
        updated.append("scripts/build_setup.ps1")

    # 9. ignite-landing/index.html
    landing_html = REPO_ROOT / "ignite-landing" / "index.html"
    if landing_html.exists():
        update_file_regex(
            landing_html,
            r'(IGNITE_Setup_v)[0-9.]+(\.exe)',
            rf'\g<1>{new_version}\g<2>',
            dry_run
        )
        update_file_regex(
            landing_html,
            r'(<span>Version\s*)[0-9.]+(</span>)',
            rf'\g<1>{new_version}\g<2>',
            dry_run
        )
        updated.append("ignite-landing/index.html")

    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatische Versionsverwaltung für IGNITE Medical Imaging Suite.")
    parser.add_argument(
        "action",
        nargs="?",
        default="current",
        help="Aktion: 'patch', 'minor', 'major', explizite Version (z. B. '3.4.0') oder 'current'"
    )
    parser.add_argument("--dry-run", action="store_true", help="Änderungen nur simulieren, ohne Dateien zu schreiben.")
    parser.add_argument("--git", action="store_true", help="Erstellt nach dem Bump automatisch einen Git-Commit und Git-Tag.")

    args = parser.parse_args()

    curr_ver = read_current_version()

    if args.action == "current":
        print(f"Aktuelle IGNITE Version: v{curr_ver}")
        return

    new_ver = calculate_next_version(curr_ver, args.action)

    print(f"\n=======================================================")
    print(f"  IGNITE Versions-Automatisierung")
    print(f"  Version: v{curr_ver} -> v{new_ver}")
    if args.dry_run:
        print(f"  [DRY-RUN MODUS] Keine Dateien werden veraendert.")
    print(f"=======================================================\n")

    updated_files = bump_all_files(new_ver, curr_ver, dry_run=args.dry_run)

    for f in updated_files:
        print(f"  [OK] Aktualisiert: {f}")

    if not args.dry_run:
        print(f"\n[OK] Alle Dateien erfolgreich auf v{new_ver} aktualisiert.")

        if args.git:
            print("\nErstelle Git-Commit und Git-Tag...")
            try:
                subprocess.run(["git", "add", "."], check=True, cwd=REPO_ROOT)
                subprocess.run(["git", "commit", "-m", f"chore(release): v{new_ver}"], check=True, cwd=REPO_ROOT)
                subprocess.run(["git", "tag", f"v{new_ver}"], check=True, cwd=REPO_ROOT)
                print(f"[OK] Git-Commit 'chore(release): v{new_ver}' und Tag 'v{new_ver}' erstellt!")
                print(f"Tipp: Push mit 'git push origin main --tags' ausfuehren.")
            except Exception as e:
                print(f"[ERROR] Git-Operation fehlgeschlagen: {e}")


if __name__ == "__main__":
    main()
