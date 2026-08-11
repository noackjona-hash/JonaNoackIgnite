# -*- coding: utf-8 -*-
"""dashboard.py – 4-Panel Grid Dashboard View für IGNITE.

Sauberes, professionelles Layout: Jedes Panel zeigt Schritt-Nummer + Titel
als kompakten Titel-Streifen, darunter der Bildbereich.
"""

import tkinter as tk
import customtkinter as ctk
from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED,
    COLOR_BG_MAIN,
    COLOR_PRIMARY_ACCENT,
    FONT_FAMILY,
)

# (key, kurzname, zeile, spalte, akzentfarbe)
_PANELS = [
    ("1. Originalbild",             "Originalbild",       0, 0, "#007AFF"),
    ("2. Hintergrund-Maske",        "Körper-Maske",       0, 1, "#34C759"),
    ("3. Lokale Hitze-Differenz",   "Top-Hat Differenz",  1, 0, "#FF9500"),
    ("4. Erkannte Hotspots (Rust)", "Hotspot-Overlay",    1, 1, "#FF3B30"),
]

_EMPTY = "Wärmebild laden um\ndie Analyse zu starten\n\nStrg+O"


class DashboardView:
    """Verwaltet das 4-Panel Grid-Layout und die Einzel-Tabs."""

    def __init__(
        self, master_tab,
        hover_callback, leave_callback,
        roi_start_callback, roi_drag_callback, roi_end_callback,
        open_fullscreen_callback=None,
    ):
        self.panels:      dict[str, ctk.CTkLabel] = {}
        self.panels_full: dict[str, ctk.CTkLabel] = {}
        self._fullscreen_cb = open_fullscreen_callback

        self._build_grid(
            master_tab,
            hover_callback, leave_callback,
            roi_start_callback, roi_drag_callback, roi_end_callback,
        )

    # ── Grid-Übersicht ───────────────────────────────────────────────────────

    def _build_grid(self, parent, hover_cb, leave_cb, roi_s, roi_d, roi_e):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill=ctk.BOTH, expand=True, padx=6, pady=6)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_columnconfigure(1, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        for key, short, row, col, color in _PANELS:
            lbl = self._make_card(
                wrap, key, short, color,
                row=row, col=col, is_grid=True,
                hover_cb=hover_cb, leave_cb=leave_cb,
                roi_s=roi_s, roi_d=roi_d, roi_e=roi_e,
            )
            self.panels[key] = lbl

    # ── Vollbild-Tabs ────────────────────────────────────────────────────────

    def setup_fullsize_tabs(self, tabview, hover_cb, leave_cb,
                            roi_start_cb, roi_drag_cb, roi_end_cb):
        tab_map = {
            "1. Originalbild":             "1. Originalbild",
            "2. Hintergrund-Maske":        "2. Hintergrund-Maske",
            "3. Lokale Hitze-Differenz":   "3. Lokale Hitze-Differenz",
            "4. Erkannte Hotspots (Rust)": "4. Erkannte Hotspots",
        }
        for key, tab_name in tab_map.items():
            _, short, _, _, color = next(p for p in _PANELS if p[0] == key)
            lbl = self._make_card(
                tabview.tab(tab_name), key, short, color,
                row=0, col=0, is_grid=False,
                hover_cb=hover_cb, leave_cb=leave_cb,
                roi_s=roi_start_cb, roi_d=roi_drag_cb, roi_e=roi_end_cb,
            )
            self.panels_full[key] = lbl

    # ── Hilfsmethode: eine Panel-Karte ───────────────────────────────────────

    def _make_card(
        self, parent, key, short_name, accent_color,
        *, row, col, is_grid,
        hover_cb, leave_cb, roi_s, roi_d, roi_e,
    ) -> ctk.CTkLabel:
        """Erstellt eine Bild-Kachel und gibt das Bild-Label zurück."""

        card = ctk.CTkFrame(
            parent,
            fg_color=COLOR_BG_CARD,
            corner_radius=10,
            border_width=1,
            border_color=COLOR_BORDER_CARD,
        )
        if is_grid:
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
        else:
            card.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

        # ── Titel-Zeile mit farbigem Punkt ───────────────────────────────────
        hdr = ctk.CTkFrame(card, fg_color="transparent", height=34)
        hdr.pack(fill=ctk.X, padx=12, pady=(8, 0))
        hdr.pack_propagate(False)

        # Kleiner farbiger Kreis als Schritt-Indikator
        _mode_idx = 0 if ctk.get_appearance_mode() == "Light" else 1
        dot_cv = tk.Canvas(hdr, width=9, height=9,
                           bg=COLOR_BG_CARD[_mode_idx],
                           highlightthickness=0)
        dot_cv.pack(side=ctk.LEFT, padx=(0, 7))
        dot_cv.create_oval(1, 1, 8, 8, fill=accent_color, outline="")

        ctk.CTkLabel(
            hdr,
            text=short_name,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w",
        ).pack(side=ctk.LEFT, fill=ctk.X, expand=True)

        if self._fullscreen_cb and is_grid:
            ctk.CTkButton(
                hdr,
                text="⤢",
                width=24, height=22,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color="transparent",
                text_color=COLOR_TEXT_MUTED,
                hover_color=COLOR_BORDER_CARD,
                corner_radius=4,
                command=lambda k=key: self._fullscreen_cb(k),
            ).pack(side=ctk.RIGHT)

        # Trennlinie
        ctk.CTkFrame(card, height=1, fg_color=COLOR_BORDER_CARD).pack(
            fill=ctk.X, padx=0, pady=(6, 0)
        )

        # ── Bild-Label ────────────────────────────────────────────────────────
        img_lbl = ctk.CTkLabel(
            card,
            text=_EMPTY,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED,
            fg_color="transparent",
            anchor="center",
            justify="center",
        )
        img_lbl.pack(fill=ctk.BOTH, expand=True, pady=(0, 6))

        # Bindings
        img_lbl.bind("<Motion>",          lambda e, k=key, g=is_grid: hover_cb(e, k, g))
        img_lbl.bind("<Leave>",           leave_cb)
        img_lbl.bind("<ButtonPress-1>",   lambda e, k=key, g=is_grid: roi_s(e, k, g))
        img_lbl.bind("<B1-Motion>",       lambda e, k=key, g=is_grid: roi_d(e, k, g))
        img_lbl.bind("<ButtonRelease-1>", lambda e, k=key, g=is_grid: roi_e(e, k, g))

        # Kontextmenü per Rechtsklick
        ctx = tk.Menu(img_lbl, tearoff=0)
        ctx.add_command(
            label="Vollbild öffnen",
            command=lambda k=key: self._fullscreen_cb(k) if self._fullscreen_cb else None,
        )
        img_lbl.bind("<Button-3>", lambda e, m=ctx: m.tk_popup(e.x_root, e.y_root))

        return img_lbl
