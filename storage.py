import os
import cv2
import numpy as np
from config import OUTPUT_DIR


def save_image_step(image: np.ndarray, step_number: int, step_name: str, original_path: str) -> str:
    """Speichert ein visuelles Zwischenergebnis als PNG-Bild ab.

    Args:
        image: NumPy-Array (Graustufen oder BGR).
        step_number: Schritt-Nummer für den Dateinamen.
        step_name: Kurzbeschreibung des Schritts.
        original_path: Pfad des Originalbildes (wird als Basis für den Dateinamen genutzt).

    Returns:
        Absoluter Pfad der gespeicherten Datei.

    Raises:
        IOError: Wenn das Bild nicht gespeichert werden konnte (z.B. kein Speicherplatz).
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    filename = f"{base_name}_step{step_number}_{step_name}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    success = cv2.imwrite(filepath, image)
    if not success:
        raise IOError(
            f"cv2.imwrite konnte '{filepath}' nicht schreiben. "
            "Prüfe Schreibrechte und verfügbaren Speicherplatz."
        )
    return filepath


def save_data_step(data: np.ndarray, step_number: int, step_name: str, original_path: str) -> str:
    """Speichert die mathematischen Rohdaten als NumPy-Matrix (.npy).

    Args:
        data: NumPy-Array mit den Rohdaten.
        step_number: Schritt-Nummer für den Dateinamen.
        step_name: Kurzbeschreibung des Schritts.
        original_path: Pfad des Originalbildes.

    Returns:
        Absoluter Pfad der gespeicherten Datei.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(original_path))[0]
    filename = f"{base_name}_step{step_number}_{step_name}.npy"
    filepath = os.path.join(OUTPUT_DIR, filename)
    np.save(filepath, data)
    return filepath
