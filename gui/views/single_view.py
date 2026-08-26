# -*- coding: utf-8 -*-
"""gui/views/single_view.py – Deep-Dive Image & ROI Inspector for IGNITE.

Features:
- Stage switching (Original, Body Mask, Top-Hat Diff, Hotspot Overlay, Bioheat, Frangi, Asymmetry)
- Interactive Zoom (100% to 800%) & Pan with mouse wheel and drag
- Dynamic Celsius Colorbar with T_min, T_mean, T_thresh, T_max markers
- Precise ROI rectangle probe with quantitative statistics (Mean, Std, Min, Max, Area)
- High-resolution snapshot export
"""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np
import cv2
from PIL import Image

from gui.theme import (
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
    COLOR_CONTAINER_BLUE,
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


class SingleInspectView(ctk.CTkFrame):
    """Detailansicht zur pixelgenauen Inspektion, Zoom/Pan und interaktiven ROI-Messung."""

    STAGES = [
        ("4. Erkannte Hotspots (Rust)", "Hotspot-Overlay"),
        ("1. Originalbild",             "1. Original"),
        ("2. Hintergrund-Maske",        "2. Gewebe-Maske"),
        ("3. Lokale Hitze-Differenz",   "3. Top-Hat Diff"),
        ("5. Pennes Bioheat",           "Pennes Bioheat"),
        ("6. Frangi-Venen",             "Frangi-Venen"),
        ("7. Bilaterale Asymmetrie",    "Asymmetrie-Map"),
    ]

    def __init__(
        self,
        master,
        on_load_click: Callable[[], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_load_click = on_load_click
        self.current_result: Optional[dict[str, Any]] = None
        self.active_stage_key: str = "4. Erkannte Hotspots (Rust)"
        self.palette_name: str = "Turbo"

        # Swipe / Split-View State
        self.is_split_view: bool = False
        self.split_ratio: float = 0.50
        self.split_target_stage: str = "4. Erkannte Hotspots (Rust)"

        # Linienprofil (1D Transect) State
        self.is_profile_mode: bool = False
        self.profile_drag_start: Optional[tuple[int, int]] = None
        self.profile_drag_current: Optional[tuple[int, int]] = None
        self.profile_line: Optional[tuple[tuple[int, int], tuple[int, int]]] = None
        self.profile_temps: list[float] = []
        self.profile_grads: list[float] = []

        # Isothermen (Thermische Bandpass-Hervorhebung) State
        self.is_isotherm_mode: bool = False
        self.isotherm_min: float = 32.0
        self.isotherm_max: float = 40.0
        self.isotherm_color_name: str = "Signalrot"
        self.isotherm_filter_mode: str = "Oberhalb"

        # Zoom & Pan State
        self.zoom_level: float = 1.0
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.pan_drag_start: Optional[tuple[int, int]] = None

        # ROI State
        self.roi_drag_start: Optional[tuple[int, int]] = None
        self.roi_drag_current: Optional[tuple[int, int]] = None
        self.roi_box: Optional[tuple[int, int, int, int]] = None
        self._rendered_pil: Optional[Image.Image] = None
        self._visible_crop: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._render_scale: float = 1.0
        self._offset_x: int = 0
        self._offset_y: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(0, weight=1)

        # ── Linker Bereich: Bildanzeige & Colorbar ───────────────────────────
        self.canvas_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.canvas_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        # Header mit Segmented Buttons & Quick Actions
        top_bar = ctk.CTkFrame(self.canvas_card, fg_color="transparent", height=46)
        top_bar.pack(fill=ctk.X, padx=14, pady=(10, 6))
        top_bar.pack_propagate(False)

        # Modus-Umschalter: Stufen-Ansicht vs. Isotherme vs. Linienprofil vs. Swipe / Split-View
        self.mode_switcher = ctk.CTkSegmentedButton(
            top_bar,
            values=["Stufen", "Isotherme", "Linienprofil", "Swipe-Split"],
            command=self._on_view_mode_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=290
        )
        self.mode_switcher.set("Stufen")
        self.mode_switcher.pack(side=ctk.LEFT, padx=(0, 8))

        # 1. Stufen-Leiste (Standard)
        self.stage_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        self.stage_frame.pack(side=ctk.LEFT, fill=ctk.Y)

        self.stage_seg = ctk.CTkSegmentedButton(
            self.stage_frame,
            values=[title for _, title in self.STAGES],
            command=self._on_segment_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=30
        )
        self.stage_seg.set("Hotspot-Overlay")
        self.stage_seg.pack(side=ctk.LEFT)

        # 2. Swipe / Split-View Leiste (wird bei Swipe-Modus aktiv)
        self.split_frame = ctk.CTkFrame(top_bar, fg_color="transparent")

        self.split_stage_opt = ctk.CTkOptionMenu(
            self.split_frame,
            values=["Hotspot-Overlay", "Pennes Bioheat", "Frangi-Venen", "Asymmetrie-Map"],
            command=self._on_split_stage_selected,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=150
        )
        self.split_stage_opt.set("Hotspot-Overlay")
        self.split_stage_opt.pack(side=ctk.LEFT, padx=(0, 8))

        ctk.CTkLabel(
            self.split_frame,
            text="Swipe:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_SECONDARY
        ).pack(side=ctk.LEFT, padx=(0, 4))

        self.split_slider = ctk.CTkSlider(
            self.split_frame,
            from_=0.0,
            to=1.0,
            number_of_steps=100,
            command=self._on_split_slider_moved,
            width=120,
            height=16,
            progress_color=COLOR_PRIMARY,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER
        )
        self.split_slider.set(0.5)
        self.split_slider.pack(side=ctk.LEFT, padx=(0, 6))

        self.split_pct_lbl = ctk.CTkLabel(
            self.split_frame,
            text="50%",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
            width=36
        )
        self.split_pct_lbl.pack(side=ctk.LEFT)

        # Rechter Bereich: 3D-Relief & Snapshot exportieren
        self.snapshot_btn = ctk.CTkButton(
            top_bar,
            text="Snapshot",
            command=self.save_snapshot,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=80
        )
        self.snapshot_btn.pack(side=ctk.RIGHT)

        self.threed_btn = ctk.CTkButton(
            top_bar,
            text="🏔️ 3D",
            command=self.open_3d_viewer,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=65
        )
        self.threed_btn.pack(side=ctk.RIGHT, padx=(0, 6))

        self.perfusion_btn = ctk.CTkButton(
            top_bar,
            text="⏱️ Perfusion",
            command=self.open_perfusion_viewer,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=95
        )
        self.perfusion_btn.pack(side=ctk.RIGHT, padx=(0, 6))

        # Reset Button (ROI / Linienprofil)
        self.reset_roi_btn = ctk.CTkButton(
            top_bar,
            text="Reset",
            command=self.reset_measurement,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_MUTED,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=70
        )
        self.reset_roi_btn.pack(side=ctk.RIGHT, padx=(0, 6))

        # Zoom Controls
        self.zoom_badge = ctk.CTkButton(
            top_bar,
            text="100%",
            command=self.reset_zoom,
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_PRIMARY,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=55
        )
        self.zoom_badge.pack(side=ctk.RIGHT, padx=(0, 6))

        ctk.CTkFrame(self.canvas_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        # Bild-Container mit Colorbar
        display_frame = ctk.CTkFrame(self.canvas_card, fg_color="transparent")
        display_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=(8, 4))
        display_frame.grid_columnconfigure(0, weight=1)
        display_frame.grid_columnconfigure(1, weight=0, minsize=55)
        display_frame.grid_rowconfigure(0, weight=1)

        # Bild Label mit Maus-Events
        self.img_lbl = ctk.CTkLabel(
            display_frame,
            text="Kein Bild geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.img_lbl.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.img_lbl.bind("<Motion>", self._on_mouse_move)
        self.img_lbl.bind("<Leave>", self._on_mouse_leave)
        self.img_lbl.bind("<ButtonPress-1>", self._on_mouse_down)
        self.img_lbl.bind("<B1-Motion>", self._on_mouse_drag)
        self.img_lbl.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.img_lbl.bind("<Double-Button-1>", lambda e: self.reset_zoom())

        # Pan via Right Click / Middle Click
        self.img_lbl.bind("<ButtonPress-3>", self._on_pan_start)
        self.img_lbl.bind("<B3-Motion>", self._on_pan_drag)
        self.img_lbl.bind("<ButtonRelease-3>", self._on_pan_end)
        self.img_lbl.bind("<ButtonPress-2>", self._on_pan_start)
        self.img_lbl.bind("<B2-Motion>", self._on_pan_drag)
        self.img_lbl.bind("<ButtonRelease-2>", self._on_pan_end)

        # Mousewheel Zoom
        self.img_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.img_lbl.bind("<Button-4>", lambda e: self._zoom_step(1.25))
        self.img_lbl.bind("<Button-5>", lambda e: self._zoom_step(0.8))

        # ── Colorbar Farblegende (Rechte Seite des Canvas) ───────────────────
        self.colorbar_frame = ctk.CTkFrame(display_frame, fg_color="transparent", width=55)
        self.colorbar_frame.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.colorbar_frame.pack_propagate(False)

        self.cb_max_lbl = ctk.CTkLabel(self.colorbar_frame, text="-- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=9, weight="bold"), text_color=COLOR_DANGER)
        self.cb_max_lbl.pack(side=ctk.TOP, anchor="e")

        self.cb_strip_lbl = ctk.CTkLabel(self.colorbar_frame, text="")
        self.cb_strip_lbl.pack(side=ctk.TOP, fill=ctk.Y, expand=True, pady=4)

        self.cb_min_lbl = ctk.CTkLabel(self.colorbar_frame, text="-- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=9, weight="bold"), text_color=COLOR_PRIMARY)
        self.cb_min_lbl.pack(side=ctk.BOTTOM, anchor="e")

        self._render_colorbar_strip()

        # ── Rechter Bereich: Live Pixel & ROI Sidebar ────────────────────────
        self.sidebar_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.sidebar_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        side_scroll = ctk.CTkScrollableFrame(self.sidebar_card, fg_color="transparent")
        side_scroll.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        # 1. Live Fadenkreuz & Pixel Tooltip
        ctk.CTkLabel(
            side_scroll,
            text="LIVE-PIXELMESSUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(2, 6))

        self.pixel_box = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.pixel_box.pack(fill=ctk.X, pady=(0, 14))

        p_inner = ctk.CTkFrame(self.pixel_box, fg_color="transparent")
        p_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.live_temp_lbl = ctk.CTkLabel(
            p_inner,
            text="--.- °C",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=24, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.live_temp_lbl.pack(fill=ctk.X)

        self.live_coord_lbl = ctk.CTkLabel(
            p_inner,
            text="Koordinaten: X=--, Y=--",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.live_coord_lbl.pack(fill=ctk.X, pady=(2, 0))

        self.live_status_lbl = ctk.CTkLabel(
            p_inner,
            text="Befund: Cursor über Bild bewegen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.live_status_lbl.pack(fill=ctk.X, pady=(2, 0))

        # 2. ROI Messbox
        ctk.CTkLabel(
            side_scroll,
            text="REGION OF INTEREST (ROI)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 6))

        self.roi_card = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.roi_card.pack(fill=ctk.X, pady=(0, 14))

        r_inner = ctk.CTkFrame(self.roi_card, fg_color="transparent")
        r_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.roi_title_lbl = ctk.CTkLabel(
            r_inner,
            text="Rechteck mit Maus aufziehen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=200
        )
        self.roi_title_lbl.pack(fill=ctk.X, pady=(0, 8))

        self.roi_stats_rows = {}
        for key, name in [
            ("mean", "Mittelwert (µ):"),
            ("std", "Standardabw. (σ):"),
            ("min", "Minimal-Temp:"),
            ("max", "Maximal-Temp:"),
            ("area", "Fläche (Pixel):")
        ]:
            row = ctk.CTkFrame(r_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.roi_stats_rows[key] = lbl

        self.copy_roi_btn = ctk.CTkButton(
            r_inner,
            text="📋 Messwerte kopieren",
            command=self.copy_roi_stats,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=28
        )
        self.copy_roi_btn.pack(fill=ctk.X, pady=(8, 0))

        # 3. Linienprofil-Karte (1D Transect)
        self.profile_card = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)

        pr_inner = ctk.CTkFrame(self.profile_card, fg_color="transparent")
        pr_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.profile_title_lbl = ctk.CTkLabel(
            pr_inner,
            text="Linie mit Maus ziehen (A → B)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=200
        )
        self.profile_title_lbl.pack(fill=ctk.X, pady=(0, 6))

        # Mini Canvas Graph für das 1D-Profil
        self.profile_canvas = tk.Canvas(
            pr_inner,
            width=240,
            height=100,
            bg="#0F172A",
            highlightthickness=1,
            highlightbackground="#334155"
        )
        self.profile_canvas.pack(fill=ctk.X, pady=(0, 8))

        self.profile_stats_rows = {}
        for key, name in [
            ("len", "Distanz (L):"),
            ("delta", "Delta-T (ΔT):"),
            ("min_max", "Min / Max:"),
            ("mean", "Mittelwert (µ):"),
            ("grad", "Max. Gradient:")
        ]:
            row = ctk.CTkFrame(pr_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.profile_stats_rows[key] = lbl

        self.copy_profile_btn = ctk.CTkButton(
            pr_inner,
            text="📋 Profildaten kopieren (CSV)",
            command=self.copy_profile_csv,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=28
        )
        self.copy_profile_btn.pack(fill=ctk.X, pady=(8, 0))

        # 3. Isothermen-Analyse Karte
        self.isotherm_card = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        # wird dynamisch gepackt

        iso_inner = ctk.CTkFrame(self.isotherm_card, fg_color="transparent")
        iso_inner.pack(fill=ctk.X, padx=14, pady=12)

        ctk.CTkLabel(
            iso_inner,
            text="ISOTHERMEN-FILTER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 4))

        # Modus: Oberhalb, Bandpass, Unterhalb
        self.iso_mode_seg = ctk.CTkSegmentedButton(
            iso_inner,
            values=["Oberhalb", "Bandpass", "Unterhalb"],
            command=self._on_iso_mode_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=28
        )
        self.iso_mode_seg.set("Oberhalb")
        self.iso_mode_seg.pack(fill=ctk.X, pady=(0, 8))

        # Min Temperatur Slider & Label
        min_row = ctk.CTkFrame(iso_inner, fg_color="transparent")
        min_row.pack(fill=ctk.X, pady=(2, 2))
        ctk.CTkLabel(min_row, text="Untere Schwelle (T_min):", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
        self.iso_min_lbl = ctk.CTkLabel(min_row, text="32.0 °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_PRIMARY)
        self.iso_min_lbl.pack(side=ctk.RIGHT)

        self.iso_min_slider = ctk.CTkSlider(
            iso_inner,
            from_=15.0,
            to=45.0,
            number_of_steps=150,
            command=self._on_iso_min_moved,
            height=16,
            progress_color=COLOR_PRIMARY,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER
        )
        self.iso_min_slider.set(32.0)
        self.iso_min_slider.pack(fill=ctk.X, pady=(0, 6))

        # Max Temperatur Slider & Label (für Bandpass / Unterhalb)
        max_row = ctk.CTkFrame(iso_inner, fg_color="transparent")
        max_row.pack(fill=ctk.X, pady=(2, 2))
        ctk.CTkLabel(max_row, text="Obere Schwelle (T_max):", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
        self.iso_max_lbl = ctk.CTkLabel(max_row, text="40.0 °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_PRIMARY)
        self.iso_max_lbl.pack(side=ctk.RIGHT)

        self.iso_max_slider = ctk.CTkSlider(
            iso_inner,
            from_=15.0,
            to=45.0,
            number_of_steps=150,
            command=self._on_iso_max_moved,
            height=16,
            progress_color=COLOR_PRIMARY,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER
        )
        self.iso_max_slider.set(40.0)
        self.iso_max_slider.pack(fill=ctk.X, pady=(0, 8))

        # Farbauswahl
        color_row = ctk.CTkFrame(iso_inner, fg_color="transparent")
        color_row.pack(fill=ctk.X, pady=(0, 8))
        ctk.CTkLabel(color_row, text="Isothermen-Farbe:", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
        self.iso_color_opt = ctk.CTkOptionMenu(
            color_row,
            values=["Signalrot", "Neon-Bernstein", "Cyan", "Magenta"],
            command=self._on_iso_color_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=26,
            width=130
        )
        self.iso_color_opt.set("Signalrot")
        self.iso_color_opt.pack(side=ctk.RIGHT)

        # Quick Presets
        ctk.CTkLabel(
            iso_inner,
            text="KLINISCHE PRESETS",
            font=ctk.CTkFont(family=FONT_FAMILY, size=9, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(2, 4))

        preset_grid = ctk.CTkFrame(iso_inner, fg_color="transparent")
        preset_grid.pack(fill=ctk.X, pady=(0, 8))
        preset_grid.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            preset_grid,
            text="⚠️ >32.0°C (IWGDF)",
            command=lambda: self._set_isotherm_preset("Oberhalb", 32.0, 42.0),
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=26
        ).grid(row=0, column=0, padx=(0, 2), pady=2, sticky="ew")

        ctk.CTkButton(
            preset_grid,
            text="🔴 >34.5°C (Akut)",
            command=lambda: self._set_isotherm_preset("Oberhalb", 34.5, 42.0),
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=26
        ).grid(row=0, column=1, padx=(2, 0), pady=2, sticky="ew")

        ctk.CTkButton(
            preset_grid,
            text="🦶 28-32°C (Normal)",
            command=lambda: self._set_isotherm_preset("Bandpass", 28.0, 32.0),
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=26
        ).grid(row=1, column=0, padx=(0, 2), pady=2, sticky="ew")

        ctk.CTkButton(
            preset_grid,
            text="❄️ <27.0°C (Hypo)",
            command=lambda: self._set_isotherm_preset("Unterhalb", 15.0, 27.0),
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=26
        ).grid(row=1, column=1, padx=(2, 0), pady=2, sticky="ew")

        # Stats Rows
        self.iso_stats_rows = {}
        for key, name in [
            ("area", "Isothermen-Fläche:"),
            ("mean", "Mitteltemperatur (µ):"),
            ("peak", "Peak-Temperatur:")
        ]:
            row = ctk.CTkFrame(iso_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.iso_stats_rows[key] = lbl

        # 4. Quick Tipp / Zoom & Pan Bedienhinweis
        hint_box = ctk.CTkFrame(side_scroll, fg_color="transparent")
        hint_box.pack(fill=ctk.X, pady=(4, 0))

        ctk.CTkLabel(
            hint_box,
            text="Bedienung:\n• Linksklick + Ziehen: ROI-Messung\n• Mausrad: Zoom (100% - 800%)\n• Rechtsklick + Ziehen: Pan (Verschieben)\n• Doppelklick / 100%-Button: Zoom-Reset",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=210,
            justify="left"
        ).pack(fill=ctk.X)

    def _render_colorbar_strip(self) -> None:
        """Erzeugt den vertikalen Farbverlaufs-Streifen für die Colorbar."""
        grad = np.linspace(255, 0, 180, dtype=np.uint8).reshape((180, 1))
        grad = np.repeat(grad, 12, axis=1)
        colored = apply_colormap_to_image(grad, self.palette_name)
        rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
        pil_strip = Image.fromarray(rgb)
        ctk_strip = ctk.CTkImage(light_image=pil_strip, dark_image=pil_strip, size=(12, 180))
        self.cb_strip_lbl.configure(image=ctk_strip)
        self.cb_strip_lbl.image = ctk_strip

    def show_results(self, result: dict[str, Any], palette_name: str = "Turbo", target_stage: str | None = None) -> None:
        self.current_result = result
        self.palette_name = palette_name
        if target_stage:
            self.active_stage_key = target_stage
            for key, title in self.STAGES:
                if key == target_stage:
                    self.stage_seg.set(title)
                    break

        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)
        self.cb_max_lbl.configure(text=f"{t_max:.1f}°C")
        self.cb_min_lbl.configure(text=f"{t_min:.1f}°C")
        self._render_colorbar_strip()
        self.redraw()

    def set_palette(self, palette_name: str) -> None:
        self.palette_name = palette_name
        self._render_colorbar_strip()
        self.redraw()

    def open_3d_viewer(self) -> None:
        """Öffnet das interaktive 3D-Relief- und Topographie-Fenster."""
        if not self.current_result:
            return
        from gui.widgets.dialogs import Thermal3DViewerModal
        raw_img = self.current_result["calibrated_original"]
        body_mask = self.current_result.get("body_mask")
        t_min = float(self.current_result.get("t_min_c", 20.0))
        t_max = float(self.current_result.get("t_max_c", 40.0))

        Thermal3DViewerModal(
            self,
            calibrated_image=raw_img,
            body_mask=body_mask,
            t_min_c=t_min,
            t_max_c=t_max,
            palette_name=self.palette_name
        )

    def open_perfusion_viewer(self) -> None:
        """Öffnet das interaktive Kälteprovokations- und dynamische Wiedererwärmungs-Fenster."""
        if not self.current_result:
            return
        from gui.widgets.dialogs import DynamicPerfusionModal
        raw_img = self.current_result["calibrated_original"]
        body_mask = self.current_result.get("body_mask")
        t_min = float(self.current_result.get("t_min_c", 20.0))
        t_max = float(self.current_result.get("t_max_c", 40.0))

        DynamicPerfusionModal(
            self,
            calibrated_image=raw_img,
            body_mask=body_mask,
            t_min_c=t_min,
            t_max_c=t_max,
            palette_name=self.palette_name
        )

    def _on_view_mode_changed(self, mode: str) -> None:
        """Schaltet zwischen Stufen-Ansicht, Isotherme, Linienprofil und interaktivem Swipe/Split-View um."""
        if mode == "Swipe-Split":
            self.is_split_view = True
            self.is_profile_mode = False
            self.is_isotherm_mode = False
            self.stage_frame.pack_forget()
            self.split_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 8))
            self.profile_card.pack_forget()
            self.isotherm_card.pack_forget()
            self.roi_card.pack(fill=ctk.X, pady=(0, 14))
            self.reset_roi_btn.configure(state="disabled")
        elif mode == "Linienprofil":
            self.is_split_view = False
            self.is_profile_mode = True
            self.is_isotherm_mode = False
            self.split_frame.pack_forget()
            self.stage_frame.pack(side=ctk.LEFT, fill=ctk.Y)
            self.roi_card.pack_forget()
            self.isotherm_card.pack_forget()
            self.profile_card.pack(fill=ctk.X, pady=(0, 14))
            self.reset_roi_btn.configure(state="normal")
        elif mode == "Isotherme":
            self.is_split_view = False
            self.is_profile_mode = False
            self.is_isotherm_mode = True
            self.split_frame.pack_forget()
            self.stage_frame.pack(side=ctk.LEFT, fill=ctk.Y)
            self.roi_card.pack_forget()
            self.profile_card.pack_forget()
            self.isotherm_card.pack(fill=ctk.X, pady=(0, 14))
            self.reset_roi_btn.configure(state="normal")
        else:  # "Stufen"
            self.is_split_view = False
            self.is_profile_mode = False
            self.is_isotherm_mode = False
            self.split_frame.pack_forget()
            self.stage_frame.pack(side=ctk.LEFT, fill=ctk.Y)
            self.profile_card.pack_forget()
            self.isotherm_card.pack_forget()
            self.roi_card.pack(fill=ctk.X, pady=(0, 14))
            self.reset_roi_btn.configure(state="normal")
        self.redraw()

    def _on_iso_mode_changed(self, mode: str) -> None:
        self.isotherm_filter_mode = mode
        self.redraw()

    def _on_iso_min_moved(self, val: float) -> None:
        self.isotherm_min = float(val)
        self.iso_min_lbl.configure(text=f"{self.isotherm_min:.1f} °C")
        if self.isotherm_min > self.isotherm_max:
            self.isotherm_max = self.isotherm_min
            self.iso_max_slider.set(self.isotherm_max)
            self.iso_max_lbl.configure(text=f"{self.isotherm_max:.1f} °C")
        self.redraw()

    def _on_iso_max_moved(self, val: float) -> None:
        self.isotherm_max = float(val)
        self.iso_max_lbl.configure(text=f"{self.isotherm_max:.1f} °C")
        if self.isotherm_max < self.isotherm_min:
            self.isotherm_min = self.isotherm_max
            self.iso_min_slider.set(self.isotherm_min)
            self.iso_min_lbl.configure(text=f"{self.isotherm_min:.1f} °C")
        self.redraw()

    def _on_iso_color_changed(self, color_name: str) -> None:
        self.isotherm_color_name = color_name
        self.redraw()

    def _set_isotherm_preset(self, mode: str, t_min: float, t_max: float) -> None:
        self.isotherm_filter_mode = mode
        self.iso_mode_seg.set(mode)
        self.isotherm_min = t_min
        self.isotherm_max = t_max
        self.iso_min_slider.set(t_min)
        self.iso_max_slider.set(t_max)
        self.iso_min_lbl.configure(text=f"{t_min:.1f} °C")
        self.iso_max_lbl.configure(text=f"{t_max:.1f} °C")
        self.redraw()

    def _compute_isotherm_overlay(self) -> np.ndarray:
        """Erzeugt ein Graustufen-Hintergrundbild mit farblich intensiv isolierter Isothermenzone."""
        if not self.current_result:
            return np.zeros((100, 100, 3), dtype=np.uint8)

        raw_img = self.current_result["calibrated_original"]
        body_mask = self.current_result.get("body_mask", np.ones_like(raw_img) * 255)
        t_min = float(self.current_result.get("t_min_c", 20.0))
        t_max = float(self.current_result.get("t_max_c", 40.0))

        # Temperaturmatrix in °C
        temp_c = t_min + (raw_img.astype(np.float32) / 255.0) * (t_max - t_min)

        # Isothermen-Maske nach Modus filtern
        if self.isotherm_filter_mode == "Oberhalb":
            iso_mask = (temp_c >= self.isotherm_min) & (body_mask > 0)
        elif self.isotherm_filter_mode == "Bandpass":
            iso_mask = (temp_c >= self.isotherm_min) & (temp_c <= self.isotherm_max) & (body_mask > 0)
        else:  # "Unterhalb"
            iso_mask = (temp_c <= self.isotherm_max) & (body_mask > 0)

        # Farbdefinitionen (BGR)
        color_map_bgr = {
            "Signalrot": (0, 0, 235),
            "Neon-Bernstein": (0, 180, 255),
            "Cyan": (255, 230, 0),
            "Magenta": (220, 50, 240)
        }
        chosen_bgr = color_map_bgr.get(self.isotherm_color_name, (0, 0, 235))

        # Hintergrund: abgedunkeltes Graustufenbild
        bg_gray = cv2.cvtColor(raw_img, cv2.COLOR_GRAY2BGR)
        bg_gray = (bg_gray.astype(np.float32) * 0.75).astype(np.uint8)

        result_img = bg_gray.copy()
        result_img[iso_mask] = chosen_bgr

        # Kontur um Isothermenzone
        iso_bin = iso_mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(iso_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result_img, contours, -1, (255, 255, 255), 1, cv2.LINE_AA)

        # Statistik aktualisieren
        body_px = int(np.sum(body_mask > 0))
        iso_px = int(np.sum(iso_mask))
        ratio = (iso_px / max(1, body_px)) * 100.0

        if iso_px > 0:
            iso_temps = temp_c[iso_mask]
            mean_iso = float(np.mean(iso_temps))
            peak_iso = float(np.max(iso_temps))
            self.iso_stats_rows["area"].configure(text=f"{iso_px:,} px ({ratio:.1f} %)")
            self.iso_stats_rows["mean"].configure(text=f"{mean_iso:.2f} °C")
            self.iso_stats_rows["peak"].configure(text=f"{peak_iso:.2f} °C")
        else:
            self.iso_stats_rows["area"].configure(text="0 px (0.0 %)")
            self.iso_stats_rows["mean"].configure(text="--.- °C")
            self.iso_stats_rows["peak"].configure(text="--.- °C")

        return result_img

    def _on_split_stage_selected(self, choice: str) -> None:
        """Wählt die Vergleichs-Ebene für den Swipe-View."""
        for key, title in self.STAGES:
            if title == choice:
                self.split_target_stage = key
                break
        self.redraw()

    def _on_split_slider_moved(self, val: float) -> None:
        """Aktualisiert die Swipe-Trennlinie bei Schieberegler-Bewegung."""
        self.split_ratio = float(val)
        self.split_pct_lbl.configure(text=f"{int(round(self.split_ratio * 100))}%")
        self.redraw()

    def copy_roi_stats(self) -> None:
        """Kopiert den aktuellen ROI-Messbefund formatiert in die Zwischenablage."""
        if not self.roi_box or not self.current_result:
            return
        x1, y1, x2, y2 = self.roi_box
        mean_txt = self.roi_stats_rows["mean"].cget("text")
        std_txt = self.roi_stats_rows["std"].cget("text")
        min_txt = self.roi_stats_rows["min"].cget("text")
        max_txt = self.roi_stats_rows["max"].cget("text")
        area_txt = self.roi_stats_rows["area"].cget("text")

        text = (
            f"IGNITE ROI-Messbefund:\n"
            f"Bereich: X={x1}..{x2}, Y={y1}..{y2} (Größe: {x2-x1}x{y2-y1} px)\n"
            f"Fläche: {area_txt}\n"
            f"Temperatur: Mittelwert {mean_txt} (Std: {std_txt}), Min: {min_txt}, Max: {max_txt}"
        )
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.copy_roi_btn.configure(text="✓ Kopiert!", fg_color=COLOR_SUCCESS)
            self.after(1500, lambda: self.copy_roi_btn.configure(text="📋 Messwerte kopieren", fg_color=COLOR_BG_CARD))
        except Exception as e:
            pass

    def _compute_line_profile(self, p1: tuple[int, int], p2: tuple[int, int]) -> None:
        """Extrahiert das 1D-Temperaturprofil entlang einer Schnittlinie und berechnet Gradienten."""
        if not self.current_result:
            return

        x1, y1 = p1
        x2, y2 = p2
        dist = float(np.hypot(x2 - x1, y2 - y1))
        if dist < 2:
            return

        num_points = max(2, int(round(dist)) + 1)
        xs = np.linspace(x1, x2, num_points)
        ys = np.linspace(y1, y2, num_points)

        raw_img = self.current_result["calibrated_original"]
        h, w = raw_img.shape[:2]

        xs_clip = np.clip(np.round(xs).astype(int), 0, w - 1)
        ys_clip = np.clip(np.round(ys).astype(int), 0, h - 1)

        px_vals = raw_img[ys_clip, xs_clip]

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)
        temps = [pixel_to_celsius(float(p), t_min, t_max) for p in px_vals]
        grads = list(np.abs(np.gradient(temps)))

        self.profile_temps = temps
        self.profile_grads = grads

        t_min_val = float(np.min(temps))
        t_max_val = float(np.max(temps))
        delta_t = t_max_val - t_min_val
        mean_t = float(np.mean(temps))
        std_t = float(np.std(temps))
        max_grad = float(np.max(grads)) if len(grads) > 0 else 0.0

        self.profile_title_lbl.configure(
            text=f"Linie: ({x1},{y1}) → ({x2},{y2})",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.profile_stats_rows["len"].configure(text=f"{dist:.1f} px")
        self.profile_stats_rows["delta"].configure(
            text=f"Δ {delta_t:.1f} °C",
            text_color=COLOR_DANGER if delta_t > 2.2 else COLOR_SUCCESS
        )
        self.profile_stats_rows["min_max"].configure(text=f"{t_min_val:.1f} / {t_max_val:.1f} °C")
        self.profile_stats_rows["mean"].configure(text=f"{mean_t:.1f} ± {std_t:.2f} °C")
        self.profile_stats_rows["grad"].configure(text=f"{max_grad:.2f} °C/px")

        self._draw_profile_plot(temps, t_min_val, t_max_val, mean_t)

    def _draw_profile_plot(self, temps: list[float], t_min_val: float, t_max_val: float, mean_t: float) -> None:
        """Zeichnet das 1D-Temperaturprofil auf den Mini-Canvas."""
        self.profile_canvas.delete("all")
        if not temps or len(temps) < 2:
            return

        cw = self.profile_canvas.winfo_width()
        ch = self.profile_canvas.winfo_height()
        if cw <= 10:
            cw = 240
        if ch <= 10:
            ch = 100

        pad_left = 32
        pad_right = 10
        pad_top = 10
        pad_bottom = 16

        pw = max(10, cw - pad_left - pad_right)
        ph = max(10, ch - pad_top - pad_bottom)

        t_range = max(0.5, t_max_val - t_min_val)
        y_min = t_min_val - 0.1 * t_range
        y_max = t_max_val + 0.1 * t_range
        y_range = max(0.5, y_max - y_min)

        def _to_canvas(idx: int, t_val: float) -> tuple[float, float]:
            cx = pad_left + (idx / (len(temps) - 1)) * pw
            cy = pad_top + ph - ((t_val - y_min) / y_range) * ph
            return cx, cy

        # Horizontale Rasterlinien
        for val, col, tag in [(t_min_val, "#334155", f"{t_min_val:.1f}"), (mean_t, "#475569", f"{mean_t:.1f}"), (t_max_val, "#334155", f"{t_max_val:.1f}")]:
            _, gy = _to_canvas(0, val)
            self.profile_canvas.create_line(pad_left, gy, pad_left + pw, gy, fill=col, dash=(2, 2))
            self.profile_canvas.create_text(pad_left - 4, gy, text=tag, fill="#94A3B8", font=("Helvetica", 7), anchor="e")

        # 1D Temperatur-Kurve zeichnen
        pts = []
        for i, t in enumerate(temps):
            pts.extend(_to_canvas(i, t))

        if len(pts) >= 4:
            self.profile_canvas.create_line(*pts, fill="#0284C7", width=2, smooth=True)

        # Max Peak Markierung
        max_idx = int(np.argmax(temps))
        mx, my = _to_canvas(max_idx, t_max_val)
        self.profile_canvas.create_oval(mx - 3, my - 3, mx + 3, my + 3, fill="#DC2626", outline="#FFFFFF", width=1)

        # X-Achsen Beschriftung
        self.profile_canvas.create_text(pad_left, ch - 6, text="A (0 px)", fill="#94A3B8", font=("Helvetica", 7), anchor="w")
        self.profile_canvas.create_text(pad_left + pw, ch - 6, text=f"B ({len(temps)-1} px)", fill="#94A3B8", font=("Helvetica", 7), anchor="e")

    def copy_profile_csv(self) -> None:
        """Kopiert das 1D-Linienprofil als CSV-Tabelle in die Zwischenablage."""
        if not self.profile_temps:
            return

        lines = ["Dist_px\tTemp_C\tGradient_C_px"]
        for i, (t, g) in enumerate(zip(self.profile_temps, self.profile_grads)):
            lines.append(f"{i}\t{t:.2f}\t{g:.3f}")
        csv_text = "\n".join(lines)

        try:
            self.clipboard_clear()
            self.clipboard_append(csv_text)
            self.copy_profile_btn.configure(text="✓ CSV Kopiert!", fg_color=COLOR_SUCCESS)
            self.after(1500, lambda: self.copy_profile_btn.configure(text="📋 Profildaten kopieren (CSV)", fg_color=COLOR_BG_CARD))
        except Exception:
            pass

    def clear_profile(self) -> None:
        """Setzt die aktive Proflinie und Messung zurück."""
        self.profile_line = None
        self.profile_drag_start = None
        self.profile_drag_current = None
        self.profile_temps = []
        self.profile_grads = []
        self.profile_canvas.delete("all")
        self.profile_title_lbl.configure(text="Linie mit Maus ziehen (A → B)", font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_MUTED)
        for lbl in self.profile_stats_rows.values():
            lbl.configure(text="--")
        self.redraw()

    def _get_stage_image(self, stage_key: str) -> np.ndarray:
        """Gibt das visualisierte BGR-Bild für die angegebene Pipeline-Stufe zurück."""
        if not self.current_result:
            return np.zeros((100, 100, 3), dtype=np.uint8)

        if self.is_isotherm_mode:
            return self._compute_isotherm_overlay()

        if stage_key == "1. Originalbild":
            return apply_colormap_to_image(self.current_result["calibrated_original"], self.palette_name)
        elif stage_key == "2. Hintergrund-Maske":
            return cv2.cvtColor(self.current_result["body_mask"], cv2.COLOR_GRAY2BGR)
        elif stage_key == "3. Lokale Hitze-Differenz":
            return cv2.cvtColor(self.current_result["heat_diff"], cv2.COLOR_GRAY2BGR)
        elif stage_key == "5. Pennes Bioheat":
            bio_res = self.current_result.get("bioheat_results", {})
            flux_mag = bio_res.get("flux_magnitude")
            if flux_mag is not None:
                norm_flux = cv2.normalize(flux_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                return apply_colormap_to_image(norm_flux, "Inferno")
            else:
                return self.current_result["overlay_bgr"]
        elif stage_key == "6. Frangi-Venen":
            frangi_map = self.current_result.get("frangi_vesselness")
            if frangi_map is not None:
                return apply_colormap_to_image(frangi_map, "Inferno")
            else:
                return self.current_result["overlay_bgr"]
        elif stage_key == "7. Bilaterale Asymmetrie":
            asym_res = self.current_result.get("bilateral_map_results", {})
            asym_map = asym_res.get("asymmetry_map")
            if asym_map is not None and asym_res.get("valid"):
                norm_asym = np.clip(asym_map / 4.0 * 255.0, 0, 255).astype(np.uint8)
                return apply_colormap_to_image(norm_asym, "Turbo")
            else:
                return self.current_result["overlay_bgr"]
        else:
            return self.current_result["overlay_bgr"]

    def _render_split_image(self, img_a: np.ndarray, img_b: np.ndarray, ratio: float) -> np.ndarray:
        """Kombiniert zwei Bilder horizontal mit einer interaktiven Swipe-Trennlinie und Grip-Handle."""
        h, w = img_a.shape[:2]
        if img_b.shape[:2] != (h, w):
            img_b = cv2.resize(img_b, (w, h), interpolation=cv2.INTER_LINEAR)

        split_x = int(np.clip(round(w * ratio), 0, w))
        merged = img_b.copy()
        if split_x > 0:
            merged[:, :split_x] = img_a[:, :split_x]

        if 0 < split_x < w:
            # Trennlinie (2px Cyan)
            cv2.line(merged, (split_x, 0), (split_x, h), (0, 230, 255), 2, cv2.LINE_AA)
            # Grip-Circle in der Bildmitte
            mid_y = h // 2
            cv2.circle(merged, (split_x, mid_y), 13, (0, 230, 255), -1, cv2.LINE_AA)
            cv2.circle(merged, (split_x, mid_y), 13, (15, 23, 42), 2, cv2.LINE_AA)
            # Grip-Pfeile
            cv2.line(merged, (split_x - 6, mid_y), (split_x - 3, mid_y - 4), (15, 23, 42), 2, cv2.LINE_AA)
            cv2.line(merged, (split_x - 6, mid_y), (split_x - 3, mid_y + 4), (15, 23, 42), 2, cv2.LINE_AA)
            cv2.line(merged, (split_x + 6, mid_y), (split_x + 3, mid_y - 4), (15, 23, 42), 2, cv2.LINE_AA)
            cv2.line(merged, (split_x + 6, mid_y), (split_x + 3, mid_y + 4), (15, 23, 42), 2, cv2.LINE_AA)

            # Badges
            cv2.putText(merged, "ORIGINAL", (max(10, split_x - 85), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(merged, "ORIGINAL", (max(10, split_x - 85), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(merged, "ANALYSE", (min(w - 85, split_x + 12), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(merged, "ANALYSE", (min(w - 85, split_x + 12), 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 230, 255), 1, cv2.LINE_AA)

        return merged

    def _on_segment_changed(self, choice: str) -> None:
        for key, title in self.STAGES:
            if title == choice:
                self.active_stage_key = key
                break
        self.redraw()

    # ── Zoom & Pan Steuerung ─────────────────────────────────────────────────
    def _on_mouse_wheel(self, event) -> None:
        if not self.current_result:
            return
        if event.delta > 0:
            self._zoom_step(1.25)
        elif event.delta < 0:
            self._zoom_step(0.8)

    def _zoom_step(self, factor: float) -> None:
        if not self.current_result:
            return
        new_zoom = float(np.clip(self.zoom_level * factor, 1.0, 8.0))
        if abs(new_zoom - self.zoom_level) > 0.01:
            self.zoom_level = new_zoom
            if self.zoom_level <= 1.01:
                self.pan_x = 0.0
                self.pan_y = 0.0
                self.zoom_badge.configure(text="100%")
            else:
                self.zoom_badge.configure(text=f"{int(round(self.zoom_level * 100))}%")
            self.redraw()

    def reset_zoom(self) -> None:
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom_badge.configure(text="100%")
        self.redraw()

    def _on_pan_start(self, event) -> None:
        if self.zoom_level > 1.0:
            self.pan_drag_start = (event.x, event.y)

    def _on_pan_drag(self, event) -> None:
        if self.pan_drag_start and self.zoom_level > 1.0 and self._rendered_pil:
            dx = event.x - self.pan_drag_start[0]
            dy = event.y - self.pan_drag_start[1]
            orig_w, orig_h = self._rendered_pil.size
            self.pan_x += dx / max(1.0, self._render_scale * self.zoom_level)
            self.pan_y += dy / max(1.0, self._render_scale * self.zoom_level)
            self.pan_drag_start = (event.x, event.y)
            self.redraw()

    def _on_pan_end(self, event) -> None:
        self.pan_drag_start = None

    def redraw(self) -> None:
        if not self.current_result:
            return

        if self.is_split_view:
            # Bild A: Kalibriertes Originalbild
            img_a = self._get_stage_image("1. Originalbild")
            # Bild B: Ausgewähltes Analyse-Vergleichsbild
            img_b = self._get_stage_image(self.split_target_stage)
            raw = self._render_split_image(img_a, img_b, self.split_ratio)
        else:
            raw = self._get_stage_image(self.active_stage_key)

        img_to_show = raw.copy()

        # ROI / Linienprofil Overlay zeichnen (nur im Stufen- und Linienprofil-Modus)
        if not self.is_split_view:
            if self.is_profile_mode:
                p1, p2 = None, None
                if self.profile_line:
                    p1, p2 = self.profile_line
                elif self.profile_drag_start and self.profile_drag_current:
                    p1, p2 = self.profile_drag_start, self.profile_drag_current

                if p1 and p2:
                    cv2.line(img_to_show, p1, p2, (0, 230, 255), 2, cv2.LINE_AA)
                    cv2.circle(img_to_show, p1, 5, (0, 255, 0), -1, cv2.LINE_AA)
                    cv2.circle(img_to_show, p1, 5, (15, 23, 42), 1, cv2.LINE_AA)
                    cv2.putText(img_to_show, "A", (p1[0] + 6, p1[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2, cv2.LINE_AA)
                    cv2.circle(img_to_show, p2, 5, (0, 0, 255), -1, cv2.LINE_AA)
                    cv2.circle(img_to_show, p2, 5, (15, 23, 42), 1, cv2.LINE_AA)
                    cv2.putText(img_to_show, "B", (p2[0] + 6, p2[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2, cv2.LINE_AA)
            else:
                if self.roi_box:
                    x1, y1, x2, y2 = self.roi_box
                    cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (255, 255, 0), 2)
                elif self.roi_drag_start and self.roi_drag_current:
                    x1, x2 = sorted([self.roi_drag_start[0], self.roi_drag_current[0]])
                    y1, y2 = sorted([self.roi_drag_start[1], self.roi_drag_current[1]])
                    cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (0, 255, 255), 1)

        rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
        full_pil = Image.fromarray(rgb)
        self._rendered_pil = full_pil

        orig_w, orig_h = full_pil.size

        # Zoom & Pan Crop berechnen
        if self.zoom_level > 1.0:
            view_w = max(10, int(round(orig_w / self.zoom_level)))
            view_h = max(10, int(round(orig_h / self.zoom_level)))

            max_pan_x = (orig_w - view_w) / 2.0
            max_pan_y = (orig_h - view_h) / 2.0
            self.pan_x = float(np.clip(self.pan_x, -max_pan_x, max_pan_x))
            self.pan_y = float(np.clip(self.pan_y, -max_pan_y, max_pan_y))

            center_x = orig_w / 2.0 - self.pan_x
            center_y = orig_h / 2.0 - self.pan_y

            crop_x1 = int(np.clip(round(center_x - view_w / 2.0), 0, orig_w - view_w))
            crop_y1 = int(np.clip(round(center_y - view_h / 2.0), 0, orig_h - view_h))
            crop_x2 = crop_x1 + view_w
            crop_y2 = crop_y1 + view_h

            self._visible_crop = (crop_x1, crop_y1, crop_x2, crop_y2)
            display_pil = full_pil.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        else:
            self._visible_crop = (0, 0, orig_w, orig_h)
            display_pil = full_pil

        self.img_lbl.update_idletasks()
        w = max(self.img_lbl.winfo_width() - 16, 300)
        h = max(self.img_lbl.winfo_height() - 16, 200)

        crop_w, crop_h = display_pil.size
        ratio = min(w / crop_w, h / crop_h)
        self._render_scale = ratio
        disp_w = max(1, int(crop_w * ratio))
        disp_h = max(1, int(crop_h * ratio))

        self._offset_x = (self.img_lbl.winfo_width() - disp_w) // 2
        self._offset_y = (self.img_lbl.winfo_height() - disp_h) // 2

        ctk_img = make_display_ctk_image(display_pil, w, h)
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img

    def save_snapshot(self) -> None:
        if not self._rendered_pil:
            return
        p = filedialog.asksaveasfilename(
            title="Snapshot speichern",
            defaultextension=".png",
            filetypes=[("PNG Bild", "*.png"), ("JPEG Bild", "*.jpg")]
        )
        if p:
            self._rendered_pil.save(p)

    def _event_to_img_coords(self, event) -> Optional[tuple[int, int]]:
        if not self.current_result or not self._rendered_pil:
            return None

        mx = event.x - self._offset_x
        my = event.y - self._offset_y

        crop_x1, crop_y1, crop_x2, crop_y2 = self._visible_crop
        crop_w = crop_x2 - crop_x1
        crop_h = crop_y2 - crop_y1

        disp_w = crop_w * self._render_scale
        disp_h = crop_h * self._render_scale

        if 0 <= mx < disp_w and 0 <= my < disp_h:
            local_x = int(mx / self._render_scale)
            local_y = int(my / self._render_scale)
            full_x = crop_x1 + local_x
            full_y = crop_y1 + local_y
            orig_w, orig_h = self._rendered_pil.size
            return min(max(full_x, 0), orig_w - 1), min(max(full_y, 0), orig_h - 1)
        return None

    def _on_mouse_move(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if not coords or not self.current_result:
            return

        x, y = coords
        raw_val = self.current_result["calibrated_original"][y, x]
        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)
        temp_c = pixel_to_celsius(raw_val, t_min, t_max)

        is_hotspot = self.current_result["hotspot_mask"][y, x] > 0
        is_body = self.current_result["body_mask"][y, x] > 0

        self.live_temp_lbl.configure(text=f"{temp_c:.1f} °C")
        self.live_coord_lbl.configure(text=f"Koordinaten: X={x}, Y={y} (px={raw_val})")

        if is_hotspot:
            self.live_status_lbl.configure(text="Befund: Hyperthermie / Hotspot", text_color=COLOR_DANGER)
        elif is_body:
            self.live_status_lbl.configure(text="Befund: Physiologisches Gewebe", text_color=COLOR_SUCCESS)
        else:
            self.live_status_lbl.configure(text="Befund: Hintergrund / Umfeld", text_color=COLOR_TEXT_MUTED)

    def _on_mouse_leave(self, event) -> None:
        self.live_temp_lbl.configure(text="--.- °C")
        self.live_coord_lbl.configure(text="Koordinaten: X=--, Y=--")
        self.live_status_lbl.configure(text="Befund: Cursor über Bild bewegen", text_color=COLOR_TEXT_MUTED)

    def _on_mouse_down(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if not coords:
            return

        if self.is_split_view:
            if self._rendered_pil:
                orig_w, _ = self._rendered_pil.size
                self.split_ratio = float(np.clip(coords[0] / max(1, orig_w), 0.0, 1.0))
                self.split_slider.set(self.split_ratio)
                self.split_pct_lbl.configure(text=f"{int(round(self.split_ratio * 100))}%")
                self.redraw()
            return

        if self.is_profile_mode:
            self.profile_drag_start = coords
            self.profile_drag_current = coords
            self.profile_line = None
            return

        self.roi_drag_start = coords
        self.roi_drag_current = coords
        self.roi_box = None

    def _on_mouse_drag(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if not coords:
            return

        if self.is_split_view:
            if self._rendered_pil:
                orig_w, _ = self._rendered_pil.size
                self.split_ratio = float(np.clip(coords[0] / max(1, orig_w), 0.0, 1.0))
                self.split_slider.set(self.split_ratio)
                self.split_pct_lbl.configure(text=f"{int(round(self.split_ratio * 100))}%")
                self.redraw()
            return

        if self.is_profile_mode:
            if coords and self.profile_drag_start:
                self.profile_drag_current = coords
                self._compute_line_profile(self.profile_drag_start, coords)
                self.redraw()
            return

        if coords and self.roi_drag_start:
            self.roi_drag_current = coords
            self.redraw()

    def _on_mouse_up(self, event) -> None:
        if self.is_split_view:
            return

        coords = self._event_to_img_coords(event)
        if self.is_profile_mode:
            if coords and self.profile_drag_start:
                p1 = self.profile_drag_start
                p2 = coords
                dist = np.hypot(p2[0] - p1[0], p2[1] - p1[1])
                if dist >= 3:
                    self.profile_line = (p1, p2)
                    self._compute_line_profile(p1, p2)
                else:
                    self.clear_profile()
                self.profile_drag_start = None
                self.profile_drag_current = None
                self.redraw()
            return

        if coords and self.roi_drag_start:
            x1, x2 = sorted([self.roi_drag_start[0], coords[0]])
            y1, y2 = sorted([self.roi_drag_start[1], coords[1]])

            if (x2 - x1) >= 3 and (y2 - y1) >= 3:
                self.roi_box = (x1, y1, x2, y2)
                self._compute_roi_stats(x1, y1, x2, y2)
            else:
                self.clear_roi()

            self.roi_drag_start = None
            self.roi_drag_current = None
            self.redraw()

    def _compute_roi_stats(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if not self.current_result:
            return

        raw_img = self.current_result["calibrated_original"]
        roi_px = raw_img[y1:y2, x1:x2]

        if len(roi_px) == 0:
            return

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)

        mean_px = float(np.mean(roi_px))
        std_px = float(np.std(roi_px))
        min_px = float(np.min(roi_px))
        max_px = float(np.max(roi_px))

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        min_c = pixel_to_celsius(min_px, t_min, t_max)
        max_c = pixel_to_celsius(max_px, t_min, t_max)
        area_px = (x2 - x1) * (y2 - y1)

        self.roi_title_lbl.configure(text=f"Auswahl: {x2-x1}x{y2-y1} px", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        self.roi_stats_rows["mean"].configure(text=f"{mean_c:.2f} °C")
        self.roi_stats_rows["std"].configure(text=f"±{std_c:.2f} °C")
        self.roi_stats_rows["min"].configure(text=f"{min_c:.1f} °C")
        self.roi_stats_rows["max"].configure(text=f"{max_c:.1f} °C")
        self.roi_stats_rows["area"].configure(text=f"{area_px:,} px")

    def reset_measurement(self) -> None:
        """Setzt die aktive Messung (ROI oder Linienprofil) zurück."""
        if self.is_profile_mode:
            self.clear_profile()
        else:
            self.clear_roi()

    def clear_roi(self) -> None:
        self.roi_box = None
        self.roi_drag_start = None
        self.roi_drag_current = None
        self.roi_title_lbl.configure(text="Rechteck mit Maus aufziehen", font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_MUTED)
        for lbl in self.roi_stats_rows.values():
            lbl.configure(text="--")
        self.redraw()
