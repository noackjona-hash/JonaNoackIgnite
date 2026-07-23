# -*- coding: utf-8 -*-
"""dashboard.py – 4-Panel Grid Dashboard View for IGNITE."""

import customtkinter as ctk
from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_BG_MAIN,
    FONT_FAMILY
)

class DashboardView:
    """Verwaltet das 4-Panel Grid-Layout (Originalbild, Hintergrund-Maske, Hitze-Differenz, Hotspots)."""

    def __init__(self, master_tab, hover_callback, leave_callback, roi_start_callback, roi_drag_callback, roi_end_callback):
        self.master_tab = master_tab
        self.panels: dict[str, ctk.CTkLabel] = {}
        self.panels_full: dict[str, ctk.CTkLabel] = {}

        self._build_grid_tab(hover_callback, leave_callback, roi_start_callback, roi_drag_callback, roi_end_callback)

    def _build_grid_tab(self, hover_cb, leave_cb, roi_start_cb, roi_drag_cb, roi_end_cb):
        grid_frame = ctk.CTkFrame(self.master_tab, fg_color="transparent")
        grid_frame.pack(fill=ctk.BOTH, expand=True)

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)

        steps = [
            ("1. Originalbild",              0, 0),
            ("2. Hintergrund-Maske",         0, 1),
            ("3. Lokale Hitze-Differenz",    1, 0),
            ("4. Erkannte Hotspots (Rust)",  1, 1),
        ]

        for name, row, col in steps:
            panel_frame = ctk.CTkFrame(
                grid_frame,
                fg_color=COLOR_BG_CARD,
                corner_radius=12,
                border_width=1,
                border_color=COLOR_BORDER_CARD
            )
            panel_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            title = ctk.CTkLabel(
                panel_frame,
                text=name,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=15, pady=(12, 4))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="\n🌡️\n\nBEREIT FÜR ANALYSE\n\nBitte laden Sie ein Wärmebild über die Seitenleiste.\n",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_MUTED,
                fg_color=COLOR_BG_MAIN,
                corner_radius=8
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))
            self.panels[name] = lbl

            # Event Bindings
            lbl.bind("<Motion>", lambda e, n=name, is_grid=True: hover_cb(e, n, is_grid))
            lbl.bind("<Leave>", leave_cb)
            lbl.bind("<ButtonPress-1>", lambda e, n=name, is_grid=True: roi_start_cb(e, n, is_grid))
            lbl.bind("<B1-Motion>", lambda e, n=name, is_grid=True: roi_drag_cb(e, n, is_grid))
            lbl.bind("<ButtonRelease-1>", lambda e, n=name, is_grid=True: roi_end_cb(e, n, is_grid))

    def setup_fullsize_tabs(self, tabview, hover_cb, leave_cb, roi_start_cb, roi_drag_cb, roi_end_cb):
        tab_mapping = {
            "1. Originalbild": "1. Originalbild",
            "2. Hintergrund-Maske": "2. Hintergrund-Maske",
            "3. Lokale Hitze-Differenz": "3. Lokale Hitze-Differenz",
            "4. Erkannte Hotspots (Rust)": "4. Erkannte Hotspots"
        }

        for step_name, tab_name in tab_mapping.items():
            panel_frame = ctk.CTkFrame(
                tabview.tab(tab_name),
                fg_color=COLOR_BG_CARD,
                corner_radius=12,
                border_width=1,
                border_color=COLOR_BORDER_CARD
            )
            panel_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

            title = ctk.CTkLabel(
                panel_frame,
                text=step_name,
                font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=20, pady=(15, 5))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="\n\n🌡️\n\nNoch kein Wärmebild geladen.\n\nBitte laden Sie eine Bilddatei über die linke Seitenleiste.\n",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=COLOR_TEXT_MUTED,
                fg_color=COLOR_BG_MAIN,
                corner_radius=8
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
            self.panels_full[step_name] = lbl

            # Event Bindings
            lbl.bind("<Motion>", lambda e, n=step_name, is_grid=False: hover_cb(e, n, is_grid))
            lbl.bind("<Leave>", leave_cb)
            lbl.bind("<ButtonPress-1>", lambda e, n=step_name, is_grid=False: roi_start_cb(e, n, is_grid))
            lbl.bind("<B1-Motion>", lambda e, n=step_name, is_grid=False: roi_drag_cb(e, n, is_grid))
            lbl.bind("<ButtonRelease-1>", lambda e, n=step_name, is_grid=False: roi_end_cb(e, n, is_grid))
