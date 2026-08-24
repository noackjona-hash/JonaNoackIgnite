# -*- coding: utf-8 -*-
"""tests/test_gui.py – Tests for IGNITE Material 3 GUI Components & Services."""

import os
import pytest
import numpy as np

def test_gui_imports():
    """Prüft, ob alle Module der neuen GUI-Architektur fehlerfrei importiert werden können."""
    from gui.theme import GOOGLE_BLUE, COLOR_BG_APP, BACKEND_STYLES
    assert GOOGLE_BLUE == "#1A73E8"
    assert "GPU" in BACKEND_STYLES

    from gui.components import TopAppBar, NavigationRail
    from gui.views import (
        DashboardView,
        SingleInspectView,
        AnalyticsView,
        PodologyView,
        BatchView,
        SettingsView,
    )
    from gui.widgets import ToastManager, CommandPalette, AboutModal, HelpModal, PatientExportModal
    from gui.services import ThermalProcessingService, ExportService
    from gui.main_window import IgniteApp

    assert IgniteApp is not None


def test_export_service_html_generation(tmp_path):
    """Testet die fehlerfreie Erzeugung eines Google Material HTML-Reports."""
    from gui.services.export_service import ExportService

    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": np.full((100, 100), 128, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "heat_diff": np.zeros((100, 100), dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "overlay_rgb": np.zeros((100, 100, 3), dtype=np.uint8),
        "asym_results": {"delta_t_c": 0.5, "is_asymmetric": False, "status": "Normal"},
        "zonal_stats": {
            "left": {"fore": 130.0, "mid": 125.0, "heel": 120.0, "exists": True},
            "right": {"fore": 131.0, "mid": 124.0, "heel": 121.0, "exists": True},
        },
        "general_hotspots": [],
        "body_pixel_count": 10000,
        "hotspot_pixel_count": 0,
        "hotspot_ratio": 0.0,
        "mean_pixel": 128.0,
        "std_pixel": 5.0,
        "max_pixel": 140.0,
        "min_pixel": 110.0,
        "t_min_c": 20.0,
        "t_max_c": 40.0,
        "backend": "Test Core",
        "analysis_mode": "Podologische Symmetrieanalyse",
        "params": {"sigma_k": 3.0, "tophat_factor": 0.05}
    }

    out_file = str(tmp_path / "test_report.html")
    res_path = ExportService.generate_html_report(
        dummy_result,
        record_id="Max Mustermann",
        operator="Tester",
        output_filepath=out_file
    )

    assert os.path.exists(res_path)
    with open(res_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IGNITE Medical Imaging Suite" in content
    assert "DSGVO Pseudonymisiert" in content
    assert "ANON-" in content  # SHA-256 Pseudonymisierung
    assert "3-Zonen-Symmetrievergleich" in content


def test_batch_summary_html_generation(tmp_path):
    """Testet die Erzeugung des Batch-Zusammenfassungsberichts."""
    from gui.services.export_service import ExportService

    items = [
        {
            "filepath": "/path/to/img1.jpg",
            "hotspot_count": 0,
            "delta_t_c": 0.4,
            "status_text": "Unauffällig",
            "is_warning": False,
            "report_filename": "report_img1.html"
        },
        {
            "filepath": "/path/to/img2.jpg",
            "hotspot_count": 250,
            "delta_t_c": 2.8,
            "status_text": "Auffällig",
            "is_warning": True,
            "report_filename": "report_img2.html"
        }
    ]

    out_file = ExportService.generate_batch_summary_html(items, str(tmp_path))
    assert os.path.exists(out_file)
    with open(out_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IGNITE Serienuntersuchungs-Bericht" in content
    assert "img1.jpg" in content
    assert "img2.jpg" in content


def test_full_gui_lifecycle():
    """Testet die Initialisierung aller Views, State-Verteilung und Tab-Wechsel."""
    import customtkinter as ctk
    from gui.main_window import IgniteApp

    root = ctk.CTk()
    root.withdraw()

    app = IgniteApp(root)
    assert len(app.views) == 6

    # Test-Daten an alle Views verteilen
    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": np.full((80, 80), 120, dtype=np.uint8),
        "body_mask": np.full((80, 80), 255, dtype=np.uint8),
        "heat_diff": np.zeros((80, 80), dtype=np.uint8),
        "hotspot_mask": np.zeros((80, 80), dtype=np.uint8),
        "overlay_rgb": np.zeros((80, 80, 3), dtype=np.uint8),
        "overlay_bgr": np.zeros((80, 80, 3), dtype=np.uint8),
        "asym_results": {"delta_t_c": 0.4, "is_asymmetric": False, "status": "Normal"},
        "zonal_stats": {
            "left": {"fore": 130.0, "mid": 125.0, "heel": 120.0, "exists": True, "bbox": (5, 5, 30, 70)},
            "right": {"fore": 131.0, "mid": 124.0, "heel": 121.0, "exists": True, "bbox": (45, 5, 30, 70)},
        },
        "general_hotspots": [{"index": 1, "area": 120, "mean_raw": 190.0, "max_raw": 220.0, "bbox": (10, 10, 20, 20)}],
        "body_pixel_count": 6400,
        "hotspot_pixel_count": 120,
        "hotspot_ratio": 1.875,
        "mean_pixel": 125.0,
        "std_pixel": 8.0,
        "max_pixel": 220.0,
        "min_pixel": 90.0,
        "t_min_c": 20.0,
        "t_max_c": 40.0,
        "backend": "Test Core",
        "analysis_mode": "Podologische Symmetrieanalyse",
        "params": {"sigma_k": 3.0, "tophat_factor": 0.05}
    }

    app._apply_pipeline_results(dummy_result)

    # Durch alle Views wechseln
    for view_key in ["dashboard", "single", "analytics", "podology", "settings", "batch"]:
        app.switch_view(view_key)
        assert app.current_view_key == view_key

    # Palette wechseln
    app._on_palette_changed("Inferno")
    assert app.palette_name == "Inferno"

    # Theme wechseln
    app.toggle_appearance_mode()

    root.destroy()

