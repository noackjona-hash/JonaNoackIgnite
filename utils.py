import os
import hashlib
import numpy as np
import config

def apply_radiometric_emissivity_correction(
    temp_celsius: float,
    emissivity: float = config.SKIN_EMISSIVITY,
    t_refl_celsius: float = config.REFLECTED_TEMP_C
) -> float:
    """
    Berechnet die physikalisch korrigierte Objekttemperatur unter Berücksichtigung
    des Emissivitätsgrads (Haut ~0.98) und der reflektierten Umgebungstemperatur
    gemäß Stefan-Boltzmann-Gesetz.

    T_obj = ((T_meas^4 - (1 - epsilon) * T_refl^4) / epsilon)^(1/4)
    """
    t_meas_k = temp_celsius + 273.15
    t_refl_k = t_refl_celsius + 273.15

    # Stefan-Boltzmann Strahlungsbilanz
    rad_meas = t_meas_k ** 4
    rad_refl = (1.0 - emissivity) * (t_refl_k ** 4)

    rad_obj = (rad_meas - rad_refl) / max(0.01, emissivity)
    t_obj_k = max(0.0, rad_obj) ** 0.25

    return t_obj_k - 273.15

def pixel_to_celsius(
    pixel_value: float,
    t_min: float = config.DEFAULT_TEMP_MIN,
    t_max: float = config.DEFAULT_TEMP_MAX,
    apply_emissivity: bool = False
) -> float:
    """Konvertiert einen 8-Bit Pixelwert (0-255) in Grad Celsius.

    Lineare Abbildung: T(x) = T_min + x * (T_max - T_min) / 255
    """
    temp_raw = t_min + (pixel_value / 255.0) * (t_max - t_min)
    if apply_emissivity:
        return apply_radiometric_emissivity_correction(temp_raw)
    return temp_raw

def convert_16bit_radiometric_to_8bit(
    raw_16bit: np.ndarray,
    t_min: float = config.DEFAULT_TEMP_MIN,
    t_max: float = config.DEFAULT_TEMP_MAX
) -> np.ndarray:
    """
    Konvertiert 16-Bit RAW Wärmebilddaten (z. B. FLIR/Hikmicro mK-Counts)
    in ein kalibriertes 8-Bit Graustufenbild.
    """
    if raw_16bit.dtype == np.uint8:
        return raw_16bit

    # Angenommene Skalierung: 1 LSB = 0.01 °C (Centikelvin)
    temp_c = raw_16bit.astype(np.float32) * 0.01 - 273.15 if raw_16bit.max() > 10000 else raw_16bit.astype(np.float32) * 0.1

    # Clipping auf Temperaturfenster
    clipped = np.clip(temp_c, t_min, t_max)
    normalized = ((clipped - t_min) / (t_max - t_min) * 255.0).astype(np.uint8)
    return normalized

def pseudonymize_patient(name: str, dob: str = "") -> str:
    """Erzeugt eine DSGVO-konforme Pseudonym-ID via SHA-256 mit systemweitem Salt."""
    raw = f"{name.strip().lower()}|{dob.strip()}|{config.SALT}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ANON-{digest[:12].upper()}"

def get_resource_path(relative_path: str) -> str:
    """Gibt den absoluten Pfad zu einer Ressource zurück, passend für PyInstaller-EXEn."""
    import sys
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
