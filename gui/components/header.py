# -*- coding: utf-8 -*-
"""gui/components/header.py – High-Contrast Clinical Workstation Top Bar for IGNITE."""

from __future__ import annotations
import os
import customtkinter as ctk
from PIL import Image

from gui.theme import (
    COLOR_BG_NAV,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_BG_INPUT,
    COLOR_BG_INPUT_HOVER,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_BUTTON,
    RADIUS_BADGE,
    BACKEND_STYLES,
)
from utils import get_resource_path
import config
import image_processing


class TopAppBar(ctk.CTkFrame):
    """Präzise Workstation-Kopfzeile am oberen Fensterrand."""

    def __init__(
        self,
        master,
        on_load_click,
        on_search_click,
        on_theme_click,
        on_info_click,
        **kwargs
    ) -> None:
        super().__init__(
            master,
            height=60,
            corner_radius=0,
            fg_color=COLOR_BG_NAV,
            border_width=0,
            **kwargs
        )
        self.pack_propagate(False)

        self.on_load_click = on_load_click
        self.on_search_click = on_search_click
        self.on_theme_click = on_theme_click
        self.on_info_click = on_info_click

        self._build_ui()

    def _build_ui(self) -> None:
        # Linker Bereich: Logo & App-Titel
        left_box = ctk.CTkFrame(self, fg_color="transparent")
        left_box.pack(side=ctk.LEFT, padx=(18, 12), pady=8)

        logo_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        if os.path.exists(logo_path):
            try:
                logo_pil = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(28, 28))
                lbl_logo = ctk.CTkLabel(left_box, image=logo_ctk, text="")
                lbl_logo.pack(side=ctk.LEFT, padx=(0, 10))
            except Exception:
                pass

        title_col = ctk.CTkFrame(left_box, fg_color="transparent")
        title_col.pack(side=ctk.LEFT)

        title_row = ctk.CTkFrame(title_col, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="IGNITE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            title_row,
            text=f" v{config.APP_VERSION} ",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_BG_CARD_VARIANT,
            corner_radius=RADIUS_BADGE,
            height=20
        ).pack(side=ctk.LEFT, padx=(6, 0))

        ctk.CTkLabel(
            title_col,
            text="Medical Imaging Suite · Jugend forscht 2026",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(1, 0))

        # Rechter Bereich: Backend Badge + Suchfeld + Theme + Help + Primary Action
        right_box = ctk.CTkFrame(self, fg_color="transparent")
        right_box.pack(side=ctk.RIGHT, padx=(12, 18), pady=10)

        # 1. Backend Status Chip (Kompakt, technisch)
        self.backend_chip = ctk.CTkFrame(
            right_box,
            fg_color=COLOR_BG_CARD_VARIANT,
            corner_radius=RADIUS_BADGE,
            border_width=1,
            border_color=COLOR_OUTLINE,
            height=34
        )
        self.backend_chip.pack(side=ctk.LEFT, padx=(0, 10))

        self.backend_dot = ctk.CTkFrame(
            self.backend_chip,
            width=8,
            height=8,
            corner_radius=4,
            fg_color=COLOR_PRIMARY
        )
        self.backend_dot.pack(side=ctk.LEFT, padx=(10, 6), pady=4)

        self.backend_lbl = ctk.CTkLabel(
            self.backend_chip,
            text="CUDA GPU Core",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.backend_lbl.pack(side=ctk.LEFT, padx=(0, 12), pady=4)

        # 2. Command Search Button
        self.search_btn = ctk.CTkButton(
            right_box,
            text="🔍 Befehle… (Ctrl+K)",
            command=self.on_search_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=190
        )
        self.search_btn.pack(side=ctk.LEFT, padx=(0, 8))

        # 3. Theme Toggle Button
        self.theme_btn = ctk.CTkButton(
            right_box,
            text="🌓 Design",
            command=self.on_theme_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=76
        )
        self.theme_btn.pack(side=ctk.LEFT, padx=(0, 8))

        # 4. Info / Help Button
        self.info_btn = ctk.CTkButton(
            right_box,
            text="ℹ️ Info",
            command=self.on_info_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=62
        )
        self.info_btn.pack(side=ctk.LEFT, padx=(0, 10))

        # 5. Primary Action Button
        self.load_btn = ctk.CTkButton(
            right_box,
            text="📂 Bild öffnen",
            command=self.on_load_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=135
        )
        self.load_btn.pack(side=ctk.LEFT)

        # Untere Trennlinie
        divider = ctk.CTkFrame(self, height=1, fg_color=COLOR_OUTLINE_VARIANT)
        divider.pack(side=ctk.BOTTOM, fill=ctk.X)

        self.update_backend_badge()

    def update_backend_badge(self) -> None:
        backend_name = image_processing.get_active_backend()
        if "GPU" in backend_name:
            style = BACKEND_STYLES["GPU"]
        elif "Rust" in backend_name:
            style = BACKEND_STYLES["RUST"]
        else:
            style = BACKEND_STYLES["PYTHON"]

        self.backend_lbl.configure(text=style["label"])
        self.backend_dot.configure(fg_color=style["dot"])
        self.backend_chip.configure(fg_color=style["bg"])
