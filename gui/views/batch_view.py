# -*- coding: utf-8 -*-
"""gui/views/batch_view.py – Automated Batch Processing Runner for IGNITE."""

from __future__ import annotations
import os
import threading
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np

import config
import image_processing
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
    COLOR_WARNING,
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card
from gui.services.export_service import ExportService


class BatchView(ctk.CTkFrame):
    """Serienuntersuchung & Ordner-Stapelverarbeitung im High-Contrast Clinical Design."""

    def __init__(
        self,
        master,
        get_current_params: Callable[[], dict[str, Any]],
        on_notify: Callable[[str, str], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.get_current_params = get_current_params
        self.on_notify = on_notify

        self.src_dir_var = tk.StringVar(value=os.path.abspath("test-data"))
        self.dest_dir_var = tk.StringVar(value=os.path.abspath(config.OUTPUT_DIR))

        self.is_running: bool = False
        self._cancel_requested: bool = False
        self._processed_items: list[dict[str, Any]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Obere Konfigurationskarte ─────────────────────────────────────────
        config_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        config_card.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")

        c_inner = ctk.CTkFrame(config_card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=18, pady=16)

        ctk.CTkLabel(
            c_inner,
            text="SERIENUNTERSUCHUNG & STAPELVERARBEITUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 10))

        # Quell- und Zielordner Zeilen
        grid_paths = ctk.CTkFrame(c_inner, fg_color="transparent")
        grid_paths.pack(fill=ctk.X, pady=(0, 10))
        grid_paths.grid_columnconfigure(1, weight=1)

        # Quellordner
        ctk.CTkLabel(grid_paths, text="Quellordner:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=4)
        self.src_entry = ctk.CTkEntry(grid_paths, textvariable=self.src_dir_var, font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=32)
        self.src_entry.grid(row=0, column=1, sticky="ew", pady=4)
        ctk.CTkButton(grid_paths, text="Durchsuchen…", width=100, height=32, corner_radius=RADIUS_BUTTON, command=self._browse_src, fg_color=COLOR_BG_CARD_VARIANT, hover_color=COLOR_BG_CARD_HOVER, border_width=1, border_color=COLOR_OUTLINE, text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=(8, 0), pady=4)

        # Zielordner
        ctk.CTkLabel(grid_paths, text="Ausgabeordner:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
        self.dest_entry = ctk.CTkEntry(grid_paths, textvariable=self.dest_dir_var, font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=32)
        self.dest_entry.grid(row=1, column=1, sticky="ew", pady=4)
        ctk.CTkButton(grid_paths, text="Durchsuchen…", width=100, height=32, corner_radius=RADIUS_BUTTON, command=self._browse_dest, fg_color=COLOR_BG_CARD_VARIANT, hover_color=COLOR_BG_CARD_HOVER, border_width=1, border_color=COLOR_OUTLINE, text_color=COLOR_TEXT_PRIMARY, font=ctk.CTkFont(size=11)).grid(row=1, column=2, padx=(8, 0), pady=4)

        # Start / Stop Button Bar
        btn_bar = ctk.CTkFrame(c_inner, fg_color="transparent")
        btn_bar.pack(fill=ctk.X, pady=(6, 0))

        self.start_btn = ctk.CTkButton(
            btn_bar,
            text="Stapelverarbeitung starten",
            command=self.toggle_batch,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=200
        )
        self.start_btn.pack(side=ctk.LEFT)

        self.open_dest_btn = ctk.CTkButton(
            btn_bar,
            text="Ausgabeordner öffnen",
            command=self._open_dest_folder,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=160
        )
        self.open_dest_btn.pack(side=ctk.LEFT, padx=(10, 0))

        # Fortschrittsbalken
        self.pbar = ctk.CTkProgressBar(c_inner, height=6, fg_color=COLOR_OUTLINE_VARIANT, progress_color=COLOR_PRIMARY)
        self.pbar.set(0.0)
        self.pbar.pack(fill=ctk.X, pady=(12, 4))

        self.status_lbl = ctk.CTkLabel(
            c_inner,
            text="Bereit für Serienanalyse",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.status_lbl.pack(fill=ctk.X)

        # ── Untere Ergebnistabelle ────────────────────────────────────────────
        self.results_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.results_card.grid(row=1, column=0, padx=14, pady=(6, 14), sticky="nsew")

        r_inner = ctk.CTkFrame(self.results_card, fg_color="transparent")
        r_inner.pack(fill=ctk.BOTH, expand=True, padx=18, pady=16)

        ctk.CTkLabel(
            r_inner,
            text="VERARBEITETE WÄRMEBILDER",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 8))

        self.results_scroll = ctk.CTkScrollableFrame(r_inner, fg_color="transparent")
        self.results_scroll.pack(fill=ctk.BOTH, expand=True)

        self.empty_table_lbl = ctk.CTkLabel(
            self.results_scroll,
            text="Noch keine Batch-Ergebnisse vorhanden. Klicke auf 'Stapelverarbeitung starten'.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.empty_table_lbl.pack(pady=30)

    def _browse_src(self) -> None:
        p = filedialog.askdirectory(title="Quellordner für Wärmebilder wählen")
        if p:
            self.src_dir_var.set(p)

    def _browse_dest(self) -> None:
        p = filedialog.askdirectory(title="Ausgabeordner wählen")
        if p:
            self.dest_dir_var.set(p)

    def _open_dest_folder(self) -> None:
        dest = self.dest_dir_var.get()
        if os.path.exists(dest):
            try:
                os.startfile(os.path.abspath(dest))
            except Exception as e:
                self.on_notify(f"Ordner konnte nicht geöffnet werden: {e}", "error")

    def toggle_batch(self) -> None:
        if self.is_running:
            self._cancel_requested = True
            self.status_lbl.configure(text="Abbruch angefordert…")
            return

        src_dir = self.src_dir_var.get()
        if not os.path.exists(src_dir):
            self.on_notify("Quellordner existiert nicht!", "error")
            return

        valid_exts = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif")
        files = [f for f in os.listdir(src_dir) if f.lower().endswith(valid_exts)]
        if not files:
            self.on_notify("Keine Bilddateien im Quellordner gefunden.", "warning")
            return

        self.is_running = True
        self._cancel_requested = False
        self.start_btn.configure(text="Abbrechen", fg_color=COLOR_DANGER, hover_color="#B91C1C")
        self._processed_items.clear()
        self.empty_table_lbl.pack_forget()

        for w in self.results_scroll.winfo_children():
            w.destroy()

        threading.Thread(target=self._run_worker, args=(src_dir, files), daemon=True).start()

    def _run_worker(self, src_dir: str, files: list[str]) -> None:
        dest_dir = self.dest_dir_var.get()
        os.makedirs(dest_dir, exist_ok=True)
        params = self.get_current_params()

        total = len(files)
        for idx, filename in enumerate(files):
            if self._cancel_requested:
                break

            filepath = os.path.join(src_dir, filename)
            progress = (idx + 1) / total

            self.after(0, lambda p=progress, f=filename, i=idx: self._update_progress(p, f"Verarbeite: {f} ({i+1}/{total})"))

            try:
                raw_img = image_processing.load_thermal_image(filepath)
                diff_vis, hotspot_mask = image_processing.run_rust_pipeline(
                    raw_img,
                    sigma_k=params.get("sigma_k", config.DEFAULT_SIGMA_K),
                    tophat_factor=params.get("tophat_factor", config.DEFAULT_TOPHAT_FACTOR),
                    min_area_factor=params.get("min_area_factor", config.DEFAULT_MIN_AREA_FACTOR),
                    min_circularity=params.get("min_circularity", config.DEFAULT_MIN_CIRCULARITY),
                    otsu_min=int(params.get("otsu_min", config.DEFAULT_OTSU_MIN)),
                    otsu_max=int(params.get("otsu_max", config.DEFAULT_OTSU_MAX)),
                    dist_erosion_factor=params.get("dist_erosion_factor", config.DEFAULT_DIST_EROSION_FACTOR),
                    use_mad=bool(params.get("use_mad", config.DEFAULT_USE_MAD))
                )

                body_mask = (diff_vis > 0).astype(np.uint8) * 255
                hotspot_count = int(np.sum(hotspot_mask == 255))
                asym = image_processing.compute_contralateral_asymmetry(raw_img, body_mask)
                delta_t = asym.get("delta_t_c", 0.0)
                is_asym = asym.get("is_asymmetric", False)

                is_warn = hotspot_count >= 150 or is_asym
                status_txt = "Auffällig" if is_warn else "Unauffällig"

                # HTML-Einzelbericht schreiben
                base_name = os.path.splitext(filename)[0]
                rep_name = f"report_{base_name}.html"
                rep_path = os.path.join(dest_dir, rep_name)

                result_data = {
                    "image_path": filepath,
                    "calibrated_original": raw_img,
                    "body_mask": body_mask,
                    "heat_diff": diff_vis,
                    "hotspot_mask": hotspot_mask,
                    "overlay_rgb": raw_img,
                    "asym_results": asym,
                    "zonal_stats": {},
                    "general_hotspots": [],
                    "body_pixel_count": int(np.sum(body_mask == 255)),
                    "hotspot_pixel_count": hotspot_count,
                    "hotspot_ratio": 0.0,
                    "mean_pixel": float(np.mean(raw_img)),
                    "std_pixel": float(np.std(raw_img)),
                    "max_pixel": float(np.max(raw_img)),
                    "min_pixel": float(np.min(raw_img)),
                    "t_min_c": 20.0,
                    "t_max_c": 40.0,
                    "backend": image_processing.get_active_backend(),
                    "analysis_mode": "Klinische Allgemeinanalyse",
                    "params": params
                }
                ExportService.generate_html_report(result_data, patient_name=f"Patient_{base_name}", output_filepath=rep_path)

                item = {
                    "filepath": filepath,
                    "hotspot_count": hotspot_count,
                    "delta_t_c": delta_t,
                    "status_text": status_txt,
                    "is_warning": is_warn,
                    "report_filename": rep_name
                }
                self._processed_items.append(item)
                self.after(0, lambda it=item: self._add_result_row(it))

            except Exception as e:
                print(f"Fehler bei {filename}: {e}")

        # Zusammenfassungsbericht schreiben
        if self._processed_items:
            ExportService.generate_batch_summary_html(self._processed_items, dest_dir)

        self.after(0, self._on_batch_finished)

    def _update_progress(self, val: float, text: str) -> None:
        self.pbar.set(val)
        self.status_lbl.configure(text=text)

    def _add_result_row(self, item: dict[str, Any]) -> None:
        card = make_material_card(self.results_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=2)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill=ctk.X, padx=14, pady=8)

        ctk.CTkLabel(
            row,
            text=os.path.basename(item["filepath"]),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        badge_color = COLOR_DANGER if item["is_warning"] else COLOR_SUCCESS
        ctk.CTkLabel(
            row,
            text=f"{item['status_text']}  (Hotspots: {item['hotspot_count']:,} px | ΔT: {item['delta_t_c']:.1f}°C)",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            text_color=badge_color
        ).pack(side=ctk.RIGHT)

    def _on_batch_finished(self) -> None:
        self.is_running = False
        self.start_btn.configure(text="Stapelverarbeitung starten", fg_color=COLOR_PRIMARY, hover_color=COLOR_PRIMARY_HOVER)
        self.status_lbl.configure(text=f"Fertig! {len(self._processed_items)} Bilder verarbeitet.")
        self.on_notify(f"Stapelverarbeitung abgeschlossen: {len(self._processed_items)} Bilder analysiert.", "success")
