import pytest
from utils import pixel_to_celsius, pseudonymize_patient
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
