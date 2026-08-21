# -*- coding: utf-8 -*-
"""gui/widgets/toast.py – Non-blocking Google Material 3 Snackbars for IGNITE."""

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
    """Verwaltet moderne Google Material 3 Snackbars/Toasts am unteren Bildschirmrand."""

    _COLORS = {
        "info":    {"dot": "#1A73E8", "bg": ("#FFFFFF", "#292A2D"), "text": ("#202124", "#E8EAED"), "border": "#1A73E8"},
        "success": {"dot": "#34A853", "bg": ("#FFFFFF", "#292A2D"), "text": ("#202124", "#E8EAED"), "border": "#34A853"},
        "warning": {"dot": "#FBBC04", "bg": ("#FFFFFF", "#292A2D"), "text": ("#202124", "#E8EAED"), "border": "#FBBC04"},
        "error":   {"dot": "#EA4335", "bg": ("#FFFFFF", "#292A2D"), "text": ("#202124", "#E8EAED"), "border": "#EA4335"},
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

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg="#000000")
        toast.transient(self.root)

        outer = tk.Frame(toast, bg="#000000", padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=bg, padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        row = tk.Frame(inner, bg=bg)
        row.pack(fill=tk.X)

        # Farbiger Status-Dot
        dot_canvas = tk.Canvas(row, width=10, height=10, bg=bg, highlightthickness=0)
        dot_canvas.pack(side=tk.LEFT, padx=(0, 8))
        dot_canvas.create_oval(1, 1, 9, 9, fill=cfg["dot"], outline="")

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
        close_lbl = tk.Label(row, text="✕", fg="#80868B", bg=bg, cursor="hand2", font=(FONT_FAMILY, 9))
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

            y = ry + rh - 40
            for toast in reversed(self._active):
                toast.update_idletasks()
                tw = max(toast.winfo_reqwidth(), 320)
                th = max(toast.winfo_reqheight(), 44)
                x = rx + rw - tw - 24
                y -= th
                toast.geometry(f"{tw}x{th}+{x}+{y}")
                y -= 8
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
