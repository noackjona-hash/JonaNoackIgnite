import os
STD_MULTIPLIER = 2.0
OUTPUT_DIR = "ignite_steps_output"
def init_output_dir():
    """Erstellt den Ausgabeordner, falls er noch nicht existiert."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
