# -*- coding: utf-8 -*-
"""gui/views/podology_view.py – Podology & 3-Zone Diabetic Foot Thermography for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np
from PIL import Image

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    COLOR_CONTAINER_BLUE,
    COLOR_CONTAINER_GREEN,
    COLOR_CONTAINER_RED,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card, make_display_ctk_image
from utils import pixel_to_celsius


class PodologyView(ctk.CTkFrame):
    """Spezialisierte podologische Analyse im Google Material 3 Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.current_result: Optional[dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ── Linke Spalte: Annotiertes Symmetrie-Bild ─────────────────────────
        self.img_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.img_card.grid(row=0, column=0, padx=(18, 10), pady=18, sticky="nsew")

        # Header
        top_bar = ctk.CTkFrame(self.img_card, fg_color="transparent", height=50)
        top_bar.pack(fill=ctk.X, padx=18, pady=(14, 8))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text="PODOLOGISCHES SYMMETRIE-BILD",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            top_bar,
            text="3-Zonen Bounding Boxes & Symmetrieachse",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        ctk.CTkFrame(self.img_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        self.img_lbl = ctk.CTkLabel(
            self.img_card,
            text="Keine Messdaten vorhanden",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.img_lbl.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        # ── Rechte Spalte: Asymmetrie-Banner & 3-Zonen Tabelle ───────────────
        self.side_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.side_card.grid(row=0, column=1, padx=(10, 18), pady=18, sticky="nsew")

        scroll = ctk.CTkScrollableFrame(self.side_card, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        # 1. Klinischer Goldstandard Banner (Armstrong 1997)
        ctk.CTkLabel(
            scroll,
            text="KLINISCHER SYMMETRIESTATUS",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.asym_banner = make_material_card(scroll, corner_radius=14, fg_color=COLOR_CONTAINER_GREEN)
        self.asym_banner.pack(fill=ctk.X, pady=(0, 18))

        b_inner = ctk.CTkFrame(self.asym_banner, fg_color="transparent")
        b_inner.pack(fill=ctk.X, padx=16, pady=14)

        self.asym_status_lbl = ctk.CTkLabel(
            b_inner,
            text="Physiologisch Symmetrisch",
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            text_color=COLOR_SUCCESS,
            anchor="w"
        )
        self.asym_status_lbl.pack(fill=ctk.X)

        self.asym_delta_lbl = ctk.CTkLabel(
            b_inner,
            text="Seiten-Differenz ΔT = 0.0 °C  (Grenzwert: 2.2 °C)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.asym_delta_lbl.pack(fill=ctk.X, pady=(4, 0))

        # 2. 3-Zonen Tabelle
        ctk.CTkLabel(
            scroll,
            text="3-ZONEN TEMPERATUR-VERGLEICH",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.zones_box = ctk.CTkFrame(scroll, fg_color="transparent")
        self.zones_box.pack(fill=ctk.X)

        self.zone_rows = {}
        zones = [
            ("fore", "Vorfuß (Ballen / Zehen)", "z. B. Druckstellen, Ulzera"),
            ("mid",  "Mittelfuß (Längsgewölbe)", "z. B. Charcot-Fuß Frühstadium"),
            ("heel", "Ferse (Rückfuß)", "z. B. Fersensporn, Entlastung")
        ]

        for z_key, title, hint in zones:
            z_card = make_material_card(self.zones_box, corner_radius=12, fg_color=COLOR_BG_CARD_VARIANT)
            z_card.pack(fill=ctk.X, pady=4)

            z_inner = ctk.CTkFrame(z_card, fg_color="transparent")
            z_inner.pack(fill=ctk.X, padx=14, pady=12)

            ctk.CTkLabel(
                z_inner,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            ).pack(fill=ctk.X)

            ctk.CTkLabel(
                z_inner,
                text=hint,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill=ctk.X, pady=(1, 6))

            # Grid mit Werten L vs R vs Delta
            val_grid = ctk.CTkFrame(z_inner, fg_color="transparent")
            val_grid.pack(fill=ctk.X)
            val_grid.grid_columnconfigure(0, weight=1)
            val_grid.grid_columnconfigure(1, weight=1)
            val_grid.grid_columnconfigure(2, weight=1)

            lbl_l = ctk.CTkLabel(val_grid, text="L: --.- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), text_color=COLOR_TEXT_SECONDARY, anchor="w")
            lbl_l.grid(row=0, column=0, sticky="w")

            lbl_r = ctk.CTkLabel(val_grid, text="R: --.- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), text_color=COLOR_TEXT_SECONDARY, anchor="w")
            lbl_r.grid(row=0, column=1, sticky="w")

            lbl_d = ctk.CTkLabel(val_grid, text="Δ --.- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_SUCCESS, anchor="e")
            lbl_d.grid(row=0, column=2, sticky="e")

            self.zone_rows[z_key] = (lbl_l, lbl_r, lbl_d)

        # 3. Klinischer Literatur-Hinweis
        lit_card = make_material_card(scroll, corner_radius=12, fg_color=COLOR_BG_CARD_VARIANT)
        lit_card.pack(fill=ctk.X, pady=(18, 0))
        l_inner = ctk.CTkFrame(lit_card, fg_color="transparent")
        l_inner.pack(fill=ctk.X, padx=14, pady=12)

        ctk.CTkLabel(
            l_inner,
            text="📚 Literatur-Referenz",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)

        ctk.CTkLabel(
            l_inner,
            text="Armstrong et al. (1997): Infrared Dermal Thermometry for the High-Risk Diabetic Foot. Phys. Ther. 77(2):169–175.\nDelta-T > 2.2 °C signalisiert signifikanten Entzündungsverdacht.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=230,
            justify="left"
        ).pack(fill=ctk.X, pady=(4, 0))

    def show_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)

        # 1. Asymmetrie-Banner aktualisieren
        asym = result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)
        is_asym = asym.get("is_asymmetric", False)

        if is_asym:
            self.asym_banner.configure(fg_color=COLOR_CONTAINER_RED)
            self.asym_status_lbl.configure(text="⚠️ Pathologische Asymmetrie", text_color=COLOR_DANGER)
            self.asym_delta_lbl.configure(text=f"Seiten-Differenz ΔT = {delta_t:.1f} °C (> 2.2 °C Goldstandard!)")
        else:
            self.asym_banner.configure(fg_color=COLOR_CONTAINER_GREEN)
            self.asym_status_lbl.configure(text="✓ Physiologisch Symmetrisch", text_color=COLOR_SUCCESS)
            self.asym_delta_lbl.configure(text=f"Seiten-Differenz ΔT = {delta_t:.1f} °C (Normbereich <= 2.2 °C)")

        # 2. 3-Zonen-Tabelle
        zonal = result.get("zonal_stats", {})
        if zonal.get("left", {}).get("exists") and zonal.get("right", {}).get("exists"):
            for z_key in ["fore", "mid", "heel"]:
                l_c = pixel_to_celsius(zonal["left"][z_key], t_min, t_max)
                r_c = pixel_to_celsius(zonal["right"][z_key], t_min, t_max)
                d_c = abs(l_c - r_c)

                lbl_l, lbl_r, lbl_d = self.zone_rows[z_key]
                lbl_l.configure(text=f"L: {l_c:.1f} °C")
                lbl_r.configure(text=f"R: {r_c:.1f} °C")

                d_color = COLOR_DANGER if d_c > 2.2 else COLOR_SUCCESS
                lbl_d.configure(text=f"Δ {d_c:.1f} °C", text_color=d_color)

        # 3. Bild rendern
        self.redraw()

    def redraw(self) -> None:
        if not self.current_result:
            return

        raw_overlay = self.current_result["overlay_rgb"]
        pil_img = Image.fromarray(raw_overlay)

        self.img_lbl.update_idletasks()
        w = max(self.img_lbl.winfo_width() - 20, 300)
        h = max(self.img_lbl.winfo_height() - 20, 200)

        ctk_img = make_display_ctk_image(pil_img, w, h)
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img
