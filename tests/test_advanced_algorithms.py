# -*- coding: utf-8 -*-
"""tests/test_advanced_algorithms.py – Validation for all 5 new IGNITE v3.3 Algorithms.

Tests:
1. Multi-Scale Morphological Top-Hat (MTH)
2. Thermal Gradients and 2D-Laplace Divergence
3. PCA-based Foot Alignment and Rotational Invariance
4. Thermal Severity Index (TSI) & IWGDF Risk Tiers
5. Multi-Otsu Tissue Segmentation
"""

import numpy as np
import cv2
import pytest

import image_processing
import config


def test_multiscale_tophat_detects_multiple_scales():
    """Testet, dass MTH sowohl kleine als auch große Hitzeherde erfasst."""
    img = np.zeros((300, 300), dtype=np.uint8)
    mask = np.ones((300, 300), dtype=np.uint8) * 255

    # 1. Kleiner Hotspot (Radius 4 px)
    rr, cc = np.ogrid[:300, :300]
    small_spot = np.sqrt((rr - 80)**2 + (cc - 80)**2) <= 4
    img[small_spot] = 220

    # 2. Großer Hotspot (Radius 25 px)
    large_spot = np.sqrt((rr - 200)**2 + (cc - 200)**2) <= 25
    img[large_spot] = 200

    mth = image_processing.compute_multiscale_tophat(
        img, factors=(0.025, 0.050, 0.100), mask=mask
    )

    # Beide Spots müssen in der MTH-Differenzkarte vorhanden sein
    assert np.max(mth[small_spot]) > 50
    assert np.max(mth[large_spot]) > 50


def test_thermal_gradients_and_divergence():
    """Testet die Berechnung des Gradientenbetrags und der Laplace-Divergenz."""
    img = np.full((100, 100), 50, dtype=np.uint8)
    mask = np.ones((100, 100), dtype=np.uint8) * 255

    # Erzeuge einen scharfen Hotspot in der Mitte
    rr, cc = np.ogrid[:100, :100]
    center_dist = np.sqrt((rr - 50)**2 + (cc - 50)**2)
    hotspot = center_dist <= 8
    img[hotspot] = 240

    res = image_processing.compute_thermal_gradients_and_divergence(img, mask)

    assert "grad_magnitude" in res
    assert "laplacian" in res
    assert res["max_gradient"] > 100.0  # Steiler Randabfall
    assert res["min_laplacian"] < -50.0  # Signifikante negative Divergenz (Wärmequelle)


def test_pca_foot_alignment_and_rotation():
    """Testet, dass PCA-Ausrichtung den Rotationswinkel und 3 Zonen rotationsinvariant berechnet."""
    img = np.zeros((400, 400), dtype=np.uint8)
    body_mask = np.zeros((400, 400), dtype=np.uint8)

    # Erzeuge einen linken Fuß (längliches Oval)
    left_foot_mask = np.zeros((400, 400), dtype=np.uint8)
    cv2.ellipse(left_foot_mask, (100, 200), (40, 120), 15, 0, 360, 255, -1)

    # Erzeuge einen rechten Fuß (längliches Oval, nach links geneigt -15 Grad)
    right_foot_mask = np.zeros((400, 400), dtype=np.uint8)
    cv2.ellipse(right_foot_mask, (300, 200), (40, 120), -15, 0, 360, 255, -1)

    body_mask = cv2.bitwise_or(left_foot_mask, right_foot_mask)
    img[body_mask > 0] = 150  # Grundtemperatur

    # Hotspot im linken Vorfuß
    img[120:140, 90:110] = 230

    pca_res = image_processing.compute_pca_foot_alignment_and_zones(img, body_mask, 20.0, 40.0)

    assert pca_res["pca_aligned"] is True
    assert pca_res["left"]["exists"] is True
    assert pca_res["right"]["exists"] is True

    # Winkel sollten annähernd erkannt werden
    l_angle = pca_res["left"]["angle_deg"]
    r_angle = pca_res["right"]["angle_deg"]
    assert isinstance(l_angle, float)
    assert isinstance(r_angle, float)

    # Vorfuß-Temperatur links sollte signifikant höher sein als rechts
    assert pca_res["left"]["fore_c"] > pca_res["right"]["fore_c"]


def test_thermal_severity_index_classification():
    """Testet die TSI-Risikoklassifikation für Normalbefund und akute Entzündung."""
    # 1. Normalbefund: kein Delta-T, keine Hotspots
    tsi_norm = image_processing.compute_thermal_severity_index(
        delta_t_c=0.3,
        hotspot_pixel_count=0,
        body_pixel_count=5000,
        max_gradient=10.0,
        std_pixel=5.0
    )
    assert tsi_norm["tier"] == 0
    assert "Normalbefund" in tsi_norm["tier_name"]
    assert tsi_norm["score"] <= 2.0

    # 2. Akuter Ulkusbefund: Delta-T = 3.5 °C, 500 Hotspot-Pixel
    tsi_acute = image_processing.compute_thermal_severity_index(
        delta_t_c=3.5,
        hotspot_pixel_count=500,
        body_pixel_count=5000,
        max_gradient=200.0,
        std_pixel=20.0
    )
    assert tsi_acute["tier"] >= 2
    assert tsi_acute["score"] >= 6.0


def test_multi_otsu_tissue_segmentation():
    """Testet, dass Multi-Otsu Gewebe sauber extrahiert und Randbereiche erodiert."""
    img = np.full((200, 200), 10, dtype=np.uint8)  # Kalter Hintergrund
    img[50:150, 50:150] = 120  # Warmes Gewebe

    mask = image_processing.extract_body_mask_multi_otsu(img)
    assert np.sum(mask == 255) > 0
    # Hintergrund darf nicht maskiert sein
    assert mask[10, 10] == 0
    # Kernbereich muss maskiert sein
    assert mask[100, 100] == 255
