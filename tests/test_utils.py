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
    raw_16bit = np.array([[30315, 29315], [31315, 28315]], dtype=np.uint16) # ~30°C, 20°C, 40°C, 10°C
    img_8bit = convert_16bit_radiometric_to_8bit(raw_16bit, t_min=20.0, t_max=40.0)

    assert img_8bit.shape == (2, 2)
    assert img_8bit.dtype == np.uint8
    assert img_8bit[0, 0] > 100 # 30°C is roughly middle of [20, 40]
    assert img_8bit[0, 1] == 0   # 20°C is min

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
