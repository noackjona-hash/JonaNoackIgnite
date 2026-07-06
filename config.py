import os

# Standardwerte für die adaptive Thermobild-Pipeline
DEFAULT_SIGMA_K = 3.0
DEFAULT_TOPHAT_FACTOR = 0.05
DEFAULT_MIN_AREA_FACTOR = 0.0005
DEFAULT_MIN_CIRCULARITY = 0.01
DEFAULT_OTSU_MIN = 35
DEFAULT_OTSU_MAX = 50
DEFAULT_DIST_EROSION_FACTOR = 0.05

# ── Celsius-Kalibrierung (Kamerabereich) ──────────────────────────────────────
# Thermischer Messbereich der Kamera in °C.
# T(x) = T_MIN + x * (T_MAX - T_MIN) / 255  [x = 8-Bit-Pixelwert]
DEFAULT_TEMP_MIN = 20.0   # Untere Grenze des Kamera-Messbereichs in °C
DEFAULT_TEMP_MAX = 40.0   # Obere Grenze des Kamera-Messbereichs in °C

OUTPUT_DIR = "ignite_steps_output"

# Audit-Trail-Pfad (persistente klinische Protokolldatei)
AUDIT_TRAIL_PATH = os.path.join(OUTPUT_DIR, "ignite_audit_trail.csv")

def init_output_dir():
    """Erstellt den Ausgabeordner, falls er noch nicht existiert."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
