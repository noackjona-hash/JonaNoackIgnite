# -*- coding: utf-8 -*-
"""gui/views/single_view.py – Deep-Dive Image & ROI Inspector for IGNITE.

Features:
- Stage switching (Original, Body Mask, Top-Hat Diff, Hotspot Overlay, Bioheat, Frangi, Asymmetry)
- Interactive Zoom (100% to 800%) & Pan with mouse wheel and drag
- Dynamic Celsius Colorbar with T_min, T_mean, T_thresh, T_max markers
- Precise ROI rectangle probe with quantitative statistics (Mean, Std, Min, Max, Area)
- High-resolution snapshot export
"""

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
    COLOR_BG_CARD_HOVER,
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
    COLOR_WARNING,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card, make_display_ctk_image, apply_colormap_to_image
from utils import pixel_to_celsius


class SingleInspectView(ctk.CTkFrame):
    """Detailansicht zur pixelgenauen Inspektion, Zoom/Pan und interaktiven ROI-Messung."""

    STAGES = [
        ("4. Erkannte Hotspots (Rust)", "Hotspot-Overlay"),
        ("1. Originalbild",             "1. Original"),
        ("2. Hintergrund-Maske",        "2. Gewebe-Maske"),
        ("3. Lokale Hitze-Differenz",   "3. Top-Hat Diff"),
        ("5. Pennes Bioheat",           "Pennes Bioheat"),
        ("6. Frangi-Venen",             "Frangi-Venen"),
        ("7. Bilaterale Asymmetrie",    "Asymmetrie-Map"),
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
        self.palette_name: str = "Turbo"

        # Zoom & Pan State
        self.zoom_level: float = 1.0
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.pan_drag_start: Optional[tuple[int, int]] = None

        # ROI State
        self.roi_drag_start: Optional[tuple[int, int]] = None
        self.roi_drag_current: Optional[tuple[int, int]] = None
        self.roi_box: Optional[tuple[int, int, int, int]] = None
        self._rendered_pil: Optional[Image.Image] = None
        self._visible_crop: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._render_scale: float = 1.0
        self._offset_x: int = 0
        self._offset_y: int = 0

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(0, weight=1)

        # ── Linker Bereich: Bildanzeige & Colorbar ───────────────────────────
        self.canvas_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.canvas_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        # Header mit Segmented Buttons & Quick Actions
        top_bar = ctk.CTkFrame(self.canvas_card, fg_color="transparent", height=46)
        top_bar.pack(fill=ctk.X, padx=14, pady=(10, 6))
        top_bar.pack_propagate(False)

        # Segmented Stage Switcher
        self.stage_seg = ctk.CTkSegmentedButton(
            top_bar,
            values=[title for _, title in self.STAGES],
            command=self._on_segment_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=30
        )
        self.stage_seg.set("Hotspot-Overlay")
        self.stage_seg.pack(side=ctk.LEFT)

        # Rechter Button: Snapshot exportieren
        self.snapshot_btn = ctk.CTkButton(
            top_bar,
            text="Snapshot exportieren",
            command=self.save_snapshot,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=135
        )
        self.snapshot_btn.pack(side=ctk.RIGHT)

        # Reset ROI Button
        self.reset_roi_btn = ctk.CTkButton(
            top_bar,
            text="ROI Reset",
            command=self.clear_roi,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_MUTED,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=75
        )
        self.reset_roi_btn.pack(side=ctk.RIGHT, padx=(0, 6))

        # Zoom Controls
        self.zoom_badge = ctk.CTkButton(
            top_bar,
            text="100%",
            command=self.reset_zoom,
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_PRIMARY,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=55
        )
        self.zoom_badge.pack(side=ctk.RIGHT, padx=(0, 6))

        ctk.CTkFrame(self.canvas_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        # Bild-Container mit Colorbar
        display_frame = ctk.CTkFrame(self.canvas_card, fg_color="transparent")
        display_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=(8, 4))
        display_frame.grid_columnconfigure(0, weight=1)
        display_frame.grid_columnconfigure(1, weight=0, minsize=55)
        display_frame.grid_rowconfigure(0, weight=1)

        # Bild Label mit Maus-Events
        self.img_lbl = ctk.CTkLabel(
            display_frame,
            text="Kein Bild geladen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.img_lbl.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.img_lbl.bind("<Motion>", self._on_mouse_move)
        self.img_lbl.bind("<Leave>", self._on_mouse_leave)
        self.img_lbl.bind("<ButtonPress-1>", self._on_mouse_down)
        self.img_lbl.bind("<B1-Motion>", self._on_mouse_drag)
        self.img_lbl.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.img_lbl.bind("<Double-Button-1>", lambda e: self.reset_zoom())

        # Pan via Right Click / Middle Click
        self.img_lbl.bind("<ButtonPress-3>", self._on_pan_start)
        self.img_lbl.bind("<B3-Motion>", self._on_pan_drag)
        self.img_lbl.bind("<ButtonRelease-3>", self._on_pan_end)
        self.img_lbl.bind("<ButtonPress-2>", self._on_pan_start)
        self.img_lbl.bind("<B2-Motion>", self._on_pan_drag)
        self.img_lbl.bind("<ButtonRelease-2>", self._on_pan_end)

        # Mousewheel Zoom
        self.img_lbl.bind("<MouseWheel>", self._on_mouse_wheel)
        self.img_lbl.bind("<Button-4>", lambda e: self._zoom_step(1.25))
        self.img_lbl.bind("<Button-5>", lambda e: self._zoom_step(0.8))

        # ── Colorbar Farblegende (Rechte Seite des Canvas) ───────────────────
        self.colorbar_frame = ctk.CTkFrame(display_frame, fg_color="transparent", width=55)
        self.colorbar_frame.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.colorbar_frame.pack_propagate(False)

        self.cb_max_lbl = ctk.CTkLabel(self.colorbar_frame, text="-- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=9, weight="bold"), text_color=COLOR_DANGER)
        self.cb_max_lbl.pack(side=ctk.TOP, anchor="e")

        self.cb_strip_lbl = ctk.CTkLabel(self.colorbar_frame, text="")
        self.cb_strip_lbl.pack(side=ctk.TOP, fill=ctk.Y, expand=True, pady=4)

        self.cb_min_lbl = ctk.CTkLabel(self.colorbar_frame, text="-- °C", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=9, weight="bold"), text_color=COLOR_PRIMARY)
        self.cb_min_lbl.pack(side=ctk.BOTTOM, anchor="e")

        self._render_colorbar_strip()

        # ── Rechter Bereich: Live Pixel & ROI Sidebar ────────────────────────
        self.sidebar_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.sidebar_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        side_scroll = ctk.CTkScrollableFrame(self.sidebar_card, fg_color="transparent")
        side_scroll.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        # 1. Live Fadenkreuz & Pixel Tooltip
        ctk.CTkLabel(
            side_scroll,
            text="LIVE-PIXELMESSUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(2, 6))

        self.pixel_box = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.pixel_box.pack(fill=ctk.X, pady=(0, 14))

        p_inner = ctk.CTkFrame(self.pixel_box, fg_color="transparent")
        p_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.live_temp_lbl = ctk.CTkLabel(
            p_inner,
            text="--.- °C",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=24, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.live_temp_lbl.pack(fill=ctk.X)

        self.live_coord_lbl = ctk.CTkLabel(
            p_inner,
            text="Koordinaten: X=--, Y=--",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w"
        )
        self.live_coord_lbl.pack(fill=ctk.X, pady=(2, 0))

        self.live_status_lbl = ctk.CTkLabel(
            p_inner,
            text="Befund: Cursor über Bild bewegen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.live_status_lbl.pack(fill=ctk.X, pady=(2, 0))

        # 2. ROI Messbox
        ctk.CTkLabel(
            side_scroll,
            text="REGION OF INTEREST (ROI)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(4, 6))

        self.roi_card = make_material_card(side_scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.roi_card.pack(fill=ctk.X, pady=(0, 14))

        r_inner = ctk.CTkFrame(self.roi_card, fg_color="transparent")
        r_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.roi_title_lbl = ctk.CTkLabel(
            r_inner,
            text="Rechteck mit Maus aufziehen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=200
        )
        self.roi_title_lbl.pack(fill=ctk.X, pady=(0, 8))

        self.roi_stats_rows = {}
        for key, name in [
            ("mean", "Mittelwert (µ):"),
            ("std", "Standardabw. (σ):"),
            ("min", "Minimal-Temp:"),
            ("max", "Maximal-Temp:"),
            ("area", "Fläche (Pixel):")
        ]:
            row = ctk.CTkFrame(r_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl.pack(side=ctk.RIGHT)
            self.roi_stats_rows[key] = lbl

        # 3. Quick Tipp / Zoom & Pan Bedienhinweis
        hint_box = ctk.CTkFrame(side_scroll, fg_color="transparent")
        hint_box.pack(fill=ctk.X, pady=(4, 0))

        ctk.CTkLabel(
            hint_box,
            text="Bedienung:\n• Linksklick + Ziehen: ROI-Messung\n• Mausrad: Zoom (100% - 800%)\n• Rechtsklick + Ziehen: Pan (Verschieben)\n• Doppelklick / 100%-Button: Zoom-Reset",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=210,
            justify="left"
        ).pack(fill=ctk.X)

    def _render_colorbar_strip(self) -> None:
        """Erzeugt den vertikalen Farbverlaufs-Streifen für die Colorbar."""
        grad = np.linspace(255, 0, 180, dtype=np.uint8).reshape((180, 1))
        grad = np.repeat(grad, 12, axis=1)
        colored = apply_colormap_to_image(grad, self.palette_name)
        rgb = cv2.cvtColor(colored, cv2.COLOR_BGR2RGB)
        pil_strip = Image.fromarray(rgb)
        ctk_strip = ctk.CTkImage(light_image=pil_strip, dark_image=pil_strip, size=(12, 180))
        self.cb_strip_lbl.configure(image=ctk_strip)
        self.cb_strip_lbl.image = ctk_strip

    def show_results(self, result: dict[str, Any], palette_name: str = "Turbo", target_stage: str | None = None) -> None:
        self.current_result = result
        self.palette_name = palette_name
        if target_stage:
            self.active_stage_key = target_stage
            for key, title in self.STAGES:
                if key == target_stage:
                    self.stage_seg.set(title)
                    break

        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)
        self.cb_max_lbl.configure(text=f"{t_max:.1f}°C")
        self.cb_min_lbl.configure(text=f"{t_min:.1f}°C")
        self._render_colorbar_strip()
        self.redraw()

    def set_palette(self, palette_name: str) -> None:
        self.palette_name = palette_name
        self._render_colorbar_strip()
        self.redraw()

    def _on_segment_changed(self, choice: str) -> None:
        for key, title in self.STAGES:
            if title == choice:
                self.active_stage_key = key
                break
        self.redraw()

    # ── Zoom & Pan Steuerung ─────────────────────────────────────────────────
    def _on_mouse_wheel(self, event) -> None:
        if not self.current_result:
            return
        if event.delta > 0:
            self._zoom_step(1.25)
        elif event.delta < 0:
            self._zoom_step(0.8)

    def _zoom_step(self, factor: float) -> None:
        if not self.current_result:
            return
        new_zoom = float(np.clip(self.zoom_level * factor, 1.0, 8.0))
        if abs(new_zoom - self.zoom_level) > 0.01:
            self.zoom_level = new_zoom
            if self.zoom_level <= 1.01:
                self.pan_x = 0.0
                self.pan_y = 0.0
                self.zoom_badge.configure(text="100%")
            else:
                self.zoom_badge.configure(text=f"{int(round(self.zoom_level * 100))}%")
            self.redraw()

    def reset_zoom(self) -> None:
        self.zoom_level = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.zoom_badge.configure(text="100%")
        self.redraw()

    def _on_pan_start(self, event) -> None:
        if self.zoom_level > 1.0:
            self.pan_drag_start = (event.x, event.y)

    def _on_pan_drag(self, event) -> None:
        if self.pan_drag_start and self.zoom_level > 1.0 and self._rendered_pil:
            dx = event.x - self.pan_drag_start[0]
            dy = event.y - self.pan_drag_start[1]
            orig_w, orig_h = self._rendered_pil.size
            self.pan_x += dx / max(1.0, self._render_scale * self.zoom_level)
            self.pan_y += dy / max(1.0, self._render_scale * self.zoom_level)
            self.pan_drag_start = (event.x, event.y)
            self.redraw()

    def _on_pan_end(self, event) -> None:
        self.pan_drag_start = None

    def redraw(self) -> None:
        if not self.current_result:
            return

        if self.active_stage_key == "1. Originalbild":
            raw = apply_colormap_to_image(self.current_result["calibrated_original"], self.palette_name)
        elif self.active_stage_key == "2. Hintergrund-Maske":
            raw = cv2.cvtColor(self.current_result["body_mask"], cv2.COLOR_GRAY2BGR)
        elif self.active_stage_key == "3. Lokale Hitze-Differenz":
            raw = cv2.cvtColor(self.current_result["heat_diff"], cv2.COLOR_GRAY2BGR)
        elif self.active_stage_key == "5. Pennes Bioheat":
            bio_res = self.current_result.get("bioheat_results", {})
            flux_mag = bio_res.get("flux_magnitude")
            if flux_mag is not None:
                norm_flux = cv2.normalize(flux_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                raw = apply_colormap_to_image(norm_flux, "Inferno")
            else:
                raw = self.current_result["overlay_bgr"]
        elif self.active_stage_key == "6. Frangi-Venen":
            frangi_map = self.current_result.get("frangi_vesselness")
            if frangi_map is not None:
                raw = apply_colormap_to_image(frangi_map, "Inferno")
            else:
                raw = self.current_result["overlay_bgr"]
        elif self.active_stage_key == "7. Bilaterale Asymmetrie":
            asym_res = self.current_result.get("bilateral_map_results", {})
            asym_map = asym_res.get("asymmetry_map")
            if asym_map is not None and asym_res.get("valid"):
                norm_asym = np.clip(asym_map / 4.0 * 255.0, 0, 255).astype(np.uint8)
                raw = apply_colormap_to_image(norm_asym, "Turbo")
            else:
                raw = self.current_result["overlay_bgr"]
        else:
            raw = self.current_result["overlay_bgr"]

        img_to_show = raw.copy()

        # ROI Overlay zeichnen
        if self.roi_box:
            x1, y1, x2, y2 = self.roi_box
            cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (255, 255, 0), 2)
        elif self.roi_drag_start and self.roi_drag_current:
            x1, x2 = sorted([self.roi_drag_start[0], self.roi_drag_current[0]])
            y1, y2 = sorted([self.roi_drag_start[1], self.roi_drag_current[1]])
            cv2.rectangle(img_to_show, (x1, y1), (x2, y2), (0, 255, 255), 1)

        rgb = cv2.cvtColor(img_to_show, cv2.COLOR_BGR2RGB)
        full_pil = Image.fromarray(rgb)
        self._rendered_pil = full_pil

        orig_w, orig_h = full_pil.size

        # Zoom & Pan Crop berechnen
        if self.zoom_level > 1.0:
            view_w = max(10, int(round(orig_w / self.zoom_level)))
            view_h = max(10, int(round(orig_h / self.zoom_level)))

            max_pan_x = (orig_w - view_w) / 2.0
            max_pan_y = (orig_h - view_h) / 2.0
            self.pan_x = float(np.clip(self.pan_x, -max_pan_x, max_pan_x))
            self.pan_y = float(np.clip(self.pan_y, -max_pan_y, max_pan_y))

            center_x = orig_w / 2.0 - self.pan_x
            center_y = orig_h / 2.0 - self.pan_y

            crop_x1 = int(np.clip(round(center_x - view_w / 2.0), 0, orig_w - view_w))
            crop_y1 = int(np.clip(round(center_y - view_h / 2.0), 0, orig_h - view_h))
            crop_x2 = crop_x1 + view_w
            crop_y2 = crop_y1 + view_h

            self._visible_crop = (crop_x1, crop_y1, crop_x2, crop_y2)
            display_pil = full_pil.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        else:
            self._visible_crop = (0, 0, orig_w, orig_h)
            display_pil = full_pil

        self.img_lbl.update_idletasks()
        w = max(self.img_lbl.winfo_width() - 16, 300)
        h = max(self.img_lbl.winfo_height() - 16, 200)

        crop_w, crop_h = display_pil.size
        ratio = min(w / crop_w, h / crop_h)
        self._render_scale = ratio
        disp_w = max(1, int(crop_w * ratio))
        disp_h = max(1, int(crop_h * ratio))

        self._offset_x = (self.img_lbl.winfo_width() - disp_w) // 2
        self._offset_y = (self.img_lbl.winfo_height() - disp_h) // 2

        ctk_img = make_display_ctk_image(display_pil, w, h)
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

        crop_x1, crop_y1, crop_x2, crop_y2 = self._visible_crop
        crop_w = crop_x2 - crop_x1
        crop_h = crop_y2 - crop_y1

        disp_w = crop_w * self._render_scale
        disp_h = crop_h * self._render_scale

        if 0 <= mx < disp_w and 0 <= my < disp_h:
            local_x = int(mx / self._render_scale)
            local_y = int(my / self._render_scale)
            full_x = crop_x1 + local_x
            full_y = crop_y1 + local_y
            orig_w, orig_h = self._rendered_pil.size
            return min(max(full_x, 0), orig_w - 1), min(max(full_y, 0), orig_h - 1)
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
            self.live_status_lbl.configure(text="Befund: Hyperthermie / Hotspot", text_color=COLOR_DANGER)
        elif is_body:
            self.live_status_lbl.configure(text="Befund: Physiologisches Gewebe", text_color=COLOR_SUCCESS)
        else:
            self.live_status_lbl.configure(text="Befund: Hintergrund / Umfeld", text_color=COLOR_TEXT_MUTED)

    def _on_mouse_leave(self, event) -> None:
        self.live_temp_lbl.configure(text="--.- °C")
        self.live_coord_lbl.configure(text="Koordinaten: X=--, Y=--")
        self.live_status_lbl.configure(text="Befund: Cursor über Bild bewegen", text_color=COLOR_TEXT_MUTED)

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

        self.roi_title_lbl.configure(text=f"Auswahl: {x2-x1}x{y2-y1} px", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        self.roi_stats_rows["mean"].configure(text=f"{mean_c:.2f} °C")
        self.roi_stats_rows["std"].configure(text=f"±{std_c:.2f} °C")
        self.roi_stats_rows["min"].configure(text=f"{min_c:.1f} °C")
        self.roi_stats_rows["max"].configure(text=f"{max_c:.1f} °C")
        self.roi_stats_rows["area"].configure(text=f"{area_px:,} px")

    def clear_roi(self) -> None:
        self.roi_box = None
        self.roi_drag_start = None
        self.roi_drag_current = None
        self.roi_title_lbl.configure(text="Rechteck mit Maus aufziehen", font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_MUTED)
        for lbl in self.roi_stats_rows.values():
            lbl.configure(text="--")
        self.redraw()
