# -*- coding: utf-8 -*-
"""gui/views/single_view.py – Deep-Dive Image & ROI Inspector for IGNITE."""

from __future__ import annotations
import os
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Any, Optional
import customtkinter as ctk
import numpy as np
import cv2
from PIL import Image

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_BLUE,
    COLOR_SUCCESS,
    COLOR_DANGER,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card, make_display_ctk_image, apply_colormap_to_image
from utils import pixel_to_celsius


class SingleInspectView(ctk.CTkFrame):
    """Detailansicht zur pixelgenauen Inspektion und interaktiven ROI-Messung."""

    STAGES = [
        ("4. Erkannte Hotspots (Rust)", "Hotspot-Overlay"),
        ("1. Originalbild",             "1. Original"),
        ("2. Hintergrund-Maske",        "2. Gewebe-Maske"),
        ("3. Lokale Hitze-Differenz",   "3. Top-Hat Diff"),
    ]

    def __init__(
        self,
        master,
        on_load_click: Callable[[], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_load_click = on_load_click
        self.current_result: Optional[dict[str, Any]] = None
        self.active_stage_key: str = "4. Erkannte Hotspots (Rust)"
        self.palette_name: str = "Google Turbo"

        # ROI State
        self.roi_drag_start: Optional[tuple[int, int]] = None
        self.roi_drag_current: Optional[tuple[int, int]] = None
        self.roi_box: Optional[tuple[int, int, int, int]] = None
        self._rendered_pil: Optional[Image.Image] = None
        self._render_scale: float = 1.0
        self._offset_x: int = 0
        self._offset_y: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Linker Bereich: Bildanzeige ──────────────────────────────────────
        self.canvas_card = make_material_card(self, corner_radius=20, fg_color=COLOR_BG_CARD)
        self.canvas_card.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="nsew")

        # Header mit Segmented Buttons & Quick Actions
        top_bar = ctk.CTkFrame(self.canvas_card, fg_color="transparent", height=54)
        top_bar.pack(fill=ctk.X, padx=20, pady=(14, 8))
        top_bar.pack_propagate(False)

        # Segmented Stage Switcher Pills
        self.stage_seg = ctk.CTkSegmentedButton(
            top_bar,
            values=[title for _, title in self.STAGES],
            command=self._on_segment_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=18,
            height=36
        )
        self.stage_seg.set("Hotspot-Overlay")
        self.stage_seg.pack(side=ctk.LEFT)

        # Rechter Button: Snapshot exportieren
        self.snapshot_btn = ctk.CTkButton(
            top_bar,
            text="📷  Snapshot speichern",
            command=self.save_snapshot,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_CONTAINER_BLUE,
            hover_color=COLOR_OUTLINE,
            text_color=COLOR_PRIMARY,
            corner_radius=18,
            height=36,
            width=160
        )
        self.snapshot_btn.pack(side=ctk.RIGHT)

        # Reset ROI Button
        self.reset_roi_btn = ctk.CTkButton(
            top_bar,
            text="✕  ROI löschen",
            command=self.clear_roi,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_SECONDARY,
            corner_radius=18,
            height=36,
            width=120
        )
        self.reset_roi_btn.pack(side=ctk.RIGHT, padx=(0, 10))

        ctk.CTkFrame(self.canvas_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        # Bild Label mit Maus-Events
        self.img_lbl = ctk.CTkLabel(
            self.canvas_card,
            text="Kein Bild geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            text_color=COLOR_TEXT_MUTED
        )
        self.img_lbl.pack(fill=ctk.BOTH, expand=True, padx=16, pady=(12, 6))

        self.img_lbl.bind("<Motion>", self._on_mouse_move)
        self.img_lbl.bind("<Leave>", self._on_mouse_leave)
        self.img_lbl.bind("<ButtonPress-1>", self._on_mouse_down)
        self.img_lbl.bind("<B1-Motion>", self._on_mouse_drag)
        self.img_lbl.bind("<ButtonRelease-1>", self._on_mouse_up)

        # ── Rechter Bereich: Live Pixel & ROI Sidebar ────────────────────────
        self.sidebar_card = make_material_card(self, corner_radius=20, fg_color=COLOR_BG_CARD)
        self.sidebar_card.grid(row=0, column=1, padx=(10, 20), pady=20, sticky="nsew")

        side_scroll = ctk.CTkScrollableFrame(self.sidebar_card, fg_color="transparent")
        side_scroll.pack(fill=ctk.BOTH, expand=True, padx=16, pady=16)

        # 1. Live Fadenkreuz & Pixel Tooltip
        ctk.CTkLabel(
            side_scroll,
            text="LIVE-PIXELMESSUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.pixel_box = make_material_card(side_scroll, corner_radius=14, fg_color=COLOR_BG_CARD_VARIANT)
        self.pixel_box.pack(fill=ctk.X, pady=(0, 18))

        p_inner = ctk.CTkFrame(self.pixel_box, fg_color="transparent")
        p_inner.pack(fill=ctk.X, padx=18, pady=16)

        self.live_temp_lbl = ctk.CTkLabel(
            p_inner,
            text="--.- °C",
            font=ctk.CTkFont(family=FONT_FAMILY, size=28, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.live_temp_lbl.pack(fill=ctk.X)

        self.live_coord_lbl = ctk.CTkLabel(
            p_inner,
            text="Koordinaten: X=--, Y=--",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.live_coord_lbl.pack(fill=ctk.X, pady=(4, 0))

        self.live_status_lbl = ctk.CTkLabel(
            p_inner,
            text="Befund: Bewege Cursor über Bild",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.live_status_lbl.pack(fill=ctk.X, pady=(4, 0))

        # 2. ROI Messbox
        ctk.CTkLabel(
            side_scroll,
            text="REGION OF INTEREST (ROI)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 8))

        self.roi_card = make_material_card(side_scroll, corner_radius=14, fg_color=COLOR_BG_CARD_VARIANT)
        self.roi_card.pack(fill=ctk.X, pady=(0, 18))

        r_inner = ctk.CTkFrame(self.roi_card, fg_color="transparent")
        r_inner.pack(fill=ctk.X, padx=18, pady=16)

        self.roi_title_lbl = ctk.CTkLabel(
            r_inner,
            text="Rechteck mit Maus aufziehen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, slant="italic"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=220
        )
        self.roi_title_lbl.pack(fill=ctk.X, pady=(0, 10))

        self.roi_stats_rows = {}
        for key, name in [
            ("mean", "Mittelwert (µ):"),
            ("std", "Standardabw. (σ):"),
            ("min", "Minimal-Temp:"),
            ("max", "Maximal-Temp:"),
            ("area", "Fläche (Pixel):")
        ]:
            row = ctk.CTkFrame(r_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=4)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=13), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.roi_stats_rows[key] = lbl

        # 3. Quick Tipp
        hint_card = make_material_card(side_scroll, corner_radius=14, fg_color=COLOR_BG_CARD_VARIANT)
        hint_card.pack(fill=ctk.X, pady=(4, 0))
        h_inner = ctk.CTkFrame(hint_card, fg_color="transparent")
        h_inner.pack(fill=ctk.X, padx=18, pady=16)

        ctk.CTkLabel(
            h_inner,
            text="💡 Intuitive Gesten",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)
        ctk.CTkLabel(
            h_inner,
            text="Ziehe mit gedrückter linker Maustaste ein beliebiges Rechteck auf, um Entzündungen punktgenau auszuwerten.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=220,
            justify="left"
        ).pack(fill=ctk.X, pady=(4, 0))

    def show_results(self, result: dict[str, Any], palette_name: str = "Google Turbo", target_stage: str | None = None) -> None:
        self.current_result = result
        self.palette_name = palette_name
        if target_stage:
            self.active_stage_key = target_stage
            for key, title in self.STAGES:
                if key == target_stage:
                    self.stage_seg.set(title)
                    break
        self.redraw()

    def set_palette(self, palette_name: str) -> None:
        self.palette_name = palette_name
        self.redraw()

    def _on_segment_changed(self, choice: str) -> None:
        for key, title in self.STAGES:
            if title == choice:
                self.active_stage_key = key
                break
        self.redraw()

    def redraw(self) -> None:
        if not self.current_result:
            return

        if self.active_stage_key == "1. Originalbild":
            raw = apply_colormap_to_image(self.current_result["calibrated_original"], self.palette_name)
        elif self.active_stage_key == "2. Hintergrund-Maske":
            raw = cv2.cvtColor(self.current_result["body_mask"], cv2.COLOR_GRAY2BGR)
        elif self.active_stage_key == "3. Lokale Hitze-Differenz":
            raw = cv2.cvtColor(self.current_result["heat_diff"], cv2.COLOR_GRAY2BGR)
        else:
            raw = self.current_result["overlay_bgr"]

        img_to_show = raw.copy()

        if self.roi_box:
            x1, y1, x2, y2 = self.roi_box
            cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (255, 255, 0), 2)
        elif self.roi_drag_start and self.roi_drag_current:
            x1, x2 = sorted([self.roi_drag_start[0], self.roi_drag_current[0]])
            y1, y2 = sorted([self.roi_drag_start[1], self.roi_drag_current[1]])
            cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (0, 255, 255), 1)

        rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        self._rendered_pil = pil_img

        self.img_lbl.update_idletasks()
        w = max(self.img_lbl.winfo_width() - 20, 300)
        h = max(self.img_lbl.winfo_height() - 20, 200)

        orig_w, orig_h = pil_img.size
        ratio = min(w / orig_w, h / orig_h)
        self._render_scale = ratio
        disp_w = max(1, int(orig_w * ratio))
        disp_h = max(1, int(orig_h * ratio))

        self._offset_x = (self.img_lbl.winfo_width() - disp_w) // 2
        self._offset_y = (self.img_lbl.winfo_height() - disp_h) // 2

        ctk_img = make_display_ctk_image(pil_img, w, h)
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img

    def save_snapshot(self) -> None:
        if not self._rendered_pil:
            return
        p = filedialog.asksaveasfilename(
            title="Snapshot speichern",
            defaultextension=".png",
            filetypes=[("PNG Bild", "*.png"), ("JPEG Bild", "*.jpg")]
        )
        if p:
            self._rendered_pil.save(p)

    def _event_to_img_coords(self, event) -> Optional[tuple[int, int]]:
        if not self.current_result or not self._rendered_pil:
            return None

        mx = event.x - self._offset_x
        my = event.y - self._offset_y

        orig_w, orig_h = self._rendered_pil.size
        disp_w = orig_w * self._render_scale
        disp_h = orig_h * self._render_scale

        if 0 <= mx < disp_w and 0 <= my < disp_h:
            img_x = int(mx / self._render_scale)
            img_y = int(my / self._render_scale)
            return min(max(img_x, 0), orig_w - 1), min(max(img_y, 0), orig_h - 1)
        return None

    def _on_mouse_move(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if not coords or not self.current_result:
            return

        x, y = coords
        raw_val = self.current_result["calibrated_original"][y, x]
        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)
        temp_c = pixel_to_celsius(raw_val, t_min, t_max)

        is_hotspot = self.current_result["hotspot_mask"][y, x] > 0
        is_body = self.current_result["body_mask"][y, x] > 0

        self.live_temp_lbl.configure(text=f"{temp_c:.1f} °C")
        self.live_coord_lbl.configure(text=f"Koordinaten: X={x}, Y={y} (px={raw_val})")

        if is_hotspot:
            self.live_status_lbl.configure(text="Befund: ⚠️ Hotspot detektiert", text_color=COLOR_DANGER)
        elif is_body:
            self.live_status_lbl.configure(text="Befund: ✓ Physiologisches Gewebe", text_color=COLOR_SUCCESS)
        else:
            self.live_status_lbl.configure(text="Befund: Hintergrund / Umfeld", text_color=COLOR_TEXT_MUTED)

    def _on_mouse_leave(self, event) -> None:
        self.live_temp_lbl.configure(text="--.- °C")
        self.live_coord_lbl.configure(text="Koordinaten: X=--, Y=--")
        self.live_status_lbl.configure(text="Befund: Bewege Cursor über Bild", text_color=COLOR_TEXT_MUTED)

    def _on_mouse_down(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if coords:
            self.roi_drag_start = coords
            self.roi_drag_current = coords
            self.roi_box = None

    def _on_mouse_drag(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if coords and self.roi_drag_start:
            self.roi_drag_current = coords
            self.redraw()

    def _on_mouse_up(self, event) -> None:
        coords = self._event_to_img_coords(event)
        if coords and self.roi_drag_start:
            x1, x2 = sorted([self.roi_drag_start[0], coords[0]])
            y1, y2 = sorted([self.roi_drag_start[1], coords[1]])

            if (x2 - x1) >= 3 and (y2 - y1) >= 3:
                self.roi_box = (x1, y1, x2, y2)
                self._compute_roi_stats(x1, y1, x2, y2)
            else:
                self.clear_roi()

            self.roi_drag_start = None
            self.roi_drag_current = None
            self.redraw()

    def _compute_roi_stats(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if not self.current_result:
            return

        raw_img = self.current_result["calibrated_original"]
        roi_px = raw_img[y1:y2, x1:x2]

        if len(roi_px) == 0:
            return

        t_min = self.current_result.get("t_min_c", 20.0)
        t_max = self.current_result.get("t_max_c", 40.0)

        mean_px = float(np.mean(roi_px))
        std_px = float(np.std(roi_px))
        min_px = float(np.min(roi_px))
        max_px = float(np.max(roi_px))

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        min_c = pixel_to_celsius(min_px, t_min, t_max)
        max_c = pixel_to_celsius(max_px, t_min, t_max)
        area_px = (x2 - x1) * (y2 - y1)

        self.roi_title_lbl.configure(text=f"Auswahl: {x2-x1}x{y2-y1} px", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLOR_PRIMARY)
        self.roi_stats_rows["mean"].configure(text=f"{mean_c:.2f} °C")
        self.roi_stats_rows["std"].configure(text=f"±{std_c:.2f} °C")
        self.roi_stats_rows["min"].configure(text=f"{min_c:.1f} °C")
        self.roi_stats_rows["max"].configure(text=f"{max_c:.1f} °C")
        self.roi_stats_rows["area"].configure(text=f"{area_px:,} px")

    def clear_roi(self) -> None:
        self.roi_box = None
        self.roi_drag_start = None
        self.roi_drag_current = None
        self.roi_title_lbl.configure(text="Rechteck mit Maus aufziehen", font=ctk.CTkFont(family=FONT_FAMILY, size=13, slant="italic"), text_color=COLOR_TEXT_MUTED)
        for lbl in self.roi_stats_rows.values():
            lbl.configure(text="--")
        self.redraw()
