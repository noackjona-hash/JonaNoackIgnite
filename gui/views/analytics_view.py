# -*- coding: utf-8 -*-
"""gui/views/analytics_view.py – Statistical Analytics & Jury Benchmark for IGNITE."""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog
from typing import Optional, Any, Callable
import customtkinter as ctk
import numpy as np
import matplotlib
try:
    if hasattr(matplotlib, "use"):
        matplotlib.use("Agg")
except Exception:
    pass
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import config
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
    COLOR_SUCCESS,
    COLOR_DANGER,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card
from utils import pixel_to_celsius


class AnalyticsView(ctk.CTkFrame):
    """Diagnostische Statistik, Temperatur-Histogramm & Jury-Evaluationsbereich."""

    def __init__(
        self,
        master,
        on_open_annotator: Optional[Callable[[], None]] = None,
        on_export_jury_report: Optional[Callable[[], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_open_annotator = on_open_annotator
        self.on_export_jury_report = on_export_jury_report

        self.current_result: Optional[dict[str, Any]] = None
        self._canvas_tk: Optional[FigureCanvasTkAgg] = None
        self.fig, self.ax = plt.subplots(figsize=(6, 3.8), dpi=100)

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=400)
        self.grid_rowconfigure(0, weight=1)

        # ── Linke Spalte: Matplotlib Histogramm ──────────────────────────────
        self.chart_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.chart_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        top_bar = ctk.CTkFrame(self.chart_card, fg_color="transparent", height=46)
        top_bar.pack(fill=ctk.X, padx=14, pady=(10, 6))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text="STATISTISCHE VERTEILUNG & SCHWELLENWERTE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            top_bar,
            text="Gaußsche Dichtekurve vs. Hotspots",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        ctk.CTkFrame(self.chart_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        self.chart_host = ctk.CTkFrame(self.chart_card, fg_color="transparent")
        self.chart_host.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # ── Rechte Spalte: Quantitative Metriken & Jury Actions ──────────────
        self.metrics_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.metrics_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")
        self.metrics_card.configure(width=400)

        scroll = ctk.CTkScrollableFrame(self.metrics_card, fg_color="transparent", width=370)
        scroll.pack(fill=ctk.BOTH, expand=True, padx=8, pady=10)

        # 1. Statistische Kennzahlen
        ctk.CTkLabel(
            scroll,
            text="QUANTITATIVE PARAMETER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(2, 6))

        self.stats_table_card = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.stats_table_card.pack(fill=ctk.X, padx=4, pady=(0, 14))

        st_inner = ctk.CTkFrame(self.stats_table_card, fg_color="transparent")
        st_inner.pack(fill=ctk.X, padx=14, pady=12)

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
            ("iwgdf_risk", "IWGDF 2023 Risikoklasse:", "Grad 0 (Normal)"),
        ]

        for m_key, title, default_v in metrics_list:
            row = ctk.CTkFrame(st_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl_v = ctk.CTkLabel(row, text=default_v, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl_v.pack(side=ctk.RIGHT)
            self.metric_rows[m_key] = lbl_v

        # 2. Rangliste der Hyperthermie-Herde
        ctk.CTkLabel(
            scroll,
            text="DETEKTIERTE HYPERTHERMIE-HERDE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(4, 6))

        self.hotspot_list_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self.hotspot_list_frame.pack(fill=ctk.X, padx=4)

        self.no_hotspots_lbl = ctk.CTkLabel(
            self.hotspot_list_frame,
            text="Keine signifikanten Entzündungsherde detektiert.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.no_hotspots_lbl.pack(pady=10)

        # 3. Wissenschaftliche Evaluation & Jury-Dossier
        ctk.CTkLabel(
            scroll,
            text="WISSENSCHAFTLICHE JURY-EVALUATION",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(14, 6))

        jury_box = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        jury_box.pack(fill=ctk.X, padx=4, pady=(0, 4))

        j_inner = ctk.CTkFrame(jury_box, fg_color="transparent")
        j_inner.pack(fill=ctk.X, padx=14, pady=12)

        ctk.CTkButton(
            j_inner,
            text="Jury-Evaluationsbericht exportieren (HTML)",
            command=self._on_click_jury_report,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(fill=ctk.X, pady=(0, 6))

        ctk.CTkButton(
            j_inner,
            text="Wissenschaftsplakat exportieren (PDF & HTML)",
            command=self._on_click_poster_export,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(fill=ctk.X, pady=(0, 6))

        ctk.CTkButton(
            j_inner,
            text="Ground-Truth Annotator öffnen",
            command=self._on_click_annotator,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(fill=ctk.X)

        # 4. Longitudinaler Verlaufs-Vergleich (Follow-Up & Monitoring)
        ctk.CTkLabel(
            scroll,
            text="LONGITUDINALER VERLAUFS-VERGLEICH",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(14, 6))

        followup_box = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        followup_box.pack(fill=ctk.X, padx=4, pady=(0, 14))

        f_inner = ctk.CTkFrame(followup_box, fg_color="transparent")
        f_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.followup_load_btn = ctk.CTkButton(
            f_inner,
            text="Follow-Up Bild laden & vergleichen",
            command=self._on_load_followup,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=32
        )
        self.followup_load_btn.pack(fill=ctk.X, pady=(0, 8))

        self.followup_status_lbl = ctk.CTkLabel(
            f_inner,
            text="Keine Vergleichsaufnahme geladen.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=210,
            justify="left"
        )
        self.followup_status_lbl.pack(fill=ctk.X, pady=(0, 6))

        self.followup_stats_rows = {}
        for key, name in [
            ("delta_t", "Mittlere Temp.-Änderung (ΔT):"),
            ("delta_max", "Max. Temperaturdifferenz:"),
            ("area_change", "Hotspot-Flächenänderung:"),
            ("status", "Klinischer Verlauf:")
        ]:
            row = ctk.CTkFrame(f_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.followup_stats_rows[key] = lbl

    def _on_click_jury_report(self) -> None:
        if self.on_export_jury_report:
            self.on_export_jury_report()

    def _on_click_poster_export(self) -> None:
        try:
            from gui.services.scientific_poster_service import ScientificPosterService
            pdf_path = ScientificPosterService.generate_poster_pdf()
            html_path = ScientificPosterService.generate_poster_html()
            from tkinter import messagebox
            messagebox.showinfo(
                "Poster-Export erfolgreich",
                f"Wissenschaftsplakat erfolgreich exportiert als:\n• PDF: {os.path.basename(pdf_path)}\n• HTML: {os.path.basename(html_path)}\n\nGespeichert in: {config.OUTPUT_DIR}"
            )
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Fehler beim Poster-Export", str(e))

    def _on_click_annotator(self) -> None:
        if self.on_open_annotator:
            self.on_open_annotator()

    def _on_load_followup(self) -> None:
        if not self.current_result:
            return
        path = filedialog.askopenfilename(
            title="Follow-Up Wärmebild wählen",
            filetypes=[("Wärmebilder", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif;*.rjpg;*.npy")]
        )
        if not path:
            return

        try:
            from gui.services.processing_service import ThermalProcessingService
            import image_processing
            t_min = self.current_result.get("t_min_c", 20.0)
            t_max = self.current_result.get("t_max_c", 40.0)
            params = self.current_result.get("params", {})

            # Follow-Up Bild laden und Pipeline berechnen
            raw2 = image_processing.load_thermal_image(path, t_min=t_min, t_max=t_max)
            diff2, hs2 = image_processing.run_rust_pipeline(
                raw2,
                sigma_k=params.get("sigma_k", 3.0),
                tophat_factor=params.get("tophat_factor", 0.05)
            )
            mask2 = (diff2 > 0).astype(np.uint8) * 255

            res2 = {
                "calibrated_original": raw2,
                "body_mask": mask2,
                "hotspot_mask": hs2,
                "t_min_c": t_min,
                "t_max_c": t_max,
            }

            long_res = ThermalProcessingService.compare_longitudinal_visits(self.current_result, res2)
            self._apply_longitudinal_results(long_res, path)
        except Exception as e:
            self.followup_status_lbl.configure(text=f"Fehler: {e}", text_color=COLOR_DANGER)

    def _apply_longitudinal_results(self, long_res: dict[str, Any], followup_path: str) -> None:
        dt_mean = long_res["delta_t_mean"]
        dt_max = long_res["delta_t_max"]
        area_pct = long_res["area_pct_change"]
        status = long_res["status"]
        color = long_res["status_color"]

        sign_dt = "+" if dt_mean > 0 else ""
        sign_max = "+" if dt_max > 0 else ""
        sign_area = "+" if area_pct > 0 else ""

        self.followup_status_lbl.configure(
            text=f"Vergleich mit: {os.path.basename(followup_path)}",
            text_color=COLOR_TEXT_PRIMARY
        )
        self.followup_stats_rows["delta_t"].configure(text=f"{sign_dt}{dt_mean:.2f} °C", text_color=color)
        self.followup_stats_rows["delta_max"].configure(text=f"{sign_max}{dt_max:.1f} °C")
        self.followup_stats_rows["area_change"].configure(text=f"{sign_area}{area_pct:.1f} %", text_color=color)
        self.followup_stats_rows["status"].configure(text=status, text_color=color)

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

        # IWGDF 2023 / Armstrong Risikoklassifikation
        asym_res = result.get("asym_results", {})
        delta_t_asym = asym_res.get("delta_t_c", 0.0) if asym_res else 0.0
        zonal = result.get("zonal_stats", {})
        arch_l = zonal.get("left", {}).get("arch_index", 0.23) if isinstance(zonal, dict) else 0.23
        arch_r = zonal.get("right", {}).get("arch_index", 0.23) if isinstance(zonal, dict) else 0.23
        max_arch = max(arch_l if isinstance(arch_l, (int, float)) else 0.23, arch_r if isinstance(arch_r, (int, float)) else 0.23)

        import dataset_evaluator
        risk_info = dataset_evaluator.classify_iwgdf_armstrong_risk(
            delta_t_c=delta_t_asym,
            hotspot_area_pct=ratio,
            arch_index=max_arch
        )
        self.metric_rows["iwgdf_risk"].configure(
            text=f"Grad {risk_info['grade']}",
            text_color=risk_info["color"]
        )

        # Herde-Karten aufbauen
        for w in self.hotspot_list_frame.winfo_children():
            w.destroy()

        hotspots = result.get("general_hotspots", [])
        if not hotspots:
            self.no_hotspots_lbl = ctk.CTkLabel(
                self.hotspot_list_frame,
                text="Keine signifikanten Entzündungsherde detektiert.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_SUCCESS
            )
            self.no_hotspots_lbl.pack(pady=10)
        else:
            for idx, spot in enumerate(hotspots[:10]):
                card = make_material_card(self.hotspot_list_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
                card.pack(fill=ctk.X, pady=2)

                c_inner = ctk.CTkFrame(card, fg_color="transparent")
                c_inner.pack(fill=ctk.X, padx=12, pady=8)

                ctk.CTkLabel(
                    c_inner,
                    text=f"Herd #{spot.get('id', idx+1)}",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                    text_color=COLOR_DANGER
                ).pack(side=ctk.LEFT)

                max_t = pixel_to_celsius(spot.get("max_intensity", 0), t_min, t_max)
                area = spot.get("area_px", 0)
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
        bg_color = "#131923" if is_dark else "#FFFFFF"
        text_color = "#F8FAFC" if is_dark else "#0F172A"
        grid_color = "#243044" if is_dark else "#E2E8F0"

        self.fig.clf()
        self.ax = self.fig.add_subplot(111)

        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(bg_color)

        # Histogramm zeichnen
        counts, bins, patches = self.ax.hist(
            temps_c, bins=45, color="#0284C7", alpha=0.85, edgecolor=bg_color, linewidth=0.5
        )

        mean_c = float(np.mean(temps_c))
        std_c = float(np.std(temps_c))
        k = float(self.current_result.get("params", {}).get("sigma_k", 3.0))
        thresh_c = mean_c + k * std_c

        # Hotspot-Balken rot einfärben
        for patch, left_edge in zip(patches, bins[:-1]):
            if left_edge >= thresh_c:
                patch.set_facecolor("#DC2626")

        # Linien
        self.ax.axvline(mean_c, color="#16A34A", linestyle="--", linewidth=1.5, label=f"Mittelwert ({mean_c:.1f}°C)")
        self.ax.axvline(thresh_c, color="#DC2626", linestyle="-", linewidth=2.0, label=f"Schwelle k={k:.1f} ({thresh_c:.1f}°C)")

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
