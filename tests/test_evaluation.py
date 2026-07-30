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

def test_gt_evaluation_runs_without_error():
    """evaluate_real_dataset_with_gt() darf nicht abstürzen, auch wenn GT fehlt."""
    results = evaluate_real_dataset_with_gt(test_data_dir="test-data")
    assert isinstance(results, dict)
    # Mindestens 1 Bild muss verarbeitet worden sein
    image_entries = {k: v for k, v in results.items() if not k.startswith("__")}
    assert len(image_entries) > 0
