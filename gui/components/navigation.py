# -*- coding: utf-8 -*-
"""gui/components/navigation.py – High-Contrast Workstation Navigation Rail for IGNITE."""

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
    COLOR_CONTAINER_ACTIVE,
    COLOR_BG_CARD_HOVER,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)


class NavigationRail(ctk.CTkFrame):
    """Präzise Workstation-Navigationsleiste am linken Fensterrand."""

    NAV_ITEMS = [
        ("dashboard", "Dashboard",     "📊", "Ctrl+1"),
        ("single",    "Inspektion",    "🔬", "Ctrl+2"),
        ("analytics", "Statistik",     "📈", "Ctrl+3"),
        ("podology",  "Podologie",     "🦶", "Ctrl+4"),
        ("batch",     "Serienanalyse", "📁", "Ctrl+5"),
        ("settings",  "Einstellungen", "⚙️", "Ctrl+6"),
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
            width=230,
            corner_radius=0,
            fg_color=COLOR_BG_NAV,
            border_width=0,
            **kwargs
        )
        self.pack_propagate(False)

        self.on_nav_change = on_nav_change
        self.on_export_report = on_export_report
        self.current_tab: str = "dashboard"
        self._buttons: dict[str, tuple[ctk.CTkFrame, ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # Rechte Begrenzungslinie
        divider = ctk.CTkFrame(self, width=1, fg_color=COLOR_OUTLINE_VARIANT)
        divider.pack(side=ctk.RIGHT, fill=ctk.Y)

        # Navigations-Container
        nav_container = ctk.CTkFrame(self, fg_color="transparent")
        nav_container.pack(fill=ctk.BOTH, expand=True, padx=12, pady=16)

        # Nav-Header Label
        ctk.CTkLabel(
            nav_container,
            text="ANSICHTEN",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            height=20,
            anchor="w"
        ).pack(fill=ctk.X, padx=8, pady=(0, 10))

        # Nav-Items generieren (Klares Einzeilen-Layout mit Icons & Shortcuts)
        for key, title, icon, shortcut in self.NAV_ITEMS:
            btn_frame = ctk.CTkFrame(
                nav_container,
                corner_radius=RADIUS_BUTTON,
                fg_color="transparent",
                height=38,
                cursor="hand2"
            )
            btn_frame.pack(fill=ctk.X, pady=2)
            btn_frame.pack_propagate(False)

            content_box = ctk.CTkFrame(btn_frame, fg_color="transparent")
            content_box.pack(fill=ctk.BOTH, expand=True, padx=6, pady=4)

            # Subtiler linker Indikatorbalken
            ind_bar = ctk.CTkFrame(content_box, width=3, corner_radius=2, fg_color="transparent")
            ind_bar.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 8), pady=2)

            # Icon
            lbl_icon = ctk.CTkLabel(
                content_box,
                text=icon,
                font=ctk.CTkFont(size=13),
                width=20
            )
            lbl_icon.pack(side=ctk.LEFT, padx=(0, 6))

            # Titel
            lbl_title = ctk.CTkLabel(
                content_box,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=COLOR_TEXT_SECONDARY,
                height=22,
                anchor="w"
            )
            lbl_title.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            # Shortcut-Pill
            lbl_shortcut = ctk.CTkLabel(
                content_box,
                text=shortcut,
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=9),
                text_color=COLOR_TEXT_MUTED,
                height=18
            )
            lbl_shortcut.pack(side=ctk.RIGHT, padx=(2, 4))

            # Hover- & Klick-Handler
            _k = key
            for w in [btn_frame, content_box, ind_bar, lbl_icon, lbl_title, lbl_shortcut]:
                w.bind("<Button-1>", lambda e, k=_k: self.select_tab(k))
                w.bind("<Enter>", lambda e, k=_k: self._on_hover(k, True))
                w.bind("<Leave>", lambda e, k=_k: self._on_hover(k, False))

            self._buttons[key] = (btn_frame, ind_bar, lbl_title, lbl_shortcut)

        # Unten: Schnell-Aktionen & Status
        bottom_box = ctk.CTkFrame(nav_container, fg_color="transparent")
        bottom_box.pack(side=ctk.BOTTOM, fill=ctk.X, pady=(10, 0))

        self.export_btn = ctk.CTkButton(
            bottom_box,
            text="📄 Bericht exportieren (Ctrl+E)",
            command=self.on_export_report,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=36
        )
        self.export_btn.pack(fill=ctk.X, pady=(0, 8))

        # Status Label unten
        self.file_status_lbl = ctk.CTkLabel(
            bottom_box,
            text="Keine Datei geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED,
            height=16,
            anchor="w",
            wraplength=190
        )
        self.file_status_lbl.pack(fill=ctk.X, padx=4)

        self.select_tab("dashboard", notify=False)

    def _on_hover(self, key: str, is_hovering: bool) -> None:
        if key == self.current_tab:
            return
        frame, _, _, _ = self._buttons[key]
        frame.configure(fg_color=COLOR_BG_CARD_HOVER if is_hovering else "transparent")

    def select_tab(self, key: str, notify: bool = True) -> None:
        self.current_tab = key
        for k, (frame, ind_bar, title_lbl, shortcut_lbl) in self._buttons.items():
            if k == key:
                frame.configure(fg_color=COLOR_CONTAINER_ACTIVE)
                ind_bar.configure(fg_color=COLOR_PRIMARY)
                title_lbl.configure(text_color=COLOR_TEXT_PRIMARY)
                shortcut_lbl.configure(text_color=COLOR_PRIMARY)
            else:
                frame.configure(fg_color="transparent")
                ind_bar.configure(fg_color="transparent")
                title_lbl.configure(text_color=COLOR_TEXT_SECONDARY)
                shortcut_lbl.configure(text_color=COLOR_TEXT_MUTED)

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
