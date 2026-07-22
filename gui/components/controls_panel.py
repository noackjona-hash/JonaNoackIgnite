"""controls_panel.py – Wiederverwendbare Steuerungselemente und Slider-Panels."""

import customtkinter as ctk
from gui.theme import COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED
from gui.utils_ui import make_slider

class ParameterControlsPanel:
    """Helper zum Erstellen von Schiebereglern für die Pipeline-Parameter."""

    @staticmethod
    def create_pipeline_controls(parent, on_change_callback):
        """Erzeugt ein Panel mit Reglern für k, TopHat, Area, Circularity etc."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")

        # Sigma k Regler
        k_slider = make_slider(
            frame,
            label="Threshold Multiplikator (k):",
            from_=1.0,
            to=5.0,
            number_of_steps=40,
            command=lambda val: on_change_callback("sigma_k", val)
        )
        k_slider.pack(fill="x", pady=4)

        # TopHat Regler
        tophat_slider = make_slider(
            frame,
            label="Top-Hat Kernel-Faktor:",
            from_=0.01,
            to=0.20,
            number_of_steps=38,
            command=lambda val: on_change_callback("tophat_factor", val)
        )
        tophat_slider.pack(fill="x", pady=4)

        return frame
