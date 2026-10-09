#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli.py – Professionelle Python CLI-Version der IGNITE Medical Imaging Suite.

Entwickelt für den deutschen Jugendwettbewerb Jugend forscht 2026 (Fachgebiet Arbeitswelt).
Bietet eine vollständige, rein in Python implementierte Befehlszeilenschnittstelle für:
  1. Einzelbild-Diagnostik (analyze): Deterministische Hotspot- & Gewebeanalyse
  2. Batch-Verarbeitung (batch): Massenanalyse ganzer Studienordner mit CSV/JSON-Export
  3. Longitudinaler Verlauf (compare): Vorher/Nachher-Therapiekontrolle (ΔT & Flächenänderung)
  4. Wissenschaftliche Evaluation (eval): Benchmarks gegen Ground-Truth & synthetische Szenarien
  5. System- & Hardware-Status (info): GPU/CUDA, Rust-Core & CPU-Telemetrie
  6. Audit-Trail (audit): Revisionssichere Protokollierung nach DSGVO Art. 30

Nutzung:
  python cli.py <image_path>                      # Direkte Schnellanalyse
  python cli.py analyze <image_path> [options]    # Detaillierte Einzelbildanalyse
  python cli.py batch <dir> [options]             # Batch-Verarbeitung
  python cli.py compare <base> <followup>         # Verlaufsuntersuchung
  python cli.py eval [options]                    # Quantitative Evaluation
  python cli.py info                              # Systemtelemetrie
"""

from __future__ import annotations

import argparse
import csv
import datetime
import glob
import hashlib
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Windows Terminal UTF-8 Encoding sicherstellen
if sys.platform.startswith("win"):
    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Projektverzeichnis zum Pfad hinzufügen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import cv2
import numpy as np

import audit_log
import config
import dataset_evaluator
import image_processing
from utils import (
    apply_radiometric_emissivity_correction,
    convert_16bit_radiometric_to_8bit,
    pixel_to_celsius,
)

# Optionale Rich-Integration für erstklassiges Terminal-Design
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. VISUELLE HILFSFUNKTIONEN & COLORMAPS (HEADLESS, REIN OPENCV)
# ─────────────────────────────────────────────────────────────────────────────

def get_opencv_colormap(colormap_name: str) -> int:
    """Mappt Farbskalennamen auf OpenCV Colormap-Konstanten."""
    c = colormap_name.lower().strip()
    if c in ("turbo", "google turbo"):
        return getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)
    elif c in ("inferno", "ironbow", "iron", "thermisch"):
        return cv2.COLORMAP_INFERNO
    elif c in ("jet", "regenbogen", "rainbow"):
        return cv2.COLORMAP_JET
    elif c in ("hot", "heiß", "heiss"):
        return cv2.COLORMAP_HOT
    elif c in ("plasma",):
        return cv2.COLORMAP_PLASMA
    elif c in ("viridis",):
        return cv2.COLORMAP_VIRIDIS
    elif c in ("magma",):
        return cv2.COLORMAP_MAGMA
    return getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)


def apply_colormap_to_image(img_gray: np.ndarray, colormap_name: str = "turbo") -> np.ndarray:
    """Wendet eine Farbskala auf ein Graustufen-Thermobild an."""
    if len(img_gray.shape) == 3 and img_gray.shape[2] == 3:
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_RGB2GRAY)

    c = colormap_name.lower().strip()
    if c in ("gray", "graustufen", "grayscale"):
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

    cmap_code = get_opencv_colormap(colormap_name)
    return cv2.applyColorMap(img_gray, cmap_code)


def render_diagnostic_overlay(
    calibrated_img: np.ndarray,
    body_mask: np.ndarray,
    hotspot_mask: np.ndarray,
    hotspots: List[Dict[str, Any]],
    pca_results: Optional[Dict[str, Any]] = None,
    colormap_name: str = "turbo",
) -> np.ndarray:
    """Erzeugt ein diagnostisches Befund-Overlay mit Bounding-Boxen und Annotationen."""
    base_bgr = apply_colormap_to_image(calibrated_img, colormap_name)

    # Rote Hotspots mit Alpha-Blending hervorheben
    red_layer = np.zeros_like(base_bgr)
    red_layer[:] = [0, 0, 255]  # BGR Rot
    blended = cv2.addWeighted(base_bgr, 0.4, red_layer, 0.6, 0)
    overlay = np.where(hotspot_mask[:, :, None] == 255, blended, base_bgr).astype(np.uint8)

    # Hotspot Bounding-Boxen & Beschriftung
    for hs in hotspots:
        x, y, w, h = hs["bbox"]
        # Roter Kasten um Hotspot
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), 2)
        label = f"#{hs['id']} {hs['max_temp_c']:.1f}C"
        # Kleiner Hintergrundkasten für Textlesbarkeit
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        ty = max(18, y - 4)
        cv2.rectangle(overlay, (x, ty - th - 3), (x + tw + 4, ty + 2), (0, 0, 0), -1)
        cv2.putText(overlay, label, (x + 2, ty - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

    # Anatomische Zonen einzeichnen, falls vorhanden
    if pca_results:
        for side in ("left", "right"):
            info = pca_results.get(side)
            if info and info.get("exists") and info.get("bbox"):
                bx, by, bw, bh = info["bbox"]
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (255, 200, 0), 1)
                h3 = max(1, bh // 3)
                cv2.line(overlay, (bx, by + h3), (bx + bw, by + h3), (255, 200, 0), 1)
                cv2.line(overlay, (bx, by + 2 * h3), (bx + bw, by + 2 * h3), (255, 200, 0), 1)
                cv2.putText(overlay, f"{side.upper()}", (bx + 6, by + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1, cv2.LINE_AA)

    return overlay


# ─────────────────────────────────────────────────────────────────────────────
# 2. ANALYSE-ENGINE FÜR EINZELBILDER
# ─────────────────────────────────────────────────────────────────────────────

def extract_hotspots_components(
    calibrated_img: np.ndarray,
    hotspot_mask: np.ndarray,
    t_min_c: float,
    t_max_c: float,
    emissivity: float = config.SKIN_EMISSIVITY,
) -> List[Dict[str, Any]]:
    """Ermittelt alle zusammenhängenden Hotspot-Regionen mit geometrischen & thermischen Kenndaten."""
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(hotspot_mask)
    hotspots: List[Dict[str, Any]] = []

    for i in range(1, num_labels):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        cx, cy = centroids[i]

        comp_mask = labels == i
        roi_pixels = calibrated_img[comp_mask]

        if len(roi_pixels) == 0:
            continue

        max_raw = int(np.max(roi_pixels))
        mean_raw = float(np.mean(roi_pixels))

        max_c = pixel_to_celsius(max_raw, t_min_c, t_max_c)
        mean_c = pixel_to_celsius(mean_raw, t_min_c, t_max_c)

        if emissivity != 1.0:
            max_c = apply_radiometric_emissivity_correction(max_c, emissivity=emissivity)
            mean_c = apply_radiometric_emissivity_correction(mean_c, emissivity=emissivity)

        # Zirkularität (Formfaktor)
        contours, _ = cv2.findContours(comp_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        circularity = 0.0
        if contours:
            perimeter = cv2.arcLength(contours[0], True)
            if perimeter > 0:
                circularity = float((4.0 * np.pi * area) / (perimeter ** 2))

        # Risikobewertung pro Hotspot
        if max_c >= 35.0 or area > 300:
            risk = "HOCH (Stufe 3)"
            risk_color = "red"
        elif max_c >= 32.0 or area > 100:
            risk = "MÄSSIG (Stufe 2)"
            risk_color = "yellow"
        else:
            risk = "GERING (Stufe 1)"
            risk_color = "green"

        hotspots.append({
            "id": len(hotspots) + 1,
            "bbox": (x, y, w, h),
            "centroid": (round(float(cx), 1), round(float(cy), 1)),
            "area_px": area,
            "circularity": round(circularity, 3),
            "max_raw": max_raw,
            "mean_raw": round(mean_raw, 1),
            "max_temp_c": round(max_c, 2),
            "mean_temp_c": round(mean_c, 2),
            "risk": risk,
            "risk_color": risk_color,
        })

    # Nach Maximaltemperatur absteigend sortieren
    hotspots.sort(key=lambda item: item["max_temp_c"], reverse=True)
    for idx, hs in enumerate(hotspots, start=1):
        hs["id"] = idx

    return hotspots


def analyze_thermal_image(
    image_path: str,
    t_min_c: float = config.DEFAULT_TEMP_MIN,
    t_max_c: float = config.DEFAULT_TEMP_MAX,
    temp_offset: float = 0.0,
    emissivity: float = config.SKIN_EMISSIVITY,
    backend: str = "auto",
    sigma_k: float = config.DEFAULT_SIGMA_K,
    tophat_factor: float = config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = config.DEFAULT_OTSU_MIN,
    otsu_max: int = config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = config.DEFAULT_DIST_EROSION_FACTOR,
    use_mad: bool = config.DEFAULT_USE_MAD,
    enable_hysteresis: bool = config.DEFAULT_ENABLE_HYSTERESIS,
    hysteresis_k_low: float = config.DEFAULT_HYSTERESIS_K_LOW,
    anatomy_region: str = "feet",
    compute_frangi: bool = False,
    compute_bioheat: bool = False,
    compute_bilateral_map: bool = False,
) -> Dict[str, Any]:
    """Führt die vollständige deterministische Bildverarbeitungs- und Diagnose-Pipeline aus."""
    t0 = time.perf_counter()

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Bilddatei '{image_path}' wurde nicht gefunden.")

    # Backend-Wahl einstellen
    old_backend = image_processing.FORCED_BACKEND
    image_processing.FORCED_BACKEND = backend

    try:
        # 1. Bild laden (inkl. 16-Bit / RAW Kalibrierung)
        raw_img = image_processing.load_thermal_image(image_path, t_min=t_min_c, t_max=t_max_c)

        # 2. Kalibrierungs-Offset anwenden
        range_c = max(1.0, t_max_c - t_min_c)
        raw_offset = int(round(temp_offset * 255.0 / range_c))
        calibrated_img = np.clip(raw_img.astype(np.int16) + raw_offset, 0, 255).astype(np.uint8)

        # 3. Multi-Scale Hotspot Pipeline ausführen
        diff_vis, hotspot_mask = image_processing.run_rust_pipeline(
            calibrated_img,
            sigma_k=sigma_k,
            tophat_factor=tophat_factor,
            min_area_factor=min_area_factor,
            min_circularity=min_circularity,
            otsu_min=otsu_min,
            otsu_max=otsu_max,
            dist_erosion_factor=dist_erosion_factor,
            use_mad=use_mad,
            enable_hysteresis=enable_hysteresis,
            hysteresis_k_low=hysteresis_k_low,
        )

        # 4. Gewebemaskierung
        try:
            body_mask = image_processing.extract_body_mask_multi_otsu(
                calibrated_img,
                otsu_min=otsu_min,
                otsu_max=otsu_max,
                dist_erosion_factor=dist_erosion_factor,
            )
            if np.sum(body_mask > 0) == 0:
                body_mask = (diff_vis > 0).astype(np.uint8) * 255
        except Exception:
            body_mask = (diff_vis > 0).astype(np.uint8) * 255

        # 5. Thermische Gradienten & Laplace-Divergenz
        gradient_results = image_processing.compute_thermal_gradients_and_divergence(
            calibrated_img, body_mask
        )

        # 6. Kontralaterale Asymmetrie-Analyse inklusive PCA
        asym_threshold = float(config.ANATOMICAL_REGIONS.get(anatomy_region, {}).get("asym_thresh_c", config.ASYMMETRY_THRESHOLD_C))
        asym_results = image_processing.compute_contralateral_asymmetry(
            calibrated_img, body_mask, t_min_c, t_max_c, asym_threshold, region_key=anatomy_region
        )
        pca_results = asym_results.get("pca")

        # 7. Hotspot-Objekte mit Metriken
        hotspots = extract_hotspots_components(
            calibrated_img, hotspot_mask, t_min_c, t_max_c, emissivity=emissivity
        )
        categorized_hotspots = image_processing.categorize_hotspots_by_pca_zones(
            hotspot_mask, pca_results
        ) if pca_results else {"left": [], "right": []}

        # 8. Pixel-Statistiken über Gewebe
        body_pixels = calibrated_img[body_mask > 0]
        if len(body_pixels) > 0:
            mean_val = float(np.mean(body_pixels))
            std_val = float(np.std(body_pixels))
            max_val = float(np.max(body_pixels))
            min_val = float(np.min(body_pixels))
        else:
            mean_val, std_val, max_val, min_val = 0.0, 0.0, 0.0, 0.0

        hotspot_pixels = int(np.sum(hotspot_mask == 255))
        hotspot_ratio = (hotspot_pixels / max(1, len(body_pixels))) * 100.0

        mean_temp_c = pixel_to_celsius(mean_val, t_min_c, t_max_c, apply_emissivity=False)
        max_temp_c = pixel_to_celsius(max_val, t_min_c, t_max_c, apply_emissivity=False)
        min_temp_c = pixel_to_celsius(min_val, t_min_c, t_max_c, apply_emissivity=False)
        std_temp_c = (std_val / 255.0) * (t_max_c - t_min_c)

        # 9. Thermal Severity Index (TSI) & IWGDF Risikostufe
        delta_t = asym_results.get("delta_t_c", 0.0)
        tsi_results = image_processing.compute_thermal_severity_index(
            delta_t_c=delta_t,
            hotspot_pixel_count=hotspot_pixels,
            body_pixel_count=len(body_pixels),
            max_gradient=gradient_results.get("max_gradient", 0.0),
            std_pixel=std_val,
        )

        # 10. Optionale Spezial-Features
        frangi_results = None
        if compute_frangi:
            frangi_results = image_processing.compute_frangi_vesselness_filter(
                calibrated_img, body_mask
            )

        bioheat_results = None
        if compute_bioheat:
            bioheat_results = image_processing.compute_pennes_bioheat_flux(
                calibrated_img, body_mask, t_min_c, t_max_c
            )

        bilateral_map = None
        if compute_bilateral_map:
            bilateral_map = image_processing.compute_bilateral_asymmetry_map(
                calibrated_img, body_mask, t_min_c, t_max_c
            )

        duration_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "image_path": os.path.abspath(image_path),
            "filename": os.path.basename(image_path),
            "dimensions": [int(calibrated_img.shape[1]), int(calibrated_img.shape[0])],
            "backend": image_processing.get_active_backend(),
            "duration_ms": round(duration_ms, 2),
            "t_min_c": t_min_c,
            "t_max_c": t_max_c,
            "temp_offset": temp_offset,
            "emissivity": emissivity,
            "anatomy_region": anatomy_region,
            # Matrizen
            "raw_img": raw_img,
            "calibrated_img": calibrated_img,
            "diff_vis": diff_vis,
            "hotspot_mask": hotspot_mask,
            "body_mask": body_mask,
            "frangi_map": frangi_results,
            "bioheat_map": bioheat_results,
            "bilateral_map": bilateral_map,
            # Statistiken
            "body_pixel_count": len(body_pixels),
            "hotspot_pixel_count": hotspot_pixels,
            "hotspot_ratio_percent": round(hotspot_ratio, 2),
            "mean_temp_c": round(mean_temp_c, 2),
            "max_temp_c": round(max_temp_c, 2),
            "min_temp_c": round(min_temp_c, 2),
            "std_temp_c": round(std_temp_c, 2),
            # Ergebnisse
            "tsi_score": tsi_results.get("score", 0.0),
            "risk_tier": tsi_results.get("tier", 0),
            "risk_name": tsi_results.get("tier_name", ""),
            "risk_desc": tsi_results.get("tier_desc", ""),
            "asymmetry": asym_results,
            "gradient": gradient_results,
            "pca": pca_results,
            "hotspots": hotspots,
            "categorized_hotspots": categorized_hotspots,
        }
    finally:
        image_processing.FORCED_BACKEND = old_backend


# ─────────────────────────────────────────────────────────────────────────────
# 3. VERLAUFS-VERGLEICH (COMPARE)
# ─────────────────────────────────────────────────────────────────────────────

def compare_longitudinal_images(
    baseline_path: str,
    followup_path: str,
    t_min_c: float = config.DEFAULT_TEMP_MIN,
    t_max_c: float = config.DEFAULT_TEMP_MAX,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Vergleicht zwei zeitlich versetzte Untersuchungen (Baseline vs. Follow-Up)."""
    res0 = analyze_thermal_image(baseline_path, t_min_c=t_min_c, t_max_c=t_max_c)
    res1 = analyze_thermal_image(followup_path, t_min_c=t_min_c, t_max_c=t_max_c)

    img0 = res0["calibrated_img"]
    img1 = res1["calibrated_img"]
    h0, w0 = img0.shape[:2]

    if img1.shape[:2] != (h0, w0):
        img1 = cv2.resize(img1, (w0, h0), interpolation=cv2.INTER_LINEAR)
        mask1 = cv2.resize(res1["body_mask"], (w0, h0), interpolation=cv2.INTER_NEAREST)
        hs1 = cv2.resize(res1["hotspot_mask"], (w0, h0), interpolation=cv2.INTER_NEAREST)
    else:
        mask1 = res1["body_mask"]
        hs1 = res1["hotspot_mask"]

    mask0 = res0["body_mask"]
    hs0 = res0["hotspot_mask"]

    temp0 = pixel_to_celsius(img0.astype(np.float32), t_min_c, t_max_c)
    temp1 = pixel_to_celsius(img1.astype(np.float32), t_min_c, t_max_c)

    common_mask = (mask0 > 0) & (mask1 > 0)
    if not np.any(common_mask):
        common_mask = (mask0 > 0) | (mask1 > 0)
    if not np.any(common_mask):
        common_mask = np.ones((h0, w0), dtype=bool)

    delta_matrix = temp1 - temp0
    valid_delta = delta_matrix[common_mask]

    delta_mean = float(np.mean(valid_delta)) if len(valid_delta) > 0 else 0.0
    delta_std = float(np.std(valid_delta)) if len(valid_delta) > 0 else 0.0
    delta_max = float(np.max(valid_delta)) if len(valid_delta) > 0 else 0.0
    delta_min = float(np.min(valid_delta)) if len(valid_delta) > 0 else 0.0

    area0 = int(np.count_nonzero(hs0))
    area1 = int(np.count_nonzero(hs1))
    area_diff = area1 - area0
    area_pct = float((area_diff / max(1, area0)) * 100.0) if area0 > 0 else (100.0 if area1 > 0 else 0.0)

    # Klinische Beurteilung nach IWGDF Verlaufsleitlinie
    if delta_mean <= -0.5 and area_pct <= -15.0:
        status = "Signifikante Regression (Befundbesserung)"
        status_code = "regression"
        color = "green"
    elif delta_mean >= 0.5 or area_pct >= 20.0:
        status = "Akute Progression (Entzündungszunahme)"
        status_code = "progression"
        color = "red"
    else:
        status = "Stabiler Befundverlauf"
        status_code = "stable"
        color = "yellow"

    # Differenzielle Heatmap rendern (-3K bis +3K Skala)
    norm_delta = np.clip((delta_matrix + 3.0) / 6.0 * 255.0, 0, 255).astype(np.uint8)
    diff_colored = cv2.applyColorMap(norm_delta, cv2.COLORMAP_JET)
    diff_colored[~common_mask] = [30, 30, 30]  # Hintergrund dunkelgrau

    diff_path = None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        diff_name = f"longitudinal_diff_{pathlib.Path(baseline_path).stem}_vs_{pathlib.Path(followup_path).stem}.png"
        diff_path = os.path.join(output_dir, diff_name)
        cv2.imwrite(diff_path, diff_colored)

    return {
        "baseline_path": baseline_path,
        "followup_path": followup_path,
        "delta_mean_c": round(delta_mean, 2),
        "delta_std_c": round(delta_std, 2),
        "delta_max_c": round(delta_max, 2),
        "delta_min_c": round(delta_min, 2),
        "hotspot_area_baseline_px": area0,
        "hotspot_area_followup_px": area1,
        "hotspot_area_change_px": area_diff,
        "hotspot_area_change_percent": round(area_pct, 1),
        "clinical_status": status,
        "status_code": status_code,
        "status_color": color,
        "diff_map_path": diff_path,
        "baseline_tsi": res0["tsi_score"],
        "followup_tsi": res1["tsi_score"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. TERMINAL-FORMATIERUNG & AUSGABE (RICH & ASCII-FALLBACK)
# ─────────────────────────────────────────────────────────────────────────────

BANNER_TEXT = rf"""
  ██╗ ██████╗ ███╗   ██╗██╗████████╗███████╗
  ██║██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝
  ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  
  ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  
  ██║╚██████╔╝██║ ╚████║██║   ██║   ███████╗
  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝
  IGNITE Medical Imaging Suite · CLI v{config.APP_VERSION}
  Jugend forscht 2026 · Fachgebiet Arbeitswelt
"""

def print_banner(no_color: bool = False) -> None:
    """Gibt das IGNITE Banner im Terminal aus."""
    if RICH_AVAILABLE and not no_color:
        console.print(f"[bold cyan]{BANNER_TEXT}[/bold cyan]")
    else:
        print(BANNER_TEXT)


def display_analysis_summary(result: Dict[str, Any], no_color: bool = False) -> None:
    """Gibt die detaillierte Befundzusammenfassung im Terminal aus."""
    if RICH_AVAILABLE and not no_color:
        _display_rich_summary(result)
    else:
        _display_plain_summary(result)


def _display_rich_summary(res: Dict[str, Any]) -> None:
    """Formatiert Ergebnisse mit der Rich-Bibliothek."""
    # 1. Übersichts-Panel
    tier = res["risk_tier"]
    badge_style = "bold white on green" if tier == 0 else (
        "bold black on yellow" if tier == 1 else (
            "bold white on red" if tier >= 2 else "bold white on dark_orange"
        )
    )

    summary_text = (
        f"[bold cyan]Datei:[/bold cyan] {res['filename']}  "
        f"([dim]{res['dimensions'][0]}×{res['dimensions'][1]} px[/dim])\n"
        f"[bold cyan]Backend:[/bold cyan] {res['backend']}  "
        f"[bold cyan]Laufzeit:[/bold cyan] {res['duration_ms']:.1f} ms\n\n"
        f"[bold]Thermal Severity Index (TSI):[/bold] [bold yellow]{res['tsi_score']}/10.0[/bold yellow]\n"
        f"[{badge_style}] {res['risk_name']} [/{badge_style}]\n"
        f"[dim]{res['risk_desc']}[/dim]"
    )
    console.print(Panel(summary_text, title="[bold cyan]IGNITE Thermografie-Befund[/bold cyan]", border_style="cyan"))

    # 2. Thermometrie & Asymmetrie
    t_table = Table(title="Thermometrische Kennwerte", expand=True, border_style="blue")
    t_table.add_column("Metrik", style="bold")
    t_table.add_column("Wert", justify="right")
    t_table.add_column("Referenz / Standard", style="dim")

    t_table.add_row("Mitteltemperatur Gewebe (T_mean)", f"{res['mean_temp_c']:.2f} °C", "Physiologische Hauttemperatur")
    t_table.add_row("Maximaltemperatur (T_max)", f"{res['max_temp_c']:.2f} °C", "Peak-Gewebetemperatur")
    t_table.add_row("Minimaltemperatur (T_min)", f"{res['min_temp_c']:.2f} °C", "Distale Peripherie")
    t_table.add_row("Temperatur-Standardabweichung (σ)", f"±{res['std_temp_c']:.2f} °C", "Thermische Homogenität")

    asym = res.get("asymmetry", {})
    delta_t = asym.get("delta_t_c", 0.0)
    thresh = asym.get("threshold_c", 2.2)
    asym_status = f"[bold red]⚠️ ΔT = {delta_t:.2f} °C (Asymmetrisch)[/bold red]" if delta_t >= thresh else f"[bold green]✓ ΔT = {delta_t:.2f} °C (Symmetrisch)[/bold green]"
    t_table.add_row("Bilateraler Seitenvergleich", asym_status, f"Armstrong-Kriterium (Schwelle: {thresh:.1f} °C)")

    console.print(t_table)

    # 3. Anatomische Zonen (PCA)
    pca = res.get("pca")
    if pca and pca.get("left", {}).get("exists") and pca.get("right", {}).get("exists"):
        z_table = Table(title="Podologische 3-Zonen-Matrix (PCA-ausgerichtet)", expand=True, border_style="magenta")
        z_table.add_column("Zone", style="bold")
        z_table.add_column("Links (L)", justify="right")
        z_table.add_column("Rechts (R)", justify="right")
        z_table.add_column("Differenz |L - R|", justify="right")

        l_info = pca["left"]
        r_info = pca["right"]
        for z_key, z_label in [("zone_1", "Vorfuß / Metatarsale"), ("zone_2", "Mittelfuß / Plantargewölbe"), ("zone_3", "Rückfuß / Calcaneus")]:
            t_l = l_info.get(f"{z_key}_c", l_info.get(z_key.replace("zone_1", "fore").replace("zone_2", "mid").replace("zone_3", "heel") + "_c", 0.0))
            t_r = r_info.get(f"{z_key}_c", r_info.get(z_key.replace("zone_1", "fore").replace("zone_2", "mid").replace("zone_3", "heel") + "_c", 0.0))
            diff = abs(t_l - t_r)
            diff_str = f"[bold red]{diff:.2f} °C[/bold red]" if diff >= 2.2 else f"{diff:.2f} °C"
            z_table.add_row(z_label, f"{t_l:.2f} °C", f"{t_r:.2f} °C", diff_str)

        if l_info.get("arch_type"):
            z_table.add_row("Fußgewölbe-Klassifikation", f"{l_info.get('arch_type')} (AI: {l_info.get('arch_index', 0):.2f})", f"{r_info.get('arch_type')} (AI: {r_info.get('arch_index', 0):.2f})", "Cavanagh & Rodgers")

        console.print(z_table)

    # 4. Hotspot-Liste
    hotspots = res.get("hotspots", [])
    if hotspots:
        h_table = Table(title=f"Erkannte Entzündungsherde / Hotspots ({len(hotspots)})", expand=True, border_style="red")
        h_table.add_column("ID", justify="center", style="bold")
        h_table.add_column("Zentroid (x, y)", justify="center")
        h_table.add_column("Fläche", justify="right")
        h_table.add_column("Peak-Temp (T_max)", justify="right", style="bold red")
        h_table.add_column("Mittel-Temp", justify="right")
        h_table.add_column("Zirkularität", justify="right")
        h_table.add_column("Risikostufe", justify="center")

        for hs in hotspots[:10]:
            h_table.add_row(
                f"#{hs['id']}",
                f"({hs['centroid'][0]:.0f}, {hs['centroid'][1]:.0f})",
                f"{hs['area_px']} px",
                f"{hs['max_temp_c']:.2f} °C",
                f"{hs['mean_temp_c']:.2f} °C",
                f"{hs['circularity']:.2f}",
                f"[{hs['risk_color']}]{hs['risk']}[/{hs['risk_color']}]",
            )
        if len(hotspots) > 10:
            h_table.add_row("...", f"... weitere {len(hotspots) - 10} Herde", "", "", "", "", "")

        console.print(h_table)
    else:
        console.print(Panel("[bold green]✓ Keine pathologischen Entzündungsherde oberhalb der statistischen Signifikanzschwelle detektiert.[/bold green]", border_style="green"))


def _display_plain_summary(res: Dict[str, Any]) -> None:
    """Formatiert Ergebnisse als reinen ASCII-Text."""
    print("=" * 78)
    print(f"IGNITE THERMOGRAFIE-BEFUNDBERICHT")
    print(f"Datei: {res['filename']} ({res['dimensions'][0]}x{res['dimensions'][1]} px)")
    print(f"Backend: {res['backend']} | Laufzeit: {res['duration_ms']:.1f} ms")
    print("-" * 78)
    print(f"Thermal Severity Index (TSI): {res['tsi_score']}/10.0")
    print(f"Risikostufe: {res['risk_name']}")
    print(f"Klinische Empfehlung: {res['risk_desc']}")
    print("-" * 78)
    print(f"Mitteltemperatur Gewebe:    {res['mean_temp_c']:.2f} °C")
    print(f"Maximaltemperatur (Peak):   {res['max_temp_c']:.2f} °C")
    print(f"Minimaltemperatur:          {res['min_temp_c']:.2f} °C")
    print(f"Standardabweichung (σ):     ±{res['std_temp_c']:.2f} °C")

    asym = res.get("asymmetry", {})
    delta_t = asym.get("delta_t_c", 0.0)
    thresh = asym.get("threshold_c", 2.2)
    print(f"Bilateraler Seitenvergleich: ΔT = {delta_t:.2f} °C (Schwelle: {thresh:.1f} °C) -> {asym.get('status')}")
    print("-" * 78)

    hotspots = res.get("hotspots", [])
    print(f"Erkannte Hotspots: {len(hotspots)}")
    if hotspots:
        print(f"{'ID':<4} | {'Zentroid':<12} | {'Fläche':<9} | {'T_max':<9} | {'T_mean':<9} | {'Risikostufe'}")
        print("-" * 78)
        for hs in hotspots[:10]:
            print(f"#{hs['id']:<3} | ({hs['centroid'][0]:.0f}, {hs['centroid'][1]:.0f}){'':<4} | {hs['area_px']:>5} px | {hs['max_temp_c']:>6.2f} °C | {hs['mean_temp_c']:>6.2f} °C | {hs['risk']}")
        if len(hotspots) > 10:
            print(f"... ({len(hotspots) - 10} weitere Herde ausgeblendet)")
    print("=" * 78)


# ─────────────────────────────────────────────────────────────────────────────
# 5. EXPORTFUNKTIONEN (BILDER, JSON, MARKDOWN-REPORT, AUDIT)
# ─────────────────────────────────────────────────────────────────────────────

def to_json_serializable(obj: Any) -> Any:
    """Konvertiert rekursiv alle Datenstrukturen in JSON-serialisierbare Standardtypen."""
    if isinstance(obj, np.ndarray):
        if obj.size <= 10:
            return obj.tolist()
        return f"<ndarray shape={obj.shape} dtype={obj.dtype}>"
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, dict):
        return {
            str(k): to_json_serializable(v)
            for k, v in obj.items()
            if k not in ("raw_img", "calibrated_img", "diff_vis", "hotspot_mask", "body_mask", "frangi_map", "bioheat_map", "bilateral_map")
        }
    elif isinstance(obj, (list, tuple)):
        return [to_json_serializable(item) for item in obj]
    return obj


def export_results(
    res: Dict[str, Any],
    output_dir: str,
    save_overlay: bool = True,
    save_mask: bool = False,
    save_diff: bool = False,
    save_all: bool = False,
    colormap_name: str = "turbo",
    json_path: Optional[str] = None,
    report_path: Optional[str] = None,
    log_audit: bool = False,
) -> Dict[str, str]:
    """Exportiert Bildartefakte, strukturierte Daten und Berichte."""
    os.makedirs(output_dir, exist_ok=True)
    stem = pathlib.Path(res["image_path"]).stem
    saved_files: Dict[str, str] = {}

    # 1. Diagnostisches Overlay
    if save_overlay or save_all:
        overlay_img = render_diagnostic_overlay(
            res["calibrated_img"],
            res["body_mask"],
            res["hotspot_mask"],
            res["hotspots"],
            pca_results=res.get("pca"),
            colormap_name=colormap_name,
        )
        overlay_path = os.path.join(output_dir, f"{stem}_diagnostic_overlay.png")
        cv2.imwrite(overlay_path, overlay_img)
        saved_files["overlay"] = overlay_path

    # 2. Binäre Maske
    if save_mask or save_all:
        mask_path = os.path.join(output_dir, f"{stem}_hotspot_mask.png")
        cv2.imwrite(mask_path, res["hotspot_mask"])
        saved_files["mask"] = mask_path

    # 3. Differenzbild
    if save_diff or save_all:
        diff_path = os.path.join(output_dir, f"{stem}_tophat_diff.png")
        cv2.imwrite(diff_path, res["diff_vis"])
        saved_files["diff"] = diff_path

    # 4. Frangi / Bioheat / Bilateral falls berechnet
    if save_all:
        if res.get("frangi_map") is not None:
            f_path = os.path.join(output_dir, f"{stem}_frangi_vesselness.png")
            cv2.imwrite(f_path, res["frangi_map"])
            saved_files["frangi"] = f_path

        body_path = os.path.join(output_dir, f"{stem}_body_mask.png")
        cv2.imwrite(body_path, res["body_mask"])
        saved_files["body_mask"] = body_path

    # 5. JSON-Export
    if json_path:
        serializable = to_json_serializable(res)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        saved_files["json"] = json_path

    # 6. Markdown-Befundbericht
    if report_path:
        generate_markdown_report(res, report_path)
        saved_files["report"] = report_path

    # 7. Revisionssicherer Audit-Trail
    if log_audit:
        try:
            entry = {
                "Zeitstempel": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Patienten-ID": f"ANON-{hashlib.sha256(stem.encode()).hexdigest()[:8]}",
                "Analysemodus": "CLI_SCREENING",
                "Bilddatei": res["filename"],
                "sigma_k": config.DEFAULT_SIGMA_K,
                "tophat_factor": config.DEFAULT_TOPHAT_FACTOR,
                "T_min_C": res["t_min_c"],
                "T_max_C": res["t_max_c"],
                "Hotspot_Pixel": res["hotspot_pixel_count"],
                "Max_Temp_C": res["max_temp_c"],
                "Symmetrie_Delta": res.get("asymmetry", {}).get("delta_t_c", 0.0),
                "Operator": "CLI_USER",
            }
            audit_log.write_audit_entry(entry)
            saved_files["audit"] = config.AUDIT_TRAIL_PATH
        except Exception as e:
            logging.debug(f"Audit-Log Fehler: {e}")

    return saved_files


def generate_markdown_report(res: Dict[str, Any], output_path: str) -> None:
    """Erstellt einen klinischen Markdown-Befundbericht."""
    ts = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    stem = pathlib.Path(res["image_path"]).stem
    anon_id = f"ANON-{hashlib.sha256(stem.encode()).hexdigest()[:8]}"

    md = [
        f"# IGNITE Medical Imaging Suite – Klinischer Befundbericht",
        f"",
        f"**Forschungsprototyp für Jugend forscht 2026** (Fachgebiet Arbeitswelt)  ",
        f"Untersuchungszeitpunkt: `{ts}`  ",
        f"Patienten-Pseudonym: `{anon_id}`  ",
        f"Quellaufnahme: `{res['filename']}`  ",
        f"",
        f"---",
        f"",
        f"## 1. Zusammenfassung & Klinische Risikoklassifikation",
        f"",
        f"- **Thermal Severity Index (TSI):** `{res['tsi_score']} / 10.0`",
        f"- **IWGDF-Risikoklasse:** **{res['risk_name']}**",
        f"- **Klinische Empfehlung:** {res['risk_desc']}",
        f"",
        f"## 2. Radiometrische Kenndaten",
        f"",
        f"| Parameter | Messwert | Referenzbereich / Status |",
        f"| :--- | :--- | :--- |",
        f"| Gewebetemperatur (Mittelwert) | `{res['mean_temp_c']:.2f} °C` | Physiologischer Normbereich |",
        f"| Peak-Temperatur (T_max) | `{res['max_temp_c']:.2f} °C` | Maximaler Gewebefokus |",
        f"| Minimaltemperatur (T_min) | `{res['min_temp_c']:.2f} °C` | Periphere Randbereiche |",
        f"| Temperaturvarianz (σ) | `±{res['std_temp_c']:.2f} °C` | Thermische Heterogenität |",
        f"| Bilaterale Asymmetrie (ΔT) | `{res.get('asymmetry', {}).get('delta_t_c', 0.0):.2f} °C` | Schwelle: `2.2 °C` ({res.get('asymmetry', {}).get('status', '')}) |",
        f"",
        f"## 3. Detektierte Hotspots & Entzündungsherde",
        f"",
        f"- **Gesamtzahl Herde:** `{len(res.get('hotspots', []))}`",
        f"- **Betroffene Gewebefläche:** `{res['hotspot_pixel_count']} Pixel` ({res['hotspot_ratio_percent']} % der Gesamtkontur)",
        f"",
    ]

    hotspots = res.get("hotspots", [])
    if hotspots:
        md.append("| # | Zentroid (x, y) | Fläche (px) | T_max (°C) | T_mean (°C) | Zirkularität | Risikostufe |")
        md.append("| :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for hs in hotspots:
            md.append(f"| #{hs['id']} | `({hs['centroid'][0]:.0f}, {hs['centroid'][1]:.0f})` | `{hs['area_px']}` | `{hs['max_temp_c']:.2f}` | `{hs['mean_temp_c']:.2f}` | `{hs['circularity']:.2f}` | {hs['risk']} |")
    else:
        md.append("> *Keine pathologischen Herde oberhalb der statistischen Signifikanzgrenze detektiert.*")

    md.extend([
        "",
        "## 4. Hardware- & Algorithmen-Telemetrie",
        "",
        f"- **Berechnungs-Backend:** `{res['backend']}`",
        f"- **Pipeline-Latenz:** `{res['duration_ms']:.1f} ms`",
        f"- **Emissivitätskorrektur:** `ε = {res['emissivity']}` (Hautgewebe)",
        "",
        "---",
        "*Automatisch generierter Befundbericht der IGNITE Suite (Deterministic Lemire Morphology Pipeline).*",
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


# ─────────────────────────────────────────────────────────────────────────────
# 6. SUBCOMMAND HANDLER
# ─────────────────────────────────────────────────────────────────────────────

def handle_analyze(args: argparse.Namespace) -> int:
    """Verarbeitet den 'analyze' Befehl."""
    image_path = args.input
    if not os.path.exists(image_path):
        print(f"[Fehler] Bilddatei '{image_path}' nicht gefunden.", file=sys.stderr)
        return 1

    if not args.quiet:
        print_banner(no_color=args.no_color)
        if RICH_AVAILABLE and not args.no_color:
            console.print(f"[cyan]Starte IGNITE Pipeline für:[/cyan] [bold]{image_path}[/bold]...")
        else:
            print(f"Starte IGNITE Pipeline für: {image_path}...")

    try:
        res = analyze_thermal_image(
            image_path=image_path,
            t_min_c=args.tmin,
            t_max_c=args.tmax,
            temp_offset=args.offset,
            emissivity=args.emissivity,
            backend=args.backend,
            sigma_k=args.sigma_k,
            tophat_factor=args.tophat_factor,
            min_area_factor=args.min_area_factor,
            min_circularity=args.min_circularity,
            otsu_min=args.otsu_min,
            otsu_max=args.otsu_max,
            dist_erosion_factor=args.dist_erosion,
            use_mad=args.use_mad,
            enable_hysteresis=args.hysteresis,
            anatomy_region=args.region,
            compute_frangi=args.frangi or args.save_all,
            compute_bioheat=args.bioheat,
            compute_bilateral_map=args.bilateral_map,
        )

        if not args.quiet and not args.json_only:
            display_analysis_summary(res, no_color=args.no_color)

        # Exporte speichern
        saved = export_results(
            res=res,
            output_dir=args.output_dir,
            save_overlay=args.save_overlay or not (args.no_overlay or args.json_only),
            save_mask=args.save_mask,
            save_diff=args.save_diff,
            save_all=args.save_all,
            colormap_name=args.colormap,
            json_path=args.output_json if args.output_json else (os.path.join(args.output_dir, f"{pathlib.Path(image_path).stem}_result.json") if args.save_json else None),
            report_path=args.output_report if args.output_report else (os.path.join(args.output_dir, f"{pathlib.Path(image_path).stem}_report.md") if args.save_report else None),
            log_audit=args.audit,
        )

        if args.json_only:
            # Reines JSON ins Terminal streamen
            print(json.dumps(to_json_serializable(res), indent=2, ensure_ascii=False))

        elif not args.quiet and saved:
            print("\nGespeicherte Artefakte:")
            for k, p in saved.items():
                print(f"  [{k}] -> {p}")

        return 0

    except Exception as e:
        print(f"[Fehler bei der Analyse] {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_batch(args: argparse.Namespace) -> int:
    """Verarbeitet den 'batch' Befehl."""
    input_dir = args.input_dir
    if not os.path.isdir(input_dir):
        print(f"[Fehler] Verzeichnis '{input_dir}' nicht gefunden.", file=sys.stderr)
        return 1

    patterns = [p.strip() for p in args.pattern.split(",")]
    files: List[str] = []
    for pat in patterns:
        if args.recursive:
            files.extend(glob.glob(os.path.join(input_dir, "**", pat), recursive=True))
        else:
            files.extend(glob.glob(os.path.join(input_dir, pat)))

    # Duplikate filtern und sortieren
    files = sorted(list(set(files)))

    if not files:
        print(f"[Hinweis] Keine passenden Dateien in '{input_dir}' mit Mustern '{args.pattern}' gefunden.")
        return 0

    if not args.quiet:
        print_banner(no_color=args.no_color)
        print(f"Starte Batch-Analyse für {len(files)} Dateien in '{input_dir}'...")

    results: List[Dict[str, Any]] = []
    t_start = time.perf_counter()

    for idx, fpath in enumerate(files, start=1):
        try:
            res = analyze_thermal_image(
                image_path=fpath,
                t_min_c=args.tmin,
                t_max_c=args.tmax,
                temp_offset=args.offset,
                emissivity=args.emissivity,
                backend=args.backend,
                sigma_k=args.sigma_k,
                tophat_factor=args.tophat_factor,
                min_area_factor=args.min_area_factor,
                min_circularity=args.min_circularity,
                otsu_min=args.otsu_min,
                otsu_max=args.otsu_max,
                dist_erosion_factor=args.dist_erosion,
                use_mad=args.use_mad,
                enable_hysteresis=args.hysteresis,
                anatomy_region=args.region,
            )
            results.append(res)

            if args.save_overlays:
                export_results(
                    res=res,
                    output_dir=args.output_dir,
                    save_overlay=True,
                    colormap_name=args.colormap,
                )

            if not args.quiet:
                status_icon = "⚠️" if res["risk_tier"] >= 2 else "✓"
                print(f"[{idx:3d}/{len(files)}] {status_icon} {res['filename']:<24} | TSI: {res['tsi_score']:4.1f} | ΔT: {res['asymmetry'].get('delta_t_c', 0.0):4.2f} °C | {res['duration_ms']:5.1f} ms")

        except Exception as e:
            print(f"[{idx:3d}/{len(files)}] ❌ Fehler bei '{fpath}': {e}", file=sys.stderr)

    total_time = time.perf_counter() - t_start

    # CSV-Export
    os.makedirs(args.output_dir, exist_ok=True)
    csv_path = args.output_csv or os.path.join(args.output_dir, "batch_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Filename", "TSI_Score", "Risk_Tier", "Risk_Name",
            "Delta_T_C", "Is_Asymmetric", "Hotspots_Count", "Hotspots_Pixels",
            "Hotspot_Ratio_Pct", "T_Mean_C", "T_Max_C", "T_Min_C", "Duration_MS"
        ])
        for r in results:
            writer.writerow([
                r["filename"],
                r["tsi_score"],
                r["risk_tier"],
                r["risk_name"],
                r["asymmetry"].get("delta_t_c", 0.0),
                r["asymmetry"].get("is_asymmetric", False),
                len(r["hotspots"]),
                r["hotspot_pixel_count"],
                r["hotspot_ratio_percent"],
                r["mean_temp_c"],
                r["max_temp_c"],
                r["min_temp_c"],
                r["duration_ms"],
            ])

    # JSON-Export
    if args.output_json:
        clean_list = [to_json_serializable(r) for r in results]
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(clean_list, f, indent=2, ensure_ascii=False)

    if not args.quiet:
        high_risk_count = sum(1 for r in results if r["risk_tier"] >= 2)
        print("=" * 78)
        print(f"Batch-Verarbeitung abgeschlossen: {len(results)}/{len(files)} Bilder erfolgreich.")
        print(f"Gesamtlaufzeit: {total_time:.2f} s (Durchschnitt: {total_time / max(1, len(results)) * 1000:.1f} ms/Bild)")
        print(f"Pathologische Befunde (Stufe 2 & 3): {high_risk_count}")
        print(f"CSV-Übersicht: {csv_path}")
        if args.output_json:
            print(f"JSON-Export:   {args.output_json}")
        print("=" * 78)

    return 0


def handle_compare(args: argparse.Namespace) -> int:
    """Verarbeitet den 'compare' Befehl (Longitudinaler Vorher/Nachher-Vergleich)."""
    if not os.path.exists(args.baseline):
        print(f"[Fehler] Baseline-Bild '{args.baseline}' nicht gefunden.", file=sys.stderr)
        return 1
    if not os.path.exists(args.followup):
        print(f"[Fehler] Follow-up-Bild '{args.followup}' nicht gefunden.", file=sys.stderr)
        return 1

    if not args.quiet:
        print_banner(no_color=args.no_color)
        print(f"Vergleiche Untersuchungen:\n  Baseline:  {args.baseline}\n  Follow-up: {args.followup}\n")

    try:
        cmp_res = compare_longitudinal_images(
            baseline_path=args.baseline,
            followup_path=args.followup,
            t_min_c=args.tmin,
            t_max_c=args.tmax,
            output_dir=args.output_dir,
        )

        if RICH_AVAILABLE and not args.no_color:
            p_style = "bold white on green" if cmp_res["status_code"] == "regression" else (
                "bold white on red" if cmp_res["status_code"] == "progression" else "bold black on yellow"
            )
            c_text = (
                f"[bold cyan]Baseline TSI:[/bold cyan] {cmp_res['baseline_tsi']:.1f}  →  "
                f"[bold cyan]Follow-Up TSI:[/bold cyan] {cmp_res['followup_tsi']:.1f}\n\n"
                f"[{p_style}] {cmp_res['clinical_status']} [/{p_style}]\n\n"
                f"• [bold]Mittlere Temperaturdifferenz (ΔT):[/bold] {cmp_res['delta_mean_c']:+.2f} °C\n"
                f"• [bold]Maximale Temperaturveränderung:[/bold]    {cmp_res['delta_max_c']:+.2f} °C\n"
                f"• [bold]Hotspot-Fläche vorher/nachher:[/bold]      {cmp_res['hotspot_area_baseline_px']} px → {cmp_res['hotspot_area_followup_px']} px\n"
                f"• [bold]Flächenveränderung:[/bold]                 {cmp_res['hotspot_area_change_percent']:+.1f} %\n"
            )
            if cmp_res.get("diff_map_path"):
                c_text += f"\n[dim]Differenzielle Heatmap gespeichert: {cmp_res['diff_map_path']}[/dim]"
            console.print(Panel(c_text, title="[bold cyan]IGNITE Longitudinaler Therapieverlauf[/bold cyan]", border_style="cyan"))
        else:
            print("=" * 78)
            print(f"LONGITUDINALER VERLAUFSVERGLEICH")
            print(f"Status: {cmp_res['clinical_status']}")
            print(f"Baseline TSI: {cmp_res['baseline_tsi']:.1f} -> Follow-Up TSI: {cmp_res['followup_tsi']:.1f}")
            print(f"Mittlere Temperaturdifferenz (ΔT): {cmp_res['delta_mean_c']:+.2f} °C")
            print(f"Flächenveränderung der Hotspots:    {cmp_res['hotspot_area_change_percent']:+.1f} %")
            if cmp_res.get("diff_map_path"):
                print(f"Differenz-Heatmap: {cmp_res['diff_map_path']}")
            print("=" * 78)

        if args.json:
            print(json.dumps(cmp_res, indent=2, ensure_ascii=False))

        return 0

    except Exception as e:
        print(f"[Fehler beim Vergleich] {e}", file=sys.stderr)
        return 1


def handle_eval(args: argparse.Namespace) -> int:
    """Verarbeitet den 'eval' Befehl (Evaluation & Benchmarking)."""
    if not args.quiet:
        print_banner(no_color=args.no_color)
        print("Starte wissenschaftliche Evaluierungs-Suite für Jugend forscht...\n")

    # 1. Synthetische Szenarien evaluieren
    if args.synthetic or args.all:
        print("--- 1. Evaluierung synthetischer klinischer Szenarien ---")
        bench = dataset_evaluator.run_benchmark_suite()
        scenarios = bench.get("scenario_results", {})
        if RICH_AVAILABLE and not args.no_color:
            s_table = Table(title="Synthetische Benchmark-Szenarien", border_style="cyan")
            s_table.add_column("Szenario", style="bold")
            s_table.add_column("Dice (F1)", justify="right")
            s_table.add_column("IoU (Jaccard)", justify="right")
            s_table.add_column("Sensitivität", justify="right")
            s_table.add_column("Spezifität", justify="right")
            for name, m in scenarios.items():
                s_table.add_row(name, f"{m['dice']:.3f}", f"{m['iou']:.3f}", f"{m['sensitivity']:.3f}", f"{m['specificity']:.3f}")
            console.print(s_table)
        else:
            for name, m in scenarios.items():
                print(f"  {name:<24} | Dice: {m['dice']:.3f} | IoU: {m['iou']:.3f} | Sens: {m['sensitivity']:.3f} | Spez: {m['specificity']:.3f}")

    # 2. Reale Ground-Truth Daten evaluieren
    if args.gt or args.all:
        test_dir = args.test_data_dir or "test-data"
        gt_dir = args.gt_dir or os.path.join(test_dir, "ground_truth")
        if os.path.isdir(test_dir):
            print(f"\n--- 2. Evaluierung gegen reale Ground-Truth ({test_dir}/) ---")
            gt_results = dataset_evaluator.evaluate_real_dataset_with_gt(test_data_dir=test_dir, gt_dir=gt_dir)
            annotated_count = sum(1 for v in gt_results.values() if v.get("has_ground_truth"))
            print(f"  Analysierte Bilder: {len(gt_results)} (davon {annotated_count} mit Ground-Truth-Annotationen)")

    # 3. Hardware-Laufzeiten
    if args.runtimes or args.all:
        print(f"\n--- 3. Hardware-Laufzeiten & Backend-Vergleich ---")
        try:
            from gui.services.scientific_report_service import ScientificReportService
            runtimes = ScientificReportService._benchmark_hardware_runtimes()
            if RICH_AVAILABLE and not args.no_color:
                r_table = Table(title="Hardware-Skalierung", border_style="green")
                r_table.add_column("Backend", style="bold")
                r_table.add_column("Latenz", justify="right")
                r_table.add_column("Durchsatz (FPS)", justify="right")
                for key, b in runtimes.items():
                    r_table.add_row(b.get("name", key), f"{b.get('latency_ms', 0):.2f} ms", f"{b.get('fps', 0):.1f} fps")
                console.print(r_table)
            else:
                for key, b in runtimes.items():
                    print(f"  {b.get('name', key):<24} | Latenz: {b.get('latency_ms', 0):.2f} ms | {b.get('fps', 0):.1f} FPS")
        except Exception as e:
            print(f"  Hardware-Benchmark übersprungen: {e}")

    return 0


def handle_info(args: argparse.Namespace) -> int:
    """Verarbeitet den 'info' Befehl (System- und Hardware-Telemetrie)."""
    print_banner(no_color=args.no_color)

    import platform
    backend_active = image_processing.get_active_backend()

    # GPU-Details
    gpu_status = "Nicht verfügbar / deaktiviert"
    if getattr(image_processing, "_GPU_AVAILABLE", False):
        try:
            torch = getattr(image_processing, "_TORCH", None)
            if torch and torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                cap = torch.cuda.get_device_capability(0)
                gpu_status = f"CUDA aktiv ({gpu_name}, Compute Capability {cap[0]}.{cap[1]})"
        except Exception:
            gpu_status = "CUDA aktiv"

    # Rust-Details
    rust_status = "Nicht verfügbar (nutze Python-Fallback)"
    if getattr(image_processing, "_RUST_BACKEND_AVAILABLE", False):
        core = getattr(image_processing, "_ignite_core", None)
        v = getattr(core, "__version__", "aktiv")
        b = getattr(core, "__backend__", "CPU+rayon")
        rust_status = f"Verfügbar (v{v}, {b})"

    if RICH_AVAILABLE and not args.no_color:
        table = Table(title="IGNITE System- und Hardware-Status", border_style="cyan", expand=True)
        table.add_column("Komponente", style="bold")
        table.add_column("Status / Konfiguration")

        table.add_row("IGNITE Version", f"v{config.APP_VERSION} (Jugend forscht 2026)")
        table.add_row("Aktives Rechen-Backend", f"[bold green]{backend_active}[/bold green]")
        table.add_row("GPU-Beschleunigung (CUDA)", gpu_status)
        table.add_row("Rust Native Core (AVX2/Rayon)", rust_status)
        table.add_row("CPU-Threads", f"{os.cpu_count() or 4} Kerne ({platform.machine()})")
        table.add_row("Betriebssystem", f"{platform.system()} {platform.release()} ({platform.version()})")
        table.add_row("Python-Laufzeit", f"{platform.python_version()} ({sys.executable})")
        table.add_row("OpenCV Version", cv2.__version__)
        table.add_row("NumPy Version", np.__version__)
        table.add_row("Standard-Schwellenwert (k)", f"{config.DEFAULT_SIGMA_K} (99.86% Konfidenz)")
        table.add_row("Armstrong Asymmetrie-Schwelle", f"{config.ASYMMETRY_THRESHOLD_C} °C (ΔT)")

        console.print(table)
    else:
        print("=" * 78)
        print("IGNITE SYSTEM- UND HARDWARE-STATUS")
        print(f"IGNITE Version:          v{config.APP_VERSION}")
        print(f"Aktives Rechen-Backend:  {backend_active}")
        print(f"GPU (CUDA):              {gpu_status}")
        print(f"Rust Core:               {rust_status}")
        print(f"CPU-Threads:             {os.cpu_count() or 4} Kerne ({platform.machine()})")
        print(f"Betriebssystem:          {platform.system()} {platform.release()}")
        print(f"Python:                  {platform.python_version()} ({sys.executable})")
        print(f"OpenCV:                  {cv2.__version__}")
        print(f"NumPy:                   {np.__version__}")
        print(f"Armstrong Schwelle:      {config.ASYMMETRY_THRESHOLD_C} °C")
        print("=" * 78)

    return 0


def handle_audit(args: argparse.Namespace) -> int:
    """Verarbeitet den 'audit' Befehl (Inspektion des klinischen Audit-Trails)."""
    csv_path = config.AUDIT_TRAIL_PATH
    if not os.path.exists(csv_path):
        print(f"[Hinweis] Bisher kein Audit-Trail unter '{csv_path}' vorhanden.")
        return 0

    entries: List[Dict[str, str]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)

    limit = args.limit or 20
    recent = entries[-limit:]

    if not args.quiet:
        print_banner(no_color=args.no_color)
        print(f"Klinischer DSGVO Audit-Trail (letzte {len(recent)} von {len(entries)} Einträgen):\n")

    if RICH_AVAILABLE and not args.no_color:
        t = Table(title=f"DSGVO Art. 30 Audit-Log ({csv_path})", border_style="cyan")
        t.add_column("Zeitstempel", style="dim")
        t.add_column("Patienten-ID", style="bold")
        t.add_column("Datei")
        t.add_column("Hotspots", justify="right")
        t.add_column("T_max (°C)", justify="right")
        t.add_column("ΔT (°C)", justify="right")
        t.add_column("Operator")

        for r in recent:
            t.add_row(
                r.get("Zeitstempel", ""),
                r.get("Patienten-ID", ""),
                r.get("Bilddatei", ""),
                r.get("Hotspot_Pixel", ""),
                f"{float(r.get('Max_Temp_C', 0.0)):.1f}" if r.get("Max_Temp_C") else "-",
                f"{float(r.get('Symmetrie_Delta', 0.0)):.2f}" if r.get("Symmetrie_Delta") else "-",
                r.get("Operator", ""),
            )
        console.print(t)
    else:
        for r in recent:
            print(f"{r.get('Zeitstempel')} | {r.get('Patienten-ID')} | {r.get('Bilddatei')} | Hotspots: {r.get('Hotspot_Pixel')} | Max: {r.get('Max_Temp_C')} °C")

    return 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. ARGPARSE SETUP & DISPATCHER
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Erstellt den ArgumentParser mit allen Subcommands und Flags."""
    parser = argparse.ArgumentParser(
        prog="ignite-cli",
        description="IGNITE Medical Imaging Suite – Deterministische Thermografie-Workstation CLI.",
        epilog="Jugend forscht 2026 · Fachgebiet Arbeitswelt · Autor: Jona Noack",
    )
    parser.add_argument("-v", "--version", action="version", version=f"IGNITE CLI v{config.APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # ── Subcommand: analyze ───────────────────────────────────────────────────
    p_analyze = subparsers.add_parser("analyze", help="Analysiert ein einzelnes Infrarot-Wärmebild.")
    p_analyze.add_argument("input", type=str, help="Pfad zum Wärmebild (JPEG, PNG, TIFF, RJPG, NPY)")
    p_analyze.add_argument("-o", "--output-dir", type=str, default=config.OUTPUT_DIR, help=f"Ausgabeverzeichnis für Artefakte (Standard: {config.OUTPUT_DIR})")
    # Kalibrierung
    p_analyze.add_argument("--tmin", type=float, default=config.DEFAULT_TEMP_MIN, help="Untere Temperaturskala in °C (Standard: 20.0)")
    p_analyze.add_argument("--tmax", type=float, default=config.DEFAULT_TEMP_MAX, help="Obere Temperaturskala in °C (Standard: 40.0)")
    p_analyze.add_argument("--offset", type=float, default=0.0, help="Kalibrierungs-Offset in K/°C (Standard: 0.0)")
    p_analyze.add_argument("--emissivity", type=float, default=config.SKIN_EMISSIVITY, help=f"Emissivitätsgrad der Haut (Standard: {config.SKIN_EMISSIVITY})")
    p_analyze.add_argument("--region", type=str, default="feet", choices=list(config.ANATOMICAL_REGIONS.keys()), help="Anatomische Region (Standard: feet)")
    # Backend & Algorithmen
    p_analyze.add_argument("--backend", type=str, default="auto", choices=["auto", "gpu", "rust", "python"], help="Rechen-Backend (Standard: auto)")
    p_analyze.add_argument("--sigma-k", type=float, default=config.DEFAULT_SIGMA_K, help="Statistischer Schwellenwert-Faktor k (Standard: 3.0)")
    p_analyze.add_argument("--tophat-factor", type=float, default=config.DEFAULT_TOPHAT_FACTOR, help="Top-Hat Strukturelement-Faktor (Standard: 0.05)")
    p_analyze.add_argument("--min-area-factor", type=float, default=config.DEFAULT_MIN_AREA_FACTOR, help="Minimale Hotspot-Fläche (Standard: 0.0005)")
    p_analyze.add_argument("--min-circularity", type=float, default=config.DEFAULT_MIN_CIRCULARITY, help="Mindest-Zirkularität (Standard: 0.08)")
    p_analyze.add_argument("--otsu-min", type=int, default=config.DEFAULT_OTSU_MIN, help="Multi-Otsu Min-Schwelle (Standard: 35)")
    p_analyze.add_argument("--otsu-max", type=int, default=config.DEFAULT_OTSU_MAX, help="Multi-Otsu Max-Schwelle (Standard: 50)")
    p_analyze.add_argument("--dist-erosion", type=float, default=config.DEFAULT_DIST_EROSION_FACTOR, help="Distanzerosions-Faktor (Standard: 0.05)")
    p_analyze.add_argument("--use-mad", action="store_true", help="Median Absolute Deviation (MAD) statt Gauß-Std nutzen")
    p_analyze.add_argument("--hysteresis", action="store_true", help="Adaptive Doppel-Schwellenwert-Hysterese aktivieren")
    p_analyze.add_argument("--frangi", action="store_true", help="Frangi-Vesselness Venenkartierungsfilter berechnen")
    p_analyze.add_argument("--bioheat", action="store_true", help="Pennes Bioheat Wärmeflussdichte berechnen")
    p_analyze.add_argument("--bilateral-map", action="store_true", help="Bilateralen Differenz-Subtraktionsplan berechnen")
    # Exporte & Rendering
    p_analyze.add_argument("--colormap", type=str, default="turbo", choices=["turbo", "inferno", "ironbow", "jet", "hot", "plasma", "gray"], help="Farbpalette für Overlay (Standard: turbo)")
    p_analyze.add_argument("--save-overlay", action="store_true", help="Diagnostisches Overlay als PNG speichern")
    p_analyze.add_argument("--no-overlay", action="store_true", help="Erstellung des Overlays überspringen")
    p_analyze.add_argument("--save-mask", action="store_true", help="Binäre Hotspot-Maske speichern")
    p_analyze.add_argument("--save-diff", action="store_true", help="Top-Hat Differenzbild speichern")
    p_analyze.add_argument("--save-all", action="store_true", help="Alle Zwischenstufen und Masken speichern")
    p_analyze.add_argument("--save-json", action="store_true", help="Ergebnis automatisch als JSON speichern")
    p_analyze.add_argument("--output-json", type=str, help="Pfad für JSON-Befundexport")
    p_analyze.add_argument("--save-report", action="store_true", help="Klinischen Markdown-Bericht generieren")
    p_analyze.add_argument("--output-report", type=str, help="Pfad für Markdown-Befundbericht (.md)")
    p_analyze.add_argument("--audit", action="store_true", help="Eintrag in revisionssicheren DSGVO-Audit-Trail schreiben")
    p_analyze.add_argument("-q", "--quiet", action="store_true", help="Terminalausgaben unterdrücken")
    p_analyze.add_argument("--json-only", action="store_true", help="Nur JSON auf stdout ausgeben (ideal für Skripte & Pipes)")
    p_analyze.add_argument("--no-color", action="store_true", help="Farbige Rich-Formatierung deaktivieren")
    p_analyze.add_argument("--verbose", action="store_true", help="Ausführliche Stacktraces bei Fehlern ausgeben")

    # ── Subcommand: batch ─────────────────────────────────────────────────────
    p_batch = subparsers.add_parser("batch", help="Batch-Verarbeitung ganzer Ordner mit Wärmebildern.")
    p_batch.add_argument("input_dir", type=str, help="Ordner mit Eingabebildern")
    p_batch.add_argument("-p", "--pattern", type=str, default="*.jpeg,*.jpg,*.png,*.tiff,*.npy", help="Dateimuster (Standard: *.jpeg,*.jpg,*.png,*.tiff,*.npy)")
    p_batch.add_argument("-r", "--recursive", action="store_true", help="Unterverzeichnisse rekursiv durchsuchen")
    p_batch.add_argument("-o", "--output-dir", type=str, default=config.OUTPUT_DIR, help=f"Ausgabeverzeichnis (Standard: {config.OUTPUT_DIR})")
    p_batch.add_argument("--output-csv", type=str, help="Pfad zur aggregierten CSV-Zusammenfassung")
    p_batch.add_argument("--output-json", type=str, help="Pfad zum aggregierten JSON-Export")
    p_batch.add_argument("--save-overlays", action="store_true", help="Diagnostische Overlays für alle Bilder rendern und speichern")
    p_batch.add_argument("--colormap", type=str, default="turbo", help="Farbpalette für Overlays")
    p_batch.add_argument("--tmin", type=float, default=config.DEFAULT_TEMP_MIN)
    p_batch.add_argument("--tmax", type=float, default=config.DEFAULT_TEMP_MAX)
    p_batch.add_argument("--offset", type=float, default=0.0)
    p_batch.add_argument("--emissivity", type=float, default=config.SKIN_EMISSIVITY)
    p_batch.add_argument("--region", type=str, default="feet")
    p_batch.add_argument("--backend", type=str, default="auto", choices=["auto", "gpu", "rust", "python"])
    p_batch.add_argument("--sigma-k", type=float, default=config.DEFAULT_SIGMA_K)
    p_batch.add_argument("--tophat-factor", type=float, default=config.DEFAULT_TOPHAT_FACTOR)
    p_batch.add_argument("--min-area-factor", type=float, default=config.DEFAULT_MIN_AREA_FACTOR)
    p_batch.add_argument("--min-circularity", type=float, default=config.DEFAULT_MIN_CIRCULARITY)
    p_batch.add_argument("--otsu-min", type=int, default=config.DEFAULT_OTSU_MIN)
    p_batch.add_argument("--otsu-max", type=int, default=config.DEFAULT_OTSU_MAX)
    p_batch.add_argument("--dist-erosion", type=float, default=config.DEFAULT_DIST_EROSION_FACTOR)
    p_batch.add_argument("--use-mad", action="store_true")
    p_batch.add_argument("--hysteresis", action="store_true")
    p_batch.add_argument("-q", "--quiet", action="store_true")
    p_batch.add_argument("--no-color", action="store_true")

    # ── Subcommand: compare ───────────────────────────────────────────────────
    p_compare = subparsers.add_parser("compare", help="Longitudinaler Vorher/Nachher-Vergleich zweier Untersuchungen.")
    p_compare.add_argument("baseline", type=str, help="Baseline-Aufnahme (Erstuntersuchung)")
    p_compare.add_argument("followup", type=str, help="Follow-up-Aufnahme (Verlaufskontrolle)")
    p_compare.add_argument("-o", "--output-dir", type=str, default=config.OUTPUT_DIR, help="Ausgabeordner für Differenz-Heatmap")
    p_compare.add_argument("--tmin", type=float, default=config.DEFAULT_TEMP_MIN)
    p_compare.add_argument("--tmax", type=float, default=config.DEFAULT_TEMP_MAX)
    p_compare.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    p_compare.add_argument("-q", "--quiet", action="store_true")
    p_compare.add_argument("--no-color", action="store_true")

    # ── Subcommand: eval ──────────────────────────────────────────────────────
    p_eval = subparsers.add_parser("eval", help="Quantitative Evaluation gegen Ground-Truth & Benchmarks.")
    p_eval.add_argument("--synthetic", action="store_true", help="Synthetische Benchmark-Szenarien evaluieren")
    p_eval.add_argument("--gt", action="store_true", help="Reale Ground-Truth Masken evaluieren")
    p_eval.add_argument("--runtimes", action="store_true", help="Hardware-Laufzeiten aller Backends messen")
    p_eval.add_argument("--all", action="store_true", default=True, help="Alle wissenschaftlichen Benchmarks durchführen (Standard)")
    p_eval.add_argument("--test-data-dir", type=str, default="test-data")
    p_eval.add_argument("--gt-dir", type=str, default=None)
    p_eval.add_argument("-q", "--quiet", action="store_true")
    p_eval.add_argument("--no-color", action="store_true")

    # ── Subcommand: info ──────────────────────────────────────────────────────
    p_info = subparsers.add_parser("info", help="Zeigt System- und Hardware-Telemetrie an (GPU, Rust, CPU).")
    p_info.add_argument("--no-color", action="store_true")

    # ── Subcommand: audit ─────────────────────────────────────────────────────
    p_audit = subparsers.add_parser("audit", help="Zeigt die letzten Einträge des revisionssicheren Audit-Trails an.")
    p_audit.add_argument("-n", "--limit", type=int, default=20, help="Anzahl der Einträge (Standard: 20)")
    p_audit.add_argument("-q", "--quiet", action="store_true")
    p_audit.add_argument("--no-color", action="store_true")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Haupteinstiegspunkt der CLI."""
    if argv is None:
        argv = sys.argv[1:]

    # Intelligentes Auto-Routing: Wenn das erste Argument ein existierendes Bild ist,
    # automatisch als 'analyze' interpretieren!
    if argv and not argv[0].startswith("-"):
        first_arg = argv[0].lower()
        subcommands = {"analyze", "batch", "compare", "eval", "info", "audit"}
        if first_arg not in subcommands:
            # Prüfen ob es eine Datei oder Bild ist
            if os.path.isfile(argv[0]) or any(first_arg.endswith(ext) for ext in (".jpeg", ".jpg", ".png", ".tiff", ".tif", ".npy")):
                argv = ["analyze"] + argv

    parser = build_parser()

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if args.command == "analyze":
        return handle_analyze(args)
    elif args.command == "batch":
        return handle_batch(args)
    elif args.command == "compare":
        return handle_compare(args)
    elif args.command == "eval":
        return handle_eval(args)
    elif args.command == "info":
        return handle_info(args)
    elif args.command == "audit":
        return handle_audit(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
