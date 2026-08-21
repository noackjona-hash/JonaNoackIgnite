# -*- coding: utf-8 -*-
"""gui/components/header.py – Google Material 3 / Material You Top App Bar for IGNITE."""

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
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    BACKEND_STYLES,
)
from utils import get_resource_path
import image_processing


class TopAppBar(ctk.CTkFrame):
    """Google Material You App Bar am oberen Fensterrand."""

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
            height=76,
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
        left_box.pack(side=ctk.LEFT, padx=(24, 16), pady=8)

        logo_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        if os.path.exists(logo_path):
            try:
                logo_pil = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(36, 36))
                lbl_logo = ctk.CTkLabel(left_box, image=logo_ctk, text="")
                lbl_logo.pack(side=ctk.LEFT, padx=(0, 14))
            except Exception:
                pass

        title_col = ctk.CTkFrame(left_box, fg_color="transparent")
        title_col.pack(side=ctk.LEFT)

        title_row = ctk.CTkFrame(title_col, fg_color="transparent")
        title_row.pack(anchor="w")

        ctk.CTkLabel(
            title_row,
            text="IGNITE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            title_row,
            text=" v3.2 ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_PRIMARY,
            fg_color=COLOR_CONTAINER_BLUE,
            corner_radius=10,
            height=22
        ).pack(side=ctk.LEFT, padx=(8, 0))

        ctk.CTkLabel(
            title_col,
            text="Medical Imaging Suite  ·  Jugend forscht 2026",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(2, 0))

        # Rechter Bereich: Backend Badge + Suchfeld + Theme + Help + Primary FAB
        right_box = ctk.CTkFrame(self, fg_color="transparent")
        right_box.pack(side=ctk.RIGHT, padx=(16, 24), pady=12)

        # 1. Backend Status Pill
        self.backend_chip = ctk.CTkFrame(
            right_box,
            fg_color=COLOR_CONTAINER_BLUE,
            corner_radius=22,
            height=44
        )
        self.backend_chip.pack(side=ctk.LEFT, padx=(0, 12))

        self.backend_dot = ctk.CTkFrame(
            self.backend_chip,
            width=10,
            height=10,
            corner_radius=5,
            fg_color=COLOR_PRIMARY
        )
        self.backend_dot.pack(side=ctk.LEFT, padx=(14, 8), pady=4)

        self.backend_lbl = ctk.CTkLabel(
            self.backend_chip,
            text="GPU CUDA Engine",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.backend_lbl.pack(side=ctk.LEFT, padx=(0, 16), pady=4)

        # 2. Google Search Style Command Button
        self.search_btn = ctk.CTkButton(
            right_box,
            text="⌕  Befehle suchen… (Ctrl+K)",
            command=self.on_search_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_SECONDARY,
            corner_radius=22,
            height=44,
            width=230
        )
        self.search_btn.pack(side=ctk.LEFT, padx=(0, 12))

        # 3. Theme Toggle Button
        self.theme_btn = ctk.CTkButton(
            right_box,
            text="🌓",
            command=self.on_theme_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=22,
            height=44,
            width=44
        )
        self.theme_btn.pack(side=ctk.LEFT, padx=(0, 10))

        # 4. Info / Help Button
        self.info_btn = ctk.CTkButton(
            right_box,
            text="?",
            command=self.on_info_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            fg_color=COLOR_BG_INPUT,
            hover_color=COLOR_BG_INPUT_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=22,
            height=44,
            width=44
        )
        self.info_btn.pack(side=ctk.LEFT, padx=(0, 14))

        # 5. Primary Google Blue Action FAB Button
        self.load_btn = ctk.CTkButton(
            right_box,
            text="+  Wärmebild öffnen",
            command=self.on_load_click,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=22,
            height=44,
            width=190
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
