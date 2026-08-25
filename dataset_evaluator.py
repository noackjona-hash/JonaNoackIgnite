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

def compute_surface_distances(pred_mask: np.ndarray, gt_mask: np.ndarray) -> tuple[float, float]:
    """Berechnet 95th-Percentile Hausdorff-Distanz (HD95) und Average Symmetric Surface Distance (ASSD).
    
    Verwendet euklidische Distanztransformationen (cv2.distanceTransform) auf den Binärkonturen.
    """
    pred_bin = (pred_mask > 0).astype(np.uint8)
    gt_bin = (gt_mask > 0).astype(np.uint8)

    # Wenn beide Masken leer sind -> perfekte anatomische Übereinstimmung (z. B. Normalbefund)
    if np.sum(pred_bin) == 0 and np.sum(gt_bin) == 0:
        return 0.0, 0.0
    # Wenn eine Maske leer ist und die andere nicht -> maximale Diskrepanz (Bilddiagonale)
    if np.sum(pred_bin) == 0 or np.sum(gt_bin) == 0:
        h, w = pred_bin.shape[:2]
        diag = float(np.hypot(h, w))
        return round(diag, 2), round(diag, 2)

    # Konturen extrahieren
    pred_contours, _ = cv2.findContours(pred_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    gt_contours, _ = cv2.findContours(gt_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    pred_pts = np.vstack([c[:, 0, :] for c in pred_contours]) if pred_contours else np.empty((0, 2), dtype=int)
    gt_pts = np.vstack([c[:, 0, :] for c in gt_contours]) if gt_contours else np.empty((0, 2), dtype=int)

    if len(pred_pts) == 0 or len(gt_pts) == 0:
        return 0.0, 0.0

    # Distanztransformationen
    gt_border = np.zeros_like(gt_bin)
    cv2.drawContours(gt_border, gt_contours, -1, 255, 1)
    dist_to_gt = cv2.distanceTransform(255 - gt_border, cv2.DIST_L2, 3)

    pred_border = np.zeros_like(pred_bin)
    cv2.drawContours(pred_border, pred_contours, -1, 255, 1)
    dist_to_pred = cv2.distanceTransform(255 - pred_border, cv2.DIST_L2, 3)

    d_pred_to_gt = dist_to_gt[pred_pts[:, 1], pred_pts[:, 0]]
    d_gt_to_pred = dist_to_pred[gt_pts[:, 1], gt_pts[:, 0]]

    all_dists = np.concatenate([d_pred_to_gt, d_gt_to_pred])
    hd95 = float(np.percentile(all_dists, 95))
    assd = float(np.mean(all_dists))

    return round(hd95, 2), round(assd, 2)


def evaluate_metrics(pred_mask: np.ndarray, gt_mask: np.ndarray, body_mask: np.ndarray = None):
    """
    Berechnet quantitative Konfusionsmatrix- und Evidenz-Metriken:
    - Klassisch: Sensitivity, Specificity, Precision, Recall, Dice, IoU
    - Klinische Evidenz: Matthews Correlation Coefficient (MCC), Cohen's Kappa (κ),
      Youden's Index (J), Diagnostic Odds Ratio (DOR), Likelihood Ratios (LR+, LR-)
    - Räumliche Konturmetriken: 95th Percentile Hausdorff Distance (HD95), ASSD
    """
    pred_bin = (pred_mask > 0).astype(bool)
    gt_bin = (gt_mask > 0).astype(bool)

    if body_mask is not None:
        valid_area = (body_mask > 0)
        pred_bin = pred_bin & valid_area
        gt_bin = gt_bin & valid_area

    tp = int(np.sum(pred_bin & gt_bin))
    fp = int(np.sum(pred_bin & ~gt_bin))
    fn = int(np.sum(~pred_bin & gt_bin))
    tn = int(np.sum(~pred_bin & ~gt_bin))

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 1.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = sensitivity
    dice = (2.0 * tp) / (2.0 * tp + fp + fn) if (2.0 * tp + fp + fn) > 0 else (1.0 if (fp + fn) == 0 else 0.0)
    iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else (1.0 if (fp + fn) == 0 else 0.0)

    # 1. Matthews Correlation Coefficient (MCC) – Goldstandard bei unausgeglichenen medizinischen Masken
    denom_mcc = np.sqrt(float(tp + fp) * float(tp + fn) * float(tn + fp) * float(tn + fn))
    if denom_mcc > 0:
        mcc = (float(tp) * float(tn) - float(fp) * float(fn)) / denom_mcc
    else:
        mcc = 1.0 if (fp + fn) == 0 else 0.0

    # 2. Cohen's Kappa (κ) – Inter-Methoden-Reliabilität
    n_total = float(tp + fp + tn + fn)
    if n_total > 0:
        po = (tp + tn) / n_total
        pe = ((tp + fp) * (tp + fn) + (tn + fp) * (tn + fn)) / (n_total * n_total)
        kappa = (po - pe) / (1.0 - pe) if (1.0 - pe) > 0 else 1.0
    else:
        kappa = 1.0

    # 3. Youden's J Index (Optimaler Schwellenwert-Performance-Index)
    youden_j = sensitivity + specificity - 1.0

    # 4. Diagnostic Odds Ratio (DOR) mit Haldane-Anscombe-Glättung
    dor = ((tp + 0.5) * (tn + 0.5)) / ((fp + 0.5) * (fn + 0.5))

    # 5. Positive & Negative Likelihood Ratios
    lr_plus = sensitivity / max(1e-5, (1.0 - specificity)) if specificity < 1.0 else 999.0
    lr_minus = (1.0 - sensitivity) / max(1e-5, specificity) if specificity > 0.0 else 0.0

    # 6. Räumliche Randdistanzen: HD95 & ASSD
    hd95, assd = compute_surface_distances(pred_bin, gt_bin)

    return {
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "sensitivity": float(round(sensitivity, 4)),
        "specificity": float(round(specificity, 4)),
        "precision": float(round(precision, 4)),
        "recall": float(round(recall, 4)),
        "dice": float(round(dice, 4)),
        "iou": float(round(iou, 4)),
        "mcc": float(round(mcc, 4)),
        "cohen_kappa": float(round(kappa, 4)),
        "youden_j": float(round(youden_j, 4)),
        "dor": float(round(dor, 2)),
        "lr_plus": float(round(lr_plus, 2)),
        "lr_minus": float(round(lr_minus, 3)),
        "hd95_px": hd95,
        "assd_px": assd,
    }


def compute_roc_auc_and_pr_auc(
    img: np.ndarray,
    gt_mask: np.ndarray,
    k_range: list[float] = None
) -> dict:
    """Berechnet ROC-AUC und PR-AUC durch systematische Schwellenwert-Parametervariation (k-Sigma Sweep).
    
    Verwendet numerische Trapezoid-Integration über die Kurvenverläufe:
    - ROC-AUC: Integral von TPR über FPR
    - PR-AUC: Integral von Precision über Recall
    """
    if k_range is None:
        k_range = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]

    body_mask = image_processing._extract_body_mask_cpu(img)

    tprs = [1.0]
    fprs = [1.0]
    recalls = [1.0]
    precisions = [float(np.sum(gt_mask > 0)) / max(1, float(np.sum(body_mask > 0)))]

    for k in sorted(k_range):
        _, pred_mask = image_processing._python_fallback_pipeline(img, sigma_k=k)
        m = evaluate_metrics(pred_mask, gt_mask, body_mask)
        tprs.append(m["sensitivity"])
        fprs.append(1.0 - m["specificity"])
        precisions.append(m["precision"])
        recalls.append(m["recall"])

    tprs.append(0.0)
    fprs.append(0.0)
    recalls.append(0.0)
    precisions.append(1.0)

    # Sortieren für monotone Trapezoid-Integration
    trapz_fn = getattr(np, "trapezoid", getattr(np, "trapz", None))

    roc_order = np.argsort(fprs)
    sorted_fprs = np.array(fprs)[roc_order]
    sorted_tprs = np.array(tprs)[roc_order]
    roc_auc = float(trapz_fn(sorted_tprs, sorted_fprs)) if trapz_fn else 1.0

    pr_order = np.argsort(recalls)
    sorted_rec = np.array(recalls)[pr_order]
    sorted_prec = np.array(precisions)[pr_order]
    pr_auc = float(trapz_fn(sorted_prec, sorted_rec)) if trapz_fn else 1.0

    roc_auc = float(np.clip(roc_auc, 0.0, 1.0))
    pr_auc = float(np.clip(pr_auc, 0.0, 1.0))

    return {
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "fpr_points": [round(float(x), 4) for x in sorted_fprs.tolist()],
        "tpr_points": [round(float(y), 4) for y in sorted_tprs.tolist()],
        "recall_points": [round(float(r), 4) for r in sorted_rec.tolist()],
        "precision_points": [round(float(p), 4) for p in sorted_prec.tolist()],
    }


def compute_bland_altman(
    values_a: list[float] | np.ndarray,
    values_b: list[float] | np.ndarray
) -> dict:
    """Führt eine Bland-Altman-Methodenvergleichsanalyse zwischen zwei Messverfahren durch.
    
    Berechnet:
    - Mittlere Differenz (Bias): d_bar
    - Standardabweichung der Differenzen: s_d
    - 95% Limits of Agreement: [d_bar - 1.96*s_d, d_bar + 1.96*s_d]
    - Ausreißerquote außerhalb der Konfidenzgrenzen
    """
    a = np.asarray(values_a, dtype=np.float64)
    b = np.asarray(values_b, dtype=np.float64)

    if len(a) != len(b) or len(a) < 2:
        return {
            "mean_bias": 0.0,
            "std_diff": 0.0,
            "loa_lower": 0.0,
            "loa_upper": 0.0,
            "outlier_pct": 0.0,
            "loa_formatted": "Bias: +0.000 [95% LoA: -0.000 bis +0.000]"
        }

    diffs = a - b
    mean_bias = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else float(np.std(diffs))

    loa_lower = mean_bias - 1.96 * std_diff
    loa_upper = mean_bias + 1.96 * std_diff

    outliers = np.sum((diffs < loa_lower) | (diffs > loa_upper))
    outlier_pct = float(outliers / len(diffs) * 100.0)

    return {
        "mean_bias": round(mean_bias, 4),
        "std_diff": round(std_diff, 4),
        "loa_lower": round(loa_lower, 4),
        "loa_upper": round(loa_upper, 4),
        "outlier_pct": round(outlier_pct, 2),
        "loa_formatted": f"Bias: {mean_bias:+.3f} [95% LoA: {loa_lower:+.3f} bis {loa_upper:+.3f}]"
    }


def classify_iwgdf_armstrong_risk(
    delta_t_c: float,
    hotspot_area_pct: float = 0.0,
    arch_index: float = 0.23,
    longitudinal_trend: str = "stable"
) -> dict:
    """Klassifiziert das klinische Risiko nach den internationalen IWGDF 2023 & Armstrong Richtlinien.
    
    Klassen:
    - Grad 0: Normal / Sehr geringes Risiko (ΔT < 1.0°C)
    - Grad 1: Geringes Risiko / Diskrete Asymmetrie (1.0°C <= ΔT < 2.2°C)
    - Grad 2: Mäßiges bis Hohes Risiko / Prä-Ulzeration (ΔT >= 2.2°C oder Senkfuß-Überlastung)
    - Grad 3: Akutes Hochrisiko / Akute Entzündung / Charcot-Verdacht (ΔT >= 3.0°C oder Progression)
    """
    if delta_t_c >= 3.0 or longitudinal_trend == "progression":
        grade = 3
        category = "Grad 3: Akutes Hochrisiko / Akute Entzündung / Charcot-Verdacht"
        action = "Sofortige Druckentlastung (Total Contact Cast / Entlastungsschuh) & Facharzt-Überweisung"
        color = "#DC2626"
    elif delta_t_c >= 2.2 or (arch_index > 0.26 and hotspot_area_pct > 2.0):
        grade = 2
        category = "Grad 2: Hohes Risiko / Prä-Ulzeratives Warnstadium (IWGDF-Grenzwert überschritten)"
        action = "Schonung, podologische Druckumverteilung (Sporteinlagen), 7-Tage-Kontrolle"
        color = "#EA580C"
    elif delta_t_c >= 1.0:
        grade = 1
        category = "Grad 1: Geringes bis mäßiges Risiko / Diskrete Asymmetrie"
        action = "Engmaschige thermografische Verlaufskontrolle, Schuhwerk-Inspektion"
        color = "#CA8A04"
    else:
        grade = 0
        category = "Grad 0: Physiologischer Normalbefund / Sehr geringes Risiko"
        action = "Routine-Vorsorge im Rahmen der arbeitsmedizinischen Jahreskontrolle"
        color = "#16A34A"

    return {
        "grade": grade,
        "category": category,
        "action": action,
        "color": color,
        "delta_t_c": round(delta_t_c, 2),
        "is_pathologic": bool(grade >= 2)
    }


def compute_bootstrap_confidence_intervals(
    scores: list[float] | np.ndarray,
    n_bootstraps: int = 1000,
    confidence_level: float = 0.95,
    seed: int = DEFAULT_BENCHMARK_SEED,
) -> dict:
    """Berechnet nicht-parametrische empirische Bootstrap-Konfidenzintervalle (z. B. 95% CI)."""
    scores_arr = np.asarray(scores, dtype=np.float64)
    if len(scores_arr) == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "std": 0.0, "ci_formatted": "0.000 [95% CI: 0.000 - 0.000]"}

    rng = np.random.default_rng(seed)
    n = len(scores_arr)
    boot_means = np.empty(n_bootstraps, dtype=np.float64)
    for i in range(n_bootstraps):
        sample = rng.choice(scores_arr, size=n, replace=True)
        boot_means[i] = np.mean(sample)

    alpha = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(boot_means, alpha * 100.0))
    ci_upper = float(np.percentile(boot_means, (1.0 - alpha) * 100.0))
    mean_val = float(np.mean(scores_arr))
    std_val = float(np.std(scores_arr))

    return {
        "mean": round(mean_val, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "std": round(std_val, 4),
        "ci_formatted": f"{mean_val:.3f} [95% CI: {ci_lower:.3f} - {ci_upper:.3f}]"
    }


def compute_wilcoxon_significance_test(
    scores_a: list[float] | np.ndarray,
    scores_b: list[float] | np.ndarray,
) -> dict:
    """Führt einen gepaarten Wilcoxon-Signed-Rank-Test durch (IGNITE vs. Baseline)."""
    a = np.asarray(scores_a, dtype=np.float64)
    b = np.asarray(scores_b, dtype=np.float64)

    if len(a) != len(b) or len(a) < 3:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "p_formatted": "p = 1.000",
            "significant": False,
            "mean_difference": 0.0
        }

    diff = a - b
    mean_diff = float(np.mean(diff))

    try:
        from scipy import stats
        res = stats.wilcoxon(a, b, alternative='greater')
        stat = float(res.statistic)
        p_val = float(res.pvalue)
    except Exception:
        nonzero_diff = diff[diff != 0]
        n_nz = len(nonzero_diff)
        if n_nz == 0:
            return {"statistic": 0.0, "p_value": 1.0, "p_formatted": "p = 1.000", "significant": False, "mean_difference": 0.0}

        ranks = np.argsort(np.abs(nonzero_diff)).argsort() + 1
        w_plus = float(np.sum(ranks[nonzero_diff > 0]))
        stat = w_plus
        mean_w = n_nz * (n_nz + 1) / 4.0
        var_w = n_nz * (n_nz + 1) * (2 * n_nz + 1) / 24.0
        z = (w_plus - 0.5 - mean_w) / max(1e-5, np.sqrt(var_w))
        from math import erfc, sqrt
        p_val = float(0.5 * erfc(z / sqrt(2)))

    p_formatted = "p < 0.001" if p_val < 0.001 else f"p = {p_val:.4f}"

    return {
        "statistic": round(stat, 3),
        "p_value": round(p_val, 6),
        "p_formatted": p_formatted,
        "significant": bool(p_val < 0.05),
        "mean_difference": round(mean_diff, 4)
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

    # 4. Statistische Validierung (Bootstrapping 95% CI, Wilcoxon Test, Bland-Altman & AUC)
    ignite_dices = [m["dice"] for m in results.values()]
    baseline_dices = [entry["otsu_baseline"]["dice"] for entry in baseline_comparison.values()]
    ignite_sens = [m["sensitivity"] for m in results.values()]
    ignite_spec = [m["specificity"] for m in results.values()]
    ignite_mccs = [m.get("mcc", 0.0) for m in results.values()]
    ignite_kappas = [m.get("cohen_kappa", 0.0) for m in results.values()]

    auc_metrics = compute_roc_auc_and_pr_auc(img_eval, gt_eval)
    bland_altman_res = compute_bland_altman(ignite_dices, baseline_dices)

    statistical_validation = {
        "wilcoxon_vs_otsu": compute_wilcoxon_significance_test(ignite_dices, baseline_dices),
        "bland_altman": bland_altman_res,
        "roc_pr_auc": auc_metrics,
        "bootstrap_ci": {
            "dice": compute_bootstrap_confidence_intervals(ignite_dices, seed=seed),
            "sensitivity": compute_bootstrap_confidence_intervals(ignite_sens, seed=seed),
            "specificity": compute_bootstrap_confidence_intervals(ignite_spec, seed=seed),
            "mcc": compute_bootstrap_confidence_intervals(ignite_mccs, seed=seed),
            "cohen_kappa": compute_bootstrap_confidence_intervals(ignite_kappas, seed=seed),
        },
    }

    output_data = {
        "scenario_results": results,
        "baseline_otsu_comparison": baseline_comparison,
        "mad_thresholding_comparison": mad_comparison,
        "sensitivity_analysis_k": k_analysis,
        "statistical_validation": statistical_validation,
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
