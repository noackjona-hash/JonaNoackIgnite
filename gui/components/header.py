# -*- coding: utf-8 -*-
"""header.py – Custom Frameless Titlebar Component for IGNITE."""

import os
import sys
import logging
import customtkinter as ctk
from PIL import Image

from gui.theme import (
    COLOR_BG_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_BORDER_CARD,
    COLOR_DANGER,
    FONT_FAMILY
)
from utils import get_resource_path

APP_VERSION = "1.0.0"

class TitleBarComponent:
    """Erstellt eine benutzerdefinierte Titel-Leiste mit Drag-Funktion, Edge-Snapping und Window-Controls."""

    def __init__(self, root: ctk.CTk, title_text: str = f"IGNITE Medical Imaging Suite v{APP_VERSION} – Thermografische Analyse") -> None:
        self.root = root
        self.title_text = title_text
        self.is_maximized = False
        self._offset_x = 0
        self._offset_y = 0
        self._normal_geometry = "1400x900"
        self._is_snapped = False

        self.title_bar = ctk.CTkFrame(self.root, height=40, corner_radius=0, fg_color=COLOR_BG_CARD)
        self.title_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.title_bar.grid_propagate(False)

        self._build_ui()
        self._bind_drag_events()
        self._apply_taskbar_fix()

    def _build_ui(self) -> None:
        # App-Logo
        icon_png_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        if os.path.exists(icon_png_path):
            try:
                logo_img = Image.open(icon_png_path)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(20, 20))
                lbl_icon = ctk.CTkLabel(self.title_bar, image=logo_ctk, text="")
                lbl_icon.pack(side="left", padx=(15, 8))
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        self.lbl_title = ctk.CTkLabel(
            self.title_bar,
            text=self.title_text,
            font=(FONT_FAMILY, 12, "bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.lbl_title.pack(side="left")

        # Window Controls
        def hard_exit():
            self.root.destroy()
            sys.exit(0)

        self.btn_close = ctk.CTkButton(
            self.title_bar,
            text="✕",
            width=46,
            height=40,
            fg_color="transparent",
            hover_color=COLOR_DANGER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=0,
            command=hard_exit
        )
        self.btn_close.pack(side="right")

        def toggle_maximize():
            if self.is_maximized:
                self.root.state("normal")
                self.is_maximized = False
                self.btn_maximize.configure(text="🗖")
            else:
                self.root.state("zoomed")
                self.is_maximized = True
                self.btn_maximize.configure(text="🗗")

        self.btn_maximize = ctk.CTkButton(
            self.title_bar,
            text="🗖",
            width=46,
            height=40,
            fg_color="transparent",
            hover_color=COLOR_BORDER_CARD,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=0,
            command=toggle_maximize
        )
        self.btn_maximize.pack(side="right")

        def minimize_window():
            self.root.iconify()

        self.btn_minimize = ctk.CTkButton(
            self.title_bar,
            text="—",
            width=46,
            height=40,
            fg_color="transparent",
            hover_color=COLOR_BORDER_CARD,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=0,
            command=minimize_window
        )
        self.btn_minimize.pack(side="right")

    def _bind_drag_events(self) -> None:
        def get_work_area():
            try:
                import ctypes
                from ctypes.wintypes import RECT
                rect = RECT()
                ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            except Exception:
                return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 40

        def start_move(event):
            if not self.is_maximized and not self._is_snapped:
                self._offset_x = event.x
                self._offset_y = event.y

        def do_move(event):
            if self.is_maximized or self._is_snapped:
                if self.is_maximized:
                    self.root.state("normal")
                    self.is_maximized = False
                    self.btn_maximize.configure(text="🗖")

                self.root.geometry(self._normal_geometry)
                self.root.update_idletasks()
                self._offset_x = self.root.winfo_width() // 2
                self._offset_y = event.y if event.y < 40 else 15
                self._is_snapped = False

            x = self.root.winfo_x() + event.x - self._offset_x
            y = self.root.winfo_y() + event.y - self._offset_y
            self.root.geometry(f"+{x}+{y}")

        def stop_move(event):
            wx, wy, ww, wh = get_work_area()
            pointer_x = self.root.winfo_pointerx()
            pointer_y = self.root.winfo_pointery()
            snap_margin = 15

            if pointer_y <= wy + snap_margin:
                self._normal_geometry = f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                self.root.state("zoomed")
                self.is_maximized = True
                self.btn_maximize.configure(text="🗗")
            elif pointer_x <= wx + snap_margin:
                self._normal_geometry = f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                self.root.geometry(f"{ww//2}x{wh}+{wx}+{wy}")
                self._is_snapped = True
            elif pointer_x >= wx + ww - snap_margin:
                self._normal_geometry = f"{self.root.winfo_width()}x{self.root.winfo_height()}"
                self.root.geometry(f"{ww//2}x{wh}+{wx + ww//2}+{wy}")
                self._is_snapped = True

        self.title_bar.bind("<Button-1>", start_move)
        self.title_bar.bind("<B1-Motion>", do_move)
        self.title_bar.bind("<ButtonRelease-1>", stop_move)
        self.lbl_title.bind("<Button-1>", start_move)
        self.lbl_title.bind("<B1-Motion>", do_move)
        self.lbl_title.bind("<ButtonRelease-1>", stop_move)

    def _apply_taskbar_fix(self) -> None:
        def set_appwindow():
            try:
                import ctypes
                from ctypes import windll
                hwnd = windll.user32.GetParent(self.root.winfo_id())
                GWL_EXSTYLE = -20
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_TOOLWINDOW = 0x00000080
                style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                style = style & ~WS_EX_TOOLWINDOW | WS_EX_APPWINDOW
                windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        self.root.after(100, set_appwindow)
