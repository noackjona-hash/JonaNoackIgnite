import os
import cv2
import numpy as np
from config import OUTPUT_DIR
def save_image_step(image, step_number, step_name, original_path):
    """Speichert ein visuelles Zwischenergebnis als PNG-Bild ab."""
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    filename = f"{base_name}_step{step_number}_{step_name}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    cv2.imwrite(filepath, image)
    return filepath
def save_data_step(data, step_number, step_name, original_path):
    """Speichert die mathematischen Rohdaten als NumPy-Matrix (.npy)."""
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    filename = f"{base_name}_step{step_number}_{step_name}.npy"
    filepath = os.path.join(OUTPUT_DIR, filename)
    np.save(filepath, data)
    return filepath
