# -*- coding: utf-8 -*-
"""gui/components/navigation.py – Google Material 3 / Material You Navigation Rail for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable
import customtkinter as ctk

from gui.theme import (
    COLOR_BG_NAV,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_CONTAINER_BLUE,
    COLOR_BG_CARD_HOVER,
    FONT_FAMILY,
)


class NavigationRail(ctk.CTkFrame):
    """Google Material You Navigations-Leiste (Links)."""

    NAV_ITEMS = [
        ("dashboard", "📊", "Dashboard",     "4-Stufen Übersicht"),
        ("single",    "🔍", "Inspektion",    "ROI- & Pixelanalyse"),
        ("analytics", "📈", "Statistik",     "Histogramm & Herde"),
        ("podology",  "🦶", "Podologie",     "3-Zonen Symmetrie"),
        ("batch",     "📁", "Stapelanalyse", "Serienuntersuchung"),
        ("settings",  "⚙️", "Einstellungen", "Parameter & Setup"),
    ]

    def __init__(
        self,
        master,
        on_nav_change: Callable[[str], None],
        on_export_report: Callable[[], None],
        **kwargs
    ) -> None:
        super().__init__(
            master,
            width=300,
            corner_radius=0,
            fg_color=COLOR_BG_NAV,
            border_width=0,
            **kwargs
        )
        self.pack_propagate(False)

        self.on_nav_change = on_nav_change
        self.on_export_report = on_export_report
        self.current_tab: str = "dashboard"
        self._buttons: dict[str, tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel, ctk.CTkLabel]] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # Rechte Begrenzungslinie
        divider = ctk.CTkFrame(self, width=1, fg_color=COLOR_OUTLINE_VARIANT)
        divider.pack(side=ctk.RIGHT, fill=ctk.Y)

        # Navigations-Container
        nav_container = ctk.CTkFrame(self, fg_color="transparent")
        nav_container.pack(fill=ctk.BOTH, expand=True, padx=14, pady=18)

        # Nav-Header Label
        ctk.CTkLabel(
            nav_container,
            text="NAVIGATION",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=16, pady=(2, 10))

        # Nav-Items generieren
        for key, icon, title, subtitle in self.NAV_ITEMS:
            btn_frame = ctk.CTkFrame(
                nav_container,
                corner_radius=28,
                fg_color="transparent",
                height=54,
                cursor="hand2"
            )
            btn_frame.pack(fill=ctk.X, pady=3)
            btn_frame.pack_propagate(False)

            content_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
            content_box.pack(fill=ctk.BOTH, expand=True, padx=16, pady=4)

            lbl_icon = ctk.CTkLabel(
                content_box,
                text=icon,
                font=ctk.CTkFont(family=FONT_FAMILY, size=18),
                text_color=COLOR_TEXT_SECONDARY,
                width=30
            )
            lbl_icon.pack(side=ctk.LEFT, padx=(0, 10))

            text_col = ctk.CTkFrame(content_box, fg_color="transparent")
            text_col.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            lbl_title = ctk.CTkLabel(
                text_col,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_title.pack(fill=ctk.X)

            lbl_sub = ctk.CTkLabel(
                text_col,
                text=subtitle,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            )
            lbl_sub.pack(fill=ctk.X)

            # Klick-Handler
            _k = key
            for w in [btn_frame, content_box, lbl_icon, text_col, lbl_title, lbl_sub]:
                w.bind("<Button-1>", lambda e, k=_k: self.select_tab(k))

            self._buttons[key] = (btn_frame, lbl_icon, lbl_title, lbl_sub)

        # Unten: Schnell-Aktionen
        bottom_box = ctk.CTkFrame(nav_container, fg_color="transparent")
        bottom_box.pack(side=ctk.BOTTOM, fill=ctk.X, pady=(12, 0))

        self.export_btn = ctk.CTkButton(
            bottom_box,
            text="📄  Bericht exportieren",
            command=self.on_export_report,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_CONTAINER_BLUE,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_PRIMARY,
            corner_radius=22,
            height=44
        )
        self.export_btn.pack(fill=ctk.X, pady=(0, 10))

        # Status Label unten
        self.file_status_lbl = ctk.CTkLabel(
            bottom_box,
            text="Keine Datei geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, slant="italic"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=260
        )
        self.file_status_lbl.pack(fill=ctk.X, padx=6)

        self.select_tab("dashboard", notify=False)

    def select_tab(self, key: str, notify: bool = True) -> None:
        self.current_tab = key
        for k, (frame, icon_lbl, title_lbl, sub_lbl) in self._buttons.items():
            if k == key:
                frame.configure(fg_color=COLOR_CONTAINER_BLUE)
                icon_lbl.configure(text_color=COLOR_PRIMARY)
                title_lbl.configure(text_color=COLOR_PRIMARY)
                sub_lbl.configure(text_color=COLOR_PRIMARY)
            else:
                frame.configure(fg_color="transparent")
                icon_lbl.configure(text_color=COLOR_TEXT_SECONDARY)
                title_lbl.configure(text_color=COLOR_TEXT_PRIMARY)
                sub_lbl.configure(text_color=COLOR_TEXT_MUTED)

        if notify and self.on_nav_change:
            self.on_nav_change(key)

    def update_loaded_file(self, filename: str | None) -> None:
        if filename:
            self.file_status_lbl.configure(
                text=f"Aktiv: {filename}",
                text_color=COLOR_TEXT_SECONDARY
            )
        else:
            self.file_status_lbl.configure(
                text="Keine Datei geladen",
                text_color=COLOR_TEXT_MUTED
            )
