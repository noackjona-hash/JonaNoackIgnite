# -*- coding: utf-8 -*-
"""cards.py – Wiederverwendbare Sidebar-Karten-Widgets für IGNITE."""

import os
import customtkinter as ctk

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_PRIMARY_ACCENT,
    COLOR_HOVER_ACCENT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_BG_INPUT,
    COLOR_BORDER_INPUT,
    FONT_FAMILY
)
from gui.utils_ui import make_slider
import config


class AnalysisModeCard(ctk.CTkFrame):
    """Karte zur Auswahl des Analysemodus (Allgemein vs. Podologisch)."""

    def __init__(self, master, on_change_callback, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD, **kwargs)
        
        mode_title = ctk.CTkLabel(self, text="ANALYSEMODUS", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT)
        mode_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.option_menu = ctk.CTkOptionMenu(
            self,
            values=["Klinische Allgemeinanalyse", "Podologische Symmetrieanalyse"],
            command=on_change_callback,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.option_menu.pack(fill=ctk.X, padx=12, pady=(4, 8))


class RoiCard(ctk.CTkFrame):
    """Karte für die interaktive Region of Interest (ROI) Analyse."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD, **kwargs)
        
        roi_title = ctk.CTkLabel(self, text="INTERAKTIVE ROI-ANALYSE", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT)
        roi_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.info_lbl = ctk.CTkLabel(
            self,
            text="Ziehe mit der Maus auf einem Bild ein Rechteck auf, um eine Region of Interest (ROI) live zu analysieren.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=250,
            justify="left"
        )
        self.info_lbl.pack(fill=ctk.X, padx=12, pady=4)

        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")


class SystemSettingsCard(ctk.CTkFrame):
    """Einklappbare Systemeinstellungen-Karte (Kalibrierung, Einheiten, Backend, Design)."""

    def __init__(
        self,
        master,
        toggle_callback,
        on_calibration_changed,
        on_temp_unit_changed,
        on_emissivity_changed,
        on_export_path_changed,
        browse_export_callback,
        on_backend_changed,
        toggle_theme_callback,
        **kwargs
    ):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD, **kwargs)
        
        self.toggle_btn = ctk.CTkButton(
            self,
            text="⚙️ Systemeinstellungen  ▸",
            command=toggle_callback,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_BORDER_CARD,
            height=32,
            anchor="w",
            corner_radius=12
        )
        self.toggle_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.boxes_frame = ctk.CTkFrame(self, fg_color="transparent")

        # Kamera-Kalibrierung
        ctk.CTkLabel(self.boxes_frame, text="KAMERA-KALIBRIERUNG", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT).pack(anchor="w", pady=(8, 2), padx=4)

        calib_row = ctk.CTkFrame(self.boxes_frame, fg_color="transparent")
        calib_row.pack(fill=ctk.X, padx=4, pady=(0, 6))
        calib_row.grid_columnconfigure(0, weight=1)
        calib_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(calib_row, text="T-Min", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(calib_row, text="T-Max", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_SECONDARY).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.t_min_entry = ctk.CTkEntry(calib_row, placeholder_text=str(config.DEFAULT_TEMP_MIN), font=ctk.CTkFont(size=12), fg_color=COLOR_BG_INPUT, border_color=COLOR_BORDER_INPUT, text_color=COLOR_TEXT_PRIMARY, height=28, width=80)
        self.t_min_entry.insert(0, str(config.DEFAULT_TEMP_MIN))
        self.t_min_entry.grid(row=1, column=0, sticky="ew", pady=4)
        self.t_min_entry.bind("<FocusOut>", on_calibration_changed)
        self.t_min_entry.bind("<Return>", on_calibration_changed)

        self.t_max_entry = ctk.CTkEntry(calib_row, placeholder_text=str(config.DEFAULT_TEMP_MAX), font=ctk.CTkFont(size=12), fg_color=COLOR_BG_INPUT, border_color=COLOR_BORDER_INPUT, text_color=COLOR_TEXT_PRIMARY, height=28, width=80)
        self.t_max_entry.insert(0, str(config.DEFAULT_TEMP_MAX))
        self.t_max_entry.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.t_max_entry.bind("<FocusOut>", on_calibration_changed)
        self.t_max_entry.bind("<Return>", on_calibration_changed)

        resolution = (config.DEFAULT_TEMP_MAX - config.DEFAULT_TEMP_MIN) / 255.0
        self.calib_status_lbl = ctk.CTkLabel(
            self.boxes_frame,
            text=f"{config.DEFAULT_TEMP_MIN:.1f}°C – {config.DEFAULT_TEMP_MAX:.1f}°C  |  {resolution:.3f}°C/px",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_MUTED, anchor="w"
        )
        self.calib_status_lbl.pack(fill=ctk.X, padx=4, pady=(0, 8))

        # Temperatureinheit
        ctk.CTkLabel(self.boxes_frame, text="Temperatureinheit", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        self.temp_unit_opt = ctk.CTkOptionMenu(
            self.boxes_frame,
            values=["Celsius (°C)", "Fahrenheit (°F)", "Kelvin (K)"],
            command=on_temp_unit_changed,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.temp_unit_opt.pack(fill=ctk.X, pady=(0, 8))

        # Emissionsgrad
        ctk.CTkLabel(self.boxes_frame, text="Emissionsgrad (ε)", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        self.emissivity_entry = ctk.CTkEntry(
            self.boxes_frame,
            placeholder_text="0.98",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER_INPUT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.emissivity_entry.insert(0, "0.98")
        self.emissivity_entry.pack(fill=ctk.X, pady=(0, 8))
        self.emissivity_entry.bind("<FocusOut>", on_emissivity_changed)
        self.emissivity_entry.bind("<Return>", on_emissivity_changed)

        # Exportordner
        ctk.CTkLabel(self.boxes_frame, text="Export-Verzeichnis", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        export_row = ctk.CTkFrame(self.boxes_frame, fg_color="transparent")
        export_row.pack(fill=ctk.X, pady=(0, 4))
        self.export_path_entry = ctk.CTkEntry(
            export_row,
            placeholder_text="Export-Pfad",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER_INPUT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.export_path_entry.insert(0, config.OUTPUT_DIR)
        self.export_path_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        self.export_path_entry.bind("<FocusOut>", on_export_path_changed)
        self.export_path_entry.bind("<Return>", on_export_path_changed)

        self.export_browse_btn = ctk.CTkButton(
            export_row,
            text="...",
            width=28,
            height=28,
            command=browse_export_callback,
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_BG_CARD
        )
        self.export_browse_btn.pack(side=ctk.RIGHT, padx=(4, 0))

        # Berechnungs-Backend
        ctk.CTkLabel(self.boxes_frame, text="Berechnungs-Backend", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(8, 2))
        self.backend_opt = ctk.CTkOptionMenu(
            self.boxes_frame,
            values=["Automatisch (Schnellstes)", "Erzwinge Rust-CPU-Core", "Erzwinge PyTorch-GPU", "Erzwinge Python-Fallback"],
            command=on_backend_changed,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.backend_opt.pack(fill=ctk.X, pady=(0, 8))

        # Design-Umschalter
        self.theme_btn = ctk.CTkButton(
            self.boxes_frame,
            text="Design wechseln (Dunkel / Hell)",
            command=toggle_theme_callback,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BG_CARD,
            border_width=1,
            border_color=COLOR_PRIMARY_ACCENT,
            height=30,
            corner_radius=6
        )
        self.theme_btn.pack(fill=ctk.X, pady=(8, 4))


class PipelineParametersCard(ctk.CTkFrame):
    """Einklappbare Pipeline-Parameter-Karte für Schieberegler & Schalter."""

    def __init__(self, master, toggle_callback, update_params_callback, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD, **kwargs)

        self.toggle_btn = ctk.CTkButton(
            self,
            text="📊 Parameter einblenden  ▸",
            command=toggle_callback,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BORDER_CARD,
            height=32,
            anchor="w",
            corner_radius=12
        )
        self.toggle_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.sliders_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.sigma_k_slider, self.sigma_k_val = make_slider(self.sliders_frame, "Threshold-Faktor (sigma_k)", 1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1)
        self.tophat_slider, self.tophat_val = make_slider(self.sliders_frame, "Top-Hat Kernel (%)", 0.01, 0.15, config.DEFAULT_TOPHAT_FACTOR, 0.005)
        self.min_area_slider, self.min_area_val = make_slider(self.sliders_frame, "Min. Fläche (%)", 0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001)
        self.min_circ_slider, self.min_circ_val = make_slider(self.sliders_frame, "Min. Circularity", 0.01, 0.50, config.DEFAULT_MIN_CIRCULARITY, 0.005)
        self.otsu_min_slider, self.otsu_min_val = make_slider(self.sliders_frame, "Otsu Min Schwellenwert", 10.0, 100.0, config.DEFAULT_OTSU_MIN, 1.0)
        self.otsu_max_slider, self.otsu_max_val = make_slider(self.sliders_frame, "Otsu Max Schwellenwert", 50.0, 150.0, config.DEFAULT_OTSU_MAX, 1.0)
        self.erosion_slider, self.erosion_val = make_slider(self.sliders_frame, "Erosions-Faktor", 0.01, 0.20, config.DEFAULT_DIST_EROSION_FACTOR, 0.005)
        self.temp_offset_slider, self.temp_offset_val = make_slider(self.sliders_frame, "Temp-Offset (Kalibrierung)", -50.0, 50.0, 0.0, 0.5)

        self.mad_switch = ctk.CTkSwitch(
            self.sliders_frame,
            text="Robustes MAD-Thresholding",
            command=update_params_callback,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        if config.DEFAULT_USE_MAD:
            self.mad_switch.select()
        else:
            self.mad_switch.deselect()
        self.mad_switch.pack(fill=ctk.X, padx=10, pady=(5, 5))

        self.asymmetry_switch = ctk.CTkSwitch(
            self.sliders_frame,
            text="Kontralat. Asymmetrie (>2.2°C)",
            command=update_params_callback,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        if config.DEFAULT_ENABLE_ASYMMETRY:
            self.asymmetry_switch.select()
        else:
            self.asymmetry_switch.deselect()
        self.asymmetry_switch.pack(fill=ctk.X, padx=10, pady=(0, 10))

        # Sliders bindings
        self.sigma_k_slider.configure(command=update_params_callback)
        self.tophat_slider.configure(command=update_params_callback)
        self.min_area_slider.configure(command=update_params_callback)
        self.min_circ_slider.configure(command=update_params_callback)
        self.otsu_min_slider.configure(command=update_params_callback)
        self.otsu_max_slider.configure(command=update_params_callback)
        self.erosion_slider.configure(command=update_params_callback)
        self.temp_offset_slider.configure(command=update_params_callback)


class AnalysisInfoCard(ctk.CTkFrame):
    """Info-Karte zur Anzeige von Dateiname, Backend, Status und Hotspot-Anzahl."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD, **kwargs)

        self.filename_label = ctk.CTkLabel(self, text="Datei: Keine", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.filename_label.pack(fill=ctk.X, padx=15, pady=(10, 4))

        self.backend_label = ctk.CTkLabel(self, text="Backend: Erkennung...", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.backend_label.pack(fill=ctk.X, padx=15, pady=4)

        self.status_label = ctk.CTkLabel(self, text="Status: Bereit", font=ctk.CTkFont(size=12, slant="italic"), text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self.status_label.pack(fill=ctk.X, padx=15, pady=4)

        self.hotspot_label = ctk.CTkLabel(self, text="Hotspots: --", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=4)

        self.pixel_info_label = ctk.CTkLabel(self, text="Pixel-Info: --", font=ctk.CTkFont(size=11, slant="italic"), text_color=COLOR_TEXT_SECONDARY, anchor="w", justify="left")
        self.pixel_info_label.pack(fill=ctk.X, padx=15, pady=(4, 10))
