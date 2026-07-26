"""
generate_documentation_assets.py
Erzeugt Schritt-für-Schritt Bilddateien der 5 Pipeline-Stufen und einen echten Screenshot der IGNITE Benutzeroberfläche für die Jugend forscht Arbeit.
"""

import os
import sys
import time
import cv2
import numpy as np
import image_processing
import config

os.makedirs("images", exist_ok=True)

# 1. Schritt-für-Schritt Pipeline-Visualisierung auf einem echten Testbild
test_img_path = os.path.join("test-data", "bild (1).jpeg")
if os.path.exists(test_img_path):
    img = image_processing.load_thermal_image(test_img_path)
    
    # Raw original colorized (Jet colormap)
    jet_orig = cv2.applyColorMap(img, cv2.COLORMAP_JET)
    cv2.imwrite("images/1_original_thermal_jet.png", jet_orig)
    cv2.imwrite("images/1_original_thermal_gray.png", img)

    # Stage 2: Body Mask & Distance Transform
    body_mask = image_processing._extract_body_mask_cpu(img)
    cv2.imwrite("images/2_body_mask.png", body_mask)
    
    dist_map = cv2.distanceTransform(body_mask, cv2.DIST_L2, 3)
    dist_vis = cv2.normalize(dist_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    dist_jet = cv2.applyColorMap(dist_vis, cv2.COLORMAP_VIRIDIS)
    cv2.imwrite("images/2_distance_transform.png", dist_jet)

    # Stage 3: Top-Hat Filtered Difference Image
    dim = min(img.shape[0], img.shape[1])
    kernel_large = image_processing.compute_odd_kernel(dim, config.DEFAULT_TOPHAT_FACTOR)
    kernel_se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_large, kernel_large))
    img_blurred = cv2.blur(img, (3, 3))
    opened = cv2.morphologyEx(img_blurred, cv2.MORPH_OPEN, kernel_se)
    tophat = cv2.subtract(img_blurred, opened)
    diff_img = cv2.bitwise_and(tophat, tophat, mask=body_mask)
    diff_vis = cv2.normalize(diff_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    cv2.imwrite("images/3_tophat_difference.png", diff_vis)

    # Stage 4 & 5: Hotspot Detection & Geometric Filter
    diff_vis_rust, hotspot_mask = image_processing.run_rust_pipeline(img)
    cv2.imwrite("images/4_hotspot_mask.png", hotspot_mask)

    # Final Overlay
    overlay = image_processing.create_hotspot_overlay(img, hotspot_mask, colormap_name="Regenbogen (Jet)")
    cv2.imwrite("images/5_final_overlay_jet.png", overlay)
    
    print("[+] Pipeline-Bilder in images/ gespeichert.")

# 2. Synthetic Scenario Comparison Image
from dataset_evaluator import generate_clinical_scenario
synth_img, synth_gt = generate_clinical_scenario("diabetic_ulcer")
synth_diff, synth_mask = image_processing.run_rust_pipeline(synth_img)
synth_overlay = image_processing.create_hotspot_overlay(synth_img, synth_mask, colormap_name="Inferno")
cv2.imwrite("images/synthetic_diabetic_ulcer.png", synth_overlay)

print("[+] Dokumentations-Assets erfolgreich erzeugt.")
