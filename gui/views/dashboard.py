# -*- coding: utf-8 -*-
"""dashboard.py – 4-Panel Grid Dashboard View für IGNITE.

Klare visuelle Hierarchie: Jedes Panel hat einen kompakten Header mit
Titel, Status-Badge und einem Vollbild-Button für schnellen Zoom.
"""

import tkinter as tk
import customtkinter as ctk
from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_BG_MAIN,
    COLOR_PRIMARY_ACCENT,
    COLOR_HOVER_ACCENT,
    COLOR_BG_INPUT,
    FONT_FAMILY
)

_PANEL_META = [
    {
        "key":   "1. Originalbild",
        "label": "1  Originalbild",
        "hint":  "Rohes Wärmebild mit gewählter Farbpalette",
        "row": 0, "col": 0,
    },
    {
        "key":   "2. Hintergrund-Maske",
        "label": "2  Körper-Maske",
        "hint":  "Otsu-Segmentierung + Distanztransformation",
        "row": 0, "col": 1,
    },
    {
        "key":   "3. Lokale Hitze-Differenz",
        "label": "3  Top-Hat Differenz",
        "hint":  "Morphologisches Top-Hat µ+kσ Thresholding",
        "row": 1, "col": 0,
    },
    {
        "key":   "4. Erkannte Hotspots (Rust)",
        "label": "4  Hotspot-Overlay",
        "hint":  "Erkannte Entzündungsherde mit Annotationen",
        "row": 1, "col": 1,
    },
]

_EMPTY_TEXT = "Bereit für Analyse\n\nWärmebild über die Seitenleiste laden\noder  Strg+O  drücken."

class DashboardView:
    """Verwaltet das 4-Panel Grid-Layout (Overview + Einzel-Tabs)."""

    def __init__(
        self,
        master_tab,
        hover_callback,
        leave_callback,
        roi_start_callback,
        roi_drag_callback,
        roi_end_callback,
        open_fullscreen_callback=None,
    ):
        self.panels: dict[str, ctk.CTkLabel] = {}
        self.panels_full: dict[str, ctk.CTkLabel] = {}
        self._open_fullscreen_cb = open_fullscreen_callback

        self._build_grid_tab(
            master_tab, hover_callback, leave_callback,
            roi_start_callback, roi_drag_callback, roi_end_callback
        )

    # ── Grid-Übersicht ───────────────────────────────────────────────────────

    def _build_grid_tab(self, master_tab, hover_cb, leave_cb, roi_start_cb, roi_drag_cb, roi_end_cb):
        grid_frame = ctk.CTkFrame(master_tab, fg_color="transparent")
        grid_frame.pack(fill=ctk.BOTH, expand=True, padx=4, pady=4)

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)

        for meta in _PANEL_META:
            self._build_panel_card(
                parent=grid_frame,
                meta=meta,
                is_grid=True,
                hover_cb=hover_cb, leave_cb=leave_cb,
                roi_start_cb=roi_start_cb, roi_drag_cb=roi_drag_cb, roi_end_cb=roi_end_cb,
            )

    def _build_panel_card(
        self, parent, meta: dict, is_grid: bool,
        hover_cb, leave_cb, roi_start_cb, roi_drag_cb, roi_end_cb,
        fullsize_tab_frame=None
    ):
        """Erstellt eine einzelne Bildkachel mit Header-Bar."""
        key = meta["key"]
        label_text = meta["label"]
        hint_text = meta["hint"]

        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )

        if is_grid:
            card.grid(row=meta["row"], column=meta["col"], padx=6, pady=6, sticky="nsew")
        else:
            card.pack(fill=ctk.BOTH, expand=True, padx=6, pady=6)

        # ── Header-Leiste ────────────────────────────────────────────────────
        header = ctk.CTkFrame(card, fg_color=COLOR_BG_INPUT, corner_radius=0, height=32)
        header.pack(fill=ctk.X, padx=0, pady=0)
        header.pack_propagate(False)

        # Farbiger linker Akzent-Streifen (visuell unterscheidet die Panels)
        _accent_colors = [COLOR_PRIMARY_ACCENT, "#34C759", "#FF9500", "#FF3B30"]
        _idx = [m["key"] for m in _PANEL_META].index(key) if key in [m["key"] for m in _PANEL_META] else 0
        accent_color = _accent_colors[_idx % len(_accent_colors)]

        ctk.CTkFrame(header, width=3, fg_color=accent_color, corner_radius=0).pack(
            side=ctk.LEFT, fill=ctk.Y, padx=(0, 8)
        )

        ctk.CTkLabel(
            header,
            text=label_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(side=ctk.LEFT)

        ctk.CTkLabel(
            header,
            text=hint_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=9),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(side=ctk.LEFT, padx=(6, 0))

        # Vollbild-Button (rechtsbündig)
        if self._open_fullscreen_cb and is_grid:
            zoom_btn = ctk.CTkButton(
                header,
                text="⤢",
                width=28, height=22,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                fg_color="transparent",
                text_color=COLOR_TEXT_MUTED,
                hover_color=COLOR_BORDER_CARD,
                corner_radius=4,
                command=lambda k=key: self._open_fullscreen_cb(k)
            )
            zoom_btn.pack(side=ctk.RIGHT, padx=4)

        # ── Bildbereich ───────────────────────────────────────────────────────
        img_lbl = ctk.CTkLabel(
            card,
            text=_EMPTY_TEXT,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            fg_color="transparent",
            anchor="center",
            justify="center"
        )
        img_lbl.pack(fill=ctk.BOTH, expand=True, padx=0, pady=(0, 0))

        # Event-Bindings
        img_lbl.bind("<Motion>",        lambda e, k=key, g=is_grid: hover_cb(e, k, g))
        img_lbl.bind("<Leave>",         leave_cb)
        img_lbl.bind("<ButtonPress-1>", lambda e, k=key, g=is_grid: roi_start_cb(e, k, g))
        img_lbl.bind("<B1-Motion>",     lambda e, k=key, g=is_grid: roi_drag_cb(e, k, g))
        img_lbl.bind("<ButtonRelease-1>", lambda e, k=key, g=is_grid: roi_end_cb(e, k, g))

        # Rechtsklick-Kontextmenü
        ctx_menu = tk.Menu(img_lbl, tearoff=0)
        ctx_menu.add_command(label="Vollbild öffnen", command=lambda k=key: (
            self._open_fullscreen_cb(k) if self._open_fullscreen_cb else None
        ))
        img_lbl.bind("<Button-3>", lambda e, m=ctx_menu: m.tk_popup(e.x_root, e.y_root))

        if is_grid:
            self.panels[key] = img_lbl
        else:
            self.panels_full[key] = img_lbl

    # ── Vollbild-Tabs ────────────────────────────────────────────────────────

    def setup_fullsize_tabs(
        self, tabview,
        hover_cb, leave_cb, roi_start_cb, roi_drag_cb, roi_end_cb
    ):
        tab_mapping = {
            "1. Originalbild":           "1. Originalbild",
            "2. Hintergrund-Maske":      "2. Hintergrund-Maske",
            "3. Lokale Hitze-Differenz": "3. Lokale Hitze-Differenz",
            "4. Erkannte Hotspots (Rust)": "4. Erkannte Hotspots",
        }

        for step_key, tab_name in tab_mapping.items():
            meta = next((m for m in _PANEL_META if m["key"] == step_key), {
                "key": step_key, "label": step_key, "hint": "", "row": 0, "col": 0
            })
            self._build_panel_card(
                parent=tabview.tab(tab_name),
                meta=meta,
                is_grid=False,
                hover_cb=hover_cb, leave_cb=leave_cb,
                roi_start_cb=roi_start_cb, roi_drag_cb=roi_drag_cb, roi_end_cb=roi_end_cb,
            )

