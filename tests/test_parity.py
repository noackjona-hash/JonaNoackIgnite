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
        
        # Check parity against Python baseline (atol=4 for 1D separable vs 2D morphology boundary variations)
        np.testing.assert_allclose(rust_diff, py_diff, atol=4, err_msg="Rust diff_img mismatch with Python fallback")
        np.testing.assert_array_equal(rust_mask, py_mask, err_msg="Rust hotspot mask mismatch with Python fallback")

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
        np.testing.assert_allclose(rust_diff, py_diff, atol=4, err_msg="Rust MAD diff_img mismatch")
        np.testing.assert_array_equal(rust_mask, py_mask, err_msg="Rust MAD hotspot mask mismatch")
