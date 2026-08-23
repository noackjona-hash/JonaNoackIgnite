# -*- coding: utf-8 -*-
"""gui/widgets/toast.py – Non-blocking Clinical Workstation Notifications for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Literal
import customtkinter as ctk

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_OUTLINE,
    COLOR_TEXT_PRIMARY,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    FONT_FAMILY,
)


class ToastManager:
    """Verwaltet diskrete Status-Benachrichtigungen am unteren Bildschirmrand."""

    _COLORS = {
        "info":    {"dot": "#0284C7", "bg": ("#FFFFFF", "#131923"), "text": ("#0F172A", "#F8FAFC"), "border": ("#CBD5E1", "#243044")},
        "success": {"dot": "#16A34A", "bg": ("#FFFFFF", "#131923"), "text": ("#0F172A", "#F8FAFC"), "border": ("#86EFAC", "#064E2B")},
        "warning": {"dot": "#D97706", "bg": ("#FFFFFF", "#131923"), "text": ("#0F172A", "#F8FAFC"), "border": ("#FDE68A", "#4D3600")},
        "error":   {"dot": "#DC2626", "bg": ("#FFFFFF", "#131923"), "text": ("#0F172A", "#F8FAFC"), "border": ("#FECACA", "#5A1313")},
    }

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._active: list[tk.Toplevel] = []

    def show(
        self,
        message: str,
        level: Literal["info", "success", "warning", "error"] = "info",
        duration_ms: int = 3500,
        action_text: str | None = None,
        action_callback: Callable | None = None,
    ) -> None:
        if len(self._active) >= 3:
            self._dismiss(self._active[0])

        cfg = self._COLORS.get(level, self._COLORS["info"])
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg = cfg["bg"][1] if is_dark else cfg["bg"][0]
        fg = cfg["text"][1] if is_dark else cfg["text"][0]
        border_col = cfg["border"][1] if is_dark else cfg["border"][0]

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=border_col)
        toast.transient(self.root)

        outer = tk.Frame(toast, bg=border_col, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=bg, padx=12, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        row = tk.Frame(inner, bg=bg)
        row.pack(fill=tk.X)

        # Status-Dot
        dot_canvas = tk.Canvas(row, width=8, height=8, bg=bg, highlightthickness=0)
        dot_canvas.pack(side=tk.LEFT, padx=(0, 8))
        dot_canvas.create_oval(1, 1, 7, 7, fill=cfg["dot"], outline="")

        # Nachricht
        tk.Label(
            row,
            text=message,
            fg=fg,
            bg=bg,
            font=(FONT_FAMILY, 10),
            justify=tk.LEFT,
            wraplength=300
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Schließen Button
        close_lbl = tk.Label(row, text="✕", fg="#64748B", bg=bg, cursor="hand2", font=(FONT_FAMILY, 9))
        close_lbl.pack(side=tk.RIGHT, padx=(8, 0))
        close_lbl.bind("<Button-1>", lambda e, t=toast: self._dismiss(t))

        self._active.append(toast)
        self._reposition()

        if duration_ms > 0:
            toast.after(duration_ms, lambda t=toast: self._dismiss(t))

    def _reposition(self) -> None:
        try:
            self.root.update_idletasks()
            rx, ry = self.root.winfo_x(), self.root.winfo_y()
            rw, rh = self.root.winfo_width(), self.root.winfo_height()

            y = ry + rh - 36
            for toast in reversed(self._active):
                toast.update_idletasks()
                tw = max(toast.winfo_reqwidth(), 300)
                th = max(toast.winfo_reqheight(), 38)
                x = rx + rw - tw - 20
                y -= th
                toast.geometry(f"{tw}x{th}+{x}+{y}")
                y -= 6
        except Exception:
            pass

    def _dismiss(self, toast: tk.Toplevel) -> None:
        if toast in self._active:
            self._active.remove(toast)
        try:
            toast.destroy()
        except Exception:
            pass
        self._reposition()
