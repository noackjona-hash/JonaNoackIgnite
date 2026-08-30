import os
import sys
import json
import secrets
import logging
from typing import Dict, Any

SETTINGS_FILE = "settings.json"
CANONICAL_APP_VERSION = "4.0.0"

def get_app_version() -> str:
    """Ermittelt die App-Version dynamisch aus der VERSION-Datei oder Fallback."""
    candidates = []
    
    # 1. PyInstaller MEIPASS
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "VERSION"))
        
    # 2. Executable-Verzeichnis (Installationspfad)
    if hasattr(sys, "executable") and sys.executable:
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "VERSION"))
        candidates.append(os.path.join(exe_dir, "_internal", "VERSION"))
        
    # 3. Modulpfad (__file__)
    try:
        file_dir = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(file_dir, "VERSION"))
        candidates.append(os.path.join(file_dir, "..", "VERSION"))
    except Exception:
        pass
    
    # 4. Arbeitsverzeichnis
    candidates.append(os.path.join(os.getcwd(), "VERSION"))

    for path in candidates:
        try:
            norm_path = os.path.abspath(path)
            if os.path.exists(norm_path):
                with open(norm_path, "r", encoding="utf-8") as f:
                    v = f.read().strip()
                    if v:
                        return v
        except Exception:
            pass
                
    return CANONICAL_APP_VERSION

APP_VERSION = get_app_version()

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "DEFAULT_SIGMA_K": 3.0,           # k=3.0 entspricht 99.86% Konfidenzintervall (Gauß)
    "DEFAULT_TOPHAT_FACTOR": 0.05,    # 5% der kleinsten Bilddimension (empirisch optimiert)
    "DEFAULT_MIN_AREA_FACTOR": 0.0005,
    "DEFAULT_MIN_CIRCULARITY": 0.08,
    "DEFAULT_OTSU_MIN": 35,
    "DEFAULT_OTSU_MAX": 50,
    "DEFAULT_DIST_EROSION_FACTOR": 0.05,
    "DEFAULT_USE_MAD": False,
    "DEFAULT_ENABLE_ASYMMETRY": True,
    # Schwellenwert nach Armstrong et al. (1997): "Infrared Dermal Thermometry for the
    # High-Risk Diabetic Foot", Physical Therapy 77(2):169–175.
    # Klinischer Goldstandard für pathologische Seitenasymmetrie beim diabetischen Fuß.
    "ASYMMETRY_THRESHOLD_C": 2.2,
    "DEFAULT_TEMP_MIN": 20.0,
    "DEFAULT_TEMP_MAX": 40.0,
    "OUTPUT_DIR": "ignite_steps_output",
    "ANATOMICAL_LOWER_CUTOFF_Y": 1.0,  # Veraltet / Deaktiviert zugunsten dynamischer PCA-Zonensegmentierung
    "DEFAULT_FOREFOOT_RATIO": 0.40,   # Vorfuß-Grenze entlang PCA-Längsachse (0.0–0.40)
    "DEFAULT_MIDFOOT_RATIO": 0.70,    # Mittelfuß-Grenze entlang PCA-Längsachse (0.40–0.70)
    "MIN_DIST_FROM_BORDER_FACTOR": 0.015,
    "MIN_DIST_FROM_BORDER_ABS": 12.0,
    "BORDER_MARGIN_PX": 10,
    # Emissivität menschlicher Haut nach Jones (1998) "A reappraisal of the use of
    # infrared thermal image analysis in medicine", IEEE Trans. Med. Imaging 17(6):1019–1027
    # und Steketee (1973) "Spectral emissivity of skin and pericardium", Phys. Med. Biol. 18(5).
    "SKIN_EMISSIVITY": 0.98,
    "REFLECTED_TEMP_C": 20.0,
    "UI_SCALE": 1.0,
    "SALT": secrets.token_hex(16),
    "APP_VERSION": "4.0.0",
    "GITHUB_REPO": "noackjona-hash/JonaNoackIgnite",
    "AUTO_CHECK_UPDATES": True,
    # ── Neue erweiterte Algorithmus-Parameter (v3.3 & v3.4) ───────────────────
    "DEFAULT_MULTISCALE_TOPHAT": True,
    "DEFAULT_MULTISCALE_FACTORS": [0.025, 0.050, 0.100],
    "DEFAULT_ENABLE_PCA_ALIGNMENT": True,
    "DEFAULT_ENABLE_GRADIENT_DIVERGENCE": True,
    "DEFAULT_ENABLE_MULTI_OTSU": True,
    "TSI_WEIGHT_DELTA_T": 0.45,
    "TSI_WEIGHT_AREA": 0.35,
    "TSI_WEIGHT_GRADIENT": 0.20,
    "DEFAULT_ENABLE_HYSTERESIS": True,
    "DEFAULT_HYSTERESIS_K_HIGH": 3.2,
    "DEFAULT_HYSTERESIS_K_LOW": 1.8,
    "DEFAULT_ENABLE_BIOHEAT": True,
    "TISSUE_THERMAL_CONDUCTIVITY": 0.37,  # W/(m·K) Pennes Gewebeleitfähigkeit
    "DEFAULT_ENABLE_FRANGI": True,
    "FRANGI_SCALE_RANGE": [1.0, 2.0, 3.0],
    "FRANGI_BETA": 0.5,
    "FRANGI_C": 15.0,
    "DEFAULT_ANATOMY_REGION": "feet", # Standard-Anatomie-Region ("feet", "hands", "knees", "spine", "general")
    "DEFAULT_ENABLE_BILATERAL_MAP": True
}

# ── Klinische & wissenschaftliche Parameter für verschiedene Körperregionen ──
ANATOMICAL_REGIONS: Dict[str, Dict[str, Any]] = {
    "feet": {
        "name": "Füße & Podologie",
        "icon": "🦶",
        "asym_thresh_c": 2.2,
        "citation": "Armstrong et al. (1997) - Goldstandard für diabetische Fußulkus-Früherkennung",
        "zone_1_name": "Vorfuß / Metatarsus",
        "zone_2_name": "Mittelfuß / Gewölbe",
        "zone_3_name": "Ferse / Calcaneus",
        "zone_1_ratio": 0.40,
        "zone_2_ratio": 0.70,
        "show_arch_index": True
    },
    "hands": {
        "name": "Hände & Finger (Raynaud / Rheuma)",
        "icon": "🖐️",
        "asym_thresh_c": 1.2,
        "citation": "Ring & Ammer (2012) / EULAR - Thermografische Kriterien für Raynaud & Arthritis",
        "zone_1_name": "Finger / Phalangen (D1-D5)",
        "zone_2_name": "Mittelhand / Metacarpus",
        "zone_3_name": "Handwurzel / Carpus",
        "zone_1_ratio": 0.45,
        "zone_2_ratio": 0.75,
        "show_arch_index": False
    },
    "knees": {
        "name": "Knie & Gelenke (Arthrose / Meniskus)",
        "icon": "🦵",
        "asym_thresh_c": 1.0,
        "citation": "Selfe et al. (2010) / Collins et al. (1974) - Patellare & periphere Gelenkthermografie",
        "zone_1_name": "Suprapatellare Bursa / Oberschenkel",
        "zone_2_name": "Patella / Gelenkspalt",
        "zone_3_name": "Tuberositas tibiae / Unterschenkel",
        "zone_1_ratio": 0.35,
        "zone_2_ratio": 0.65,
        "show_arch_index": False
    },
    "spine": {
        "name": "Rücken & Wirbelsäule (Myofasziale Dysbalance)",
        "icon": "👤",
        "asym_thresh_c": 0.8,
        "citation": "Feldman & Nickoloff (1984) - Paravertebrale thermografische Asymmetrie",
        "zone_1_name": "HWS / Obere BWS (Trapezius)",
        "zone_2_name": "Mittlere BWS / Rhomboidei",
        "zone_3_name": "LWS / Sakralbereich",
        "zone_1_ratio": 0.33,
        "zone_2_ratio": 0.66,
        "show_arch_index": False
    },
    "general": {
        "name": "Allgemeine Weichteile & Wundbereich",
        "icon": "🩹",
        "asym_thresh_c": 1.5,
        "citation": "IWGDF & Standard Medical Thermography - Allgemeine Weichteil-Hyperthermie",
        "zone_1_name": "Proximaler Bereich",
        "zone_2_name": "Zentraler Wund-/Gewebebereich",
        "zone_3_name": "Distaler Bereich",
        "zone_1_ratio": 0.33,
        "zone_2_ratio": 0.66,
        "show_arch_index": False
    }
}

def load_settings() -> Dict[str, Any]:
    """Lädt Konfigurationseinstellungen aus settings.json mit Fallback zu Defaults."""
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_SETTINGS, f, indent=4)
        return _DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings: Dict[str, Any] = json.load(f)
            # Merge with defaults in case of missing keys
            updated = False
            for k, v in _DEFAULT_SETTINGS.items():
                if k not in settings:
                    settings[k] = v
                    updated = True
            
            # WICHTIG: APP_VERSION muss immer die tatsächliche Code-/Binary-Version widerspiegeln
            if settings.get("APP_VERSION") != APP_VERSION:
                settings["APP_VERSION"] = APP_VERSION
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
DEFAULT_USE_MAD = _settings["DEFAULT_USE_MAD"]
DEFAULT_ENABLE_ASYMMETRY = _settings["DEFAULT_ENABLE_ASYMMETRY"]
ASYMMETRY_THRESHOLD_C = _settings["ASYMMETRY_THRESHOLD_C"]

# ── Celsius-Kalibrierung (Kamerabereich) ──────────────────────────────────────
DEFAULT_TEMP_MIN = _settings["DEFAULT_TEMP_MIN"]
DEFAULT_TEMP_MAX = _settings["DEFAULT_TEMP_MAX"]

OUTPUT_DIR = _settings["OUTPUT_DIR"]

# Audit-Trail-Pfad (persistente klinische Protokolldatei)
AUDIT_TRAIL_PATH = os.path.join(OUTPUT_DIR, "ignite_audit_trail.csv")

# ── Anatomische Filter- & PCA-Zonen-Parameter ──────────────────────────────────
ANATOMICAL_LOWER_CUTOFF_Y = _settings.get("ANATOMICAL_LOWER_CUTOFF_Y", 1.0)
DEFAULT_FOREFOOT_RATIO = _settings.get("DEFAULT_FOREFOOT_RATIO", 0.40)
DEFAULT_MIDFOOT_RATIO = _settings.get("DEFAULT_MIDFOOT_RATIO", 0.70)
MIN_DIST_FROM_BORDER_FACTOR = _settings["MIN_DIST_FROM_BORDER_FACTOR"]
MIN_DIST_FROM_BORDER_ABS = _settings["MIN_DIST_FROM_BORDER_ABS"]
BORDER_MARGIN_PX = _settings["BORDER_MARGIN_PX"]
SKIN_EMISSIVITY = _settings["SKIN_EMISSIVITY"]
REFLECTED_TEMP_C = _settings["REFLECTED_TEMP_C"]

# ── Erweiterte Algorithmus-Konstanten ──────────────────────────────────────────
DEFAULT_MULTISCALE_TOPHAT = _settings.get("DEFAULT_MULTISCALE_TOPHAT", True)
DEFAULT_MULTISCALE_FACTORS = tuple(_settings.get("DEFAULT_MULTISCALE_FACTORS", [0.025, 0.050, 0.100]))
DEFAULT_ENABLE_PCA_ALIGNMENT = _settings.get("DEFAULT_ENABLE_PCA_ALIGNMENT", True)
DEFAULT_ENABLE_GRADIENT_DIVERGENCE = _settings.get("DEFAULT_ENABLE_GRADIENT_DIVERGENCE", True)
TSI_WEIGHT_DELTA_T = _settings.get("TSI_WEIGHT_DELTA_T", 0.45)
TSI_WEIGHT_AREA = _settings.get("TSI_WEIGHT_AREA", 0.35)
TSI_WEIGHT_GRADIENT = _settings.get("TSI_WEIGHT_GRADIENT", 0.20)
DEFAULT_ENABLE_HYSTERESIS = _settings.get("DEFAULT_ENABLE_HYSTERESIS", True)
DEFAULT_HYSTERESIS_K_HIGH = _settings.get("DEFAULT_HYSTERESIS_K_HIGH", 3.2)
DEFAULT_HYSTERESIS_K_LOW = _settings.get("DEFAULT_HYSTERESIS_K_LOW", 1.8)
DEFAULT_ENABLE_BIOHEAT = _settings.get("DEFAULT_ENABLE_BIOHEAT", True)
TISSUE_THERMAL_CONDUCTIVITY = _settings.get("TISSUE_THERMAL_CONDUCTIVITY", 0.37)
DEFAULT_ENABLE_FRANGI = _settings.get("DEFAULT_ENABLE_FRANGI", True)
FRANGI_SCALE_RANGE = tuple(_settings.get("FRANGI_SCALE_RANGE", [1.0, 2.0, 3.0]))
FRANGI_BETA = _settings.get("FRANGI_BETA", 0.5)
FRANGI_C = _settings.get("FRANGI_C", 15.0)
DEFAULT_ENABLE_BILATERAL_MAP = _settings.get("DEFAULT_ENABLE_BILATERAL_MAP", True)
DEFAULT_ANATOMY_REGION = _settings.get("DEFAULT_ANATOMY_REGION", "feet")

# ── UI-Skalierung ──────────────────────────────────────────────────────────────
UI_SCALE = _settings.get("UI_SCALE", 1.0)

# ── Update & Versions-Konfiguration ───────────────────────────────────────────
GITHUB_REPO = _settings.get("GITHUB_REPO", "noackjona-hash/JonaNoackIgnite")
AUTO_CHECK_UPDATES = _settings.get("AUTO_CHECK_UPDATES", True)

SALT = _settings["SALT"]

def init_output_dir() -> None:
    """Erstellt den Ausgabeordner, falls er noch nicht existiert."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


