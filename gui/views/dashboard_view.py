# -*- coding: utf-8 -*-
"""gui/views/dashboard_view.py – High-Contrast Clinical 4-Panel Dashboard for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np
from PIL import Image

from gui.theme import (
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_BG_CARD_HOVER,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_ACTIVE,
    COLOR_CONTAINER_BLUE,
    COLOR_CONTAINER_GREEN,
    COLOR_CONTAINER_RED,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card, make_display_ctk_image, apply_colormap_to_image
from utils import pixel_to_celsius


class DashboardView(ctk.CTkFrame):
    """4-Stufen Haupt-Dashboard im High-Contrast Clinical Design."""

    PANEL_DEFS = [
        ("1. Originalbild",             "1. Original-Wärmebild",          "Rohdaten & Kalibrierung"),
        ("2. Hintergrund-Maske",        "2. Gewebe-Segmentierung",        "Hintergrund- & Artefaktfilter"),
        ("3. Lokale Hitze-Differenz",   "3. Morphologische Differenz",    "Strukturelle Hitzekontraste"),
        ("4. Erkannte Hotspots (Rust)", "4. Diagnose & Hotspots",         "Entzündungsherde & Bounding Boxes"),
    ]

    def __init__(
        self,
        master,
        on_load_click: Callable[[], None],
        on_inspect_panel: Callable[[str], None],
        on_palette_change: Callable[[str], None],
        on_mode_change: Callable[[str], None],
        on_load_demo: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_load_click = on_load_click
        self.on_inspect_panel = on_inspect_panel
        self.on_palette_change = on_palette_change
        self.on_mode_change = on_mode_change
        self.on_load_demo = on_load_demo

        self.current_result: Optional[dict[str, Any]] = None
        self._panel_labels: dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # ── 1. KPI Metriken-Leiste oben ──────────────────────────────────────
        self.kpi_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_bar.pack(fill=ctk.X, padx=14, pady=(12, 6))

        self.kpi_cards = {}
        kpi_configs = [
            ("temp_mean", "MITTLERE TEMPERATUR", "--.- °C", "Gewebe-Mittelwert"),
            ("temp_max",  "MAXIMAL-TEMPERATUR",  "--.- °C", "Heißester Messpunkt"),
            ("symmetry",  "SEITEN-ASYMMETRIE",    "Δ --.- °C", "Armstrong Grenzwert: 2.2 °C"),
            ("tsi",       "THERMAL SEVERITY INDEX", "-- / 10", "IWGDF Risikostufe"),
        ]

        for col in range(4):
            self.kpi_bar.grid_columnconfigure(col, weight=1)

        for col, (kpi_id, title, default_val, sub) in enumerate(kpi_configs):
            card = make_material_card(self.kpi_bar, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
            card.grid(row=0, column=col, padx=4, sticky="nsew")

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill=ctk.BOTH, expand=True, padx=14, pady=12)

            ctk.CTkLabel(
                content,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill=ctk.X)

            lbl_val = ctk.CTkLabel(
                content,
                text=default_val,
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=22, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, pady=(2, 0))

            lbl_sub = ctk.CTkLabel(
                content,
                text=sub,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w"
            )
            lbl_sub.pack(fill=ctk.X, pady=(1, 0))

            self.kpi_cards[kpi_id] = (lbl_val, lbl_sub)

        # ── 2. Filter & Steuerungsleiste über dem Grid ────────────────────────
        ctrl_bar = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_bar.pack(fill=ctk.X, padx=18, pady=(4, 8))

        ctk.CTkLabel(
            ctrl_bar,
            text="PIPELINE-STUFEN",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.LEFT)

        # Colormap Dropdown rechts
        self.palette_menu = ctk.CTkOptionMenu(
            ctrl_bar,
            values=["Turbo", "Graustufen", "Inferno", "Heiß (Hot)"],
            command=self._on_palette_select,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=140
        )
        self.palette_menu.pack(side=ctk.RIGHT, padx=(8, 0))

        ctk.CTkLabel(
            ctrl_bar,
            text="Palette:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        # Modus Dropdown
        self.mode_menu = ctk.CTkOptionMenu(
            ctrl_bar,
            values=["Klinische Allgemeinanalyse", "Podologische Symmetrieanalyse"],
            command=self.on_mode_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=220
        )
        self.mode_menu.pack(side=ctk.RIGHT, padx=(8, 16))

        ctk.CTkLabel(
            ctrl_bar,
            text="Modus:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        # ── 3. Haupt-Container für Grid vs. Empty State ──────────────────────
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill=ctk.BOTH, expand=True, padx=14, pady=(0, 14))

        # 4-Panel Grid
        self.grid_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.grid_frame.grid_columnconfigure(0, weight=1)
        self.grid_frame.grid_columnconfigure(1, weight=1)
        self.grid_frame.grid_rowconfigure(0, weight=1)
        self.grid_frame.grid_rowconfigure(1, weight=1)

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for (key, title, subtitle), (r, c) in zip(self.PANEL_DEFS, positions):
            card = make_material_card(self.grid_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
            card.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

            header = ctk.CTkFrame(card, fg_color="transparent", height=38)
            header.pack(fill=ctk.X, padx=12, pady=(8, 4))
            header.pack_propagate(False)

            title_box = ctk.CTkFrame(header, fg_color="transparent")
            title_box.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            ctk.CTkLabel(
                title_box,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            ).pack(fill=ctk.X)

            _k = key
            inspect_btn = ctk.CTkButton(
                header,
                text="Details",
                command=lambda k=_k: self.on_inspect_panel(k),
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=COLOR_BG_CARD_VARIANT,
                hover_color=COLOR_BG_CARD_HOVER,
                text_color=COLOR_TEXT_PRIMARY,
                border_width=1,
                border_color=COLOR_OUTLINE,
                corner_radius=RADIUS_BUTTON,
                height=26,
                width=64
            )
            inspect_btn.pack(side=ctk.RIGHT)

            ctk.CTkFrame(card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X, padx=0, pady=(4, 0))

            img_lbl = ctk.CTkLabel(
                card,
                text="Kein Bild geladen",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_MUTED
            )
            img_lbl.pack(fill=ctk.BOTH, expand=True, padx=8, pady=8)
            self._panel_labels[key] = img_lbl

        # Empty / Welcome State
        self.welcome_card = make_material_card(
            self.content_area,
            corner_radius=RADIUS_CARD,
            fg_color=COLOR_BG_CARD
        )
        self._build_welcome_state()

        self.show_empty_state()

    def _on_palette_select(self, val: str) -> None:
        if self.on_palette_change:
            self.on_palette_change(val)

    def _build_welcome_state(self) -> None:
        """Erstellt eine aufgeräumte, professionelle Workstation-Startansicht."""
        center_box = ctk.CTkFrame(self.welcome_card, fg_color="transparent")
        center_box.pack(expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            center_box,
            text="Wärmebild zur Analyse laden",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            center_box,
            text="Unterstützte Formate: Radiometrische und 8-Bit Infrarotaufnahmen (.jpg, .png, .tiff, .flir).\nAutomatische Entzündungsdetektion, Top-Hat-Filterung und Symmetrievergleich.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED,
            justify="center",
            wraplength=520
        ).pack(pady=(0, 24))

        ctk.CTkButton(
            center_box,
            text="+ Wärmebild auswählen…",
            command=self.on_load_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=40,
            width=200
        ).pack(pady=(0, 24))

        # Beispieldatensätze
        demo_box = ctk.CTkFrame(center_box, fg_color="transparent")
        demo_box.pack()

        ctk.CTkLabel(
            demo_box,
            text="Oder Beispieldatensatz laden:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(pady=(0, 8))

        demos = [
            ("Diabetischer Fuß", "test-data/bild (4).jpeg"),
            ("Entzündungsherd",  "test-data/bild (1).jpeg"),
            ("Normalbefund",     "test-data/bild (15).jpeg")
        ]

        demo_btns_row = ctk.CTkFrame(demo_box, fg_color="transparent")
        demo_btns_row.pack()

        for d_title, d_path in demos:
            if hasattr(self, "on_load_demo") and self.on_load_demo:
                _p = d_path
                ctk.CTkButton(
                    demo_btns_row,
                    text=d_title,
                    command=lambda p=_p: self.on_load_demo(p),
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    fg_color=COLOR_BG_CARD_VARIANT,
                    hover_color=COLOR_BG_CARD_HOVER,
                    text_color=COLOR_TEXT_PRIMARY,
                    border_width=1,
                    border_color=COLOR_OUTLINE,
                    corner_radius=RADIUS_BUTTON,
                    height=30,
                    width=130
                ).pack(side=ctk.LEFT, padx=4)

    def show_empty_state(self) -> None:
        self.grid_frame.pack_forget()
        self.welcome_card.pack(fill=ctk.BOTH, expand=True, padx=4, pady=4)

    def show_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        self.welcome_card.pack_forget()
        self.grid_frame.pack(fill=ctk.BOTH, expand=True)

        # KPIs aktualisieren
        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)
        mean_c = pixel_to_celsius(result.get("mean_pixel", 0.0), t_min, t_max)
        max_c = pixel_to_celsius(result.get("max_pixel", 0.0), t_min, t_max)
        hotspots = result.get("hotspot_pixel_count", 0)
        ratio = result.get("hotspot_ratio", 0.0)
        asym = result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)
        is_asym = asym.get("is_asymmetric", False)

        self.kpi_cards["temp_mean"][0].configure(text=f"{mean_c:.1f} °C")
        self.kpi_cards["temp_max"][0].configure(text=f"{max_c:.1f} °C")

        sym_txt = f"Δ {delta_t:.1f} °C"
        sym_color = COLOR_DANGER if is_asym else COLOR_SUCCESS
        self.kpi_cards["symmetry"][0].configure(text=sym_txt, text_color=sym_color)
        self.kpi_cards["symmetry"][1].configure(text=f"{hotspots:,} Hotspot-Pixel ({ratio:.1f}%)" if hotspots > 0 else "Symmetrischer Normalbefund")

        tsi = result.get("tsi_results", {})
        tsi_score = tsi.get("score", 0.0)
        tsi_tier_name = tsi.get("tier_name", "Stufe 0: Normalbefund")
        tsi_color = tsi.get("color", COLOR_SUCCESS)

        self.kpi_cards["tsi"][0].configure(text=f"{tsi_score:.1f} / 10", text_color=tsi_color)
        self.kpi_cards["tsi"][1].configure(text=tsi_tier_name)

        self.redraw_images()

    def redraw_images(self) -> None:
        if not self.current_result:
            return

        palette = self.palette_menu.get()
        images = {
            "1. Originalbild":             apply_colormap_to_image(self.current_result["calibrated_original"], palette),
            "2. Hintergrund-Maske":        self.current_result["body_mask"],
            "3. Lokale Hitze-Differenz":   self.current_result["heat_diff"],
            "4. Erkannte Hotspots (Rust)": self.current_result["overlay_rgb"]
        }

        for key, raw_array in images.items():
            lbl = self._panel_labels.get(key)
            if not lbl:
                continue

            lbl.update_idletasks()
            w = max(lbl.winfo_width() - 16, 260)
            h = max(lbl.winfo_height() - 16, 160)

            if len(raw_array.shape) == 2:
                pil_img = Image.fromarray(raw_array).convert("RGB")
            elif raw_array.shape[2] == 3 and key == "4. Erkannte Hotspots (Rust)":
                pil_img = Image.fromarray(raw_array)
            else:
                pil_img = Image.fromarray(raw_array).convert("RGB")

            ctk_img = make_display_ctk_image(pil_img, w, h)
            lbl.configure(image=ctk_img, text="")
            lbl.image = ctk_img
