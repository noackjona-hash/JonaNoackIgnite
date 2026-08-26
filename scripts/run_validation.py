"""Reproduzierbare Validierung von IGNITE auf den annotierten Realbildern.

Erzeugt alle Zahlen, die in der schriftlichen Arbeit (Kapitel 5) berichtet werden:

  1. Laufzeitmessung aller verfuegbaren Backends inkl. Hardware-Kontext
  2. Dice/IoU/Sensitivitaet/Spezifitaet auf den GT-annotierten Realbildern
     inkl. Bootstrap-Konfidenzintervall und Wilcoxon-Test gegen Otsu-Baseline
  3. Ablation der geometrischen Filter (anatomischer Cutoff, Randfilter)
  4. Rust/Python-Paritaetspruefung auf echten Bildern

Aufruf:  python scripts/run_validation.py
Ausgabe: ignite_steps_output/validation_report.json  (+ Konsolenbericht)
"""
from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as _config  # noqa: E402
import dataset_evaluator as de  # noqa: E402
import image_processing as ip  # noqa: E402

TEST_DIR = "test-data"
GT_DIR = os.path.join(TEST_DIR, "ground_truth")
RNG_SEED = 20260726


# ────────────────────────────────────────────────────────────────────────────
# 1. Laufzeiten
# ────────────────────────────────────────────────────────────────────────────
def measure_runtimes(repeats: int = 100, warmup: int = 5) -> dict:
    """Misst die Pipeline-Laufzeit pro Backend bei zwei Aufloesungen.

    Berichtet Median und Standardabweichung statt nur Mittelwert, weil
    Einzelmessungen auf einem Desktop-Betriebssystem stark streuen.
    """
    base = cv2.imread(os.path.join(TEST_DIR, "bild (1).jpeg"), cv2.IMREAD_GRAYSCALE)
    if base is None:
        raise FileNotFoundError("Referenzbild test-data/bild (1).jpeg nicht gefunden")

    def _time(fn, img, n):
        for _ in range(warmup):
            fn(img)
        samples = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn(img)
            samples.append((time.perf_counter() - t0) * 1000.0)
        return {
            "median_ms": round(statistics.median(samples), 2),
            "mean_ms": round(statistics.fmean(samples), 2),
            "stdev_ms": round(statistics.pstdev(samples), 2),
            "n": n,
        }

    backends = {}
    for label, size in (("400x400", (400, 400)), ("1440x1080", (1440, 1080))):
        img = np.ascontiguousarray(cv2.resize(base, size), dtype=np.uint8)
        entry = {}

        if ip._RUST_BACKEND_AVAILABLE and ip._ignite_core is not None:
            entry["rust_cpu"] = _time(
                lambda im: ip._ignite_core.process_thermal_pipeline(
                    im,
                    _config.DEFAULT_SIGMA_K,
                    _config.DEFAULT_TOPHAT_FACTOR,
                    _config.DEFAULT_MIN_AREA_FACTOR,
                    _config.DEFAULT_MIN_CIRCULARITY,
                    _config.DEFAULT_OTSU_MIN,
                    _config.DEFAULT_OTSU_MAX,
                    _config.DEFAULT_DIST_EROSION_FACTOR,
                ),
                img, repeats,
            )
        else:
            entry["rust_cpu"] = None

        entry["python_opencv"] = _time(ip._python_fallback_pipeline, img, max(10, repeats // 10))

        if ip._GPU_AVAILABLE:
            entry["pytorch_gpu"] = _time(ip._pytorch_gpu_pipeline, img, repeats)
        else:
            entry["pytorch_gpu"] = None

        backends[label] = entry

    return {
        "hardware": {
            "cpu": platform.processor() or platform.machine(),
            "cpu_cores": os.cpu_count(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "gpu_backend_available": bool(ip._GPU_AVAILABLE),
            "rust_backend_available": bool(ip._RUST_BACKEND_AVAILABLE),
        },
        "measurements": backends,
    }


# ────────────────────────────────────────────────────────────────────────────
# 2. Ground-Truth-Validierung auf Realdaten
# ────────────────────────────────────────────────────────────────────────────
def _nanmean_std(values: list[float]) -> tuple[float, float, int]:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return float("nan"), float("nan"), 0
    return float(np.mean(arr)), float(np.std(arr, ddof=1) if arr.size > 1 else 0.0), int(arr.size)


def _bootstrap_ci(values: list[float], iterations: int = 10000, alpha: float = 0.05) -> tuple:
    arr = np.asarray([v for v in values if v is not None], dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(RNG_SEED)
    means = np.mean(rng.choice(arr, size=(iterations, arr.size), replace=True), axis=1)
    return (
        float(np.percentile(means, 100 * alpha / 2)),
        float(np.percentile(means, 100 * (1 - alpha / 2))),
    )


def evaluate_ground_truth() -> dict:
    res = de.evaluate_real_dataset_with_gt(TEST_DIR, GT_DIR)

    per_image = []
    for name, entry in sorted(res.items()):
        if name.startswith("__") or not entry.get("has_ground_truth"):
            continue
        mi, mb = entry["ignite_metrics"], entry["baseline_otsu_metrics"]
        per_image.append({
            "image": name,
            "gt_file": entry.get("ground_truth_file"),
            "ignite": {k: mi[k] for k in ("dice", "iou", "sensitivity", "specificity", "precision", "mcc")},
            "otsu": {k: mb[k] for k in ("dice", "iou", "sensitivity", "specificity")},
        })

    summary = {}
    for metric in ("dice", "iou", "sensitivity", "specificity", "precision", "mcc"):
        vals = [p["ignite"][metric] for p in per_image]
        mean, std, n = _nanmean_std(vals)
        lo, hi = _bootstrap_ci(vals)
        summary[metric] = {
            "mean": round(mean, 4), "std": round(std, 4), "n_valid": n,
            "ci95_low": round(lo, 4), "ci95_high": round(hi, 4),
        }

    otsu_summary = {}
    for metric in ("dice", "iou", "sensitivity", "specificity"):
        vals = [p["otsu"][metric] for p in per_image]
        mean, std, n = _nanmean_std(vals)
        otsu_summary[metric] = {"mean": round(mean, 4), "std": round(std, 4), "n_valid": n}

    # Gepaarter Wilcoxon-Vorzeichen-Rangtest IGNITE vs. Otsu auf Dice.
    # Nutzt die projekteigene Implementierung, die ohne SciPy auf eine
    # Normalapproximation zurueckfaellt (SciPy ist keine harte Abhaengigkeit).
    a = [p["ignite"]["dice"] for p in per_image]
    b = [p["otsu"]["dice"] for p in per_image]
    wilcoxon = de.compute_wilcoxon_significance_test(a, b)

    return {
        "n_images_total": len([f for f in os.listdir(TEST_DIR) if f.lower().endswith((".jpeg", ".jpg", ".png"))]),
        "n_images_annotated": len(per_image),
        "per_image": per_image,
        "ignite_summary": summary,
        "otsu_baseline_summary": otsu_summary,
        "wilcoxon_ignite_vs_otsu_dice": wilcoxon,
    }


def _annotated_pairs() -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Laedt alle (Bild, Ground-Truth)-Paare mit nicht-leerer Annotation."""
    pairs = []
    for fname in sorted(os.listdir(TEST_DIR)):
        if not fname.lower().endswith((".jpeg", ".jpg")):
            continue
        stem = os.path.splitext(fname)[0]
        gt_path = next((p for p in (os.path.join(GT_DIR, stem + "_mask.png"),
                                    os.path.join(GT_DIR, stem + ".png")) if os.path.exists(p)), None)
        if gt_path is None:
            continue
        gt = cv2.imread(gt_path, cv2.IMREAD_GRAYSCALE)
        img = cv2.imread(os.path.join(TEST_DIR, fname), cv2.IMREAD_GRAYSCALE)
        if gt is None or img is None or np.count_nonzero(gt > 127) == 0:
            continue
        if gt.shape != img.shape:
            gt = cv2.resize(gt, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
        pairs.append((fname, np.ascontiguousarray(img, dtype=np.uint8), (gt > 127).astype(np.uint8) * 255))
    return pairs


def tuning_test_split_evaluation(k_grid: list[float] | None = None) -> dict:
    """Bestimmt den Schwellenwertfaktor k auf einem Tuning-Satz und wertet ihn
    genau einmal auf einem disjunkten Testsatz aus.

    Damit wird das Data-Leakage-Problem behoben: Frueher wurde k auf denselben
    Bildern optimiert, auf denen anschliessend die Guete berichtet wurde. Die
    Aufteilung ist deterministisch (fester Seed) und wird mitprotokolliert.
    """
    if k_grid is None:
        k_grid = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]

    pairs = _annotated_pairs()
    if len(pairs) < 4:
        return {"status": f"Zu wenige annotierte Bilder ({len(pairs)}) fuer einen Split"}

    rng = np.random.default_rng(RNG_SEED)
    order = rng.permutation(len(pairs))
    n_tune = max(2, len(pairs) // 2)
    tune_idx, test_idx = order[:n_tune], order[n_tune:]

    def _dice_for_k(indices, k) -> float:
        scores = []
        for i in indices:
            fname, img, gt = pairs[i]
            _, mask = ip._ignite_core.process_thermal_pipeline(
                img, k, _config.DEFAULT_TOPHAT_FACTOR,
                _config.DEFAULT_MIN_AREA_FACTOR, _config.DEFAULT_MIN_CIRCULARITY,
                _config.DEFAULT_OTSU_MIN, _config.DEFAULT_OTSU_MAX,
                _config.DEFAULT_DIST_EROSION_FACTOR,
            ) if ip._RUST_BACKEND_AVAILABLE else ip._python_fallback_pipeline(img, sigma_k=k)
            body = ip._extract_body_mask_cpu(img)
            scores.append(de.evaluate_metrics(mask, gt, body)["dice"])
        return float(np.nanmean(scores))

    tuning_curve = {str(k): round(_dice_for_k(tune_idx, k), 4) for k in k_grid}
    best_k = float(max(k_grid, key=lambda k: tuning_curve[str(k)]))

    # Genau EINE Auswertung auf dem Testsatz mit dem gewaehlten k
    test_scores = []
    for i in test_idx:
        fname, img, gt = pairs[i]
        _, mask = ip._ignite_core.process_thermal_pipeline(
            img, best_k, _config.DEFAULT_TOPHAT_FACTOR,
            _config.DEFAULT_MIN_AREA_FACTOR, _config.DEFAULT_MIN_CIRCULARITY,
            _config.DEFAULT_OTSU_MIN, _config.DEFAULT_OTSU_MAX,
            _config.DEFAULT_DIST_EROSION_FACTOR,
        ) if ip._RUST_BACKEND_AVAILABLE else ip._python_fallback_pipeline(img, sigma_k=best_k)
        body = ip._extract_body_mask_cpu(img)
        m = de.evaluate_metrics(mask, gt, body)
        test_scores.append({"image": fname, **{key: m[key] for key in
                                               ("dice", "iou", "sensitivity", "specificity", "precision")}})

    summary = {}
    for metric in ("dice", "iou", "sensitivity", "specificity", "precision"):
        vals = [s[metric] for s in test_scores]
        mean, std, n = _nanmean_std(vals)
        summary[metric] = {"mean": round(mean, 4), "std": round(std, 4), "n_valid": n}

    return {
        "k_grid": k_grid,
        "split_seed": RNG_SEED,
        "tuning_images": [pairs[i][0] for i in tune_idx],
        "test_images": [pairs[i][0] for i in test_idx],
        "tuning_dice_curve": tuning_curve,
        "selected_k": best_k,
        "default_k_in_config": _config.DEFAULT_SIGMA_K,
        "holdout_test_scores": test_scores,
        "holdout_test_summary": summary,
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. Ablation der geometrischen Filter
# ────────────────────────────────────────────────────────────────────────────
def ablation_geometric_filters() -> dict:
    """Quantifiziert, wie viel Ground-Truth-Flaeche die harten anatomischen
    Filterregeln systematisch verwerfen.

    Der anatomische Cutoff verwirft jeden Hotspot unterhalb von
    ANATOMICAL_LOWER_CUTOFF_Y * Bildhoehe, der Randfilter jeden Hotspot zu nahe
    am Bildrand. Beide Regeln koennen echte Befunde ausloeschen.
    """
    cutoff = _config.ANATOMICAL_LOWER_CUTOFF_Y
    border_factor = _config.MIN_DIST_FROM_BORDER_FACTOR
    border_abs = _config.MIN_DIST_FROM_BORDER_ABS

    rows, tot_gt, lost_cut, lost_border = [], 0, 0, 0
    for fname in sorted(os.listdir(TEST_DIR)):
        if not fname.lower().endswith((".jpeg", ".jpg", ".png")):
            continue
        stem = os.path.splitext(fname)[0]
        gt_path = next((p for p in (os.path.join(GT_DIR, stem + "_mask.png"),
                                    os.path.join(GT_DIR, stem + ".png")) if os.path.exists(p)), None)
        if gt_path is None:
            continue
        gt = cv2.imread(gt_path, cv2.IMREAD_GRAYSCALE)
        if gt is None or np.count_nonzero(gt > 127) == 0:
            continue

        h, w = gt.shape[:2]
        gt_bin = (gt > 127)
        n_gt = int(gt_bin.sum())

        ys, xs = np.nonzero(gt_bin)
        below = int(np.sum(ys > cutoff * h))
        margin = max(border_abs, border_factor * min(h, w))
        near_border = int(np.sum(
            (xs < margin) | (xs > w - margin) | (ys < margin) | (ys > h - margin)
        ))

        tot_gt += n_gt
        lost_cut += below
        lost_border += near_border
        rows.append({
            "image": fname,
            "gt_pixels": n_gt,
            "gt_pixels_below_anatomical_cutoff": below,
            "percent_below_cutoff": round(100.0 * below / n_gt, 2),
            "gt_pixels_near_border": near_border,
            "percent_near_border": round(100.0 * near_border / n_gt, 2),
        })

    return {
        "anatomical_lower_cutoff_y": cutoff,
        "min_dist_from_border_factor": border_factor,
        "min_dist_from_border_abs": border_abs,
        "total_gt_pixels": tot_gt,
        "percent_gt_below_cutoff": round(100.0 * lost_cut / tot_gt, 2) if tot_gt else float("nan"),
        "percent_gt_near_border": round(100.0 * lost_border / tot_gt, 2) if tot_gt else float("nan"),
        "per_image": rows,
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. Rust/Python-Paritaet auf echten Bildern
# ────────────────────────────────────────────────────────────────────────────
def parity_on_real_images() -> dict:
    if not (ip._RUST_BACKEND_AVAILABLE and ip._ignite_core is not None):
        return {"status": "Rust-Backend nicht verfuegbar"}

    rows = []
    for fname in sorted(os.listdir(TEST_DIR)):
        if not fname.lower().endswith((".jpeg", ".jpg")):
            continue
        img = cv2.imread(os.path.join(TEST_DIR, fname), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = np.ascontiguousarray(img, dtype=np.uint8)

        py_diff, py_mask = ip._python_fallback_pipeline(img)
        rust_diff, rust_mask = ip._ignite_core.process_thermal_pipeline(
            img,
            _config.DEFAULT_SIGMA_K, _config.DEFAULT_TOPHAT_FACTOR,
            _config.DEFAULT_MIN_AREA_FACTOR, _config.DEFAULT_MIN_CIRCULARITY,
            _config.DEFAULT_OTSU_MIN, _config.DEFAULT_OTSU_MAX,
            _config.DEFAULT_DIST_EROSION_FACTOR,
        )

        pb, rb = (py_mask > 0), (rust_mask > 0)
        inter, union = int((pb & rb).sum()), int((pb | rb).sum())
        rows.append({
            "image": fname,
            "python_hotspot_px": int(pb.sum()),
            "rust_hotspot_px": int(rb.sum()),
            "mask_iou": round(inter / union, 4) if union else 1.0,
            "mask_identical": bool(np.array_equal(pb, rb)),
            "mean_abs_diff_tophat": round(float(np.mean(np.abs(
                rust_diff.astype(np.int32) - py_diff.astype(np.int32)))), 4),
        })

    ious = [r["mask_iou"] for r in rows]
    return {
        "n_images": len(rows),
        "n_identical_masks": sum(r["mask_identical"] for r in rows),
        "mean_mask_iou": round(float(np.mean(ious)), 4) if ious else float("nan"),
        "min_mask_iou": round(float(np.min(ious)), 4) if ious else float("nan"),
        "per_image": rows,
    }


def main() -> None:
    _config.init_output_dir()
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seed": RNG_SEED,
        "runtimes": measure_runtimes(),
        "ground_truth_validation": evaluate_ground_truth(),
        "tuning_test_split": tuning_test_split_evaluation(),
        "geometric_filter_ablation": ablation_geometric_filters(),
        "backend_parity_real_images": parity_on_real_images(),
    }

    out = os.path.join(_config.OUTPUT_DIR, "validation_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    gt = report["ground_truth_validation"]
    rt = report["runtimes"]["measurements"]
    ab = report["geometric_filter_ablation"]
    pa = report["backend_parity_real_images"]

    print("\n" + "=" * 68)
    print("IGNITE – Validierungsbericht")
    print("=" * 68)
    print(f"Hardware: {report['runtimes']['hardware']['cpu']} "
          f"({report['runtimes']['hardware']['cpu_cores']} Kerne)")
    for label, entry in rt.items():
        parts = [f"{k}={v['median_ms']}±{v['stdev_ms']} ms" for k, v in entry.items() if v]
        print(f"  Laufzeit {label:10s}: " + ", ".join(parts))

    print(f"\nGround Truth: {gt['n_images_annotated']} von {gt['n_images_total']} Bildern annotiert")
    for m, s in gt["ignite_summary"].items():
        print(f"  IGNITE {m:12s}: {s['mean']:.4f} ± {s['std']:.4f} "
              f"(95%-KI {s['ci95_low']:.4f}–{s['ci95_high']:.4f}, n={s['n_valid']})")
    for m, s in gt["otsu_baseline_summary"].items():
        print(f"  Otsu   {m:12s}: {s['mean']:.4f} ± {s['std']:.4f}")
    print(f"  Wilcoxon (Dice): {gt['wilcoxon_ignite_vs_otsu_dice']}")

    sp = report["tuning_test_split"]
    if "selected_k" in sp:
        print(f"\nTuning-/Test-Split (Seed {sp['split_seed']}):")
        print(f"  Tuning-Bilder: {len(sp['tuning_images'])} | Test-Bilder: {len(sp['test_images'])}")
        print(f"  Dice-Kurve auf Tuning-Satz: {sp['tuning_dice_curve']}")
        print(f"  Gewaehltes k = {sp['selected_k']} (Config-Default {sp['default_k_in_config']})")
        for m, s in sp["holdout_test_summary"].items():
            print(f"  Holdout {m:12s}: {s['mean']:.4f} ± {s['std']:.4f} (n={s['n_valid']})")

    print(f"\nAblation geometrischer Filter:")
    print(f"  GT-Pixel unterhalb anatomischem Cutoff y>{ab['anatomical_lower_cutoff_y']}: "
          f"{ab['percent_gt_below_cutoff']} %")
    print(f"  GT-Pixel in Randzone: {ab['percent_gt_near_border']} %")

    print(f"\nBackend-Paritaet auf {pa.get('n_images', 0)} Realbildern:")
    print(f"  Identische Masken: {pa.get('n_identical_masks')}/{pa.get('n_images')}")
    print(f"  Mittlere Masken-IoU: {pa.get('mean_mask_iou')} (min {pa.get('min_mask_iou')})")
    print(f"\nBericht gespeichert: {out}\n")


if __name__ == "__main__":
    main()
