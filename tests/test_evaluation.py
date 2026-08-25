import pytest
import numpy as np
from dataset_evaluator import (
    generate_clinical_scenario,
    evaluate_metrics,
    run_benchmark_suite,
    _baseline_otsu_predict,
    evaluate_real_dataset_with_gt,
)
import image_processing

def test_generate_clinical_scenario():
    img, gt = generate_clinical_scenario("diabetic_ulcer")
    img2, gt2 = generate_clinical_scenario("diabetic_ulcer")
    assert img.shape == (400, 400)
    assert gt.shape == (400, 400)
    assert np.sum(gt) > 0
    np.testing.assert_array_equal(img, img2)
    np.testing.assert_array_equal(gt, gt2)

def test_evaluate_metrics():
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[10:20, 10:20] = 255 # 100 pixels
    
    pred = np.zeros((100, 100), dtype=np.uint8)
    pred[10:20, 10:20] = 255 # 100 pixels matching exactly
    
    metrics = evaluate_metrics(pred, gt)
    assert metrics["sensitivity"] == 1.0
    assert metrics["specificity"] == 1.0
    assert metrics["dice"] == 1.0
    assert metrics["iou"] == 1.0


def test_statistical_validation_functions():
    """Testet Bootstrap-Konfidenzintervalle und Wilcoxon-Signifikanztest."""
    from dataset_evaluator import compute_bootstrap_confidence_intervals, compute_wilcoxon_significance_test

    scores_a = [0.92, 0.95, 0.90, 0.96, 0.94, 0.91, 0.95]
    scores_b = [0.45, 0.50, 0.40, 0.55, 0.48, 0.42, 0.51]

    # 1. Bootstrap CI
    ci_res = compute_bootstrap_confidence_intervals(scores_a, n_bootstraps=500, seed=42)
    assert 0.88 <= ci_res["ci_lower"] <= ci_res["mean"] <= ci_res["ci_upper"] <= 1.0
    assert "95% CI:" in ci_res["ci_formatted"]

    # 2. Wilcoxon Test
    wilc_res = compute_wilcoxon_significance_test(scores_a, scores_b)
    assert wilc_res["significant"] is True
    assert wilc_res["p_value"] < 0.05
    assert wilc_res["mean_difference"] > 0.4


@pytest.mark.benchmark
def test_run_benchmark_suite():
    res1 = run_benchmark_suite()
    res2 = run_benchmark_suite()
    assert "scenario_results" in res1
    assert "diabetic_ulcer" in res1["scenario_results"]
    assert res1["scenario_results"]["diabetic_ulcer"]["sensitivity"] == 1.0
    assert res1["scenario_results"] == res2["scenario_results"]
    assert res1["sensitivity_analysis_k"] == res2["sensitivity_analysis_k"]
    assert res1["reproducibility"]["seed"] == 42
    assert res1["reproducibility"]["backend"] == "python"
    assert "statistical_validation" in res1

def test_new_scenarios_exist():
    """Alle 9 Szenarien müssen generierbar sein und sinnvolle Bilder erzeugen."""
    new_scenarios = ["pressure_ulcer", "post_surgical_inflammation", "venous_insufficiency"]
    for scenario in new_scenarios:
        img, gt = generate_clinical_scenario(scenario, add_noise=True)
        assert img.shape == (400, 400), f"{scenario}: falsche Bildgröße"
        assert img.dtype == np.uint8, f"{scenario}: falscher Dtype"
        # GT kann 0 sein (normal-Szenario), aber bei diesen Szenarien sollte etwas da sein
        assert np.sum(gt) > 0, f"{scenario}: Ground-Truth-Maske ist leer"

def test_baseline_otsu_worse_than_ignite():
    """IGNITE muss auf allen klinischen Szenarien besseren Dice als Otsu-Baseline erreichen."""
    for scenario in ["diabetic_ulcer", "plantar_fasciitis", "pressure_ulcer"]:
        img, gt = generate_clinical_scenario(scenario, add_noise=True, seed=42)
        body_mask = image_processing._extract_body_mask_cpu(img)

        _, ignite_mask = image_processing._python_fallback_pipeline(img)
        baseline_mask = _baseline_otsu_predict(img)

        m_ignite = evaluate_metrics(ignite_mask, gt, body_mask)
        m_baseline = evaluate_metrics(baseline_mask, gt, body_mask)

        assert m_ignite["dice"] >= m_baseline["dice"], (
            f"{scenario}: IGNITE Dice ({m_ignite['dice']:.3f}) "
            f"< Otsu-Baseline Dice ({m_baseline['dice']:.3f})"
        )

@pytest.mark.benchmark
def test_benchmark_has_baseline_comparison():
    """run_benchmark_suite() muss baseline_otsu_comparison enthalten."""
    result = run_benchmark_suite()
    assert "baseline_otsu_comparison" in result
    for scenario in ["diabetic_ulcer", "plantar_fasciitis"]:
        assert scenario in result["baseline_otsu_comparison"]
        entry = result["baseline_otsu_comparison"][scenario]
        assert "ignite" in entry
        assert "otsu_baseline" in entry
        assert "dice_improvement" in entry


@pytest.mark.benchmark
def test_gt_evaluation_runs_without_error():
    """evaluate_real_dataset_with_gt() darf nicht abstürzen, auch wenn GT fehlt."""
    results = evaluate_real_dataset_with_gt(test_data_dir="test-data")
    assert isinstance(results, dict)
    # Mindestens 1 Bild muss verarbeitet worden sein
    image_entries = {k: v for k, v in results.items() if not k.startswith("__")}
    assert len(image_entries) > 0


def test_advanced_clinical_metrics_and_agreement():
    """Testet Matthews Correlation Coefficient, Cohen's Kappa, Youden's J, DOR und Oberflächen-Distanzen."""
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[20:40, 20:40] = 255  # 400 px Ground Truth

    pred = np.zeros((100, 100), dtype=np.uint8)
    pred[22:42, 22:42] = 255  # 400 px leicht verschobene Vorhersage

    m = evaluate_metrics(pred, gt)

    # Matthews Correlation Coefficient & Cohen's Kappa
    assert 0.80 <= m["mcc"] <= 1.0
    assert 0.80 <= m["cohen_kappa"] <= 1.0
    assert 0.80 <= m["youden_j"] <= 1.0
    assert m["dor"] > 10.0
    assert m["lr_plus"] > 10.0
    assert m["lr_minus"] < 0.2

    # Hausdorff-95 und ASSD Distanzen
    assert 0.0 <= m["hd95_px"] <= 5.0
    assert 0.0 <= m["assd_px"] <= 4.0


def test_roc_auc_and_pr_auc_computation():
    """Testet die numerische Integration von ROC-AUC und PR-AUC über k-Sigma Parametervariation."""
    from dataset_evaluator import compute_roc_auc_and_pr_auc

    img, gt = generate_clinical_scenario("diabetic_ulcer", add_noise=True, seed=42)
    auc_res = compute_roc_auc_and_pr_auc(img, gt, k_range=[1.0, 2.0, 3.0, 4.0, 5.0])

    assert "roc_auc" in auc_res
    assert "pr_auc" in auc_res
    assert 0.90 <= auc_res["roc_auc"] <= 1.0
    assert 0.40 <= auc_res["pr_auc"] <= 1.0
    assert len(auc_res["tpr_points"]) == len(auc_res["fpr_points"])


def test_bland_altman_method_comparison():
    """Testet die Bland-Altman Methodenvergleichsanalyse mit 95% Limits of Agreement."""
    from dataset_evaluator import compute_bland_altman

    # Simulierte Dice-Scores: IGNITE (~0.95) vs. Otsu (~0.45)
    ignite_scores = [0.94, 0.96, 0.95, 0.97, 0.93, 0.95, 0.96]
    otsu_scores = [0.42, 0.46, 0.44, 0.50, 0.38, 0.45, 0.47]

    ba = compute_bland_altman(ignite_scores, otsu_scores)

    assert ba["mean_bias"] > 0.45  # Systematischer Bias / Überlegenheit von IGNITE
    assert ba["loa_lower"] < ba["mean_bias"] < ba["loa_upper"]
    assert "Bias:" in ba["loa_formatted"]
    assert ba["outlier_pct"] <= 15.0


def test_iwgdf_armstrong_risk_stratification():
    """Testet die klinische Risikostratifizierung nach IWGDF 2023 & Armstrong."""
    from dataset_evaluator import classify_iwgdf_armstrong_risk

    # Grad 0: Normalbefund (ΔT < 1.0°C)
    g0 = classify_iwgdf_armstrong_risk(delta_t_c=0.4, hotspot_area_pct=0.0, arch_index=0.23)
    assert g0["grade"] == 0
    assert g0["is_pathologic"] is False

    # Grad 1: Geringes Risiko (1.0°C <= ΔT < 2.2°C)
    g1 = classify_iwgdf_armstrong_risk(delta_t_c=1.6, hotspot_area_pct=0.5, arch_index=0.24)
    assert g1["grade"] == 1
    assert g1["is_pathologic"] is False

    # Grad 2: Hohes Risiko / IWGDF-Grenzwert (ΔT >= 2.2°C)
    g2 = classify_iwgdf_armstrong_risk(delta_t_c=2.4, hotspot_area_pct=1.8, arch_index=0.25)
    assert g2["grade"] == 2
    assert g2["is_pathologic"] is True

    # Grad 3: Akutes Hochrisiko (ΔT >= 3.0°C oder Progression)
    g3 = classify_iwgdf_armstrong_risk(delta_t_c=3.5, hotspot_area_pct=4.2, arch_index=0.29, longitudinal_trend="progression")
    assert g3["grade"] == 3
    assert g3["is_pathologic"] is True

