import pytest
import numpy as np
from utils import (
    pixel_to_celsius,
    pseudonymize_patient,
    apply_radiometric_emissivity_correction,
    convert_16bit_radiometric_to_8bit
)
import config

def test_pixel_to_celsius():
    t_min = 20.0
    t_max = 40.0

    # Test min value
    assert pixel_to_celsius(0, t_min, t_max) == 20.0

    # Test max value
    assert pixel_to_celsius(255, t_min, t_max) == 40.0

    # Test mid value
    assert pixel_to_celsius(127.5, t_min, t_max) == 30.0

def test_radiometric_emissivity_correction():
    # Bei 30°C Gemessener Temp und Emissivität 0.98 sollte korrigierte Temp leicht höher liegen
    t_corr = apply_radiometric_emissivity_correction(30.0, emissivity=0.98, t_refl_celsius=20.0)
    assert t_corr >= 30.0
    assert abs(t_corr - 30.2) < 0.5

def test_convert_16bit_radiometric_to_8bit():
    t_min, t_max = 20.0, 40.0

    # 1. Centikelvin: 1 LSB = 0.01 K (29315 = 20°C, 30315 = 30°C, 31315 = 40°C)
    ck_raw = np.array([[29315, 30315], [31315, 32315]], dtype=np.uint16)
    ck_8bit = convert_16bit_radiometric_to_8bit(ck_raw, t_min=t_min, t_max=t_max)
    assert ck_8bit.dtype == np.uint8
    assert ck_8bit[0, 0] == 0       # 20°C -> 0
    assert 126 <= ck_8bit[0, 1] <= 129  # 30°C -> ~127
    assert ck_8bit[1, 0] == 255     # 40°C -> 255
    assert ck_8bit[1, 1] == 255     # 50°C -> geclippt auf 255

    # 2. Decikelvin: 1 LSB = 0.1 K (2931 = 19.95°C -> 0, 3031 = 29.95°C, 3132 = 40.05°C -> 255)
    dk_raw = np.array([[2931, 3031], [3132, 2831]], dtype=np.uint16)
    dk_8bit = convert_16bit_radiometric_to_8bit(dk_raw, t_min=t_min, t_max=t_max)
    assert dk_8bit[0, 0] == 0
    assert 126 <= dk_8bit[0, 1] <= 129
    assert dk_8bit[1, 0] == 255

    # 3. Centicelsius: 1 LSB = 0.01°C (2000 = 20.0°C, 3000 = 30.0°C, 4000 = 40.0°C)
    cc_raw = np.array([[2000, 3000], [4000, 1500]], dtype=np.uint16)
    cc_8bit = convert_16bit_radiometric_to_8bit(cc_raw, t_min=t_min, t_max=t_max)
    assert cc_8bit[0, 0] == 0
    assert 126 <= cc_8bit[0, 1] <= 129
    assert cc_8bit[1, 0] == 255

    # 4. Decicelsius: 1 LSB = 0.1°C (200 = 20.0°C, 300 = 30.0°C, 400 = 40.0°C)
    dc_raw = np.array([[200, 300], [400, 100]], dtype=np.uint16)
    dc_8bit = convert_16bit_radiometric_to_8bit(dc_raw, t_min=t_min, t_max=t_max)
    assert dc_8bit[0, 0] == 0
    assert 126 <= dc_8bit[0, 1] <= 129
    assert dc_8bit[1, 0] == 255

    # 5. Float32/Float64 direkte Celsiuswerte
    flt_raw = np.array([[20.0, 30.0], [40.0, 10.0]], dtype=np.float32)
    flt_8bit = convert_16bit_radiometric_to_8bit(flt_raw, t_min=t_min, t_max=t_max)
    assert flt_8bit[0, 0] == 0
    assert 126 <= flt_8bit[0, 1] <= 129
    assert flt_8bit[1, 0] == 255

    # 6. Unkalibrierte 16-Bit Counts (z.B. ADU 0 bis 60000)
    adu_raw = np.linspace(5000, 45000, 100, dtype=np.uint16).reshape((10, 10))
    adu_8bit = convert_16bit_radiometric_to_8bit(adu_raw, t_min=t_min, t_max=t_max)
    assert adu_8bit.dtype == np.uint8
    assert adu_8bit.min() == 0
    assert adu_8bit.max() == 255


def test_load_thermal_image_multiformat(tmp_path):
    import image_processing
    import cv2

    # 1. 16-bit PNG/TIFF speichern und laden
    raw_16 = np.full((50, 50), 30315, dtype=np.uint16) # 30°C in Centikelvin
    raw_16[10:20, 10:20] = 31315 # 40°C
    tiff_path = str(tmp_path / "test_16bit.png")
    cv2.imwrite(tiff_path, raw_16)

    loaded = image_processing.load_thermal_image(tiff_path, t_min=20.0, t_max=40.0)
    assert loaded.shape == (50, 50)
    assert loaded.dtype == np.uint8
    assert 126 <= loaded[0, 0] <= 129
    assert loaded[15, 15] == 255

    # 2. NumPy .npy Datei speichern und laden
    npy_arr = np.array([[20.0, 30.0], [40.0, 25.0]], dtype=np.float32)
    npy_path = str(tmp_path / "test_raw.npy")
    np.save(npy_path, npy_arr)

    loaded_npy = image_processing.load_thermal_image(npy_path, t_min=20.0, t_max=40.0)
    assert loaded_npy.shape == (2, 2)
    assert loaded_npy[0, 0] == 0
    assert 126 <= loaded_npy[0, 1] <= 129
    assert loaded_npy[1, 0] == 255

    # 3. 3-Kanal False-Color Bild laden (RGB)
    rgb_img = np.zeros((30, 30, 3), dtype=np.uint8)
    rgb_img[:, :] = [100, 150, 200]
    rgb_path = str(tmp_path / "test_rgb.png")
    cv2.imwrite(rgb_path, rgb_img)

    loaded_rgb = image_processing.load_thermal_image(rgb_path)
    assert loaded_rgb.shape == (30, 30)
    assert loaded_rgb.dtype == np.uint8

def test_pseudonymize_patient():
    config.SALT = "test_salt"

    # Same inputs should yield same output
    res1 = pseudonymize_patient("Max Mustermann", "01.01.2000")
    res2 = pseudonymize_patient("max mustermann", "01.01.2000")
    assert res1 == res2

    # Prefix check
    assert res1.startswith("ANON-")
    assert len(res1) == 5 + 12

    # Different dob should yield different output
    res3 = pseudonymize_patient("Max Mustermann", "02.01.2000")
    assert res1 != res3

def test_contralateral_asymmetry():
    import image_processing
    img = np.zeros((100, 200), dtype=np.uint8)
    body_mask = np.zeros((100, 200), dtype=np.uint8)

    # Left foot: colder ~85 (26.6°C)
    img[20:80, 20:80] = 85
    body_mask[20:80, 20:80] = 255

    # Right foot: warmer ~160 (32.5°C) -> Delta ~5.9°C > 2.2°C
    img[20:80, 120:180] = 160
    body_mask[20:80, 120:180] = 255

    res = image_processing.compute_contralateral_asymmetry(img, body_mask, 20.0, 40.0, 2.2)
    assert res["is_asymmetric"] is True
    assert res["delta_t_c"] > 2.2
