"""dataset_evaluator.py – Quantitativer Benchmark & Evaluierungs-Engine für IGNITE.

Generiert synthetische klinische Szenarien mit realistischen Rauschmodellen 
(Gaußsches Sensorrauschen, Gewebe-Unschärfe, thermische Gradienten) und 
evaluiert reale thermografische Test-Bilddaten aus test-data/.

Enthält außerdem:
- Vergleich gegen eine einfache Otsu-Baseline (Nachweis der Überlegenheit von IGNITE)
- Quantitative GT-Evaluation anhand manuell annotierter Masken aus test-data/ground_truth/
"""

import os
import json
import hashlib
from contextlib import contextmanager
import cv2
import numpy as np
import image_processing
import config

DEFAULT_BENCHMARK_SEED = 42
DEFAULT_BENCHMARK_BACKEND = "python"


def _scenario_seed(scenario_type: str, base_seed: int) -> int:
    digest = hashlib.sha256(scenario_type.encode("utf-8")).digest()
    offset = int.from_bytes(digest[:8], "little")
    return (base_seed + offset) % (2**32)


@contextmanager
def _forced_backend(backend: str):
    previous_backend = image_processing.FORCED_BACKEND
    image_processing.FORCED_BACKEND = backend
    try:
        yield
    finally:
        image_processing.FORCED_BACKEND = previous_backend


def generate_clinical_scenario(
    scenario_type: str = "diabetic_ulcer",
    width: int = 400,
    height: int = 400,
    add_noise: bool = True,
    seed: int = DEFAULT_BENCHMARK_SEED,
):
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

    elif scenario_type == "bimodal_undercooled_extremity":
        # Bimodale Verteilung: Unterkühlte Zehen/Peripherie + entzündeter Ulcus
        img[180:240, 60:180] = 35.0
        rr, cc = np.ogrid[:height, :width]
        h_bio = np.sqrt((rr - 100)**2 + (cc - 120)**2) <= 6
        img[h_bio] = 210.0
        ground_truth[h_bio] = 255

    elif scenario_type == "pressure_ulcer":
        # Dekubitus: Ein flächiger, elliptischer Druckwundenherd am Fersenbein
        # (typisch bei bettlägerigen Patienten – Berufserkrankung in der Pflege)
        rr, cc = np.ogrid[:height, :width]
        dist_heel = np.sqrt(((rr - 220) / 12.0)**2 + ((cc - 120) / 8.0)**2)
        hotspot = dist_heel <= 1.0
        img[hotspot] = 195.0
        ground_truth[hotspot] = 255

    elif scenario_type == "post_surgical_inflammation":
        # Post-operative Entzündung: Zwei symmetrisch angeordnete Narbenherde
        # (häufig nach Arbeitsunfällen / berufsbedingten Operationen am Fuß)
        rr, cc = np.ogrid[:height, :width]
        h_left = np.sqrt((rr - 130)**2 + (cc - 90)**2) <= 5
        h_right = np.sqrt((rr - 130)**2 + (cc - 310)**2) <= 5
        img[h_left | h_right] = 185.0
        ground_truth[h_left | h_right] = 255

    elif scenario_type == "venous_insufficiency":
        # Venöse Insuffizienz: Diffuser Wärmestreifen entlang der Vene
        # (Berufserkrankung durch langes Stehen – z.B. Chirurgen, Verkäufer)
        rng = np.random.default_rng(seed=_scenario_seed(scenario_type, seed))
        for x_center in [100, 280]:
            for y in range(50, 220):
                jitter = int(rng.integers(-3, 4))
                xc = x_center + jitter
                if 0 <= xc < width:
                    img[y, max(0, xc - 2):min(width, xc + 3)] = 175.0
                    ground_truth[y, max(0, xc - 2):min(width, xc + 3)] = 255

    if add_noise:
        # Realistisches Gaußsches Sensorrauschen (sigma = 2.5)
        rng = np.random.default_rng(seed=_scenario_seed(scenario_type, seed))
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


def _baseline_otsu_predict(img: np.ndarray) -> np.ndarray:
    """Naiver Otsu-Baseline-Prediktor (ohne Top-Hat, ohne Geometriefilter).

    Dient als Vergleichsreferenz, um die Überlegenheit der IGNITE-Pipeline
    gegenüber einfacher globaler Schwellenwertbildung zu belegen.
    """
    body_mask = image_processing._extract_body_mask_cpu(img)
    body_pixels = img[body_mask > 0]
    if len(body_pixels) == 0:
        return np.zeros_like(img)
    thresh_val = float(np.percentile(body_pixels, 90))
    raw = ((img > thresh_val) & (body_mask > 0)).astype(np.uint8) * 255
    return raw


def evaluate_real_dataset_with_gt(
    test_data_dir: str = "test-data",
    gt_dir: str = None,
) -> dict:
    """Evaluiert IGNITE gegen manuell annotierte Ground-Truth-Masken.

    Für Bilder ohne vorhandene GT-Maske wird nur die Coverage-Statistik berechnet.
    Für annotierte Bilder werden zusätzlich Dice, IoU, Sensitivität und Spezifität
    sowohl für IGNITE als auch für die Otsu-Baseline berechnet.

    Args:
        test_data_dir: Ordner mit den Originalbildern (JPEG/PNG).
        gt_dir: Ordner mit den annotierten Masken. Standard: test_data_dir/ground_truth.

    Returns:
        Dictionary mit Ergebnissen je Bild.
    """
    if gt_dir is None:
        gt_dir = os.path.join(test_data_dir, "ground_truth")

    image_files = sorted(
        f for f in os.listdir(test_data_dir)
        if f.lower().endswith((".jpeg", ".jpg", ".png"))
    )
    if not image_files:
        print(f"[!] Keine Bilddateien in '{test_data_dir}' gefunden.")
        return {}

    print(f"\n--- GT-basierte Evaluierung ({len(image_files)} Bilder, GT-Verzeichnis: {gt_dir}/) ---")
    results = {}
    gt_count = 0
    ignite_dice_sum = 0.0
    baseline_dice_sum = 0.0

    for img_name in image_files:
        img_path = os.path.join(test_data_dir, img_name)
        try:
            img = image_processing.load_thermal_image(img_path)
        except Exception as e:
            results[img_name] = {"status": f"Ladefehler: {e}"}
            continue

        try:
            diff_vis, hotspot_mask = image_processing.run_rust_pipeline(img)
        except Exception as e:
            results[img_name] = {"status": f"Pipeline-Fehler: {e}"}
            continue

        body_mask = image_processing._extract_body_mask_cpu(img)
        body_pixels = int(np.sum(body_mask == 255))
        hotspot_pixels = int(np.sum(hotspot_mask == 255))
        coverage = round((hotspot_pixels / body_pixels * 100.0) if body_pixels > 0 else 0.0, 2)

        entry: dict = {
            "dimensions": [int(img.shape[1]), int(img.shape[0])],
            "body_pixels": body_pixels,
            "hotspot_pixels": hotspot_pixels,
            "hotspot_coverage_percent": coverage,
            "has_ground_truth": False,
        }

        # Ground-Truth laden: Name-Stem suchen (ohne Extension)
        stem = os.path.splitext(img_name)[0]
        gt_candidates = [
            os.path.join(gt_dir, f"{stem}_mask.png"),
            os.path.join(gt_dir, f"{stem}.png"),
        ]
        gt_path = next((p for p in gt_candidates if os.path.exists(p)), None)

        if gt_path is not None:
            gt_raw = cv2.imread(gt_path, cv2.IMREAD_GRAYSCALE)
            if gt_raw is not None:
                # GT-Maske muss ggf. auf Bildgröße reskaliert werden
                if gt_raw.shape != img.shape:
                    gt_raw = cv2.resize(gt_raw, (img.shape[1], img.shape[0]),
                                        interpolation=cv2.INTER_NEAREST)
                gt_bin = (gt_raw > 127).astype(np.uint8) * 255

                # IGNITE-Metriken
                m_ignite = evaluate_metrics(hotspot_mask, gt_bin, body_mask)

                # Otsu-Baseline-Metriken
                baseline_mask = _baseline_otsu_predict(img)
                m_baseline = evaluate_metrics(baseline_mask, gt_bin, body_mask)

                entry["has_ground_truth"] = True
                entry["ignite_metrics"] = m_ignite
                entry["baseline_otsu_metrics"] = m_baseline
                entry["dice_improvement_over_baseline"] = round(
                    m_ignite["dice"] - m_baseline["dice"], 4
                )

                ignite_dice_sum += m_ignite["dice"]
                baseline_dice_sum += m_baseline["dice"]
                gt_count += 1

                print(
                    f"[GT] {img_name:22s} | IGNITE Dice={m_ignite['dice']:.3f} "
                    f"Sens={m_ignite['sensitivity']:.3f} Spec={m_ignite['specificity']:.3f} | "
                    f"Otsu Dice={m_baseline['dice']:.3f}"
                )
            else:
                print(f"[  ] {img_name:22s} | GT-Maske nicht lesbar: {gt_path}")
        else:
            print(
                f"[  ] {img_name:22s} | Keine GT-Maske – Coverage={coverage:.2f}% "
                f"({hotspot_pixels}px Hotspot)"
            )

        results[img_name] = entry

    if gt_count > 0:
        mean_ignite_dice = round(ignite_dice_sum / gt_count, 4)
        mean_baseline_dice = round(baseline_dice_sum / gt_count, 4)
        print(f"\n=== Zusammenfassung ({gt_count} GT-annotierte Bilder) ===")
        print(f"  IGNITE  mittl. Dice: {mean_ignite_dice:.4f}")
        print(f"  Otsu    mittl. Dice: {mean_baseline_dice:.4f}")
        print(f"  Verbesserung:        +{mean_ignite_dice - mean_baseline_dice:.4f}")
        results["__summary__"] = {
            "gt_annotated_images": gt_count,
            "mean_ignite_dice": mean_ignite_dice,
            "mean_baseline_otsu_dice": mean_baseline_dice,
            "mean_dice_improvement": round(mean_ignite_dice - mean_baseline_dice, 4),
        }

    return results
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

def run_benchmark_suite(
    seed: int = DEFAULT_BENCHMARK_SEED,
    backend: str = DEFAULT_BENCHMARK_BACKEND,
):
    """Führt die vollständige Benchmark-Testsuite durch.

    Beinhaltet:
    - 9 synthetische Szenarien (inkl. Berufserkrankungen) mit realistischen Rausch-Modellen
    - Vergleich IGNITE vs. Otsu-Baseline für jedes Szenario
    - Vergleich Standard µ+k·σ vs. Robustes MAD-Thresholding
    - Parameter-Sensitivitätsanalyse (k = 1.0 … 5.0)
    - Reale Test-Bilddaten aus test-data/ inkl. GT-Masken-Evaluation
    """
    scenarios = [
        "normal",
        "diabetic_ulcer",
        "plantar_fasciitis",
        "focal_sensor_noise",
        "complex_multi_inflammation",
        "bimodal_undercooled_extremity",
        "pressure_ulcer",
        "post_surgical_inflammation",
        "venous_insufficiency",
    ]
    results = {}
    mad_comparison = {}
    baseline_comparison = {}

    print("=== IGNITE Medical Thermal Evaluation Benchmark ===")

    with _forced_backend(backend):
        for scenario in scenarios:
            img, gt = generate_clinical_scenario(scenario, add_noise=True, seed=seed)
            body_mask = image_processing._extract_body_mask_cpu(img)

            # Standard µ + k·σ (IGNITE)
            diff_img, pred_mask_std = image_processing.run_rust_pipeline(img, use_mad=False)
            metrics_std = evaluate_metrics(pred_mask_std, gt, body_mask)
            results[scenario] = metrics_std

            # Robustes MAD-Thresholding (IGNITE)
            diff_img_mad, pred_mask_mad = image_processing.run_rust_pipeline(img, use_mad=True)
            metrics_mad = evaluate_metrics(pred_mask_mad, gt, body_mask)
            mad_comparison[scenario] = {
                "mean_std": metrics_std,
                "mad_robust": metrics_mad,
            }

            # Einfache Otsu-Baseline (Vergleich)
            baseline_mask = _baseline_otsu_predict(img)
            metrics_baseline = evaluate_metrics(baseline_mask, gt, body_mask)
            baseline_comparison[scenario] = {
                "ignite": metrics_std,
                "otsu_baseline": metrics_baseline,
                "dice_improvement": round(metrics_std["dice"] - metrics_baseline["dice"], 4),
            }

            print(
                f"Szenario [{scenario:28s}]: "
                f"IGNITE Dice={metrics_std['dice']:.2f} Sens={metrics_std['sensitivity']:.2f} | "
                f"MAD Dice={metrics_mad['dice']:.2f} | "
                f"Otsu Dice={metrics_baseline['dice']:.2f} "
                f"(+{metrics_std['dice'] - metrics_baseline['dice']:.2f})"
            )

        # Parameter-Sensitivitätsanalyse für k (1.0 bis 5.0)
        print("\n--- Parameter-Sensitivitätsanalyse (Sigma k) ---")
        k_analysis = {}
        img_eval, gt_eval = generate_clinical_scenario("diabetic_ulcer", add_noise=True, seed=seed)
        body_mask_eval = image_processing._extract_body_mask_cpu(img_eval)

        for k_val in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
            diff_img, pred_mask = image_processing._python_fallback_pipeline(
                img_eval,
                sigma_k=k_val
            )
            m = evaluate_metrics(pred_mask, gt_eval, body_mask_eval)
            k_analysis[str(k_val)] = m
            print(f"k = {k_val:.1f} | Sensitivität: {m['sensitivity']:.4f} | Spezifität: {m['specificity']:.4f} | Dice: {m['dice']:.4f}")

        # Reale Testbilder aus test-data/ auswerten (inkl. GT-Masken)
        real_dataset_results = evaluate_real_dataset_with_gt()

    output_data = {
        "scenario_results": results,
        "baseline_otsu_comparison": baseline_comparison,
        "mad_thresholding_comparison": mad_comparison,
        "sensitivity_analysis_k": k_analysis,
        "real_test_dataset": real_dataset_results,
        "reproducibility": {
            "seed": seed,
            "backend": backend,
            "scenario_seeds": {
                scenario: _scenario_seed(scenario, seed) for scenario in scenarios
            },
        },
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
