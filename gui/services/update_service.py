# -*- coding: utf-8 -*-
"""gui/services/update_service.py – Automated GitHub Releases Updater for IGNITE.

Provides:
1. GitHub REST API release querying (latest release, tags, assets).
2. Semantic version comparison and release notes extraction.
3. Chunked background downloading with live progress and cancel support.
4. Silent or interactive Inno Setup installer execution and app restart under Windows.
5. Environment detection (installed frozen binary vs. developer source mode).
"""

from __future__ import annotations
import os
import sys
import json
import re
import time
import urllib.request
import urllib.error
import tempfile
import subprocess
import threading
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Dict, Any, Tuple


@dataclass
class UpdateInfo:
    """Metadaten zu einem verfügbaren Release."""
    version: str
    tag_name: str
    release_name: str
    release_notes: str
    html_url: str
    asset_name: str
    asset_url: str
    asset_size: int
    published_at: str
    is_newer: bool = True


def parse_version(v_str: str) -> Tuple[int, ...]:
    """Konvertiert einen Versionsstring (z. B. 'v3.2.1', '3.2.0-rc1') in ein vergleichbares Tupel."""
    if not v_str:
        return (0, 0, 0)
    cleaned = v_str.strip().lstrip("vV")
    # Nur Ziffernblöcke extrahieren
    parts = re.findall(r"\d+", cleaned)
    if not parts:
        return (0, 0, 0)
    return tuple(int(p) for p in parts)


def is_version_newer(remote_version: str, current_version: str) -> bool:
    """Prüft, ob remote_version strikt neuer als current_version ist."""
    r_tuple = parse_version(remote_version)
    c_tuple = parse_version(current_version)
    
    # Länge angleichen für präzisen Vergleich (z. B. (3, 2) vs (3, 2, 0))
    max_len = max(len(r_tuple), len(c_tuple))
    r_norm = r_tuple + (0,) * (max_len - len(r_tuple))
    c_norm = c_tuple + (0,) * (max_len - len(c_tuple))
    
    return r_norm > c_norm


def is_frozen_app() -> bool:
    """Gibt True zurück, wenn die Anwendung als kompilierte Binary (PyInstaller) läuft."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


class UpdateService:
    """Service zur Abfrage, zum Download und zur Installation von Software-Updates."""

    DEFAULT_REPO = "noackjona-hash/JonaNoackIgnite"
    USER_AGENT = "IGNITE-Medical-Imaging-Suite-Updater"

    @classmethod
    def check_for_updates(
        cls,
        current_version: str = "3.3.0",
        repo: str = DEFAULT_REPO,
        timeout: float = 8.0
    ) -> Optional[UpdateInfo]:
        """Fragt das neueste Release von GitHub ab und prüft auf Updates."""
        api_url = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": cls.USER_AGENT,
                "Accept": "application/vnd.github.v3+json",
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    logging.warning(f"GitHub API meldete Status {resp.status}")
                    return None
                data: Dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logging.warning(f"HTTP-Fehler bei Update-Prüfung ({api_url}): {e.code} {e.reason}")
            return None
        except Exception as e:
            logging.debug(f"Update-Prüfung fehlgeschlagen: {e}")
            return None

        tag_name = data.get("tag_name", "")
        remote_ver_str = tag_name.lstrip("vV")
        release_name = data.get("name") or tag_name
        release_notes = data.get("body", "").strip()
        html_url = data.get("html_url", f"https://github.com/{repo}/releases")
        published_at = data.get("published_at", "")

        is_newer = is_version_newer(remote_ver_str, current_version)

        # Passendes Asset für das aktuelle Betriebssystem suchen
        assets = data.get("assets", [])
        chosen_asset_name = ""
        chosen_asset_url = ""
        chosen_asset_size = 0

        is_win = sys.platform.startswith("win")

        for a in assets:
            name = a.get("name", "")
            dl_url = a.get("browser_download_url", "")
            size = a.get("size", 0)

            if is_win and name.endswith(".exe"):
                chosen_asset_name = name
                chosen_asset_url = dl_url
                chosen_asset_size = size
                break
            elif not is_win and (name.endswith(".tar.gz") or name.endswith(".AppImage") or name.endswith(".deb")):
                chosen_asset_name = name
                chosen_asset_url = dl_url
                chosen_asset_size = size
                break

        # Fallback falls kein spezifisches OS-Asset gefunden wurde: erstes Asset
        if not chosen_asset_url and assets:
            first = assets[0]
            chosen_asset_name = first.get("name", "")
            chosen_asset_url = first.get("browser_download_url", "")
            chosen_asset_size = first.get("size", 0)

        return UpdateInfo(
            version=remote_ver_str,
            tag_name=tag_name,
            release_name=release_name,
            release_notes=release_notes,
            html_url=html_url,
            asset_name=chosen_asset_name,
            asset_url=chosen_asset_url,
            asset_size=chosen_asset_size,
            published_at=published_at,
            is_newer=is_newer
        )

    @classmethod
    def download_update_asset(
        cls,
        asset_url: str,
        dest_filename: Optional[str] = None,
        progress_callback: Optional[Callable[[float, int, int], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> str:
        """Lädt ein Release-Asset blockweise mit Fortschritts-Callbacks herunter."""
        if not asset_url:
            raise ValueError("Keine Download-URL für das Release-Asset angegeben.")

        temp_dir = tempfile.gettempdir()
        if not dest_filename:
            dest_filename = os.path.basename(asset_url) or "IGNITE_Update_Setup.exe"

        dest_path = os.path.join(temp_dir, dest_filename)

        req = urllib.request.Request(asset_url, headers={"User-Agent": cls.USER_AGENT})
        
        with urllib.request.urlopen(req, timeout=30.0) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 64 * 1024  # 64 KB

            with open(dest_path, "wb") as f_out:
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise InterruptedError("Download durch Benutzer abgebrochen.")

                    chunk = response.read(block_size)
                    if not chunk:
                        break

                    f_out.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        pct = (downloaded / total_size) if total_size > 0 else 0.0
                        progress_callback(pct, downloaded, total_size)

        return dest_path

    @classmethod
    def apply_update(cls, installer_path: str, is_silent: bool = False) -> None:
        """Führt das heruntergeladene Setup-Programm aus und schließt die aktuelle App."""
        if not os.path.exists(installer_path):
            raise FileNotFoundError(f"Installer nicht gefunden: {installer_path}")

        if sys.platform.startswith("win"):
            # Inno Setup Parameter:
            # /SP- : Bestätigungsdialog vor Installation überspringen
            # /CLOSEAPPLICATIONS : Laufende App vor Überschreiben beenden
            # /RESTARTAPPLICATIONS : App nach erfolgreichem Update neu starten
            args = [installer_path, "/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
            if is_silent:
                args.append("/SILENT")

            logging.info(f"Starte Installer: {args}")
            # Subprocess unabhängig vom aktuellen Prozess abkoppeln
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

            subprocess.Popen(
                args,
                creationflags=flags,
                close_fds=True
            )
            # App sauber beenden
            time.sleep(0.5)
            sys.exit(0)
        else:
            # Linux: Dateimanager öffnen oder Berechtigung setzen
            try:
                os.chmod(installer_path, 0o755)
            except Exception:
                pass
            if installer_path.endswith(".tar.gz"):
                # Ordner mit heruntergeladener Datei öffnen
                subprocess.Popen(["xdg-open", os.path.dirname(installer_path)])
            else:
                subprocess.Popen([installer_path])
            sys.exit(0)
