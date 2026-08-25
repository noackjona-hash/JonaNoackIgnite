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


def test_export_service_pdf_generation(tmp_path):
    """Testet die fehlerfreie Erzeugung eines druckreifen A4 PDF-Reports."""
    from gui.services.export_service import ExportService

    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": np.full((100, 100), 128, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "heat_diff": np.zeros((100, 100), dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "overlay_rgb": np.full((100, 100, 3), 180, dtype=np.uint8),
        "asym_results": {"delta_t_c": 2.5, "is_asymmetric": True, "status": "Pathologisch"},
        "tsi_results": {"score": 5.8, "tier_name": "Stufe 2", "tier_desc": "Mäßige Hyperthermie", "color": "#DC2626"},
        "gradient_results": {"max_gradient": 85.0},
        "pca_results": {
            "left": {"exists": True, "angle_deg": 10.0, "arch_index": 0.23, "arch_type": "Normal", "arch_code": "normal"},
            "right": {"exists": True, "angle_deg": -8.0, "arch_index": 0.29, "arch_type": "Pes Planus", "arch_code": "planus"},
        },
        "zonal_stats": {
            "left": {"fore": 135.0, "mid": 125.0, "heel": 120.0, "arch_index": 0.23, "arch_type": "Normal", "exists": True},
            "right": {"fore": 120.0, "mid": 124.0, "heel": 121.0, "arch_index": 0.29, "arch_type": "Pes Planus", "exists": True},
        },
        "body_pixel_count": 10000,
        "hotspot_pixel_count": 150,
        "hotspot_ratio": 1.5,
        "mean_pixel": 128.0,
        "std_pixel": 5.0,
        "max_pixel": 160.0,
        "min_pixel": 110.0,
        "t_min_c": 20.0,
        "t_max_c": 40.0,
        "backend": "Test Core",
        "analysis_mode": "Podologische Symmetrieanalyse",
        "params": {"sigma_k": 3.0, "tophat_factor": 0.05}
    }

    out_file = str(tmp_path / "test_report.pdf")
    pdf_path = ExportService.generate_pdf_report(
        dummy_result,
        record_id="Max Mustermann",
        operator="Tester JuFo",
        notes="Auffällige Hyperthermie im Vorfuß links.",
        output_filepath=out_file
    )

    assert os.path.exists(pdf_path)
    assert os.path.getsize(pdf_path) > 1000  # Valide PDF-Datei


def test_export_service_multi_format(tmp_path):
    """Testet die universelle export_report Methode für PDF, HTML und Beide."""
    from gui.services.export_service import ExportService

    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": np.full((100, 100), 128, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "heat_diff": np.zeros((100, 100), dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "overlay_rgb": np.full((100, 100, 3), 180, dtype=np.uint8),
        "asym_results": {"delta_t_c": 0.5, "is_asymmetric": False},
        "zonal_stats": {},
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
        "analysis_mode": "Klinische Allgemeinanalyse",
        "params": {"sigma_k": 3.0}
    }

    # 1. Nur PDF
    res_pdf = ExportService.export_report(dummy_result, format_choice="PDF (.pdf)")
    assert len(res_pdf) == 1
    assert res_pdf[0].endswith(".pdf")

    # 2. Beide
    res_both = ExportService.export_report(dummy_result, format_choice="Beide (PDF + HTML)")
    assert len(res_both) == 2
    assert any(p.endswith(".pdf") for p in res_both)
    assert any(p.endswith(".html") for p in res_both)


def test_batch_summary_pdf_generation(tmp_path):
    """Testet die Erzeugung des Batch-Zusammenfassungsberichts als PDF."""
    from gui.services.export_service import ExportService

    items = [
        {"filepath": "/path/to/img1.jpg", "hotspot_count": 0, "delta_t_c": 0.4, "status_text": "Unauffällig", "is_warning": False},
        {"filepath": "/path/to/img2.jpg", "hotspot_count": 250, "delta_t_c": 2.8, "status_text": "Auffällig", "is_warning": True}
    ]

    pdf_out = ExportService.generate_batch_summary_pdf(items, str(tmp_path))
    assert os.path.exists(pdf_out)
    assert os.path.getsize(pdf_out) > 500


@pytest.fixture(scope="module")
def app_root():
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def test_full_gui_lifecycle(app_root):
    """Testet die Initialisierung aller Views, State-Verteilung und Tab-Wechsel."""
    from gui.main_window import IgniteApp

    app = IgniteApp(app_root)
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


def test_single_view_swipe_and_roi(app_root):
    """Testet den Swipe / Split-View Modus und ROI-Berechnungen im SingleInspectView."""
    from gui.views.single_view import SingleInspectView

    single_view = SingleInspectView(app_root, on_load_click=lambda: None)

    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": np.full((100, 100), 150, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "heat_diff": np.zeros((100, 100), dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "overlay_bgr": np.full((100, 100, 3), 200, dtype=np.uint8),
        "t_min_c": 20.0,
        "t_max_c": 40.0,
    }

    single_view.show_results(dummy_result)
    assert single_view.current_result is not None

    # Swipe-Modus umschalten
    single_view._on_view_mode_changed("Swipe-Split")
    assert single_view.is_split_view is True

    # Slider bewegen
    single_view._on_split_slider_moved(0.75)
    assert single_view.split_ratio == 0.75

    # Split-Image rendering testen
    img_a = single_view._get_stage_image("1. Originalbild")
    img_b = single_view._get_stage_image("4. Erkannte Hotspots (Rust)")
    merged = single_view._render_split_image(img_a, img_b, 0.5)
    assert merged.shape == (100, 100, 3)

    # Zurück zu Stufen
    single_view._on_view_mode_changed("Stufen")
    assert single_view.is_split_view is False

    # ROI Messung testen
    single_view.roi_box = (10, 10, 50, 50)
    single_view._compute_roi_stats(10, 10, 50, 50)
    assert single_view.roi_stats_rows["mean"].cget("text") != "--"

    # Messwerte kopieren
    single_view.copy_roi_stats()


def test_longitudinal_visit_comparison(app_root):
    """Testet die quantitative Berechnung von Baseline- vs. Follow-Up-Untersuchungen."""
    from gui.services.processing_service import ThermalProcessingService
    from gui.views.analytics_view import AnalyticsView

    analytics_view = AnalyticsView(app_root)

    # Baseline (z. B. Visit 1 mit akutem Hotspot)
    res_baseline = {
        "calibrated_original": np.full((100, 100), 160, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "t_min_c": 20.0,
        "t_max_c": 40.0,
    }
    res_baseline["hotspot_mask"][40:60, 40:60] = 255  # 400 px Hotspot

    # Follow-Up (z. B. Visit 2 nach 4 Wochen Therapie: abgekühlt und kleinerer Herd)
    res_followup = {
        "calibrated_original": np.full((100, 100), 140, dtype=np.uint8),
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "t_min_c": 20.0,
        "t_max_c": 40.0,
    }
    res_followup["hotspot_mask"][45:55, 45:55] = 255  # 100 px Hotspot (-75%)

    long_res = ThermalProcessingService.compare_longitudinal_visits(res_baseline, res_followup)
    assert long_res["delta_t_mean"] < 0.0  # Abkühlung
    assert long_res["area_pct_change"] < 0.0  # Flächenreduktion
    assert long_res["status_code"] == "regression"
    assert long_res["diff_map_bgr"].shape == (100, 100, 3)

    # Analytics View UI Verifikation
    analytics_view.show_results(res_baseline)
    analytics_view._apply_longitudinal_results(long_res, "/tmp/followup_visit2.png")
    assert "°C" in analytics_view.followup_stats_rows["delta_t"].cget("text")
    assert "%" in analytics_view.followup_stats_rows["area_change"].cget("text")


def test_podology_view_arch_index_and_zonal_warnings(app_root):
    """Testet die Darstellung von Cavanagh & Rodgers Arch Index und Zonen-Warnungen in PodologyView."""
    from gui.views.podology_view import PodologyView

    podology_view = PodologyView(app_root)

    dummy_result = {
        "t_min_c": 20.0,
        "t_max_c": 40.0,
        "asym_results": {"delta_t_c": 2.6, "is_asymmetric": True},
        "pca_results": {
            "left": {"exists": True, "angle_deg": 12.0},
            "right": {"exists": True, "angle_deg": -10.5},
        },
        "zonal_stats": {
            "left": {
                "fore": 34.0, "mid": 28.0, "heel": 27.0, "exists": True,
                "arch_index": 0.235, "arch_type": "Normales Längsgewölbe", "arch_code": "normal"
            },
            "right": {
                "fore": 31.0, "mid": 27.5, "heel": 26.8, "exists": True,
                "arch_index": 0.285, "arch_type": "Pes Planus (Senk-/Plattfuß / Charcot-Verdacht)", "arch_code": "planus"
            },
        },
        "overlay_rgb": np.full((100, 100, 3), 180, dtype=np.uint8),
    }

    podology_view.show_results(dummy_result)

    assert "Pathologische Asymmetrie" in podology_view.asym_status_lbl.cget("text")
    assert "0.235" in podology_view.arch_l_lbl.cget("text")
    assert "0.285" in podology_view.arch_r_lbl.cget("text")
    # Vorfuß-Differenz beträgt 3.0°C (> 2.2°C) -> sollte Warnsymbol enthalten
    assert "⚠️" in podology_view.zone_rows["fore"][2].cget("text")


def test_single_view_line_profile_transect(app_root):
    """Testet das 1D-Schnittlinien-Temperaturprofil (Transect) in SingleInspectView."""
    from gui.views.single_view import SingleInspectView

    single_view = SingleInspectView(app_root, on_load_click=lambda: None)

    # Erzeuge ein Test-Wärmebild mit einer Temperatur-Stufe (z. B. 25°C links, 35°C rechts)
    raw = np.full((100, 100), 100, dtype=np.uint8)
    raw[:, 50:] = 200

    dummy_result = {
        "image_path": "test-data/bild (1).jpeg",
        "calibrated_original": raw,
        "body_mask": np.full((100, 100), 255, dtype=np.uint8),
        "heat_diff": np.zeros((100, 100), dtype=np.uint8),
        "hotspot_mask": np.zeros((100, 100), dtype=np.uint8),
        "overlay_bgr": np.full((100, 100, 3), 200, dtype=np.uint8),
        "t_min_c": 20.0,
        "t_max_c": 40.0,
    }

    single_view.show_results(dummy_result)

    # Umschalten auf Linienprofil-Modus
    single_view._on_view_mode_changed("Linienprofil")
    assert single_view.is_profile_mode is True

    # 1D-Linie von (10, 50) nach (90, 50) berechnen
    single_view._compute_line_profile((10, 50), (90, 50))

    assert len(single_view.profile_temps) == 81  # 81 Stützpunkte entlang 80 px
    assert single_view.profile_temps[0] < single_view.profile_temps[-1]  # Erwärmung entlang der Linie
    assert float(np.max(single_view.profile_grads)) > 0.0  # Thermischer Gradient detektiert

    # Stats-Labels verifizieren
    assert single_view.profile_stats_rows["len"].cget("text") == "80.0 px"
    assert "°C" in single_view.profile_stats_rows["delta"].cget("text")

    # CSV-Kopieren testen
    single_view.copy_profile_csv()

    # Reset
    single_view.reset_measurement()
    assert len(single_view.profile_temps) == 0



