import os
import hashlib
import numpy as np
import config

def apply_radiometric_emissivity_correction(
    temp_celsius: float,
    emissivity: float = config.SKIN_EMISSIVITY,
    t_refl_celsius: float = config.REFLECTED_TEMP_C,
    distance_m: float = 1.0,
    rel_humidity: float = 0.50,
    t_ambient_c: float = 20.0
) -> float:
    """
    Berechnet die physikalisch korrigierte Objekttemperatur unter Berücksichtigung
    des Emissivitätsgrads (Haut ~0.98), der reflektierten Umgebungstemperatur und
    der atmosphärischen Transmission (Dämpfung durch Messdistanz und Luftfeuchte).

    Strahlungsbilanz:
    W_tot = eps * tau * W_obj + (1 - eps) * tau * W_refl + (1 - tau) * W_atm
    W_obj = (W_tot - (1 - eps) * tau * W_refl - (1 - tau) * W_atm) / (eps * tau)
    """
    t_meas_k = temp_celsius + 273.15
    t_refl_k = t_refl_celsius + 273.15
    t_atm_k = t_ambient_c + 273.15

    # Atmosphärische Transmission (FLIR Modell)
    # Sättigungsdampfdruck e_s in hPa (Magnus-Formel)
    e_s = 6.112 * np.exp((17.67 * t_ambient_c) / (t_ambient_c + 243.5))
    h_abs = (rel_humidity * e_s * 216.7) / (t_ambient_c + 273.15)
    d = max(0.05, distance_m)
    # Dämpfungskoeffizient für langwelliges Infrarot (8 - 14 µm)
    tau = float(np.clip(np.exp(-np.sqrt(d) * (0.0065 + 0.0012 * np.sqrt(max(0.0, h_abs)))), 0.6, 1.0))

    # Stefan-Boltzmann Strahlungsbilanz
    rad_meas = t_meas_k ** 4
    rad_refl = (1.0 - emissivity) * tau * (t_refl_k ** 4)
    rad_atm = (1.0 - tau) * (t_atm_k ** 4)

    rad_obj = (rad_meas - rad_refl - rad_atm) / max(0.01, emissivity * tau)
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
    Konvertiert 16-Bit / Float RAW Wärmebilddaten (z. B. FLIR/Optris/Hikmicro mK-Counts,
    Centikelvin, Decikelvin, 0.1°C oder 32-Bit Float °C) in ein physikalisch kalibriertes
    8-Bit Graustufenbild.

    Unterstützte Formate / Skalierungen:
    - 8-Bit (uint8): Unverändert zurückgeben
    - Float (float32, float64): Direkte Temperaturwerte in °C -> lineare Skalierung auf [t_min, t_max]
    - Centikelvin / mK (Werte > 20000, z. B. 29315 - 32315 -> 20.0°C - 50.0°C): T_C = raw * 0.01 - 273.15
    - Decikelvin (Werte 2500 - 4500, z. B. 2931 -> 20.0°C): T_C = raw * 0.1 - 273.15
    - Centicelsius / 0.01°C (Werte 1500 - 6000, wenn max < 10000): T_C = raw * 0.01
    - Decicelsius / 0.1°C (Werte 150 - 1000): T_C = raw * 0.1
    - Unkalibrierte 16-Bit Counts (z. B. 0 - 65535 oder 0 - 16383 RAW-Sensor-ADU):
      Robuste Min-Max-Skalierung (0.5 - 99.5 Perzentil zur Ausreißer-Unterdrückung)
    """
    if raw_16bit.dtype == np.uint8:
        return raw_16bit

    if np.issubdtype(raw_16bit.dtype, np.floating):
        # Direkte Celsius-Fließkommawerte
        temp_c = raw_16bit.astype(np.float32)
    else:
        raw_max = float(np.max(raw_16bit))
        raw_min = float(np.min(raw_16bit))

        if raw_max > 20000:
            # Centikelvin: 1 LSB = 0.01 K (z. B. FLIR RAW: 30000 = 300.00 K = 26.85 °C)
            temp_c = raw_16bit.astype(np.float32) * 0.01 - 273.15
        elif 2500 <= raw_max <= 4500 and raw_min >= 2000:
            # Decikelvin: 1 LSB = 0.1 K (z. B. 3031 = 303.1 K = 30.0 °C)
            temp_c = raw_16bit.astype(np.float32) * 0.1 - 273.15
        elif 1500 <= raw_max <= 6000 and raw_min >= 500:
            # Centicelsius: 1 LSB = 0.01 °C (z. B. 3250 = 32.50 °C)
            temp_c = raw_16bit.astype(np.float32) * 0.01
        elif 150 <= raw_max <= 1000 and raw_min >= 50:
            # Decicelsius: 1 LSB = 0.1 °C (z. B. 325 = 32.5 °C)
            temp_c = raw_16bit.astype(np.float32) * 0.1
        else:
            # Unkalibrierte Sensor-Rohdaten (ADU 14-Bit / 16-Bit)
            # Robuste Normalisierung über Perzentile
            p1 = float(np.percentile(raw_16bit, 0.5))
            p99 = float(np.percentile(raw_16bit, 99.5))
            if p99 > p1:
                norm = np.clip((raw_16bit.astype(np.float32) - p1) / (p99 - p1), 0.0, 1.0)
                return (norm * 255.0).astype(np.uint8)
            else:
                return np.zeros_like(raw_16bit, dtype=np.uint8)

    # Lineares Mapping auf [t_min, t_max] und Konvertierung nach 8-Bit
    range_c = max(1e-5, t_max - t_min)
    clipped = np.clip(temp_c, t_min, t_max)
    normalized = np.clip(np.round((clipped - t_min) / range_c * 255.0), 0, 255).astype(np.uint8)
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
