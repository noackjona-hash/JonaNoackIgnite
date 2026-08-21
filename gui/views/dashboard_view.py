# -*- coding: utf-8 -*-
"""gui/views/dashboard_view.py – Google Material 3 4-Panel Dashboard for IGNITE."""

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
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_BLUE,
    COLOR_CONTAINER_GREEN,
    COLOR_CONTAINER_RED,
    COLOR_CONTAINER_YELLOW,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card, make_display_ctk_image, apply_colormap_to_image
from utils import pixel_to_celsius


class DashboardView(ctk.CTkFrame):
    """4-Stufen Haupt-Dashboard im Google Material 3 Design."""

    PANEL_DEFS = [
        ("1. Originalbild",             "1. Original-Wärmebild",          "Rohdaten & Kalibrierung",     "#1A73E8"),
        ("2. Hintergrund-Maske",        "2. Gewebe-Segmentierung",        "Hintergrund & Artefaktfilter", "#34A853"),
        ("3. Lokale Hitze-Differenz",   "3. Morphologische Top-Hat Diff", "Strukturelle Hitzekontraste",  "#FBBC04"),
        ("4. Erkannte Hotspots (Rust)", "4. Diagnose & Hotspot-Overlay",  "Entzündungsherde & BBoxes",    "#EA4335"),
    ]

    def __init__(
        self,
        master,
        on_load_click: Callable[[], None],
        on_inspect_panel: Callable[[str], None],
        on_palette_change: Callable[[str], None],
        on_mode_change: Callable[[str], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_load_click = on_load_click
        self.on_inspect_panel = on_inspect_panel
        self.on_palette_change = on_palette_change
        self.on_mode_change = on_mode_change

        self.current_result: Optional[dict[str, Any]] = None
        self._panel_labels: dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # ── 1. KPI Metriken-Leiste oben ──────────────────────────────────────
        self.kpi_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.kpi_bar.pack(fill=ctk.X, padx=20, pady=(16, 8))

        self.kpi_cards = {}
        kpi_configs = [
            ("temp_mean", "MITTLERE TEMPERATUR", "-- °C", "Gewebe-Mittelwert", COLOR_CONTAINER_BLUE, COLOR_PRIMARY),
            ("temp_max",  "MAXIMAL-TEMPERATUR",  "-- °C", "Heißester Messpunkt", COLOR_CONTAINER_RED, COLOR_DANGER),
            ("hotspots",  "HOTSPOT-FLÄCHE",      "-- px", "0.0% des Gewebes", COLOR_CONTAINER_YELLOW, COLOR_WARNING),
            ("symmetry",  "SEITEN-SYMMETRIE",    "Δ -- °C", "Klinische Differenz", COLOR_CONTAINER_GREEN, COLOR_SUCCESS),
        ]

        self.kpi_bar.grid_columnconfigure(0, weight=1)
        self.kpi_bar.grid_columnconfigure(1, weight=1)
        self.kpi_bar.grid_columnconfigure(2, weight=1)
        self.kpi_bar.grid_columnconfigure(3, weight=1)

        for col, (kpi_id, title, default_val, sub, bg_tonal, text_acc) in enumerate(kpi_configs):
            card = make_material_card(self.kpi_bar, corner_radius=18, fg_color=COLOR_BG_CARD)
            card.grid(row=0, column=col, padx=8, sticky="nsew")

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill=ctk.BOTH, expand=True, padx=20, pady=16)

            ctk.CTkLabel(
                content,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            ).pack(fill=ctk.X)

            lbl_val = ctk.CTkLabel(
                content,
                text=default_val,
                font=ctk.CTkFont(family=FONT_FAMILY, size=26, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, pady=(4, 0))

            lbl_sub = ctk.CTkLabel(
                content,
                text=sub,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w"
            )
            lbl_sub.pack(fill=ctk.X, pady=(2, 0))

            self.kpi_cards[kpi_id] = (lbl_val, lbl_sub)

        # ── 2. Filter & Steuerungsleiste über dem Grid ────────────────────────
        ctrl_bar = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_bar.pack(fill=ctk.X, padx=28, pady=(4, 10))

        ctk.CTkLabel(
            ctrl_bar,
            text="PIPELINE-STUFEN",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.LEFT)

        # Colormap Dropdown rechts
        self.palette_menu = ctk.CTkOptionMenu(
            ctrl_bar,
            values=["Google Turbo", "Graustufen", "Inferno", "Heiß (Hot)"],
            command=self.on_palette_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=10,
            height=36,
            width=160
        )
        self.palette_menu.pack(side=ctk.RIGHT, padx=(10, 0))

        ctk.CTkLabel(
            ctrl_bar,
            text="Farbpalette:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(side=ctk.RIGHT)

        # Modus Dropdown
        self.mode_menu = ctk.CTkOptionMenu(
            ctrl_bar,
            values=["Klinische Allgemeinanalyse", "Podologische Symmetrieanalyse"],
            command=self.on_mode_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=10,
            height=36,
            width=240
        )
        self.mode_menu.pack(side=ctk.RIGHT, padx=(10, 20))

        ctk.CTkLabel(
            ctrl_bar,
            text="Modus:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(side=ctk.RIGHT)

        # ── 3. Haupt-Container für Grid vs. Empty State ──────────────────────
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # 4-Panel Grid
        self.grid_frame = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.grid_frame.grid_columnconfigure(0, weight=1)
        self.grid_frame.grid_columnconfigure(1, weight=1)
        self.grid_frame.grid_rowconfigure(0, weight=1)
        self.grid_frame.grid_rowconfigure(1, weight=1)

        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for (key, title, subtitle, color), (r, c) in zip(self.PANEL_DEFS, positions):
            card = make_material_card(self.grid_frame, corner_radius=18, fg_color=COLOR_BG_CARD)
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

            header = ctk.CTkFrame(card, fg_color="transparent", height=48)
            header.pack(fill=ctk.X, padx=18, pady=(12, 6))
            header.pack_propagate(False)

            dot = ctk.CTkFrame(header, width=10, height=10, corner_radius=5, fg_color=color)
            dot.pack(side=ctk.LEFT, padx=(0, 10), pady=4)

            title_box = ctk.CTkFrame(header, fg_color="transparent")
            title_box.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            ctk.CTkLabel(
                title_box,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            ).pack(fill=ctk.X)

            _k = key
            inspect_btn = ctk.CTkButton(
                header,
                text="⤢ Details",
                command=lambda k=_k: self.on_inspect_panel(k),
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                fg_color=COLOR_CONTAINER_BLUE,
                hover_color=COLOR_BG_CARD_VARIANT,
                text_color=COLOR_PRIMARY,
                corner_radius=16,
                height=30,
                width=84
            )
            inspect_btn.pack(side=ctk.RIGHT)

            ctk.CTkFrame(card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X, padx=0, pady=(6, 0))

            img_lbl = ctk.CTkLabel(
                card,
                text="Kein Bild geladen",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=COLOR_TEXT_MUTED
            )
            img_lbl.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)
            self._panel_labels[key] = img_lbl

        # Empty / Welcome State
        self.welcome_card = make_material_card(
            self.content_area,
            corner_radius=24,
            fg_color=COLOR_BG_CARD
        )
        self._build_welcome_state()

        self.show_empty_state()

    def _build_welcome_state(self) -> None:
        """Erstellt einen eleganten, responsiven Google-Style Startbildschirm."""
        center_box = ctk.CTkFrame(self.welcome_card, fg_color="transparent")
        center_box.pack(expand=True, padx=24, pady=24)

        # Icon
        ctk.CTkLabel(
            center_box,
            text="🔬",
            font=ctk.CTkFont(size=64)
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            center_box,
            text="Wärmebild zur Diagnose laden",
            font=ctk.CTkFont(family=FONT_FAMILY, size=26, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            center_box,
            text="Lade ein 8-Bit oder radiometrisches Infrarotbild (.jpg, .png, .tiff, .flir),\num automatische Entzündungs- und Symmetrieanalysen durchzuführen.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color=COLOR_TEXT_SECONDARY,
            justify="center",
            wraplength=580
        ).pack(pady=(0, 30))

        ctk.CTkButton(
            center_box,
            text="+  Wärmebild auswählen…",
            command=self.on_load_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=24,
            height=48,
            width=260
        ).pack(pady=(0, 28))

        # Schnell-Tipps Leiste
        tips_row = ctk.CTkFrame(center_box, fg_color="transparent")
        tips_row.pack(pady=(12, 0))

        tips = [
            ("⚡ High-Speed", "Rust & CUDA Beschleunigung"),
            ("🛡️ DSGVO", "Lokale In-Memory Verarbeitung"),
            ("📐 Goldstandard", "Armstrong 2.2 °C Asymmetrie")
        ]
        for icon_title, desc in tips:
            pill = ctk.CTkFrame(tips_row, fg_color=COLOR_BG_CARD_VARIANT, corner_radius=16)
            pill.pack(side=ctk.LEFT, padx=8)
            ctk.CTkLabel(
                pill,
                text=f"{icon_title} · {desc}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_SECONDARY
            ).pack(padx=16, pady=8)

    def show_empty_state(self) -> None:
        self.grid_frame.pack_forget()
        self.welcome_card.pack(fill=ctk.BOTH, expand=True, padx=8, pady=8)

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

        if hotspots > 0:
            self.kpi_cards["hotspots"][0].configure(text=f"{hotspots:,} px", text_color=COLOR_DANGER)
            self.kpi_cards["hotspots"][1].configure(text=f"{ratio:.2f}% der Oberfläche auffällig")
        else:
            self.kpi_cards["hotspots"][0].configure(text="0 px", text_color=COLOR_SUCCESS)
            self.kpi_cards["hotspots"][1].configure(text="Keine Entzündungsherde")

        sym_txt = f"Δ {delta_t:.1f} °C"
        sym_color = COLOR_DANGER if is_asym else COLOR_SUCCESS
        self.kpi_cards["symmetry"][0].configure(text=sym_txt, text_color=sym_color)
        self.kpi_cards["symmetry"][1].configure(text="Pathologische Asymmetrie" if is_asym else "Physiologisch symmetrisch")

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
            w = max(lbl.winfo_width() - 20, 260)
            h = max(lbl.winfo_height() - 20, 160)

            if len(raw_array.shape) == 2:
                pil_img = Image.fromarray(raw_array).convert("RGB")
            elif raw_array.shape[2] == 3 and key == "4. Erkannte Hotspots (Rust)":
                pil_img = Image.fromarray(raw_array)
            else:
                pil_img = Image.fromarray(raw_array).convert("RGB")

            ctk_img = make_display_ctk_image(pil_img, w, h)
            lbl.configure(image=ctk_img, text="")
            lbl.image = ctk_img
