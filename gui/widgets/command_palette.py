# -*- coding: utf-8 -*-
"""gui/widgets/command_palette.py – Command Palette (Strg+K / Strg+P) für IGNITE.

Eine VS Code / Spotlight-ähnliche Befehlssuche: Strg+K öffnet ein schwebendes
Fenster, in dem Nutzer Befehle per Freitext suchen und per Enter ausführen können.
Unterstützt Fuzzy-Matching gegen Label und Beschreibung aller registrierten Befehle.
"""

from __future__ import annotations
import tkinter as tk
from typing import Callable
import customtkinter as ctk


class CommandPalette(ctk.CTkToplevel):
    """Schwebendes Command-Palette-Fenster.

    Args:
        master: Das übergeordnete Fenster.
        commands: Liste von Befehlsdefinitionen. Jeder Eintrag ist ein dict:
            {
                "label":    str,       # Angezeigter Name
                "desc":     str,       # Kurzbeschreibung (optional)
                "shortcut": str,       # Tastenkürzel-Hinweis (optional)
                "action":   callable,  # Wird bei Auswahl ausgeführt
            }
    """

    _W, _H = 580, 440

    def __init__(self, master: tk.Misc, commands: list[dict], **kwargs) -> None:
        super().__init__(master, **kwargs)

        self._all_commands = [c for c in commands if c.get("action")]
        self._filtered: list[dict] = list(self._all_commands)
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

        self.after(60, lambda: self._search_entry.focus_set())

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from gui.theme import (
            COLOR_BG_CARD, COLOR_BORDER_CARD, COLOR_BG_MAIN,
            COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
            COLOR_PRIMARY_ACCENT, FONT_FAMILY
        )

        # Äußerer Rahmen (wirkt wie Schatten)
        shadow = tk.Frame(self, bg="#000000", padx=1, pady=1)
        shadow.pack(fill=tk.BOTH, expand=True)

        outer = ctk.CTkFrame(
            shadow, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER_CARD,
            fg_color=COLOR_BG_CARD
        )
        outer.pack(fill=tk.BOTH, expand=True)

        # ── Suchzeile ───────────────────────────────────────────────────────
        search_row = ctk.CTkFrame(outer, fg_color="transparent", height=56)
        search_row.pack(fill=tk.X, padx=16, pady=(14, 0))
        search_row.pack_propagate(False)

        ctk.CTkLabel(
            search_row, text="⌕",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18),
            text_color=COLOR_TEXT_MUTED, width=28
        ).pack(side=tk.LEFT)

        self._search_var = tk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text="Befehl oder Funktion suchen…",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
            border_width=0, fg_color="transparent",
            text_color=COLOR_TEXT_PRIMARY,
            height=40
        )
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())

        esc_badge = ctk.CTkLabel(
            search_row, text="  ESC  ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED,
            fg_color=("#E4E4E7", "#3F3F46"),
            corner_radius=4
        )
        esc_badge.pack(side=tk.RIGHT, ipady=3)

        # Trennlinie
        ctk.CTkFrame(outer, height=1, fg_color=COLOR_BORDER_CARD, corner_radius=0).pack(
            fill=tk.X, padx=0, pady=(10, 0)
        )

        # ── Ergebnisliste ────────────────────────────────────────────────────
        self._results_scroll = ctk.CTkScrollableFrame(
            outer, fg_color="transparent", height=310,
            scrollbar_button_color=("#C0C0C0", "#505050"),
            scrollbar_button_hover_color=("#A0A0A0", "#707070")
        )
        self._results_scroll.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 0))

        # ── Statusleiste ─────────────────────────────────────────────────────
        hint = ctk.CTkFrame(outer, fg_color=("#F4F4F5", "#27272A"), corner_radius=0, height=30)
        hint.pack(fill=tk.X, side=tk.BOTTOM)
        hint.pack_propagate(False)

        ctk.CTkLabel(
            hint,
            text="↑↓ navigieren   ↵ ausführen   Esc schließen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=tk.LEFT, padx=16, pady=5)

        self._count_lbl = ctk.CTkLabel(
            hint,
            text="",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        )
        self._count_lbl.pack(side=tk.RIGHT, padx=16)

        self._render_results()

    def _render_results(self) -> None:
        from gui.theme import (
            COLOR_BG_CARD, COLOR_BORDER_CARD,
            COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY, COLOR_TEXT_MUTED,
            COLOR_PRIMARY_ACCENT, FONT_FAMILY
        )

        for w in self._results_scroll.winfo_children():
            w.destroy()

        self._count_lbl.configure(
            text=f"{len(self._filtered)} Befehle"
        )

        if not self._filtered:
            ctk.CTkLabel(
                self._results_scroll,
                text="Keine passenden Befehle gefunden.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_MUTED
            ).pack(pady=24)
            return

        for idx, cmd in enumerate(self._filtered):
            selected = idx == self._sel_idx
            row_bg = COLOR_PRIMARY_ACCENT if selected else "transparent"
            lbl_color = "#FFFFFF" if selected else COLOR_TEXT_PRIMARY
            desc_color = "#E0F0FF" if selected else COLOR_TEXT_MUTED

            row = ctk.CTkFrame(
                self._results_scroll,
                fg_color=row_bg,
                corner_radius=8,
                cursor="hand2"
            )
            row.pack(fill=tk.X, padx=4, pady=2)

            content = ctk.CTkFrame(row, fg_color="transparent")
            content.pack(fill=tk.X, padx=14, pady=8)

            # Label + Beschreibung
            text_col = ctk.CTkFrame(content, fg_color="transparent")
            text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ctk.CTkLabel(
                text_col,
                text=cmd["label"],
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=lbl_color,
                anchor="w"
            ).pack(fill=tk.X)

            if cmd.get("desc"):
                ctk.CTkLabel(
                    text_col,
                    text=cmd["desc"],
                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                    text_color=desc_color,
                    anchor="w"
                ).pack(fill=tk.X)

            # Tastenkürzel-Badge
            if cmd.get("shortcut"):
                badge_bg = ("#0056A8", "#003D7A") if selected else ("#E4E4E7", "#3F3F46")
                badge_fg = "#FFFFFF" if selected else COLOR_TEXT_MUTED
                ctk.CTkLabel(
                    content,
                    text=f"  {cmd['shortcut']}  ",
                    font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                    text_color=badge_fg,
                    fg_color=badge_bg,
                    corner_radius=4
                ).pack(side=tk.RIGHT, padx=(8, 0), ipady=3)

            # Klick-Bindungen auf alle Kindelemente
            _idx = idx
            for widget in [row, content] + list(content.winfo_children()) + list(
                w for child in content.winfo_children() for w in [child] + list(child.winfo_children())
            ):
                try:
                    widget.bind("<Button-1>", lambda e, i=_idx: self._execute(i))
                except Exception:
                    pass

    # ── Ereignishandler ──────────────────────────────────────────────────────

    def _on_search_changed(self) -> None:
        query = self._search_var.get().strip().lower()
        if not query:
            self._filtered = list(self._all_commands)
        else:
            self._filtered = [
                c for c in self._all_commands
                if query in c["label"].lower() or query in c.get("desc", "").lower()
            ]
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
                self.after(60, action)

    def _close(self, event=None) -> None:
        try:
            self.destroy()
        except Exception:
            pass

    def _on_focus_out(self, event=None) -> None:
        # Schließe wenn Fokus das Fenster verlässt (außer wenn auf Kindwidget)
        try:
            focused = self.focus_get()
            if focused and (focused == self or str(focused).startswith(str(self))):
                return
            self._close()
        except Exception:
            self._close()

    def _position(self) -> None:
        """Zentriert die Palette horizontal, im oberen Drittel des Elternfensters."""
        try:
            self.update_idletasks()
            m = self.master
            m.update_idletasks()
            mx, my = m.winfo_x(), m.winfo_y()
            mw, mh = m.winfo_width(), m.winfo_height()
            x = mx + (mw - self._W) // 2
            y = my + max(60, int(mh * 0.14))
            self.geometry(f"{self._W}x{self._H}+{x}+{y}")
        except Exception:
            self.geometry(f"{self._W}x{self._H}")
