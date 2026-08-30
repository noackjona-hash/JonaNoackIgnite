# -*- coding: utf-8 -*-
"""tests/test_update_service.py – Unit tests for automated GitHub Releases updater."""

import os
import sys
import json
import io
import tempfile
import threading
import unittest.mock as mock
import pytest

from gui.services.update_service import (
    parse_version,
    is_version_newer,
    is_frozen_app,
    UpdateService,
    UpdateInfo
)


def test_parse_version_standard():
    assert parse_version("3.2.0") == (3, 2, 0)
    assert parse_version("v3.2.0") == (3, 2, 0)
    assert parse_version("V3.2.1") == (3, 2, 1)
    assert parse_version("v3.10.5") == (3, 10, 5)


def test_parse_version_complex_strings():
    assert parse_version("v3.2.0-rc1") == (3, 2, 0, 1)
    assert parse_version("3.2") == (3, 2)
    assert parse_version("") == (0, 0, 0)
    assert parse_version(None) == (0, 0, 0)


def test_is_version_newer():
    # Neuere Versionen
    assert is_version_newer("3.2.1", "3.2.0") is True
    assert is_version_newer("v3.3.0", "3.2.0") is True
    assert is_version_newer("4.0.0", "3.2.0") is True
    assert is_version_newer("3.2.0.1", "3.2.0") is True

    # Ältere oder gleiche Versionen
    assert is_version_newer("3.2.0", "3.2.0") is False
    assert is_version_newer("v3.2.0", "3.2.0") is False
    assert is_version_newer("3.1.9", "3.2.0") is False
    assert is_version_newer("2.9.9", "3.2.0") is False


def test_is_frozen_app_detection():
    # In regulärer Testumgebung (venv) ist frozen False
    assert is_frozen_app() is False


def test_check_for_updates_mock_success_windows():
    mock_payload = {
        "tag_name": "v3.4.0",
        "name": "IGNITE Medical Imaging Suite v3.4.0",
        "body": "### Was ist neu in v3.4.0:\n- Automatischer Updater integriert\n- Beschleunigte Rust-Engine",
        "html_url": "https://github.com/noackjona-hash/JonaNoackIgnite/releases/tag/v3.4.0",
        "published_at": "2026-08-28T12:00:00Z",
        "assets": [
            {
                "name": "IGNITE_Setup_v3.4.0.exe",
                "browser_download_url": "https://github.com/noackjona-hash/JonaNoackIgnite/releases/download/v3.4.0/IGNITE_Setup_v3.4.0.exe",
                "size": 25600000
            },
            {
                "name": "IGNITE_Linux_x86_64.tar.gz",
                "browser_download_url": "https://github.com/noackjona-hash/JonaNoackIgnite/releases/download/v3.4.0/IGNITE_Linux_x86_64.tar.gz",
                "size": 31200000
            }
        ]
    }

    mock_response = mock.MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        info = UpdateService.check_for_updates(current_version="3.3.0")
        assert info is not None
        assert info.version == "3.4.0"
        assert info.tag_name == "v3.4.0"
        assert info.is_newer is True
        assert "Automatischer Updater" in info.release_notes
        if sys.platform.startswith("win"):
            assert info.asset_name == "IGNITE_Setup_v3.4.0.exe"
            assert "IGNITE_Setup_v3.4.0.exe" in info.asset_url
            assert info.asset_size == 25600000


def test_check_for_updates_when_already_latest():
    mock_payload = {
        "tag_name": "v3.3.0",
        "name": "IGNITE v3.3.0",
        "body": "Aktuelle Version",
        "html_url": "https://github.com/noackjona-hash/JonaNoackIgnite/releases/tag/v3.3.0",
        "published_at": "2026-08-28T10:00:00Z",
        "assets": []
    }

    mock_response = mock.MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(mock_payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        info = UpdateService.check_for_updates(current_version="3.3.0")
        assert info is not None
        assert info.is_newer is False


def test_check_for_updates_network_error():
    with mock.patch("urllib.request.urlopen", side_effect=Exception("Connection timed out")):
        info = UpdateService.check_for_updates(current_version="3.3.0")
        assert info is None


def test_download_update_asset_with_progress():
    dummy_data = b"DUMMY_INSTALLER_BINARY_CONTENT_" * 1024  # 32 KB
    mock_response = mock.MagicMock()
    mock_response.headers = {"content-length": str(len(dummy_data))}
    
    stream = io.BytesIO(dummy_data)
    mock_response.read = stream.read
    mock_response.__enter__.return_value = mock_response

    progress_records = []

    def _on_progress(pct, current_b, total_b):
        progress_records.append((pct, current_b, total_b))

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        saved_file = UpdateService.download_update_asset(
            asset_url="https://example.com/fake_setup.exe",
            dest_filename="test_mock_setup.exe",
            progress_callback=_on_progress
        )

        assert os.path.exists(saved_file)
        assert os.path.getsize(saved_file) == len(dummy_data)
        assert len(progress_records) > 0
        assert progress_records[-1][0] == 1.0  # 100%

        # Aufräumen
        try:
            os.remove(saved_file)
        except Exception:
            pass


def test_download_update_asset_cancellation():
    dummy_data = b"A" * 100000
    mock_response = mock.MagicMock()
    mock_response.headers = {"content-length": str(len(dummy_data))}
    stream = io.BytesIO(dummy_data)
    mock_response.read = stream.read
    mock_response.__enter__.return_value = mock_response

    cancel_evt = threading.Event()
    cancel_evt.set()  # Sofort abgebrochen

    with mock.patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(InterruptedError):
            UpdateService.download_update_asset(
                asset_url="https://example.com/fake_setup.exe",
                dest_filename="test_cancelled_setup.exe",
                cancel_event=cancel_evt
            )


def test_update_modal_dialog_rendering(app_root):
    from gui.widgets.dialogs import UpdateModal

    if app_root is None:
        pytest.skip("Headless Tkinter nicht verfügbar")

    info_newer = UpdateInfo(
        version="3.4.0",
        tag_name="v3.4.0",
        release_name="IGNITE v3.4.0",
        release_notes="### Changelog\n- Neuer Algorithmus",
        html_url="https://github.com",
        asset_name="IGNITE_Setup_v3.4.0.exe",
        asset_url="https://github.com/.../IGNITE_Setup_v3.4.0.exe",
        asset_size=25000000,
        published_at="2026-08-28",
        is_newer=True
    )
    modal = UpdateModal(app_root, update_info=info_newer)
    assert modal is not None
    assert modal.title() == "IGNITE – Software-Update"
    modal.destroy()

    info_current = UpdateInfo(
        version="3.3.2",
        tag_name="v3.3.2",
        release_name="IGNITE v3.3.2",
        release_notes="",
        html_url="https://github.com",
        asset_name="IGNITE_Setup_v3.3.2.exe",
        asset_url="https://github.com/.../IGNITE_Setup_v3.3.2.exe",
        asset_size=25000000,
        published_at="2026-08-28",
        is_newer=False
    )
    modal2 = UpdateModal(app_root, update_info=info_current)
    assert modal2 is not None
    modal2.destroy()


def test_apply_update_windows_flow(tmp_path):
    """Testet, dass apply_update unter Windows mit Force-Close-Parametern gestartet und der Prozess beendet wird."""
    dummy_installer = tmp_path / "IGNITE_Setup_test.exe"
    dummy_installer.write_text("DUMMY_EXE_CONTENT", encoding="utf-8")

    with mock.patch("sys.platform", "win32"), \
         mock.patch("subprocess.Popen") as mock_popen, \
         mock.patch("os._exit") as mock_exit, \
         mock.patch("time.sleep"):

        UpdateService.apply_update(str(dummy_installer), is_silent=False)

        assert mock_popen.called
        call_args = mock_popen.call_args[0][0]
        assert str(dummy_installer) in call_args[0]
        assert "/FORCECLOSEAPPLICATIONS" in call_args
        assert "/CLOSEAPPLICATIONS" in call_args
        assert "/RESTARTAPPLICATIONS" in call_args
        assert "/SP-" in call_args

        # Sicherstellen, dass os._exit(0) aufgerufen wurde
        mock_exit.assert_called_once_with(0)


def test_apply_update_file_not_found():
    """Testet, dass bei nicht vorhandener Datei FileNotFoundError ausgelöst wird."""
    with pytest.raises(FileNotFoundError):
        UpdateService.apply_update("non_existent_setup_12345.exe")


