# -*- coding: utf-8 -*-
"""tests/test_scientific_features.py – Validation for Jury Dossier & Ground Truth Annotation.

Tests:
1. ScientificReportService execution & HTML generation
2. GroundTruthAnnotatorDialog metrics calculation (Dice, IoU, Sensitivity, Specificity)
3. ROC curve points generation
"""

import os
import numpy as np
import pytest

import config
from gui.services.scientific_report_service import ScientificReportService
import dataset_evaluator
import image_processing


@pytest.fixture(scope="module")
def app_root():
    """Initialisiert eine headless CustomTkinter Root Instanz für GUI-Tests."""
    import customtkinter as ctk
    ctk.set_appearance_mode("Dark")
    root = ctk.CTk()
    root.geometry("1024x768")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.mark.benchmark
def test_scientific_report_generation(tmp_path):
    """Testet die vollständige Erstellung des wissenschaftlichen Jury-Reports (Benchmark-Modus)."""
    out_dir = str(tmp_path / "jury_reports")
    report_path = ScientificReportService.run_full_evaluation_and_generate_html(
        output_dir=out_dir,
        test_data_dir="test-data",
        gt_dir="test-data/ground_truth"
    )

    assert os.path.exists(report_path)
    assert report_path.endswith(".html")

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "IGNITE: Wissenschaftlicher Evaluationsbericht" in content
    assert "Executive Summary" in content
    assert "Dice-Score (F₁)" in content
    assert "ROC-Analyse" in content
    assert "Hardware-Skalierung" in content


def test_scientific_report_rendering_fast(tmp_path):
    """Schneller Render-Test für das HTML-Dossier mit synthetischen Mock-Ergebnissen."""
    mock_benchmark = {
        "scenario_results": {"diabetic_ulcer": {"dice": 0.95, "sensitivity": 1.0, "specificity": 0.99, "iou": 0.90, "TP": 100, "FP": 1, "TN": 1000, "FN": 0}},
        "baseline_otsu_comparison": {"diabetic_ulcer": {"ignite": {"dice": 0.95}, "otsu_baseline": {"dice": 0.50}, "dice_improvement": 0.45}},
        "mad_thresholding_comparison": {"diabetic_ulcer": {"mean_std": {"dice": 0.95}, "mad_robust": {"dice": 0.96}}},
        "statistical_validation": {
            "wilcoxon_vs_otsu": {"p_formatted": "p < 0.001", "statistic": 45.0, "significant": True, "mean_difference": 0.35},
            "bootstrap_ci": {"dice": {"ci_formatted": "0.950 [95% CI: 0.920 - 0.980]"}}
        }
    }
    mock_runtimes = {"python": {"name": "Python CPU", "latency_ms": 78.2, "fps": 12.8}}
    mock_roc = [{"k": 3.0, "tpr": 1.0, "fpr": 0.01, "dice": 0.95}]
    
    html = ScientificReportService._render_jury_dossier_html(
        benchmark_results=mock_benchmark,
        real_gt_results={},
        runtime_benchmarks=mock_runtimes,
        roc_points=mock_roc,
        total_duration=0.1
    )
    assert "IGNITE: Wissenschaftlicher Evaluationsbericht" in html
    assert "Diabetic Ulcer" in html


def test_roc_points_computation():
    """Testet die ROC-Kurven Berechnung über verschiedene k-Sigma Werte."""
    points = ScientificReportService._compute_roc_curve_points()
    assert len(points) > 0
    for p in points:
        assert "k" in p
        assert "tpr" in p
        assert "fpr" in p
        assert 0.0 <= p["tpr"] <= 1.0
        assert 0.0 <= p["fpr"] <= 1.0


def test_hardware_benchmark_execution():
    """Testet die automatische Latenz- und Durchsatzmessung."""
    bench = ScientificReportService._benchmark_hardware_runtimes()
    assert "python" in bench
    assert bench["python"]["latency_ms"] > 0
    assert bench["python"]["fps"] > 0


def test_scientific_poster_generation_pdf_and_html(tmp_path):
    """Testet die Erzeugung des druckreifen DIN A3/A4 Wettbewerbsplakates als PDF und HTML."""
    from gui.services.scientific_poster_service import ScientificPosterService

    pdf_out = str(tmp_path / "jufo_poster.pdf")
    html_out = str(tmp_path / "jufo_poster.html")

    res_pdf = ScientificPosterService.generate_poster_pdf(
        output_filepath=pdf_out,
        author="Jona Noack",
        competition="Jugend forscht 2026 · Fachgebiet Arbeitswelt"
    )
    assert os.path.exists(res_pdf)
    assert os.path.getsize(res_pdf) > 2000  # Gültiges PDF

    res_html = ScientificPosterService.generate_poster_html(
        output_filepath=html_out,
        author="Jona Noack",
        competition="Jugend forscht 2026 · Fachgebiet Arbeitswelt"
    )
    assert os.path.exists(res_html)
    assert os.path.getsize(res_html) > 2000  # Gültiges HTML

    with open(res_html, "r", encoding="utf-8") as f:
        html_text = f.read()

    assert "IGNITE Medical Imaging Suite" in html_text
    assert "Problemstellung & Arbeitswelt-Fokus" in html_text
    assert "Mathematische Kern-Pipeline" in html_text
    assert "IWGDF 2023" in html_text
    assert "0.945" in html_text


def test_thermal_3d_viewer_modal(app_root, monkeypatch):
    """Testet den interaktiven 3D-Relief und Oberflächentopographie-Viewer."""
    from gui.widgets.dialogs import Thermal3DViewerModal

    # Matplotlib show/update sicher ausführen
    test_img = np.full((60, 60), 120, dtype=np.uint8)
    test_img[20:40, 20:40] = 230  # Hotspot Berg
    body_mask = np.ones((60, 60), dtype=np.uint8) * 255

    modal = Thermal3DViewerModal(
        master=app_root,
        calibrated_image=test_img,
        body_mask=body_mask,
        t_min_c=20.0,
        t_max_c=40.0,
        palette_name="turbo"
    )

    # 1. Elevation und Azimut ändern
    modal._on_elev_changed(60)
    assert modal.elev == 60

    modal._on_azim_changed(45)
    assert modal.azim == 45

    # 2. Skalierung ändern
    modal._on_scale_changed(2.0)
    assert modal.z_scale == 2.0

    # 3. Mesh-Modus umschalten
    modal._on_mode_changed("Drahtgitter")
    assert modal.surface_mode == "Drahtgitter"

    modal.destroy()

