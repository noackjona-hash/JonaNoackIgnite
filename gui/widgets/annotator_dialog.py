# -*- coding: utf-8 -*-
"""gui/widgets/annotator_dialog.py – Interactive Ground Truth Annotator for IGNITE."""

from __future__ import annotations
import os
import tkinter as tk
from typing import Optional, Callable, Any
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import cv2

import config
import image_processing
import dataset_evaluator
from gui.theme import (
    COLOR_BG_APP,
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
    COLOR_CONTAINER_GREEN,
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card, apply_colormap_to_image


class GroundTruthAnnotatorDialog(ctk.CTkToplevel):
    """Interaktiver Ground-Truth-Annotator zur wissenschaftlichen Modell-Validierung."""

    def __init__(
        self,
        master,
        image_path: str,
        on_saved: Optional[Callable[[str], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)

        self.image_path = image_path
        self.on_saved = on_saved
        self.title("IGNITE – Ground-Truth Annotator & Modell-Validierung")
        self.geometry("1180x760")
        self.minsize(1050, 680)

        self.transient(master)
        self.grab_set()

        # State
        self.raw_img = image_processing.load_thermal_image(image_path)
        self.h_img, self.w_img = self.raw_img.shape[:2]

        # IGNITE Pipeline ausführen
        self.diff_vis, self.pred_mask = image_processing.run_rust_pipeline(self.raw_img)
        self.body_mask = image_processing._extract_body_mask_cpu(self.raw_img)

        # Ground Truth Maske initialisieren (vorhandene laden falls existent)
        self.gt_mask = np.zeros((self.h_img, self.w_img), dtype=np.uint8)
        self._load_existing_gt()

        # Tool State
        self.current_tool: str = "brush"  # 'brush', 'eraser'
        self.brush_size: int = 14
        self.gt_alpha: float = 0.60
        self.pred_alpha: float = 0.40

        self.canvas_scale: float = 1.0
        self.offset_x: int = 0
        self.offset_y: int = 0
        self._tk_img = None

        self._build_ui()
        self._render_canvas()
        self._update_live_metrics()

    def _load_existing_gt(self) -> None:
        """Lädt eine existierende Maske aus test-data/ground_truth/ falls vorhanden."""
        stem = os.path.splitext(os.path.basename(self.image_path))[0]
        gt_dir = os.path.join(os.path.dirname(self.image_path), "ground_truth")
        candidates = [
            os.path.join(gt_dir, f"{stem}_mask.png"),
            os.path.join(gt_dir, f"{stem}.png")
        ]
        for p in candidates:
            if os.path.exists(p):
                loaded = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
                if loaded is not None:
                    if loaded.shape != (self.h_img, self.w_img):
                        loaded = cv2.resize(loaded, (self.w_img, self.h_img), interpolation=cv2.INTER_NEAREST)
                    self.gt_mask = (loaded > 127).astype(np.uint8) * 255
                    break

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)  # Canvas Bereich
        self.grid_columnconfigure(1, weight=0, minsize=380)  # Sidebar
        self.grid_rowconfigure(0, weight=1)

        # ── Linker Bereich: Canvas ───────────────────────────────────────────
        left_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        left_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        # Top Bar
        top_bar = ctk.CTkFrame(left_card, fg_color="transparent", height=46)
        top_bar.pack(fill=ctk.X, padx=14, pady=(10, 6))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text=f"ANNOTATION: {os.path.basename(self.image_path)}",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            top_bar,
            text="Linksklick + Ziehen zum Zeichnen · Rechtsklick / Tool zum Radieren",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT)

        ctk.CTkFrame(left_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        self.canvas = tk.Canvas(
            left_card,
            bg="#0F172A",
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        self.canvas.bind("<Button-1>", self._on_draw_start)
        self.canvas.bind("<B1-Motion>", self._on_draw_move)
        self.canvas.bind("<Button-3>", self._on_erase_start)
        self.canvas.bind("<B3-Motion>", self._on_erase_move)
        self.canvas.bind("<Configure>", lambda e: self._render_canvas())

        # ── Rechter Bereich: Tools & Live Scorecard ──────────────────────────
        self.side_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.side_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")
        self.side_card.configure(width=380)

        scroll = ctk.CTkScrollableFrame(self.side_card, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=12, pady=12)

        # 1. Tool-Auswahl
        ctk.CTkLabel(
            scroll,
            text="WERKZEUGE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(2, 6))

        tool_btn_box = ctk.CTkFrame(scroll, fg_color="transparent")
        tool_btn_box.pack(fill=ctk.X, pady=(0, 10))

        self.btn_brush = ctk.CTkButton(
            tool_btn_box,
            text="Pinsel (GT)",
            command=lambda: self._set_tool("brush"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=32,
            width=110
        )
        self.btn_brush.pack(side=ctk.LEFT, padx=(0, 6))

        self.btn_eraser = ctk.CTkButton(
            tool_btn_box,
            text="Radiergummi",
            command=lambda: self._set_tool("eraser"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=32,
            width=110
        )
        self.btn_eraser.pack(side=ctk.LEFT, padx=6)

        ctk.CTkButton(
            tool_btn_box,
            text="Löschen",
            command=self._clear_gt,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_DANGER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            corner_radius=RADIUS_BUTTON,
            height=32,
            width=80
        ).pack(side=ctk.RIGHT)

        # Pinselgröße Slider
        ctk.CTkLabel(scroll, text="Pinselgröße:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(fill=ctk.X)
        self.brush_slider = ctk.CTkSlider(scroll, from_=4, to=40, number_of_steps=18, command=self._on_brush_slider)
        self.brush_slider.set(self.brush_size)
        self.brush_slider.pack(fill=ctk.X, pady=(2, 12))

        # 2. Live Scorecard
        ctk.CTkLabel(
            scroll,
            text="LIVE-MODELLVALIDIERUNG (VS. IGNITE)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, pady=(6, 6))

        self.score_card = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.score_card.pack(fill=ctk.X, pady=(0, 14))

        sc_inner = ctk.CTkFrame(self.score_card, fg_color="transparent")
        sc_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.metric_labels = {}
        metrics = [
            ("dice", "Dice-Score (F₁):", "0.000"),
            ("iou", "IoU (Jaccard Index):", "0.000"),
            ("sens", "Sensitivität (Recall):", "0.0 %"),
            ("spec", "Spezifität (TNR):", "0.0 %"),
            ("prec", "Präzision (PPV):", "0.0 %"),
            ("gain", "Gewinn vs. Otsu:", "+0.000")
        ]

        for k, title, d_val in metrics:
            row = ctk.CTkFrame(sc_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            lbl_v = ctk.CTkLabel(row, text=d_val, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
            lbl_v.pack(side=ctk.RIGHT)
            self.metric_labels[k] = lbl_v

        # 3. Transparenz-Regler
        ctk.CTkLabel(scroll, text="Overlay-Transparenz:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(fill=ctk.X, pady=(4, 2))
        self.alpha_slider = ctk.CTkSlider(scroll, from_=0.0, to=1.0, command=self._on_alpha_slider)
        self.alpha_slider.set(self.gt_alpha)
        self.alpha_slider.pack(fill=ctk.X, pady=(0, 16))

        # 4. Speichern Button
        self.save_btn = ctk.CTkButton(
            scroll,
            text="Ground-Truth Maske speichern",
            command=self._save_gt_mask,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=40
        )
        self.save_btn.pack(fill=ctk.X, pady=(0, 8))

        self.status_lbl = ctk.CTkLabel(
            scroll,
            text="Bereit zum Annotieren",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.status_lbl.pack(fill=ctk.X)

    def _set_tool(self, tool: str) -> None:
        self.current_tool = tool
        if tool == "brush":
            self.btn_brush.configure(fg_color=COLOR_PRIMARY, text_color="#FFFFFF")
            self.btn_eraser.configure(fg_color=COLOR_BG_CARD_VARIANT, text_color=COLOR_TEXT_PRIMARY)
        else:
            self.btn_eraser.configure(fg_color=COLOR_PRIMARY, text_color="#FFFFFF")
            self.btn_brush.configure(fg_color=COLOR_BG_CARD_VARIANT, text_color=COLOR_TEXT_PRIMARY)

    def _on_brush_slider(self, val: float) -> None:
        self.brush_size = int(val)

    def _on_alpha_slider(self, val: float) -> None:
        self.gt_alpha = float(val)
        self._render_canvas()

    def _clear_gt(self) -> None:
        self.gt_mask.fill(0)
        self._render_canvas()
        self._update_live_metrics()

    def _canvas_to_img_coords(self, cx: int, cy: int) -> tuple[int, int]:
        ix = int((cx - self.offset_x) / self.canvas_scale)
        iy = int((cy - self.offset_y) / self.canvas_scale)
        return max(0, min(self.w_img - 1, ix)), max(0, min(self.h_img - 1, iy))

    def _on_draw_start(self, event):
        ix, iy = self._canvas_to_img_coords(event.x, event.y)
        color = 255 if self.current_tool == "brush" else 0
        cv2.circle(self.gt_mask, (ix, iy), self.brush_size, color, -1)
        self._render_canvas()
        self._update_live_metrics()

    def _on_draw_move(self, event):
        ix, iy = self._canvas_to_img_coords(event.x, event.y)
        color = 255 if self.current_tool == "brush" else 0
        cv2.circle(self.gt_mask, (ix, iy), self.brush_size, color, -1)
        self._render_canvas()
        self._update_live_metrics()

    def _on_erase_start(self, event):
        ix, iy = self._canvas_to_img_coords(event.x, event.y)
        cv2.circle(self.gt_mask, (ix, iy), self.brush_size, 0, -1)
        self._render_canvas()
        self._update_live_metrics()

    def _on_erase_move(self, event):
        ix, iy = self._canvas_to_img_coords(event.x, event.y)
        cv2.circle(self.gt_mask, (ix, iy), self.brush_size, 0, -1)
        self._render_canvas()
        self._update_live_metrics()

    def _render_canvas(self) -> None:
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        self.canvas_scale = min(cw / self.w_img, ch / self.h_img)
        disp_w = int(self.w_img * self.canvas_scale)
        disp_h = int(self.h_img * self.canvas_scale)
        self.offset_x = (cw - disp_w) // 2
        self.offset_y = (ch - disp_h) // 2

        # Basis: Originalbild (Turbo Colormap)
        base_rgb = apply_colormap_to_image(self.raw_img, "Turbo")
        base_bgr = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2BGR)

        # 1. IGNITE Vorhersage-Maske einblenden (Rot)
        red_layer = np.zeros_like(base_bgr)
        red_layer[:] = [0, 0, 255]
        pred_blend = cv2.addWeighted(base_bgr, 1.0 - self.pred_alpha, red_layer, self.pred_alpha, 0)
        overlay = np.where(self.pred_mask[:, :, None] == 255, pred_blend, base_bgr).astype(np.uint8)

        # 2. Ground Truth Maske einblenden (Grün)
        green_layer = np.zeros_like(overlay)
        green_layer[:] = [0, 255, 0]
        gt_blend = cv2.addWeighted(overlay, 1.0 - self.gt_alpha, green_layer, self.gt_alpha, 0)
        final_overlay = np.where(self.gt_mask[:, :, None] == 255, gt_blend, overlay).astype(np.uint8)

        # Reskalieren für Anzeige
        resized = cv2.resize(final_overlay, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)
        rgb_disp = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        pil_img = Image.fromarray(rgb_disp)
        self._tk_img = ImageTk.PhotoImage(pil_img)

        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y, anchor="nw", image=self._tk_img)

    def _update_live_metrics(self) -> None:
        """Berechnet Dice, IoU, Sensitivität etc. in Echtzeit."""
        gt_pixels = int(np.sum(self.gt_mask == 255))
        if gt_pixels == 0:
            self.metric_labels["dice"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            self.metric_labels["iou"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            self.metric_labels["sens"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            self.metric_labels["spec"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            self.metric_labels["prec"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            self.metric_labels["gain"].configure(text="--.-", text_color=COLOR_TEXT_MUTED)
            return

        m_ignite = dataset_evaluator.evaluate_metrics(self.pred_mask, self.gt_mask, self.body_mask)
        m_otsu = dataset_evaluator.evaluate_metrics(
            dataset_evaluator._baseline_otsu_predict(self.raw_img), self.gt_mask, self.body_mask
        )

        dice = m_ignite["dice"]
        iou = m_ignite["iou"]
        sens = m_ignite["sensitivity"] * 100.0
        spec = m_ignite["specificity"] * 100.0
        prec = m_ignite["precision"] * 100.0
        gain = dice - m_otsu["dice"]

        d_color = COLOR_SUCCESS if dice >= 0.80 else (COLOR_PRIMARY if dice >= 0.50 else COLOR_DANGER)
        self.metric_labels["dice"].configure(text=f"{dice:.3f}", text_color=d_color)
        self.metric_labels["iou"].configure(text=f"{iou:.3f}")
        self.metric_labels["sens"].configure(text=f"{sens:.1f} %")
        self.metric_labels["spec"].configure(text=f"{spec:.1f} %")
        self.metric_labels["prec"].configure(text=f"{prec:.1f} %")

        gain_color = COLOR_SUCCESS if gain > 0 else COLOR_DANGER
        self.metric_labels["gain"].configure(text=f"{gain:+.3f}", text_color=gain_color)

    def _save_gt_mask(self) -> None:
        """Speichert die GT-Maske in test-data/ground_truth/."""
        gt_dir = os.path.join(os.path.dirname(self.image_path), "ground_truth")
        os.makedirs(gt_dir, exist_ok=True)

        stem = os.path.splitext(os.path.basename(self.image_path))[0]
        out_path = os.path.join(gt_dir, f"{stem}_mask.png")

        cv2.imwrite(out_path, self.gt_mask)
        self.status_lbl.configure(
            text=f"✓ Gespeichert: {os.path.basename(out_path)}",
            text_color=COLOR_SUCCESS
        )

        if self.on_saved:
            self.on_saved(out_path)
