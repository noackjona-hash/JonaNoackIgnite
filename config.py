import os
import json
import secrets
import logging

SETTINGS_FILE = "settings.json"

_DEFAULT_SETTINGS = {
    "DEFAULT_SIGMA_K": 3.0,
    "DEFAULT_TOPHAT_FACTOR": 0.05,
    "DEFAULT_MIN_AREA_FACTOR": 0.0005,
    "DEFAULT_MIN_CIRCULARITY": 0.01,
    "DEFAULT_OTSU_MIN": 35,
    "DEFAULT_OTSU_MAX": 50,
    "DEFAULT_DIST_EROSION_FACTOR": 0.05,
    "DEFAULT_TEMP_MIN": 20.0,
    "DEFAULT_TEMP_MAX": 40.0,
    "OUTPUT_DIR": "ignite_steps_output",
    "ANATOMICAL_LOWER_CUTOFF_Y": 0.65,
    "MIN_DIST_FROM_BORDER_FACTOR": 0.005,
    "MIN_DIST_FROM_BORDER_ABS": 4.0,
    "BORDER_MARGIN_PX": 10,
    "SALT": secrets.token_hex(16)
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_SETTINGS, f, indent=4)
        return _DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Merge with defaults in case of missing keys
            updated = False
            for k, v in _DEFAULT_SETTINGS.items():
                if k not in settings:
                    settings[k] = v
                    updated = True
            
            if updated:
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f2:
                    json.dump(settings, f2, indent=4)
                    
            return settings
    except Exception as e:
        logging.error(f"Fehler beim Laden der {SETTINGS_FILE}: {e}", exc_info=True)
        return _DEFAULT_SETTINGS.copy()

_settings = load_settings()

# Standardwerte für die adaptive Thermobild-Pipeline
DEFAULT_SIGMA_K = _settings["DEFAULT_SIGMA_K"]
DEFAULT_TOPHAT_FACTOR = _settings["DEFAULT_TOPHAT_FACTOR"]
DEFAULT_MIN_AREA_FACTOR = _settings["DEFAULT_MIN_AREA_FACTOR"]
DEFAULT_MIN_CIRCULARITY = _settings["DEFAULT_MIN_CIRCULARITY"]
DEFAULT_OTSU_MIN = _settings["DEFAULT_OTSU_MIN"]
DEFAULT_OTSU_MAX = _settings["DEFAULT_OTSU_MAX"]
DEFAULT_DIST_EROSION_FACTOR = _settings["DEFAULT_DIST_EROSION_FACTOR"]

# ── Celsius-Kalibrierung (Kamerabereich) ──────────────────────────────────────
DEFAULT_TEMP_MIN = _settings["DEFAULT_TEMP_MIN"]
DEFAULT_TEMP_MAX = _settings["DEFAULT_TEMP_MAX"]

OUTPUT_DIR = _settings["OUTPUT_DIR"]

# Audit-Trail-Pfad (persistente klinische Protokolldatei)
AUDIT_TRAIL_PATH = os.path.join(OUTPUT_DIR, "ignite_audit_trail.csv")

# ── Anatomische Filterparameter ────────────────────────────────────────────────
ANATOMICAL_LOWER_CUTOFF_Y = _settings["ANATOMICAL_LOWER_CUTOFF_Y"]
MIN_DIST_FROM_BORDER_FACTOR = _settings["MIN_DIST_FROM_BORDER_FACTOR"]
MIN_DIST_FROM_BORDER_ABS = _settings["MIN_DIST_FROM_BORDER_ABS"]
BORDER_MARGIN_PX = _settings["BORDER_MARGIN_PX"]

SALT = _settings["SALT"]

def init_output_dir():
    """Erstellt den Ausgabeordner, falls er noch nicht existiert."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
