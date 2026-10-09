# -*- coding: utf-8 -*-
"""tests/test_cli.py – Unit- und Integrationstests für die IGNITE Python CLI."""

import os
import json
import pytest
import numpy as np

import cli


def test_cli_parser_creation():
    """Prüft, ob der ArgumentParser alle Befehle und Flags korrekt initialisiert."""
    parser = cli.build_parser()
    assert parser is not None
    # Subcommands prüfen
    subparsers_actions = [
        action for action in parser._actions
        if isinstance(action, cli.argparse._SubParsersAction)
    ]
    assert len(subparsers_actions) == 1
    choices = subparsers_actions[0].choices
    assert "analyze" in choices
    assert "batch" in choices
    assert "compare" in choices
    assert "eval" in choices
    assert "info" in choices
    assert "audit" in choices


def test_cli_info_execution(capsys):
    """Testet die Ausführung des 'info' Befehls."""
    parser = cli.build_parser()
    args = parser.parse_args(["info", "--no-color"])
    exit_code = cli.handle_info(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "IGNITE SYSTEM- UND HARDWARE-STATUS" in captured.out or "IGNITE System- und Hardware-Status" in captured.out
    assert "v5.0.0" in captured.out


def test_cli_analyze_single_image(tmp_path):
    """Testet die Einzelbildanalyse mit Artefakt-Generierung."""
    test_img = os.path.join("test-data", "bild (1).jpeg")
    if not os.path.exists(test_img):
        pytest.skip("Testbild nicht vorhanden")

    out_dir = str(tmp_path / "cli_output")
    json_path = os.path.join(out_dir, "test_result.json")
    report_path = os.path.join(out_dir, "test_report.md")

    parser = cli.build_parser()
    args = parser.parse_args([
        "analyze", test_img,
        "--output-dir", out_dir,
        "--save-overlay",
        "--save-mask",
        "--save-diff",
        "--output-json", json_path,
        "--output-report", report_path,
        "--quiet"
    ])

    exit_code = cli.handle_analyze(args)
    assert exit_code == 0

    assert os.path.exists(json_path)
    assert os.path.exists(report_path)

    # JSON prüfen
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "tsi_score" in data
    assert "risk_tier" in data
    assert "asymmetry" in data
    assert "hotspots" in data
    assert data["filename"] == "bild (1).jpeg"


def test_cli_compare_images(tmp_path):
    """Testet den longitudinalen Vorher/Nachher-Vergleich."""
    img1 = os.path.join("test-data", "bild (1).jpeg")
    img2 = os.path.join("test-data", "bild (2).jpeg")
    if not (os.path.exists(img1) and os.path.exists(img2)):
        pytest.skip("Testbilder nicht vorhanden")

    out_dir = str(tmp_path / "cmp_output")
    parser = cli.build_parser()
    args = parser.parse_args([
        "compare", img1, img2,
        "--output-dir", out_dir,
        "--quiet"
    ])

    exit_code = cli.handle_compare(args)
    assert exit_code == 0


def test_cli_batch_processing(tmp_path):
    """Testet die Batch-Verarbeitung eines Verzeichnisses."""
    if not os.path.isdir("test-data"):
        pytest.skip("test-data Verzeichnis fehlt")

    out_dir = str(tmp_path / "batch_out")
    csv_path = os.path.join(out_dir, "summary.csv")
    json_path = os.path.join(out_dir, "summary.json")

    parser = cli.build_parser()
    args = parser.parse_args([
        "batch", "test-data",
        "--pattern", "bild (1).jpeg,bild (2).jpeg",
        "--output-dir", out_dir,
        "--output-csv", csv_path,
        "--output-json", json_path,
        "--quiet"
    ])

    exit_code = cli.handle_batch(args)
    assert exit_code == 0
    assert os.path.exists(csv_path)
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        batch_data = json.load(f)
    assert len(batch_data) == 2


def test_cli_auto_routing(monkeypatch, capsys):
    """Testet, ob ein Dateipfad als erstes Argument automatisch als 'analyze' geroutet wird."""
    test_img = os.path.join("test-data", "bild (1).jpeg")
    if not os.path.exists(test_img):
        pytest.skip("Testbild fehlt")

    # Aufruf mit argv = [test_img, "--quiet"]
    exit_code = cli.main([test_img, "--quiet", "--no-overlay"])
    assert exit_code == 0
