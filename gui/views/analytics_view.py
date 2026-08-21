# -*- coding: utf-8 -*-
"""gui/views/analytics_view.py – Statistical Temperature Histogram & Metrics for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card
from utils import pixel_to_celsius


class AnalyticsView(ctk.CTkFrame):
    """Statistischer Histogramm- und Metriken-Viewer im Google Material 3 Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.current_result: Optional[dict[str, Any]] = None
        self._canvas_widget: Optional[FigureCanvasTkAgg] = None
        self._current_fig: Optional[Figure] = None

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ── Linke Spalte: Matplotlib Histogramm ──────────────────────────────
        self.chart_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.chart_card.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")

        # Header
        top_bar = ctk.CTkFrame(self.chart_card, fg_color="transparent", height=44)
        top_bar.pack(fill=ctk.X, padx=16, pady=(12, 6))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text="TEMPERATUR-VERTEILUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            top_bar,
            text="Gaußsches Dichtemodell & Hotspot-Schwellenwert",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        ctk.CTkFrame(self.chart_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        # Chart Container
        self.chart_container = ctk.CTkFrame(self.chart_card, fg_color="transparent")
        self.chart_container.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        self.empty_chart_lbl = ctk.CTkLabel(
            self.chart_container,
            text="Keine Bilddaten geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.empty_chart_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Rechte Spalte: Metriken & Hotspot-Tabelle ────────────────────────
        self.metrics_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.metrics_card.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")

        scroll = ctk.CTkScrollableFrame(self.metrics_card, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        # 1. Metriken-Übersicht
        ctk.CTkLabel(
            scroll,
            text="QUANTITATIVE KENNZAHLEN",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.stat_labels = {}
        metric_items = [
            ("body_px",    "Gewebe-Oberfläche:",     "-- px"),
            ("mean_t",     "Mittelwert (µ):",        "-- °C"),
            ("std_t",      "Standardabweichung (σ):", "±-- °C"),
            ("thresh_t",   "Hotspot-Grenze (µ+k·σ):", "-- °C"),
            ("max_t",      "Spitzentemperatur:",     "-- °C"),
            ("hotspot_px", "Hotspot-Fläche:",        "-- px"),
            ("ratio",      "Anteil an Gewebe:",      "-- %"),
        ]

        metric_box = make_material_card(scroll, corner_radius=10, fg_color=COLOR_BG_CARD_VARIANT)
        metric_box.pack(fill=ctk.X, pady=(0, 16))

        m_inner = ctk.CTkFrame(metric_box, fg_color="transparent")
        m_inner.pack(fill=ctk.X, padx=14, pady=10)

        for key, name, default_val in metric_items:
            row = ctk.CTkFrame(m_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=3)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text=default_val, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.stat_labels[key] = lbl

        # 2. Hotspots Rangliste Tabelle
        ctk.CTkLabel(
            scroll,
            text="DETEKTIERTE HYPERTHERMIE-HERDE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 6))

        self.table_box = ctk.CTkFrame(scroll, fg_color="transparent")
        self.table_box.pack(fill=ctk.X)

        self.table_empty_lbl = ctk.CTkLabel(
            self.table_box,
            text="Keine Hotspots erkannt (Unauffällig)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, slant="italic"),
            text_color=COLOR_SUCCESS,
            anchor="w"
        )
        self.table_empty_lbl.pack(fill=ctk.X, pady=8)

    def show_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        self.empty_chart_lbl.place_forget()

        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)
        body_px = result.get("body_pixel_count", 0)
        hotspot_px = result.get("hotspot_pixel_count", 0)
        ratio = result.get("hotspot_ratio", 0.0)

        mean_px = result.get("mean_pixel", 0.0)
        std_px = result.get("std_pixel", 0.0)
        max_px = result.get("max_pixel", 0.0)

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        max_c = pixel_to_celsius(max_px, t_min, t_max)

        sk = result.get("params", {}).get("sigma_k", 3.0)
        thresh_px = mean_px + sk * std_px
        thresh_c = pixel_to_celsius(thresh_px, t_min, t_max)

        self.stat_labels["body_px"].configure(text=f"{body_px:,} px")
        self.stat_labels["mean_t"].configure(text=f"{mean_c:.2f} °C")
        self.stat_labels["std_t"].configure(text=f"±{std_c:.2f} °C")
        self.stat_labels["thresh_t"].configure(text=f"{thresh_c:.2f} °C")
        self.stat_labels["max_t"].configure(text=f"{max_c:.2f} °C")

        if hotspot_px > 0:
            self.stat_labels["hotspot_px"].configure(text=f"{hotspot_px:,} px", text_color=COLOR_DANGER)
            self.stat_labels["ratio"].configure(text=f"{ratio:.2f} %", text_color=COLOR_DANGER)
        else:
            self.stat_labels["hotspot_px"].configure(text="0 px", text_color=COLOR_SUCCESS)
            self.stat_labels["ratio"].configure(text="0.00 %", text_color=COLOR_SUCCESS)

        self._render_histogram()
        self._render_hotspots_table()

    def _render_histogram(self) -> None:
        """Erzeugt ein Google Material 3 Histogramm mit Matplotlib."""
        if not self.current_result:
            return

        body_mask = self.current_result["body_mask"] > 0
        raw_img = self.current_result["calibrated_original"]
        pixels = raw_img[body_mask]

        if len(pixels) == 0:
            return

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)
        temps_c = [t_min + (p / 255.0) * (t_max - t_min) for p in pixels]

        mean_c = pixel_to_celsius(self.current_result["mean_pixel"], t_min, t_max)
        std_c = (self.current_result["std_pixel"] / 255.0) * (t_max - t_min)
        sk = self.current_result.get("params", {}).get("sigma_k", 3.0)
        thresh_c = mean_c + sk * std_c

        # Altes Chart sauber entfernen
        if self._canvas_widget:
            self._canvas_widget.get_tk_widget().destroy()
            self._canvas_widget = None
        if self._current_fig:
            self._current_fig.clf()
            self._current_fig = None

        # Dark / Light Theme Farben
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#292A2D" if is_dark else "#FFFFFF"
        text_color = "#E8EAED" if is_dark else "#202124"
        grid_color = "#3C4043" if is_dark else "#E8EAED"

        fig = Figure(figsize=(5.5, 4.0), dpi=100, facecolor=bg_color)
        ax = fig.add_subplot(111, facecolor=bg_color)

        # Histogramm Balken (Google Blue)
        n, bins, patches = ax.hist(temps_c, bins=64, color="#1A73E8", alpha=0.75, edgecolor="none")

        # Hotspot Balken über Schwellenwert in Google Red einfärben
        for patch, b_left in zip(patches, bins[:-1]):
            if b_left >= thresh_c:
                patch.set_facecolor("#EA4335")
                patch.set_alpha(0.9)

        # Vertikale Linien
        ax.axvline(mean_c, color=text_color, linestyle="--", linewidth=1.5, label=f"Mittelwert ({mean_c:.1f} °C)")
        ax.axvline(thresh_c, color="#EA4335", linestyle="-.", linewidth=2.0, label=f"Schwelle k={sk:.1f} ({thresh_c:.1f} °C)")

        ax.set_xlabel("Temperatur (°C)", color=text_color, fontsize=10, fontweight="bold")
        ax.set_ylabel("Pixel-Anzahl", color=text_color, fontsize=10, fontweight="bold")
        ax.tick_params(colors=text_color, labelsize=9)

        for spine in ax.spines.values():
            spine.set_color(grid_color)

        ax.grid(color=grid_color, linestyle=":", linewidth=0.8, alpha=0.7)
        ax.legend(facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color, fontsize=9, loc="upper right")

        fig.tight_layout()

        self._current_fig = fig
        self._canvas_widget = FigureCanvasTkAgg(fig, master=self.chart_container)
        self._canvas_widget.draw()
        self._canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _render_hotspots_table(self) -> None:
        """Baut die Liste der detektierten Hotspots auf."""
        for w in self.table_box.winfo_children():
            w.destroy()

        hotspots = self.current_result.get("general_hotspots", []) if self.current_result else []
        if not hotspots:
            lbl = ctk.CTkLabel(
                self.table_box,
                text="✓ Keine signifikanten Entzündungsherde detektiert",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_SUCCESS,
                anchor="w"
            )
            lbl.pack(fill=ctk.X, pady=8)
            return

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)

        for hs in hotspots[:8]:  # Top 8 Hotspots
            idx = hs["index"]
            area = hs["area"]
            mean_c = pixel_to_celsius(hs["mean_raw"], t_min, t_max)
            max_c = pixel_to_celsius(hs["max_raw"], t_min, t_max)

            card = make_material_card(self.table_box, corner_radius=8, fg_color=COLOR_BG_CARD_VARIANT)
            card.pack(fill=ctk.X, pady=3)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill=ctk.X, padx=10, pady=6)

            ctk.CTkLabel(
                inner,
                text=f"Herd #{idx}",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                text_color=COLOR_DANGER
            ).pack(side=ctk.LEFT)

            ctk.CTkLabel(
                inner,
                text=f"{area:,} px  ·  Ø {mean_c:.1f}°C  ·  Max {max_c:.1f}°C",
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10),
                text_color=COLOR_TEXT_PRIMARY
            ).pack(side=ctk.RIGHT)
