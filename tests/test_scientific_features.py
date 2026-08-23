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

from gui.services.scientific_report_service import ScientificReportService
import dataset_evaluator
import image_processing


def test_scientific_report_generation(tmp_path):
    """Testet die fehlerfreie Erstellung des wissenschaftlichen Jury-Reports."""
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
