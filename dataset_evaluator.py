"""dataset_evaluator.py – Quantitativer Benchmark & Evaluierungs-Engine für IGNITE.

Generiert synthetische klinische Szenarien (z. B. Diabetischer Fuß, Plantarfasziitis,
sensorbedingtes Rauschen) mit Ground-Truth-Masken und berechnet metrische Gütemaße
(Sensitivität, Spezifität, Precision, Recall, Dice-Koeffizient, IoU und ROC-Kurven).
"""

import os
import json
import numpy as np
import image_processing
import config

def generate_clinical_scenario(scenario_type: str = "diabetic_ulcer", width: int = 400, height: int = 400):
    """
    Generiert ein synthetisches Wärmebild und die dazugehörige Ground-Truth-Maske
    für klinische Entzündungsszenarien.
    """
    img = np.zeros((height, width), dtype=np.uint8)
    ground_truth = np.zeros((height, width), dtype=np.uint8)

    # 1. Körperkontur (Simulierte Füße/Körperbereich)
    # Hintergrund: ~10-20 (kalt, Raummilieu), Körper: ~80-100 (Hauttemperatur ~30-34°C)
    img[40:240, 60:180] = 85   # Linker Fuß
    img[40:240, 220:340] = 85  # Rechter Fuß

    if scenario_type == "normal":
        # Physiologisch normaler Zustand ohne signifikante Entzündungsherde
        pass

    elif scenario_type == "diabetic_ulcer":
        # Lokaler Hotspot im Mittelfuß/Zehenbereich (starke lokale Erwärmung)
        rr, cc = np.ogrid[:height, :width]
        dist1 = np.sqrt((rr - 100)**2 + (cc - 120)**2)
        hotspot1_mask = dist1 <= 6
        img[hotspot1_mask] = 195  # Starke Hitzeentwicklung
        ground_truth[hotspot1_mask] = 255

    elif scenario_type == "plantar_fasciitis":
        # Hotspot an der Ferse des rechten Fußes (innerhalb des gültigen Y-Bereichs)
        rr, cc = np.ogrid[:height, :width]
        dist_heel = np.sqrt((rr - 200)**2 + (cc - 280)**2)
        hotspot_heel = dist_heel <= 7
        img[hotspot_heel] = 190
        ground_truth[hotspot_heel] = 255

    elif scenario_type == "focal_sensor_noise":
        # Einzelne isolierte Rausch-Pixel (sollten vom geometrischen Filter E entfernt werden)
        img[80, 100] = 240
        img[150, 300] = 245
        # Ground Truth bleibt 0, da es sich um Rauschartefakte handelt!

    elif scenario_type == "complex_multi_inflammation":
        # Kombiniertes Szenario mit mehreren Hotspots
        rr, cc = np.ogrid[:height, :width]

        # Hotspot 1: Zehe links (Radius 5)
        h1 = np.sqrt((rr - 70)**2 + (cc - 110)**2) <= 5
        img[h1] = 190
        ground_truth[h1] = 255

        # Hotspot 2: Mittelfuß rechts (Radius 7)
        h2 = np.sqrt((rr - 160)**2 + (cc - 270)**2) <= 7
        img[h2] = 200
        ground_truth[h2] = 255

    return img, ground_truth

def evaluate_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray, body_mask: np.ndarray = None):
    """
    Berechnet quantitative Konfusionsmatrix-Metriken:
    - Sensitivity (Recall)
    - Specificity
    - Precision
    - Dice-Koeffizient (F1-Score)
    - IoU (Intersection over Union / Jaccard Index)
    """
    pred_bin = (pred_mask > 0).astype(bool)
    gt_bin = (gt_mask > 0).astype(bool)

    if body_mask is not None:
        # Auswertung exklusiv auf dem Körperbereich (Hintergrund ignorieren)
        valid_area = (body_mask > 0)
        pred_bin = pred_bin & valid_area
        gt_bin = gt_bin & valid_area

    tp = np.sum(pred_bin & gt_bin)
    fp = np.sum(pred_bin & ~gt_bin)
    fn = np.sum(~pred_bin & gt_bin)
    tn = np.sum(~pred_bin & ~gt_bin)

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 1.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = sensitivity
    dice = (2.0 * tp) / (2.0 * tp + fp + fn) if (2.0 * tp + fp + fn) > 0 else (1.0 if (fp + fn) == 0 else 0.0)
    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else (1.0 if (fp + fn) == 0 else 0.0)

    return {
        "TP": int(tp),
        "FP": int(fp),
        "TN": int(tn),
        "FN": int(fn),
        "sensitivity": float(round(sensitivity, 4)),
        "specificity": float(round(specificity, 4)),
        "precision": float(round(precision, 4)),
        "recall": float(round(recall, 4)),
        "dice": float(round(dice, 4)),
        "iou": float(round(iou, 4))
    }

def run_benchmark_suite():
    """
    Führt die vollständige Benchmark-Testsuite über alle klinischen Szenarien durch
    und generiert eine Parameter-Sensitivitätsanalyse für Sigma-k (mu + k*sigma).
    """
    scenarios = ["normal", "diabetic_ulcer", "plantar_fasciitis", "focal_sensor_noise", "complex_multi_inflammation"]
    results = {}

    print("=== IGNITE Medical Thermal Evaluation Benchmark ===")

    for scenario in scenarios:
        img, gt = generate_clinical_scenario(scenario)
        diff_img, pred_mask = image_processing.run_rust_pipeline(img)

        # Body-Mask extrahieren
        body_mask = image_processing._extract_body_mask_cpu(img)
        metrics = evaluate_metrics(pred_mask, gt, body_mask)
        results[scenario] = metrics

        print(f"Szenario [{scenario:25s}]: Sensitivity={metrics['sensitivity']:.2f}, Specificity={metrics['specificity']:.2f}, Dice={metrics['dice']:.2f}, IoU={metrics['iou']:.2f}")

    # Parameter-Sensitivitätsanalyse für k (1.0 bis 5.0)
    print("\n--- Parameter-Sensitivitätsanalyse (Sigma k) ---")
    k_analysis = {}
    img_eval, gt_eval = generate_clinical_scenario("diabetic_ulcer")
    body_mask_eval = image_processing._extract_body_mask_cpu(img_eval)

    for k_val in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
        diff_img, pred_mask = image_processing._python_fallback_pipeline(
            img_eval,
            sigma_k=k_val
        )
        m = evaluate_metrics(pred_mask, gt_eval, body_mask_eval)
        k_analysis[str(k_val)] = m
        print(f"k = {k_val:.1f} | Sensitivität: {m['sensitivity']:.4f} | Spezifität: {m['specificity']:.4f} | Dice: {m['dice']:.4f}")

    output_data = {
        "scenario_results": results,
        "sensitivity_analysis_k": k_analysis
    }

    # Ergebnisse speichern
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(config.OUTPUT_DIR, "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"\n[+] Benchmark erfolgreich abgeschlossen! Ergebnisse gespeichert in: {out_path}")
    return output_data

if __name__ == "__main__":
    run_benchmark_suite()
