import os

# Standardwerte für die adaptive Thermobild-Pipeline
DEFAULT_SIGMA_K = 3.0
DEFAULT_TOPHAT_FACTOR = 0.05
DEFAULT_MIN_AREA_FACTOR = 0.0005
DEFAULT_MIN_CIRCULARITY = 0.01
DEFAULT_OTSU_MIN = 35
DEFAULT_OTSU_MAX = 50
DEFAULT_DIST_EROSION_FACTOR = 0.05

OUTPUT_DIR = "ignite_steps_output"

def init_output_dir():
    """Erstellt den Ausgabeordner, falls er noch nicht existiert."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
