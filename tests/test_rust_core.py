import pytest
import numpy as np
try:
    import ignite_core
except ImportError:
    ignite_core = None

@pytest.mark.skipif(ignite_core is None, reason="Rust Core (ignite_core) is not installed")
def test_rust_pipeline_returns_correct_types():
    # Erstelle ein 100x100 Dummy Wärmebild
    dummy_img = np.random.randint(0, 255, size=(100, 100), dtype=np.uint8)
    
    # Mache es contiguous
    dummy_img = np.ascontiguousarray(dummy_img, dtype=np.uint8)
    
    diff_vis, final_mask = ignite_core.process_thermal_pipeline(
        dummy_img,
        2.0,  # sigma_k
        0.05, # tophat_factor
        0.005, # min_area_factor
        0.01, # min_circularity
        35,   # otsu_min
        50,   # otsu_max
        0.05  # dist_erosion_factor
    )
    
    assert isinstance(diff_vis, np.ndarray)
    assert isinstance(final_mask, np.ndarray)
    assert diff_vis.shape == (100, 100)
    assert final_mask.shape == (100, 100)
    assert diff_vis.dtype == np.uint8
    assert final_mask.dtype == np.uint8
