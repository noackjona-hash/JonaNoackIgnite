# -*- coding: utf-8 -*-
"""gui/utils_ui.py – UI Helper Utilities for IGNITE Medical Imaging Suite."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk
import cv2
import numpy as np
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
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BADGE,
    RADIUS_BUTTON,
)


def make_material_card(
    master,
    corner_radius: int = RADIUS_CARD,
    border_width: int = 1,
    border_color=COLOR_OUTLINE,
    fg_color=COLOR_BG_CARD,
    **kwargs
) -> ctk.CTkFrame:
    """Erstellt ein präzises, kontraststarkes Workstation-Panel."""
    return ctk.CTkFrame(
        master,
        corner_radius=corner_radius,
        border_width=border_width,
        border_color=border_color,
        fg_color=fg_color,
        **kwargs
    )


def make_status_chip(
    master,
    text: str,
    dot_color: str = COLOR_PRIMARY,
    bg_color=COLOR_CONTAINER_BLUE,
    text_color=COLOR_TEXT_PRIMARY,
    corner_radius: int = RADIUS_BADGE,
    height: int = 26,
    **kwargs
) -> ctk.CTkFrame:
    """Erstellt ein kompaktes, professionelles Status-Badge."""
    chip = ctk.CTkFrame(
        master,
        fg_color=bg_color,
        corner_radius=corner_radius,
        border_width=0,
        height=height,
        **kwargs
    )
    chip.pack_propagate(False)

    dot = ctk.CTkFrame(
        chip,
        width=7,
        height=7,
        corner_radius=3,
        fg_color=dot_color
    )
    dot.pack(side=ctk.LEFT, padx=(8, 6), pady=4)

    lbl = ctk.CTkLabel(
        chip,
        text=text,
        font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
        text_color=text_color
    )
    lbl.pack(side=ctk.LEFT, padx=(0, 8), pady=2)

    return chip


def make_slider_setting(
    master,
    title: str,
    description: str,
    from_: float,
    to: float,
    default_val: float,
    resolution: float = 0.01,
    unit_str: str = "",
    command: Optional[Callable[[float], None]] = None,
    is_percent: bool = False,
) -> tuple[ctk.CTkSlider, ctk.CTkLabel]:
    """Erstellt eine technische Parameter-Schiebereglerzeile."""
    row_frame = ctk.CTkFrame(master, fg_color="transparent")
    row_frame.pack(fill=ctk.X, pady=8)

    # Header-Zeile mit Titel & Badge
    header = ctk.CTkFrame(row_frame, fg_color="transparent")
    header.pack(fill=ctk.X, pady=(0, 4))

    lbl_title = ctk.CTkLabel(
        header,
        text=title,
        font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
        text_color=COLOR_TEXT_PRIMARY,
        anchor="w"
    )
    lbl_title.pack(side=ctk.LEFT)

    # Formatierungsfunktion
    def _fmt(v: float) -> str:
        if is_percent:
            return f"{v * 100:.1f} %"
        elif resolution >= 1.0:
            return f"{int(round(v))} {unit_str}".strip()
        elif resolution >= 0.1:
            return f"{v:.1f} {unit_str}".strip()
        else:
            return f"{v:.2f} {unit_str}".strip()

    val_badge = ctk.CTkLabel(
        header,
        text=_fmt(default_val),
        font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"),
        text_color=COLOR_PRIMARY,
        fg_color=COLOR_BG_CARD_VARIANT,
        corner_radius=RADIUS_BADGE,
        width=64,
        height=24
    )
    val_badge.pack(side=ctk.RIGHT)

    if description:
        lbl_desc = ctk.CTkLabel(
            row_frame,
            text=description,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=480,
            justify="left"
        )
        lbl_desc.pack(fill=ctk.X, pady=(1, 4))

    # Callback wrapper
    def _on_slide(val: float):
        val_badge.configure(text=_fmt(val))
        if command:
            command(val)

    steps = max(1, int(round((to - from_) / resolution)))
    slider = ctk.CTkSlider(
        row_frame,
        from_=from_,
        to=to,
        number_of_steps=steps,
        fg_color=COLOR_OUTLINE,
        progress_color=COLOR_PRIMARY,
        button_color=COLOR_PRIMARY,
        button_hover_color=COLOR_PRIMARY_HOVER,
        height=16,
        button_length=16,
        button_corner_radius=4,
        command=_on_slide
    )
    slider.set(default_val)
    slider.pack(fill=ctk.X, pady=(2, 2))

    return slider, val_badge


def apply_colormap_to_image(img_gray: np.ndarray, colormap_name: str) -> np.ndarray:
    """Wendet die gewünschte Farbpalette auf ein Graustufen-Thermobild an."""
    if len(img_gray.shape) == 3 and img_gray.shape[2] == 3:
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_RGB2GRAY)

    if colormap_name in ("Turbo", "Google Turbo", "Regenbogen (Jet)", "Jet"):
        try:
            return cv2.applyColorMap(img_gray, cv2.COLORMAP_TURBO)
        except Exception:
            return cv2.applyColorMap(img_gray, cv2.COLORMAP_JET)
    elif colormap_name in ("Inferno", "Thermisch"):
        return cv2.applyColorMap(img_gray, cv2.COLORMAP_INFERNO)
    elif colormap_name in ("Heiß (Hot)", "Hot"):
        return cv2.applyColorMap(img_gray, cv2.COLORMAP_HOT)
    elif colormap_name in ("Plasma",):
        return cv2.applyColorMap(img_gray, cv2.COLORMAP_PLASMA)
    else:  # Graustufen
        return cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)


def make_display_ctk_image(pil_img: Image.Image, max_w: int, max_h: int, scaling_factor: float = 1.0) -> ctk.CTkImage:
    """Skaliert ein PIL Image mit Anti-Aliasing und erzeugt ein DPI-korrektes CTkImage."""
    orig_w, orig_h = pil_img.size
    if orig_w == 0 or orig_h == 0:
        return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(1, 1))

    # Thumbnail unter Beibehaltung des Seitenverhältnisses
    ratio = min(max_w / orig_w, max_h / orig_h)
    new_w = max(1, int(round(orig_w * ratio)))
    new_h = max(1, int(round(orig_h * ratio)))

    resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    sf = max(0.5, scaling_factor)
    disp_w = max(1, int(round(new_w / sf)))
    disp_h = max(1, int(round(new_h / sf)))

    return ctk.CTkImage(light_image=resized, dark_image=resized, size=(disp_w, disp_h))
