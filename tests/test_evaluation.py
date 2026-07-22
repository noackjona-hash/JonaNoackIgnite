import pytest
import numpy as np
from dataset_evaluator import generate_clinical_scenario, evaluate_metrics, run_benchmark_suite

def test_generate_clinical_scenario():
    img, gt = generate_clinical_scenario("diabetic_ulcer")
    assert img.shape == (400, 400)
    assert gt.shape == (400, 400)
    assert np.sum(gt) > 0

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
    res = run_benchmark_suite()
    assert "scenario_results" in res
    assert "diabetic_ulcer" in res["scenario_results"]
    assert res["scenario_results"]["diabetic_ulcer"]["sensitivity"] == 1.0
