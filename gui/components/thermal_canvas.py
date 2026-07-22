"""thermal_canvas.py – Widget zur Anzeige und Visualisierung von Thermografien."""

import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np

class ThermalCanvasWidget(ctk.CTkFrame):
    """Widget zur hochperformanten Anzeige von Graustufen- und Falschfarben-Wärmebildern."""

    def __init__(self, master, title: str = "Wärmebild", **kwargs):
        super().__init__(master, **kwargs)

        self.title_label = ctk.CTkLabel(self, text=title, font=("Segoe UI", 12, "bold"))
        self.title_label.pack(anchor="w", padx=8, pady=(4, 2))

        self.image_label = ctk.CTkLabel(self, text="Kein Bild geladen")
        self.image_label.pack(expand=True, fill="both", padx=4, pady=4)
        self._current_photo = None

    def display_numpy_image(self, img_array: np.ndarray, width: int = 400, height: int = 300):
        """Konvertiert eine NumPy-Matrix in ein PIL Image und zeigt es im Label an."""
        if img_array is None:
            return

        if len(img_array.shape) == 2:
            pil_img = Image.fromarray(img_array).convert("RGB")
        else:
            pil_img = Image.fromarray(img_array)

        resized = pil_img.resize((width, height), Image.Resampling.LANCZOS)
        self._current_photo = ctk.CTkImage(light_image=resized, dark_image=resized, size=(width, height))
        self.image_label.configure(image=self._current_photo, text="")
