# -*- coding: utf-8 -*-
"""gui/views/analytics_view.py – Statistical Temperature Histogram & Metrics for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
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
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card
from utils import pixel_to_celsius


class AnalyticsView(ctk.CTkFrame):
    """Diagnostische Statistik & Temperatur-Histogramm im Google Material 3 Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.current_result: Optional[dict[str, Any]] = None
        self._canvas_tk: Optional[FigureCanvasTkAgg] = None
        self.fig, self.ax = plt.subplots(figsize=(6, 3.8), dpi=100)

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ── Linke Spalte: Matplotlib Histogramm ──────────────────────────────
        self.chart_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.chart_card.grid(row=0, column=0, padx=(18, 10), pady=18, sticky="nsew")

        top_bar = ctk.CTkFrame(self.chart_card, fg_color="transparent", height=50)
        top_bar.pack(fill=ctk.X, padx=18, pady=(14, 8))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text="STATISTISCHE VERTEILUNG & SCHWELLENWERTE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            top_bar,
            text="Gaußsche Dichtekurve vs. Hotspots",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        ctk.CTkFrame(self.chart_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        self.chart_host = ctk.CTkFrame(self.chart_card, fg_color="transparent")
        self.chart_host.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        # ── Rechte Spalte: Quantitative Metriken & Herde-Tabelle ─────────────
        self.metrics_card = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        self.metrics_card.grid(row=0, column=1, padx=(10, 18), pady=18, sticky="nsew")

        scroll = ctk.CTkScrollableFrame(self.metrics_card, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        # 1. Statistische Kennzahlen
        ctk.CTkLabel(
            scroll,
            text="QUANTITATIVE PARAMETER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.stats_table_card = make_material_card(scroll, corner_radius=12, fg_color=COLOR_BG_CARD_VARIANT)
        self.stats_table_card.pack(fill=ctk.X, pady=(0, 18))

        st_inner = ctk.CTkFrame(self.stats_table_card, fg_color="transparent")
        st_inner.pack(fill=ctk.X, padx=16, pady=14)

        self.metric_rows = {}
        metrics_list = [
            ("mean", "Gewebe-Mittelwert (µ):", "--.- °C"),
            ("std", "Standardabweichung (σ):", "±-.- °C"),
            ("k_thresh", "Adaptive Schwelle (µ + k·σ):", "--.- °C"),
            ("max", "Maximaltemperatur:", "--.- °C"),
            ("min", "Minimaltemperatur:", "--.- °C"),
            ("body_px", "Segmentierte Gewebepixel:", "-- px"),
            ("hotspot_px", "Erkannte Hotspot-Pixel:", "-- px"),
            ("hotspot_ratio", "Hyperthermie-Anteil:", "-.-- %"),
        ]

        for m_key, title, default_v in metrics_list:
            row = ctk.CTkFrame(st_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=3)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl_v = ctk.CTkLabel(row, text=default_v, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl_v.pack(side=ctk.RIGHT)
            self.metric_rows[m_key] = lbl_v

        # 2. Rangliste der Hyperthermie-Herde
        ctk.CTkLabel(
            scroll,
            text="DETEKTIERTE HYPERTHERMIE-HERDE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.hotspot_list_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.hotspot_list_frame.pack(fill=ctk.X)

        self.no_hotspots_lbl = ctk.CTkLabel(
            self.hotspot_list_frame,
            text="Keine signifikanten Entzündungsherde detektiert.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, slant="italic"),
            text_color=COLOR_TEXT_MUTED
        )
        self.no_hotspots_lbl.pack(pady=12)

    def show_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)

        mean_px = result.get("mean_pixel", 0.0)
        std_px = result.get("std_pixel", 0.0)
        max_px = result.get("max_pixel", 0.0)
        min_px = result.get("min_pixel", 0.0)

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        max_c = pixel_to_celsius(max_px, t_min, t_max)
        min_c = pixel_to_celsius(min_px, t_min, t_max)

        k = result.get("params", {}).get("sigma_k", 3.0)
        thresh_px = mean_px + k * std_px
        thresh_c = pixel_to_celsius(thresh_px, t_min, t_max)

        body_px = result.get("body_pixel_count", 0)
        hotspot_px = result.get("hotspot_pixel_count", 0)
        ratio = result.get("hotspot_ratio", 0.0)

        # Tabellenwerte aktualisieren
        self.metric_rows["mean"].configure(text=f"{mean_c:.2f} °C")
        self.metric_rows["std"].configure(text=f"±{std_c:.2f} °C")
        self.metric_rows["k_thresh"].configure(text=f"{thresh_c:.2f} °C (k={k})")
        self.metric_rows["max"].configure(text=f"{max_c:.1f} °C")
        self.metric_rows["min"].configure(text=f"{min_c:.1f} °C")
        self.metric_rows["body_px"].configure(text=f"{body_px:,} px")

        hs_color = COLOR_DANGER if hotspot_px > 0 else COLOR_SUCCESS
        self.metric_rows["hotspot_px"].configure(text=f"{hotspot_px:,} px", text_color=hs_color)
        self.metric_rows["hotspot_ratio"].configure(text=f"{ratio:.2f} %", text_color=hs_color)

        # Herde-Karten aufbauen
        for w in self.hotspot_list_frame.winfo_children():
            w.destroy()

        hotspots = result.get("general_hotspots", [])
        if not hotspots:
            self.no_hotspots_lbl = ctk.CTkLabel(
                self.hotspot_list_frame,
                text="✓ Keine signifikanten Entzündungsherde detektiert.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=COLOR_SUCCESS
            )
            self.no_hotspots_lbl.pack(pady=12)
        else:
            for idx, spot in enumerate(hotspots[:10]):
                card = make_material_card(self.hotspot_list_frame, corner_radius=10, fg_color=COLOR_BG_CARD_VARIANT)
                card.pack(fill=ctk.X, pady=3)

                c_inner = ctk.CTkFrame(card, fg_color="transparent")
                c_inner.pack(fill=ctk.X, padx=12, pady=10)

                ctk.CTkLabel(
                    c_inner,
                    text=f"Herd #{spot.get('index', idx+1)}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLOR_DANGER
                ).pack(side=ctk.LEFT)

                max_t = pixel_to_celsius(spot.get("max_raw", 0), t_min, t_max)
                area = spot.get("area", 0)
                ctk.CTkLabel(
                    c_inner,
                    text=f"Max: {max_t:.1f} °C  ·  Fläche: {area:,} px",
                    font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
                    text_color=COLOR_TEXT_PRIMARY
                ).pack(side=ctk.RIGHT)

        self._draw_chart()

    def _draw_chart(self) -> None:
        if not self.current_result:
            return

        raw_img = self.current_result["calibrated_original"]
        body_mask = self.current_result["body_mask"]
        body_pixels = raw_img[body_mask == 255]

        if len(body_pixels) == 0:
            return

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)
        temps_c = t_min + (body_pixels.astype(np.float32) / 255.0) * (t_max - t_min)

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2D2F31" if is_dark else "#FFFFFF"
        text_color = "#E8EAED" if is_dark else "#202124"
        grid_color = "#3C4043" if is_dark else "#E8EAED"

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)

        # Histogramm zeichnen
        counts, bins, patches = self.ax.hist(
            temps_c, bins=45, color="#1A73E8", alpha=0.85, edgecolor=bg_color, linewidth=0.5
        )

        mean_c = np.mean(temps_c)
        std_c = np.std(temps_c)
        k = self.current_result.get("params", {}).get("sigma_k", 3.0)
        thresh_c = mean_c + k * std_c

        # Hotspot-Balken rot einfärben
        for patch, left_edge in zip(patches, bins[:-1]):
            if left_edge >= thresh_c:
                patch.set_facecolor("#EA4335")

        # Linien
        self.ax.axvline(mean_c, color="#34A853", linestyle="--", linewidth=1.5, label=f"Mittelwert ({mean_c:.1f}°C)")
        self.ax.axvline(thresh_c, color="#EA4335", linestyle="-", linewidth=2.0, label=f"Schwelle k={k:.1f} ({thresh_c:.1f}°C)")

        self.ax.set_xlabel("Temperatur (°C)", color=text_color, fontsize=10, family=FONT_FAMILY)
        self.ax.set_ylabel("Pixelanzahl", color=text_color, fontsize=10, family=FONT_FAMILY)
        self.ax.tick_params(colors=text_color, labelsize=9)

        for spine in self.ax.spines.values():
            spine.set_color(grid_color)

        self.ax.grid(True, linestyle=":", alpha=0.5, color=grid_color)
        self.ax.legend(facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color, fontsize=9)
        self.fig.tight_layout()

        # Canvas einbetten
        if self._canvas_tk:
            self._canvas_tk.get_tk_widget().destroy()

        self._canvas_tk = FigureCanvasTkAgg(self.fig, master=self.chart_host)
        self._canvas_tk.draw()
        self._canvas_tk.get_tk_widget().pack(fill=tk.BOTH, expand=True)
