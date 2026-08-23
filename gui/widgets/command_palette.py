# -*- coding: utf-8 -*-
"""gui/widgets/command_palette.py – High-Contrast Command Palette (Ctrl+K) for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any
import customtkinter as ctk

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
    COLOR_CONTAINER_ACTIVE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)


class CommandPalette(ctk.CTkToplevel):
    """Präzise Befehlssuche (Ctrl+K / Ctrl+P) im High-Contrast Workstation Design."""

    _W, _H = 600, 420

    def __init__(self, master: tk.Misc, commands: list[dict[str, Any]], **kwargs) -> None:
        super().__init__(master, **kwargs)

        self._all_commands = [c for c in commands if c.get("action")]
        self._filtered: list[dict[str, Any]] = list(self._all_commands)
        self._sel_idx = 0

        self.title("")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.transient(master)
        self.resizable(False, False)

        self._build_ui()
        self._position()

        self.bind("<Escape>", self._close)
        self.bind("<Return>", self._execute_selected)
        self.bind("<Up>", self._move_up)
        self.bind("<Down>", self._move_down)
        self.bind("<FocusOut>", self._on_focus_out)

        self.after(50, lambda: self._search_entry.focus_set())

    def _build_ui(self) -> None:
        outer = ctk.CTkFrame(
            self,
            corner_radius=RADIUS_CARD,
            border_width=1,
            border_color=COLOR_OUTLINE,
            fg_color=COLOR_BG_CARD
        )
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Suchzeile ────────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(outer, fg_color="transparent", height=50)
        search_row.pack(fill=ctk.X, padx=16, pady=(10, 0))
        search_row.pack_propagate(False)

        ctk.CTkLabel(
            search_row,
            text="⌕",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20),
            text_color=COLOR_PRIMARY,
            width=26
        ).pack(side=ctk.LEFT)

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text="Befehl oder Funktion suchen…",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            border_width=0,
            fg_color="transparent",
            text_color=COLOR_TEXT_PRIMARY,
            height=38
        )
        self._search_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=8)
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())

        esc_badge = ctk.CTkLabel(
            search_row,
            text=" ESC ",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            fg_color=COLOR_BG_CARD_VARIANT,
            corner_radius=RADIUS_BADGE,
            height=22,
            width=42
        )
        esc_badge.pack(side=ctk.RIGHT)

        ctk.CTkFrame(outer, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X, pady=(8, 0))

        # ── Ergebnisliste ────────────────────────────────────────────────────
        self._results_scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent", height=300)
        self._results_scroll.pack(fill=ctk.BOTH, expand=True, padx=8, pady=(4, 0))

        # ── Statusleiste ─────────────────────────────────────────────────────
        hint = ctk.CTkFrame(outer, fg_color=COLOR_BG_CARD_VARIANT, corner_radius=0, height=28)
        hint.pack(fill=ctk.X, side=ctk.BOTTOM)
        hint.pack_propagate(False)

        ctk.CTkLabel(
            hint,
            text="↑↓ Navigieren   ·   ↵ Ausführen   ·   Esc Schließen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.LEFT, padx=16)

        self._render_results()

    def _render_results(self) -> None:
        for w in self._results_scroll.winfo_children():
            w.destroy()

        if not self._filtered:
            ctk.CTkLabel(
                self._results_scroll,
                text="Keine passenden Befehle gefunden.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_MUTED
            ).pack(pady=30)
            return

        for idx, cmd in enumerate(self._filtered):
            selected = idx == self._sel_idx
            bg_color = COLOR_CONTAINER_ACTIVE if selected else "transparent"
            text_color = COLOR_TEXT_PRIMARY

            row = ctk.CTkFrame(self._results_scroll, fg_color=bg_color, corner_radius=RADIUS_BUTTON, cursor="hand2", height=38)
            row.pack(fill=ctk.X, padx=4, pady=1)
            row.pack_propagate(False)

            content = ctk.CTkFrame(row, fg_color="transparent")
            content.pack(fill=ctk.BOTH, expand=True, padx=10, pady=4)

            # Left indicator bar
            ind_bar = ctk.CTkFrame(content, width=3, corner_radius=2, fg_color=COLOR_PRIMARY if selected else "transparent")
            ind_bar.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 8), pady=2)

            lbl_col = ctk.CTkFrame(content, fg_color="transparent")
            lbl_col.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            ctk.CTkLabel(
                lbl_col,
                text=cmd["label"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold" if selected else "normal"),
                text_color=text_color,
                height=20,
                anchor="w"
            ).pack(fill=ctk.X)

            if cmd.get("shortcut"):
                ctk.CTkLabel(
                    content,
                    text=cmd["shortcut"],
                    font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10, weight="bold"),
                    text_color=COLOR_PRIMARY if selected else COLOR_TEXT_MUTED,
                    fg_color=COLOR_BG_CARD_VARIANT if not selected else "transparent",
                    corner_radius=RADIUS_BADGE,
                    height=20,
                    width=54
                ).pack(side=ctk.RIGHT)

            _i = idx
            for w in [row, content, lbl_col]:
                w.bind("<Button-1>", lambda e, i=_i: self._execute(i))

    def _on_search_changed(self) -> None:
        q = self._search_var.get().strip().lower()
        if not q:
            self._filtered = list(self._all_commands)
        else:
            self._filtered = [c for c in self._all_commands if q in c["label"].lower() or q in c.get("desc", "").lower()]
        self._sel_idx = 0
        self._render_results()

    def _move_up(self, event=None) -> None:
        if self._sel_idx > 0:
            self._sel_idx -= 1
            self._render_results()

    def _move_down(self, event=None) -> None:
        if self._sel_idx < len(self._filtered) - 1:
            self._sel_idx += 1
            self._render_results()

    def _execute_selected(self, event=None) -> None:
        self._execute(self._sel_idx)

    def _execute(self, idx: int) -> None:
        if 0 <= idx < len(self._filtered):
            action = self._filtered[idx].get("action")
            self._close()
            if callable(action):
                self.after(50, action)

    def _close(self, event=None) -> None:
        try:
            self.destroy()
        except Exception:
            pass

    def _on_focus_out(self, event=None) -> None:
        try:
            f = self.focus_get()
            if f and (f == self or str(f).startswith(str(self))):
                return
            self._close()
        except Exception:
            self._close()

    def _position(self) -> None:
        try:
            self.update_idletasks()
            m = self.master
            m.update_idletasks()
            mx, my = m.winfo_x(), m.winfo_y()
            mw, mh = m.winfo_width(), m.winfo_height()
            x = mx + (mw - self._W) // 2
            y = my + max(50, int(mh * 0.15))
            self.geometry(f"{self._W}x{self._H}+{x}+{y}")
        except Exception:
            self.geometry(f"{self._W}x{self._H}")
