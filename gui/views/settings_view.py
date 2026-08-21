# -*- coding: utf-8 -*-
"""gui/views/settings_view.py – Settings & Algorithm Tuning for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk

import config
import image_processing
from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card, make_slider_setting


class SettingsView(ctk.CTkFrame):
    """Einstellungs- und Parameter-Steuerung im Google Material 3 Design."""

    PRESETS = {
        "Standard (Jugend forscht)": {
            "sigma_k": 3.0, "tophat_factor": 0.05, "min_area_factor": 0.0005,
            "min_circularity": 0.08, "otsu_min": 35, "otsu_max": 50, "dist_erosion_factor": 0.05,
            "use_mad": False, "enable_asymmetry": True
        },
        "Hochempfindlich (Früherkennung)": {
            "sigma_k": 2.2, "tophat_factor": 0.04, "min_area_factor": 0.0002,
            "min_circularity": 0.04, "otsu_min": 30, "otsu_max": 45, "dist_erosion_factor": 0.03,
            "use_mad": False, "enable_asymmetry": True
        },
        "Podologie / Diabetischer Fuß": {
            "sigma_k": 3.0, "tophat_factor": 0.06, "min_area_factor": 0.0008,
            "min_circularity": 0.10, "otsu_min": 35, "otsu_max": 55, "dist_erosion_factor": 0.05,
            "use_mad": True, "enable_asymmetry": True
        },
        "Robust / Rauschunterdrückung": {
            "sigma_k": 3.5, "tophat_factor": 0.05, "min_area_factor": 0.0010,
            "min_circularity": 0.12, "otsu_min": 40, "otsu_max": 60, "dist_erosion_factor": 0.08,
            "use_mad": True, "enable_asymmetry": True
        }
    }

    def __init__(
        self,
        master,
        on_param_changed: Callable[[], None],
        on_backend_changed: Callable[[str], None],
        on_notify: Callable[[str, str], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_param_changed = on_param_changed
        self.on_backend_changed = on_backend_changed
        self.on_notify = on_notify

        self.sliders: dict[str, tuple[ctk.CTkSlider, ctk.CTkLabel]] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll_left = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")

        scroll_right = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_right.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        # ── 1. Linke Spalte: Pipeline-Parameter & Presets ─────────────────────
        param_card = make_material_card(scroll_left, corner_radius=16, fg_color=COLOR_BG_CARD)
        param_card.pack(fill=ctk.X, pady=(0, 16))

        p_inner = ctk.CTkFrame(param_card, fg_color="transparent")
        p_inner.pack(fill=ctk.X, padx=20, pady=16)

        ctk.CTkLabel(
            p_inner,
            text="PIPELINE-PARAMETER & ALGORITHMUS",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)

        # Preset Auswahl Dropdown
        ctk.CTkLabel(p_inner, text="Diagnostisches Preset:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(10, 2))
        self.preset_menu = ctk.CTkOptionMenu(
            p_inner,
            values=list(self.PRESETS.keys()),
            command=self._apply_preset,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_CONTAINER_BLUE,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_PRIMARY,
            corner_radius=8,
            height=32
        )
        self.preset_menu.pack(fill=ctk.X, pady=(0, 12))

        ctk.CTkFrame(p_inner, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X, pady=(0, 8))

        # Sliders
        s_k, l_k = make_slider_setting(
            p_inner, "Threshold Multiplikator (k)",
            "Hotspot-Grenze T_rel = µ + k·σ (k=3 entspricht 99.86% Konfidenz)",
            1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1, "",
            command=lambda v: self._on_slider_move()
        )
        self.sliders["sigma_k"] = (s_k, l_k)

        s_th, l_th = make_slider_setting(
            p_inner, "Top-Hat Kernel (%)",
            "Größe der morphologischen Öffnung relativ zu min(B, H)",
            0.01, 0.15, config.DEFAULT_TOPHAT_FACTOR, 0.005, "",
            command=lambda v: self._on_slider_move(),
            is_percent=True
        )
        self.sliders["tophat_factor"] = (s_th, l_th)

        s_ma, l_ma = make_slider_setting(
            p_inner, "Min. Hotspot-Fläche (%)",
            "Unterdrückt isolierte thermische Rauschpixel unterhalb dieser Fläche",
            0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001, "",
            command=lambda v: self._on_slider_move(),
            is_percent=True
        )
        self.sliders["min_area_factor"] = (s_ma, l_ma)

        s_mc, l_mc = make_slider_setting(
            p_inner, "Min. Circularity (Formfaktor)",
            "Filtert längliche Randartefakte und Reflexionen",
            0.01, 0.50, config.DEFAULT_MIN_CIRCULARITY, 0.01, "",
            command=lambda v: self._on_slider_move()
        )
        self.sliders["min_circularity"] = (s_mc, l_mc)

        s_er, l_er = make_slider_setting(
            p_inner, "Distanz-Erosionsfaktor",
            "Entfernt Artefakte am Übergang zwischen Haut und Hintergrund",
            0.01, 0.20, config.DEFAULT_DIST_EROSION_FACTOR, 0.005, "",
            command=lambda v: self._on_slider_move(),
            is_percent=True
        )
        self.sliders["dist_erosion_factor"] = (s_er, l_er)

        s_to, l_to = make_slider_setting(
            p_inner, "Temperatur-Kalibrierungs-Offset",
            "Manuelle Nullpunktverschiebung bei Sensordrift",
            -20.0, 20.0, 0.0, 0.5, "°C",
            command=lambda v: self._on_slider_move()
        )
        self.sliders["temp_offset"] = (s_to, l_to)

        # Switches
        self.mad_switch = ctk.CTkSwitch(
            p_inner,
            text="Robustes MAD-Thresholding (Median Absolute Deviation)",
            command=self._on_slider_move,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        if config.DEFAULT_USE_MAD:
            self.mad_switch.select()
        self.mad_switch.pack(fill=ctk.X, pady=(8, 4))

        self.asym_switch = ctk.CTkSwitch(
            p_inner,
            text="Kontralaterale Asymmetrieprüfung aktivieren (> 2.2 °C)",
            command=self._on_slider_move,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        if config.DEFAULT_ENABLE_ASYMMETRY:
            self.asym_switch.select()
        self.asym_switch.pack(fill=ctk.X, pady=(4, 8))

        # ── 2. Rechte Spalte: Hardware, Backend & Radiometrie ────────────────
        hw_card = make_material_card(scroll_right, corner_radius=16, fg_color=COLOR_BG_CARD)
        hw_card.pack(fill=ctk.X, pady=(0, 16))

        h_inner = ctk.CTkFrame(hw_card, fg_color="transparent")
        h_inner.pack(fill=ctk.X, padx=20, pady=16)

        ctk.CTkLabel(
            h_inner,
            text="BERECHNUNGS-BACKEND & BESCHLEUNIGUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)

        ctk.CTkLabel(h_inner, text="Ausführungs-Engine:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(10, 2))
        self.backend_menu = ctk.CTkOptionMenu(
            h_inner,
            values=["Automatisch (Schnellstes)", "Erzwinge Rust-CPU-Core", "Erzwinge PyTorch-GPU", "Erzwinge Python-Fallback"],
            command=self._on_backend_select,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=8,
            height=32
        )
        self.backend_menu.pack(fill=ctk.X, pady=(0, 12))

        # Radiometrie Card
        radio_card = make_material_card(scroll_right, corner_radius=16, fg_color=COLOR_BG_CARD)
        radio_card.pack(fill=ctk.X, pady=(0, 16))

        r_inner = ctk.CTkFrame(radio_card, fg_color="transparent")
        r_inner.pack(fill=ctk.X, padx=20, pady=16)

        ctk.CTkLabel(
            r_inner,
            text="RADIOMETRISCHE EMISSIVITÄTS-KORREKTUR",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)

        ctk.CTkLabel(
            r_inner,
            text="Stefan-Boltzmann Strahlungsbilanz für menschliche Haut (Jones 1998 / Steketee 1973).",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=360,
            justify="left"
        ).pack(fill=ctk.X, pady=(4, 10))

        # Emissivität
        ctk.CTkLabel(r_inner, text="Haut-Emissivitätsgrad (ε):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.emissivity_entry = ctk.CTkEntry(r_inner, placeholder_text="0.98", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.emissivity_entry.insert(0, str(config.SKIN_EMISSIVITY))
        self.emissivity_entry.pack(fill=ctk.X, pady=(2, 10))

        # Reflektierte Temperatur
        ctk.CTkLabel(r_inner, text="Reflektierte Umgebungstemperatur (°C):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.refl_temp_entry = ctk.CTkEntry(r_inner, placeholder_text="20.0", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.refl_temp_entry.insert(0, str(config.REFLECTED_TEMP_C))
        self.refl_temp_entry.pack(fill=ctk.X, pady=(2, 10))

        # Reset Button
        ctk.CTkButton(
            scroll_right,
            text="↺  Standardwerte wiederherstellen",
            command=self._reset_defaults,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_CONTAINER_BLUE,
            hover_color=COLOR_OUTLINE,
            text_color=COLOR_PRIMARY,
            corner_radius=10,
            height=36
        ).pack(fill=ctk.X, pady=(8, 0))

    def _apply_preset(self, choice: str) -> None:
        p = self.PRESETS.get(choice)
        if not p:
            return

        self.sliders["sigma_k"][0].set(p["sigma_k"])
        self.sliders["tophat_factor"][0].set(p["tophat_factor"])
        self.sliders["min_area_factor"][0].set(p["min_area_factor"])
        self.sliders["min_circularity"][0].set(p["min_circularity"])
        self.sliders["dist_erosion_factor"][0].set(p["dist_erosion_factor"])

        if p.get("use_mad", False):
            self.mad_switch.select()
        else:
            self.mad_switch.deselect()

        # Labels aktualisieren
        for k, (slider, label) in self.sliders.items():
            val = slider.get()
            if k in ("tophat_factor", "min_area_factor", "dist_erosion_factor"):
                label.configure(text=f"{val*100:.1f} %")
            else:
                label.configure(text=f"{val:.2f}".rstrip('0').rstrip('.'))

        self.on_notify(f"Preset '{choice}' angewendet.", "info")
        self.on_param_changed()

    def _reset_defaults(self) -> None:
        self._apply_preset("Standard (Jugend forscht)")

    def _on_slider_move(self) -> None:
        self.on_param_changed()

    def _on_backend_select(self, choice: str) -> None:
        mapping = {
            "Automatisch (Schnellstes)": "auto",
            "Erzwinge Rust-CPU-Core": "rust",
            "Erzwinge PyTorch-GPU": "gpu",
            "Erzwinge Python-Fallback": "python"
        }
        val = mapping.get(choice, "auto")
        image_processing.FORCED_BACKEND = val
        self.on_backend_changed(val)
        self.on_notify(f"Backend umgestellt auf: {choice}", "info")

    def get_params(self) -> dict[str, Any]:
        """Liest alle Parameter strukturiert aus."""
        try:
            em = float(self.emissivity_entry.get().replace(",", "."))
        except Exception:
            em = config.SKIN_EMISSIVITY

        return {
            "sigma_k": float(self.sliders["sigma_k"][0].get()),
            "tophat_factor": float(self.sliders["tophat_factor"][0].get()),
            "min_area_factor": float(self.sliders["min_area_factor"][0].get()),
            "min_circularity": float(self.sliders["min_circularity"][0].get()),
            "dist_erosion_factor": float(self.sliders["dist_erosion_factor"][0].get()),
            "temp_offset": float(self.sliders["temp_offset"][0].get()),
            "use_mad": self.mad_switch.get() == 1,
            "enable_asymmetry": self.asym_switch.get() == 1,
            "emissivity": em,
            "otsu_min": config.DEFAULT_OTSU_MIN,
            "otsu_max": config.DEFAULT_OTSU_MAX
        }
