import os
import hashlib
import config

def pixel_to_celsius(pixel_value: float, t_min: float, t_max: float) -> float:
    """Konvertiert einen 8-Bit Pixelwert (0-255) in Grad Celsius.

    Lineare Abbildung: T(x) = T_min + x * (T_max - T_min) / 255

    Args:
        pixel_value: Rohwert aus dem Thermobild (0–255).
        t_min: Minimaler Temperaturbereich der Kamera in °C.
        t_max: Maximaler Temperaturbereich der Kamera in °C.

    Returns:
        Temperatur in Grad Celsius.
    """
    return t_min + (pixel_value / 255.0) * (t_max - t_min)

def pseudonymize_patient(name: str, dob: str = "") -> str:
    """Erzeugt eine DSGVO-konforme Pseudonym-ID via SHA-256 mit systemweitem Salt.

    Args:
        name: Klartextname des Patienten.
        dob: Optionales Geburtsdatum zur Erhöhung der Eindeutigkeit.

    Returns:
        12-stellige alphanumerische Patienten-ID (Präfix 'ANON-').
    """
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
