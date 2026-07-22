"""dataset_evaluator.py – Quantitativer Benchmark & Evaluierungs-Engine für IGNITE.

Generiert synthetische klinische Szenarien mit realistischen Rauschmodellen 
(Gaußsches Sensorrauschen, Gewebe-Unschärfe, thermische Gradienten) und 
evaluiert reale thermografische Test-Bilddaten aus test-data/.
"""

import os
import json
import cv2
import numpy as np
import image_processing
import config

def generate_clinical_scenario(scenario_type: str = "diabetic_ulcer", width: int = 400, height: int = 400, add_noise: bool = True):
    """
    Generiert ein synthetisches Wärmebild und die dazugehörige Ground-Truth-Maske
    für klinische Entzündungsszenarien inkl. realistischer Rausch- & Gradienten-Modelle.
    """
    img = np.zeros((height, width), dtype=np.float32)
    ground_truth = np.zeros((height, width), dtype=np.uint8)

    # 1. Körperkontur (Simulierte Füße/Körperbereich)
    # Hintergrund: ~15 (kalt), Körper: ~85 (Hauttemperatur)
    img[40:240, 60:180] = 85.0   # Linker Fuß
    img[40:240, 220:340] = 85.0  # Rechter Fuß

    if scenario_type == "normal":
        pass

    elif scenario_type == "diabetic_ulcer":
        rr, cc = np.ogrid[:height, :width]
        dist1 = np.sqrt((rr - 100)**2 + (cc - 120)**2)
        hotspot1_mask = dist1 <= 6
        img[hotspot1_mask] = 195.0  # Starke Hitzeentwicklung
        ground_truth[hotspot1_mask] = 255

    elif scenario_type == "plantar_fasciitis":
        rr, cc = np.ogrid[:height, :width]
        dist_heel = np.sqrt((rr - 200)**2 + (cc - 280)**2)
        hotspot_heel = dist_heel <= 7
        img[hotspot_heel] = 190.0
        ground_truth[hotspot_heel] = 255

    elif scenario_type == "focal_sensor_noise":
        img[80, 100] = 240.0
        img[150, 300] = 245.0
        # Ground Truth bleibt 0 (Artefakte)

    elif scenario_type == "complex_multi_inflammation":
        rr, cc = np.ogrid[:height, :width]
        h1 = np.sqrt((rr - 70)**2 + (cc - 110)**2) <= 5
        img[h1] = 190.0
        ground_truth[h1] = 255

        h2 = np.sqrt((rr - 160)**2 + (cc - 270)**2) <= 7
        img[h2] = 200.0
        ground_truth[h2] = 255

    if add_noise:
        # Realistisches Gaußsches Sensorrauschen (sigma = 2.5)
        rng = np.random.default_rng(seed=42)
        noise = rng.normal(0, 2.5, size=(height, width)).astype(np.float32)
        img += noise

        # Thermischer Rand-Gradient (Weichzeichnung anatomischer Gewebeübergänge)
        img = cv2.GaussianBlur(img, (3, 3), 0.8)

    img = np.clip(img, 0, 255).astype(np.uint8)
    return img, ground_truth

def evaluate_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray, body_mask: np.ndarray = None):
    """
    Berechnet quantitative Konfusionsmatrix-Metriken:
    Sensitivity, Specificity, Precision, Recall, Dice, IoU.
    """
    pred_bin = (pred_mask > 0).astype(bool)
    gt_bin = (gt_mask > 0).astype(bool)

    if body_mask is not None:
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

def evaluate_real_test_dataset(test_data_dir: str = "test-data"):
    """
    Evaluiert reale klinische/thermodynamische Bilddateien im Ordner test-data/.
    """
    if not os.path.exists(test_data_dir):
        print(f"[!] Warnung: Ordner '{test_data_dir}' nicht gefunden.")
        return {}

    image_files = [f for f in os.listdir(test_data_dir) if f.lower().endswith(('.jpeg', '.jpg', '.png'))]
    if not image_files:
        print(f"[!] Keine Bilddateien in '{test_data_dir}' gefunden.")
        return {}

    print(f"\n--- Evaluierung realer Test-Bilddaten ({len(image_files)} Bilder in {test_data_dir}/) ---")
    real_results = {}

    for img_name in sorted(image_files):
        img_path = os.path.join(test_data_dir, img_name)
        try:
            img = image_processing.load_thermal_image(img_path)
            diff_vis, hotspot_mask = image_processing.run_rust_pipeline(img)
            body_mask = image_processing._extract_body_mask_cpu(img)

            body_pixels = np.sum(body_mask == 255)
            hotspot_pixels = np.sum(hotspot_mask == 255)
            ratio = (hotspot_pixels / body_pixels * 100.0) if body_pixels > 0 else 0.0

            real_results[img_name] = {
                "dimensions": [int(img.shape[1]), int(img.shape[0])],
                "body_pixels": int(body_pixels),
                "hotspot_pixels": int(hotspot_pixels),
                "hotspot_coverage_percent": float(round(ratio, 2)),
                "status": "Erfolgreich verarbeitet"
            }
            print(f"Bild [{img_name:18s}]: Dim={img.shape[1]}x{img.shape[0]} | Body={body_pixels}px | Hotspot={hotspot_pixels}px ({ratio:.2f}%)")

        except Exception as e:
            real_results[img_name] = {"status": f"Fehler: {e}"}
            print(f"Bild [{img_name:18s}]: Fehler - {e}")

    return real_results

def run_benchmark_suite():
    """
    Führt die vollständige Benchmark-Testsuite durch:
    - Synthetische Szenarien mit realistischen Rausch-Modellen
    - Parameter-Sensitivitätsanalyse
    - Reale Test-Bilddaten-Evaluierung aus test-data/
    """
    scenarios = ["normal", "diabetic_ulcer", "plantar_fasciitis", "focal_sensor_noise", "complex_multi_inflammation"]
    results = {}

    print("=== IGNITE Medical Thermal Evaluation Benchmark ===")

    for scenario in scenarios:
        img, gt = generate_clinical_scenario(scenario, add_noise=True)
        diff_img, pred_mask = image_processing.run_rust_pipeline(img)
        body_mask = image_processing._extract_body_mask_cpu(img)

        metrics = evaluate_metrics(pred_mask, gt, body_mask)
        results[scenario] = metrics

        print(f"Szenario [{scenario:25s}]: Sensitivity={metrics['sensitivity']:.2f}, Specificity={metrics['specificity']:.2f}, Dice={metrics['dice']:.2f}, IoU={metrics['iou']:.2f}")

    # Parameter-Sensitivitätsanalyse für k (1.0 bis 5.0)
    print("\n--- Parameter-Sensitivitätsanalyse (Sigma k) ---")
    k_analysis = {}
    img_eval, gt_eval = generate_clinical_scenario("diabetic_ulcer", add_noise=True)
    body_mask_eval = image_processing._extract_body_mask_cpu(img_eval)

    for k_val in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
        diff_img, pred_mask = image_processing._python_fallback_pipeline(
            img_eval,
            sigma_k=k_val
        )
        m = evaluate_metrics(pred_mask, gt_eval, body_mask_eval)
        k_analysis[str(k_val)] = m
        print(f"k = {k_val:.1f} | Sensitivität: {m['sensitivity']:.4f} | Spezifität: {m['specificity']:.4f} | Dice: {m['dice']:.4f}")

    # Reale Testbilder aus test-data/ auswerten
    real_dataset_results = evaluate_real_test_dataset()

    output_data = {
        "scenario_results": results,
        "sensitivity_analysis_k": k_analysis,
        "real_test_dataset": real_dataset_results
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
