# -*- coding: utf-8 -*-
"""gui/widgets/toast.py – Nicht-blockierende Toast-Benachrichtigungen für IGNITE.

Zeigt dezente Hinweisfenster in der unteren rechten Ecke, die nach einer
konfigurierbaren Zeit automatisch verschwinden – ohne den Arbeitsfluss zu unterbrechen.

Verwendung:
    toast = ToastManager(root)
    toast.show("Analyse abgeschlossen.", level="success")
    toast.show("Fehler beim Laden.", level="error", duration_ms=6000)
    toast.show("Gelöscht.", level="warning", action_text="Rückgängig", action_callback=fn)
"""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Literal


class ToastManager:
    """Verwaltet alle aktiven Toast-Benachrichtigungen eines Hauptfensters."""

    _COLORS_DARK = {
        "info":    {"bg": "#1E3A5F", "accent": "#4CC2FF", "text": "#E8F4FD"},
        "success": {"bg": "#14532D", "accent": "#4ADE80", "text": "#ECFDF5"},
        "warning": {"bg": "#78350F", "accent": "#FBBF24", "text": "#FFFBEB"},
        "error":   {"bg": "#7F1D1D", "accent": "#F87171", "text": "#FEF2F2"},
    }
    _COLORS_LIGHT = {
        "info":    {"bg": "#EFF6FF", "accent": "#2563EB", "text": "#1E3A5F"},
        "success": {"bg": "#F0FDF4", "accent": "#16A34A", "text": "#14532D"},
        "warning": {"bg": "#FFFBEB", "accent": "#D97706", "text": "#78350F"},
        "error":   {"bg": "#FEF2F2", "accent": "#DC2626", "text": "#7F1D1D"},
    }
    _ICONS = {"info": "ℹ", "success": "✓", "warning": "⚠", "error": "✕"}

    def __init__(self, root: tk.Misc) -> None:
        self.root = root
        self._active: list[tk.Toplevel] = []
        self._max_visible = 4

    def show(
        self,
        message: str,
        level: Literal["info", "success", "warning", "error"] = "info",
        duration_ms: int = 3500,
        action_text: str | None = None,
        action_callback: Callable | None = None,
    ) -> None:
        """Zeigt eine Toast-Benachrichtigung an."""
        # Älteste entfernen wenn Maximum erreicht
        if len(self._active) >= self._max_visible:
            self._dismiss(self._active[0])

        toast = self._build_toast(message, level, action_text, action_callback)
        self._active.append(toast)
        self._reposition_all()

        if duration_ms > 0:
            toast.after(duration_ms, lambda t=toast: self._dismiss(t))

    def dismiss_all(self) -> None:
        """Schließt alle aktiven Toasts sofort."""
        for t in list(self._active):
            self._dismiss(t)

    # ── Interne Hilfsmethoden ────────────────────────────────────────────────

    def _palette(self, level: str) -> dict:
        try:
            import customtkinter as ctk
            dark = ctk.get_appearance_mode() == "Dark"
        except Exception:
            dark = False
        return (self._COLORS_DARK if dark else self._COLORS_LIGHT).get(
            level, self._COLORS_LIGHT["info"]
        )

    def _build_toast(
        self,
        message: str,
        level: str,
        action_text: str | None,
        action_callback: Callable | None,
    ) -> tk.Toplevel:
        pal = self._palette(level)
        bg = pal["bg"]
        accent = pal["accent"]
        text_color = pal["text"]
        icon = self._ICONS.get(level, "ℹ")
        font_family = "Segoe UI"

        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(bg=bg)
        toast.transient(self.root)

        # Äußerer Rahmen mit farbigem Akzent-Streifen links
        outer = tk.Frame(toast, bg=accent, padx=3, pady=0)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=bg, padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        # Icon + Nachricht + Schließen-Button
        row = tk.Frame(inner, bg=bg)
        row.pack(fill=tk.X)

        tk.Label(
            row, text=icon, fg=accent, bg=bg,
            font=(font_family, 14, "bold"), width=2
        ).pack(side=tk.LEFT)

        tk.Label(
            row, text=message, fg=text_color, bg=bg,
            font=(font_family, 11), justify=tk.LEFT,
            wraplength=280, anchor="w"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        close = tk.Label(
            row, text="✕", fg="#94A3B8", bg=bg,
            cursor="hand2", font=(font_family, 10)
        )
        close.pack(side=tk.RIGHT, padx=(8, 0))
        close.bind("<Button-1>", lambda e, t=toast: self._dismiss(t))

        # Optionaler Aktions-Link
        if action_text and action_callback:
            def _on_action(t=toast):
                action_callback()
                self._dismiss(t)

            act_row = tk.Frame(inner, bg=bg)
            act_row.pack(fill=tk.X, pady=(6, 0))

            act = tk.Label(
                act_row, text=action_text, fg=accent, bg=bg,
                cursor="hand2", font=(font_family, 10, "underline")
            )
            act.pack(side=tk.LEFT, padx=(20, 0))
            act.bind("<Button-1>", lambda e: _on_action())

        return toast

    def _reposition_all(self) -> None:
        """Stapelt alle aktiven Toasts rechts unten, von unten nach oben."""
        try:
            self.root.update_idletasks()
        except Exception:
            return

        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()

        margin_right = 20
        margin_bottom = 36   # Platz für Status-Leiste
        gap = 6

        y = ry + rh - margin_bottom

        for toast in reversed(self._active):
            try:
                toast.update_idletasks()
                tw = max(toast.winfo_reqwidth(), 340)
                th = max(toast.winfo_reqheight(), 64)
                x = rx + rw - tw - margin_right
                y -= th
                toast.geometry(f"{tw}x{th}+{x}+{y}")
                y -= gap
            except Exception:
                pass

    def _dismiss(self, toast: tk.Toplevel) -> None:
        if toast in self._active:
            self._active.remove(toast)
        try:
            toast.destroy()
        except Exception:
            pass
        self._reposition_all()
