# -*- coding: utf-8 -*-
"""analysis.py – Analysis Tab Views (Histogram, Zonal, Detail Table, Batch) for IGNITE."""

import customtkinter as ctk
import numpy as np
import cv2

# Matplotlib Integration
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY_ACCENT,
    COLOR_BG_MAIN,
    FONT_FAMILY
)

class AnalysisView:
    """Verwaltet die Analyse-Tabs (Histogramm, Zonal-Analyse, Detail-Statistiken, Batch)."""

    def __init__(self, tabview: ctk.CTkTabview):
        self.tabview = tabview

        # References for Histogram & Stats
        self.title_hist = None
        self.hist_container = None
        self.stats_labels = {}
        self.stats_title_labels = {}
        self.stats_divider_label = None

        # References for Detail Tab
        self.detail_panel = None
        self.detail_title = None
        self.detail_content_frame = None

        self._setup_tabs()

    def _setup_tabs(self):
        # ── TAB 5: Temperatur-Verteilung ─────────────────────────────────────
        hist_tab = self.tabview.tab("5. Temperatur-Verteilung")
        hist_tab.grid_columnconfigure(0, weight=3)
        hist_tab.grid_columnconfigure(1, weight=1)
        hist_tab.grid_rowconfigure(0, weight=1)

        canvas_panel = ctk.CTkFrame(
            hist_tab,
            fg_color=COLOR_BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        canvas_panel.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.title_hist = ctk.CTkLabel(
            canvas_panel,
            text="Statistisches Intensitätshistogramm",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.title_hist.pack(fill=ctk.X, padx=20, pady=(15, 5))

        self.hist_container = ctk.CTkFrame(canvas_panel, fg_color=COLOR_BG_MAIN, corner_radius=6)
        self.hist_container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Stats Sidebar inside Tab
        stats_panel = ctk.CTkFrame(
            hist_tab,
            fg_color=COLOR_BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        stats_panel.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        title_stats = ctk.CTkLabel(
            stats_panel,
            text="MESSWERTE & STATISTIK",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT,
            anchor="w"
        )
        title_stats.pack(fill=ctk.X, padx=15, pady=(15, 10))

        stat_items = [
            ("Fußoberfläche (Pixel)", "pixel_count"),
            ("Mittelwert Fußhitze (µ)", "mean"),
            ("Standardabweichung (σ)", "std"),
            ("Hotspot-Grenze (µ + k*σ)", "threshold"),
            ("Maximaler Hitzewert", "max_val"),
            ("Hotspot-Pixel", "hotspots"),
            ("Prozentualer Anteil", "percentage"),
            ("---------------------------------", "divider"),
            ("Mittelwert Links (L)", "mean_left"),
            ("Mittelwert Rechts (R)", "mean_right"),
            ("Symmetrie-Delta (Δ)", "delta"),
            ("Symmetriestatus", "status_symmetry")
        ]

        for display_name, key in stat_items:
            if key == "divider":
                self.stats_divider_label = ctk.CTkLabel(
                    stats_panel,
                    text="KLINISCHE SYMMETRIE (L/R)",
                    font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
                    text_color=COLOR_PRIMARY_ACCENT,
                    anchor="w"
                )
                self.stats_divider_label.pack(fill=ctk.X, padx=15, pady=(15, 2))
                continue

            lbl_title = ctk.CTkLabel(
                stats_panel,
                text=display_name,
                font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w"
            )
            lbl_title.pack(fill=ctk.X, padx=15, pady=(6, 1))
            self.stats_title_labels[key] = lbl_title

            lbl_val = ctk.CTkLabel(
                stats_panel,
                text="--",
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, padx=15, pady=(0, 6))
            self.stats_labels[key] = lbl_val

        # ── TAB 6: Detail-Analyse ──────────────────────────────────────────
        detail_tab = self.tabview.tab("6. Detail-Analyse")
        self.detail_panel = ctk.CTkFrame(detail_tab, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD)
        self.detail_panel.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        self.detail_title = ctk.CTkLabel(
            self.detail_panel,
            text="Detail-Analyse der Messergebnisse",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.detail_title.pack(fill=ctk.X, padx=20, pady=(20, 10))

        self.detail_content_frame = ctk.CTkFrame(self.detail_panel, fg_color=COLOR_BG_MAIN, corner_radius=6)
        self.detail_content_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
