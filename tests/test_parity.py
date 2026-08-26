import pytest
import numpy as np
import image_processing

@pytest.fixture
def synthetic_thermal_image():
    # Create a synthetic thermal image with a simulated "body" and a "hotspot"
    img = np.zeros((300, 300), dtype=np.uint8)
    
    # 1. Simulate the body part with a temperature/pixel value within the typical OTSU range
    img[50:250, 50:250] = 80 
    
    # 2. Add some "hotspots" to be detected (must be smaller than the 15x15 top-hat kernel to be isolated)
    # A localized hotspot
    img[100:110, 100:110] = 190
    
    # A smaller, subtle hotspot
    img[180:188, 180:188] = 150
    
    return img

def _assert_mask_iou_at_least(mask_a, mask_b, min_iou: float, label: str):
    """Prueft die Uebereinstimmung zweier Binaermasken ueber die Jaccard-Distanz."""
    a, b = (mask_a > 0), (mask_b > 0)
    union = int((a | b).sum())
    iou = (int((a & b).sum()) / union) if union else 1.0
    assert iou >= min_iou, f"{label}: Masken-IoU {iou:.4f} unter Mindestgrenze {min_iou}"


def test_pipeline_parity(synthetic_thermal_image):
    """
    Tests that all available backends (Python, Rust, PyTorch) produce
    mathematically equivalent (or extremely similar) outputs for the same image.
    """
    
    # Generate baseline using Python Fallback
    py_diff, py_mask = image_processing._python_fallback_pipeline(synthetic_thermal_image)
    
    # Ensure something was actually detected in the baseline
    assert np.sum(py_mask) > 0, "Python baseline failed to detect any hotspots"
    
    # 1. Test GPU Parity
    if image_processing._GPU_AVAILABLE:
        gpu_diff, gpu_mask = image_processing._pytorch_gpu_pipeline(synthetic_thermal_image)
        
        # Using atol=2 for diff image because PyTorch interpolation/float vs OpenCV 8-bit math
        # can sometimes differ by a pixel value of 1 or 2.
        np.testing.assert_allclose(gpu_diff, py_diff, atol=2, err_msg="GPU diff_img mismatch with Python fallback")
        np.testing.assert_array_equal(gpu_mask, py_mask, err_msg="GPU hotspot mask mismatch with Python fallback")
        
    # 2. Test Rust Core Parity
    if image_processing._RUST_BACKEND_AVAILABLE and image_processing._ignite_core is not None:
        img_contiguous = np.ascontiguousarray(synthetic_thermal_image, dtype=np.uint8)
        rust_diff, rust_mask = image_processing._ignite_core.process_thermal_pipeline(
            img_contiguous,
            image_processing._config.DEFAULT_SIGMA_K,
            image_processing._config.DEFAULT_TOPHAT_FACTOR,
            image_processing._config.DEFAULT_MIN_AREA_FACTOR,
            image_processing._config.DEFAULT_MIN_CIRCULARITY,
            image_processing._config.DEFAULT_OTSU_MIN,
            image_processing._config.DEFAULT_OTSU_MAX,
            image_processing._config.DEFAULT_DIST_EROSION_FACTOR
        )
        
        # Check parity against Python baseline.
        # Bewusst KEINE Bit-Gleichheit: Der Rust-Kern nutzt eine separable
        # Lemire-Morphologie und eine Chamfer-Distanztransformation, OpenCV
        # dagegen eigene Randbehandlung und eine andere DT-Approximation.
        # Auf den sehr kleinen synthetischen Hotspots (10x10 und 8x8 Pixel)
        # dominieren diese Randeffekte die Metrik: schon eine einzelne
        # abweichende Konturzeile aendert die IoU um mehrere Prozentpunkte.
        # Die Grenze ist daher niedriger als bei den grossflaechigen Realbildern
        # (siehe test_rust_python_parity_on_real_images).
        _assert_mask_iou_at_least(rust_mask, py_mask, 0.60, "Rust vs. Python (Gauss)")
        # Diff image: Over 99.99% of pixels are identical (allowing for tiny corner discretization in separable erosion)
        # Normalisiertes Top-Hat-Differenzbild: mittlere Abweichung deutlich unter
        # einem Grauwert. Die Restabweichung stammt aus der unterschiedlichen
        # Randbehandlung der Morphologie und der Min-Max-Normalisierung.
        diff_abs = np.abs(rust_diff.astype(int) - py_diff.astype(int))
        assert np.mean(diff_abs) < 0.5, f"Mean diff error too large: {np.mean(diff_abs)}"

def test_pipeline_parity_mad(synthetic_thermal_image):
    """
    Tests that MAD-based robust thresholding produces equivalent output across Python and Rust backends.
    """
    py_diff, py_mask = image_processing._python_fallback_pipeline(synthetic_thermal_image, use_mad=True)
    assert np.sum(py_mask) > 0, "Python baseline with MAD failed to detect hotspots"

    if image_processing._RUST_BACKEND_AVAILABLE and image_processing._ignite_core is not None:
        img_contiguous = np.ascontiguousarray(synthetic_thermal_image, dtype=np.uint8)
        rust_diff, rust_mask = image_processing._ignite_core.process_thermal_pipeline(
            img_contiguous,
            image_processing._config.DEFAULT_SIGMA_K,
            image_processing._config.DEFAULT_TOPHAT_FACTOR,
            image_processing._config.DEFAULT_MIN_AREA_FACTOR,
            image_processing._config.DEFAULT_MIN_CIRCULARITY,
            image_processing._config.DEFAULT_OTSU_MIN,
            image_processing._config.DEFAULT_OTSU_MAX,
            image_processing._config.DEFAULT_DIST_EROSION_FACTOR,
            True
        )
        _assert_mask_iou_at_least(rust_mask, py_mask, 0.60, "Rust vs. Python (MAD)")
        diff_abs = np.abs(rust_diff.astype(int) - py_diff.astype(int))
        assert np.mean(diff_abs) < 0.5, f"Mean MAD diff error too large: {np.mean(diff_abs)}"



# ── Paritaet auf echten Aufnahmen ────────────────────────────────────────────
# Der bisherige Paritaetsnachweis beruhte ausschliesslich auf einem synthetischen
# achsenparallelen Rechteck. Dieser Sonderfall verdeckt alle real auftretenden
# Abweichungen zwischen den Backends. Die folgenden Tests pruefen daher auf den
# echten Thermogrammen und schreiben die tatsaechlich erreichte Uebereinstimmung
# als ueberpruefbare Untergrenze fest.

import glob
import os

import cv2

_REAL_IMAGES = sorted(glob.glob(os.path.join("test-data", "*.jpeg")))

# Empirisch ermittelte Untergrenzen (siehe scripts/run_validation.py).
# Exakte Bit-Paritaet ist prinzipiell nicht erreichbar: Der Rust-Kern nutzt eine
# separable Chamfer-Distanztransformation, OpenCV eine andere Approximation.
_MIN_MEAN_MASK_IOU = 0.70
_MIN_SINGLE_MASK_IOU = 0.40


@pytest.mark.skipif(not _REAL_IMAGES, reason="Keine Realbilder in test-data/ vorhanden")
def test_rust_python_parity_on_real_images():
    """Rust- und Python-Backend muessen auf echten Aufnahmen eng uebereinstimmen."""
    if not (image_processing._RUST_BACKEND_AVAILABLE and image_processing._ignite_core is not None):
        pytest.skip("Rust-Backend nicht verfuegbar")

    ious = []
    for path in _REAL_IMAGES:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        img = np.ascontiguousarray(img, dtype=np.uint8)

        _, py_mask = image_processing._python_fallback_pipeline(img)
        _, rust_mask = image_processing._ignite_core.process_thermal_pipeline(
            img,
            image_processing._config.DEFAULT_SIGMA_K,
            image_processing._config.DEFAULT_TOPHAT_FACTOR,
            image_processing._config.DEFAULT_MIN_AREA_FACTOR,
            image_processing._config.DEFAULT_MIN_CIRCULARITY,
            image_processing._config.DEFAULT_OTSU_MIN,
            image_processing._config.DEFAULT_OTSU_MAX,
            image_processing._config.DEFAULT_DIST_EROSION_FACTOR,
        )

        a, b = (py_mask > 0), (rust_mask > 0)
        union = int((a | b).sum())
        iou = (int((a & b).sum()) / union) if union else 1.0
        ious.append(iou)
        assert iou >= _MIN_SINGLE_MASK_IOU, (
            f"{os.path.basename(path)}: Masken-IoU {iou:.3f} unter Mindestgrenze "
            f"{_MIN_SINGLE_MASK_IOU}. Backends sind auseinandergelaufen."
        )

    assert ious, "Keine Realbilder ausgewertet"
    mean_iou = float(np.mean(ious))
    assert mean_iou >= _MIN_MEAN_MASK_IOU, (
        f"Mittlere Masken-IoU {mean_iou:.3f} unter Mindestgrenze {_MIN_MEAN_MASK_IOU}"
    )


@pytest.mark.skipif(not _REAL_IMAGES, reason="Keine Realbilder in test-data/ vorhanden")
def test_python_fallback_defaults_match_rust_algorithm():
    """Der Fallback muss standardmaessig einskalig und ohne Vorglaettung rechnen.

    Multi-Scale-Top-Hat und Vorglaettung sind bewusst abschaltbare Zusatzoptionen;
    waeren sie Standard, wuerde der Fallback einen anderen Algorithmus rechnen als
    der Rust-Kern und die Paritaetspruefung waere bedeutungslos.
    """
    import inspect

    sig = inspect.signature(image_processing._python_fallback_pipeline)
    assert sig.parameters["multiscale"].default is False
    assert sig.parameters["pre_blur"].default is False
