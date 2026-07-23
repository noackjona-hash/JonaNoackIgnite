# -*- coding: utf-8 -*-
"""gui.py – CustomTkinter-Frontend für die IGNITE Medical Imaging Suite.

Dieses Modul stellt das grafische Benutzer-Interface bereit. Die Bildverarbeitung
wird vollständig an das native Rust-Core-Modul `ignite_core` oder die
GPU-beschleunigte PyTorch-Pipeline delegiert.
"""

import os
import logging
import csv
import hashlib
import datetime
import tkinter as tk
import threading
from collections import OrderedDict
from tkinter import filedialog, messagebox
import cv2
import numpy as np
from PIL import Image
import customtkinter as ctk

# Matplotlib integration
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import config
import image_processing
import storage


from gui.theme import *
from gui.utils_ui import make_slider
from gui.services.export_service import ExportService
from gui.services.processing_service import ThermalProcessingService
from gui.components.thermal_canvas import ThermalCanvasWidget
from gui.components.controls_panel import ParameterControlsPanel





# ─── KLINISCHE HILFSFUNKTIONEN ────────────────────────────────────────────────

from utils import pixel_to_celsius, pseudonymize_patient, get_resource_path
from audit_log import write_audit_entry


APP_VERSION = "1.0.0"


class IgniteApp:
    """Haupt-Anwendungsklasse für das IGNITE Thermografie-Analyse-System v1.0.

    Verwaltet das Hauptfenster unter Verwendung von CustomTkinter, die Seitenleiste
    für Steuerelemente und Statistiken sowie die sechs Analyse-Tabs und das
    Temperatur-Histogramm-Tab.
    """

    def __init__(self, root: ctk.CTk) -> None:
        """Initialisiert die IGNITE-Anwendung.

        Args:
            root: Das CustomTkinter-Hauptfenster-Objekt.
        """
        self.root = root
        self.root.overrideredirect(True)
        self.root.title(f"IGNITE Medical Imaging Suite v{APP_VERSION} – Thermografische Analyse")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 780)
        self.root.configure(fg_color=COLOR_BG_MAIN)

        # Setze das Anwendungs-Icon (Favicon)
        icon_path = get_resource_path(os.path.join("icon", "LogoRund.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        # Ausgabe-Verzeichnis anlegen
        config.init_output_dir()

        # State-Variablen für Bilder und Fenster-Resizing
        self.current_filepath: str | None = None
        self.panels: dict[str, ctk.CTkLabel] = {}
        self.panels_full: dict[str, ctk.CTkLabel] = {}

        # Raw-Bilder für Pixel-Inspektor, Farbpaletten-Umschaltung, Histogramm & Symmetrievergleich
        self.current_raw_original: np.ndarray | None = None
        self.current_raw_mask: np.ndarray | None = None
        self.current_images: dict[str, np.ndarray] = {}
        self.zonal_stats: dict = {}
        self.general_hotspots: list = []

        # Klinische Kalibrierungs-State-Variablen
        self.t_min_celsius: float = config.DEFAULT_TEMP_MIN   # Kamera-Minimumtemperatur in °C
        self.t_max_celsius: float = config.DEFAULT_TEMP_MAX   # Kamera-Maximumtemperatur in °C
        self.dsgvo_anonymize: bool = False  # DSGVO-Pseudonymisierung aktiv?
        self.emissivity: float = 0.98       # Standard-Emissionsgrad für Haut

        self.resize_job: str | None = None
        # PIL-Bild-Cache für die Bildanzeige (LRU-beschränkt auf 20 Einträge).
        # OrderedDict ermöglicht effizientes LRU-Eviction:
        # älteste Einträge werden entfernt, wenn das Limit überschritten wird.
        # Verhindert Memory-Leaks bei Batch-Verarbeitung vieler Bilder.
        self._PIL_CACHE_MAXSIZE = 20
        self.pil_cache: OrderedDict[str, Image.Image] = OrderedDict()

        # ROI State-Variablen
        self.drawing_roi: bool = False
        self.roi_active_panel: str | None = None
        self.roi_active_is_grid: bool = False
        self.roi_start_x: int = 0
        self.roi_start_y: int = 0
        self.roi_current_x: int = 0
        self.roi_current_y: int = 0
        self.roi_end_x: int = 0
        self.roi_end_y: int = 0

        self.backend_var = tk.StringVar(value="auto")
        self.setup_title_bar()
        self.setup_ui()

        # Bind-Event für dynamische Skalierung bei Fenster-Größenänderungen (Debounced)
        self.root.bind("<Configure>", self.on_window_configure)

        # Aktives Backend beim Start abfragen
        self.update_backend_label()

    def make_slider(self, master, label_text, from_, to, default_val, resolution=0.01):
        """Erstellt ein Steuerelement mit Slider und dynamischer Werteanzeige."""
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.pack(fill=ctk.X, pady=6)
        
        top_row = ctk.CTkFrame(frame, fg_color="transparent")
        top_row.pack(fill=ctk.X)
        
        lbl_title = ctk.CTkLabel(top_row, text=label_text, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
        lbl_title.pack(side=ctk.LEFT)
        
        val_lbl = ctk.CTkLabel(top_row, text=str(default_val), font=ctk.CTkFont(size=11), text_color=COLOR_PRIMARY_ACCENT)
        val_lbl.pack(side=ctk.RIGHT)
        
        slider = ctk.CTkSlider(
            frame, 
            from_=from_, 
            to=to, 
            number_of_steps=int((to - from_)/resolution), 
            fg_color=COLOR_BORDER_CARD, 
            progress_color=COLOR_PRIMARY_ACCENT, 
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT
        )
        slider.set(default_val)
        slider.pack(fill=ctk.X, pady=2)
        
        return slider, val_lbl

    def setup_title_bar(self) -> None:
        """Erstellt eine komplett benutzerdefinierte Titel-Leiste mit Drag-Funktion und Window-Controls."""
        self.title_bar = ctk.CTkFrame(self.root, height=40, corner_radius=0, fg_color=COLOR_BG_CARD)
        self.title_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.title_bar.grid_propagate(False)

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

        lbl_title = ctk.CTkLabel(self.title_bar, text=f"IGNITE Medical Imaging Suite v{APP_VERSION} – Thermografische Analyse", font=(FONT_FAMILY, 12, "bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_title.pack(side="left")

        # Window Controls
        def hard_exit():
            self.root.destroy()
            import sys
            sys.exit(0)
        btn_close = ctk.CTkButton(self.title_bar, text="✕", width=46, height=40, fg_color="transparent", hover_color=COLOR_DANGER, text_color=COLOR_TEXT_PRIMARY, corner_radius=0, command=hard_exit)
        btn_close.pack(side="right")

        self.is_maximized = False
        def toggle_maximize():
            if self.is_maximized:
                self.root.state("normal")
                self.is_maximized = False
                btn_maximize.configure(text="🗖")
            else:
                self.root.state("zoomed")
                self.is_maximized = True
                btn_maximize.configure(text="🗗")

        btn_maximize = ctk.CTkButton(self.title_bar, text="🗖", width=46, height=40, fg_color="transparent", hover_color=COLOR_BORDER_CARD, text_color=COLOR_TEXT_PRIMARY, corner_radius=0, command=toggle_maximize)
        btn_maximize.pack(side="right")

        def minimize_window():
            self.root.iconify()

        btn_minimize = ctk.CTkButton(self.title_bar, text="—", width=46, height=40, fg_color="transparent", hover_color=COLOR_BORDER_CARD, text_color=COLOR_TEXT_PRIMARY, corner_radius=0, command=minimize_window)
        btn_minimize.pack(side="right")

        # Window Dragging & Edge Snapping
        self._offset_x = 0
        self._offset_y = 0
        self._normal_geometry = "1400x900"
        self._is_snapped = False

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
                    btn_maximize.configure(text="🗖")
                
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
                btn_maximize.configure(text="🗗")
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
        lbl_title.bind("<Button-1>", start_move)
        lbl_title.bind("<B1-Motion>", do_move)
        lbl_title.bind("<ButtonRelease-1>", stop_move)
        
        # CTYPES Taskbar Fix
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

    def setup_ui(self) -> None:
        """Erstellt das moderne Interface mit Sidebar und Tabview-Bildanzeige."""
        # Haupt-Grid
        self.root.grid_columnconfigure(0, weight=0)  # Sidebar behält feste Breite
        self.root.grid_columnconfigure(1, weight=1)  # Tab-Inhalt dehnt sich aus
        self.root.grid_rowconfigure(0, weight=0)  # Title bar
        self.root.grid_rowconfigure(1, weight=1)  # App Inhalt

        # ── 1. LINKE SEITENLEISTE ─────────────────────────────────────────────
        sidebar_frame = ctk.CTkFrame(self.root, width=320, corner_radius=0, fg_color=COLOR_BG_MAIN)
        sidebar_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        sidebar_frame.grid_propagate(False)

        # App-Logo
        icon_png_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        pady_title = (30, 2)
        if os.path.exists(icon_png_path):
            try:
                logo_img = Image.open(icon_png_path)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(64, 64))
                logo_lbl = ctk.CTkLabel(sidebar_frame, image=logo_ctk, text="")
                logo_lbl.pack(padx=20, pady=(25, 5), anchor="w")
                pady_title = (5, 2)
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        # App-Header
        title_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="IGNITE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=26, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        title_lbl.pack(padx=20, pady=pady_title, anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Medical Imaging Suite  ·  v1.0",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_SECONDARY
        )
        subtitle_lbl.pack(padx=20, pady=(0, 4), anchor="w")

        sub2_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Thermografische Entzündungsdetektion",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        )
        sub2_lbl.pack(padx=20, pady=(0, 20), anchor="w")

        # Scrollbare Steuerleiste für Parameter
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar_frame, 
            fg_color="transparent",
            scrollbar_button_color="#27272A",
            scrollbar_button_hover_color="#3F3F46"
        )
        self.sidebar_scroll.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        # Sektion: Analyse-Modus
        mode_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD)
        mode_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        mode_title = ctk.CTkLabel(mode_card, text="ANALYSEMODUS", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT)
        mode_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.analysis_mode_opt = ctk.CTkOptionMenu(
            mode_card,
            values=["Klinische Allgemeinanalyse", "Podologische Symmetrieanalyse"],
            command=self.on_analysis_mode_changed,
            font=ctk.CTkFont(size=12), 
            fg_color=COLOR_BG_INPUT, 
            button_color=COLOR_PRIMARY_ACCENT, 
            button_hover_color=COLOR_HOVER_ACCENT, 
            text_color=COLOR_TEXT_PRIMARY, 
            height=28
        )
        self.analysis_mode_opt.pack(fill=ctk.X, padx=12, pady=(4, 8))

        # Sektion: Interaktive ROI-Analyse
        self.roi_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD)
        self.roi_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        roi_title = ctk.CTkLabel(self.roi_card, text="INTERAKTIVE ROI-ANALYSE", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT)
        roi_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.roi_info_lbl = ctk.CTkLabel(
            self.roi_card,
            text="Ziehe mit der Maus auf einem Bild ein Rechteck auf, um eine Region of Interest (ROI) live zu analysieren.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
            wraplength=250,
            justify="left"
        )
        self.roi_info_lbl.pack(fill=ctk.X, padx=12, pady=4)

        self.roi_stats_frame = ctk.CTkFrame(self.roi_card, fg_color="transparent")



        # ── Systemeinstellungen-Karte (standardmäßig eingeklappt) ────────────
        self.settings_visible = False  # Standardmäßig EINGEKLAPPT für cleane UI
        self.settings_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD)
        self.settings_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        self.toggle_settings_btn = ctk.CTkButton(
            self.settings_card,
            text="⚙️ Systemeinstellungen  ▸",
            command=self.toggle_settings_visibility,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_BORDER_CARD,
            height=32,
            anchor="w",
            corner_radius=12
        )
        self.toggle_settings_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.settings_boxes_frame = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        # Standardmäßig NICHT gepackt → eingeklappt

        # Kamera-Kalibrierung (jetzt in Systemeinstellungen)
        ctk.CTkLabel(self.settings_boxes_frame, text="KAMERA-KALIBRIERUNG", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_PRIMARY_ACCENT).pack(anchor="w", pady=(8, 2), padx=4)

        calib_row = ctk.CTkFrame(self.settings_boxes_frame, fg_color="transparent")
        calib_row.pack(fill=ctk.X, padx=4, pady=(0, 6))
        calib_row.grid_columnconfigure(0, weight=1)
        calib_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(calib_row, text="T-Min", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_SECONDARY).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(calib_row, text="T-Max", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_SECONDARY).grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.t_min_entry = ctk.CTkEntry(calib_row, placeholder_text=str(config.DEFAULT_TEMP_MIN), font=ctk.CTkFont(size=12), fg_color=COLOR_BG_INPUT, border_color=COLOR_BORDER_INPUT, text_color=COLOR_TEXT_PRIMARY, height=28, width=80)
        self.t_min_entry.insert(0, str(config.DEFAULT_TEMP_MIN))
        self.t_min_entry.grid(row=1, column=0, sticky="ew", pady=4)
        self.t_min_entry.bind("<FocusOut>", self.on_calibration_changed)
        self.t_min_entry.bind("<Return>", self.on_calibration_changed)

        self.t_max_entry = ctk.CTkEntry(calib_row, placeholder_text=str(config.DEFAULT_TEMP_MAX), font=ctk.CTkFont(size=12), fg_color=COLOR_BG_INPUT, border_color=COLOR_BORDER_INPUT, text_color=COLOR_TEXT_PRIMARY, height=28, width=80)
        self.t_max_entry.insert(0, str(config.DEFAULT_TEMP_MAX))
        self.t_max_entry.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.t_max_entry.bind("<FocusOut>", self.on_calibration_changed)
        self.t_max_entry.bind("<Return>", self.on_calibration_changed)

        resolution = (config.DEFAULT_TEMP_MAX - config.DEFAULT_TEMP_MIN) / 255.0
        self.calib_status_lbl = ctk.CTkLabel(
            self.settings_boxes_frame,
            text=f"{config.DEFAULT_TEMP_MIN:.1f}°C – {config.DEFAULT_TEMP_MAX:.1f}°C  |  {resolution:.3f}°C/px",
            font=ctk.CTkFont(size=9),
            text_color=COLOR_TEXT_MUTED, anchor="w"
        )
        self.calib_status_lbl.pack(fill=ctk.X, padx=4, pady=(0, 8))

        # Einheit
        ctk.CTkLabel(self.settings_boxes_frame, text="Temperatureinheit", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        self.temp_unit_opt = ctk.CTkOptionMenu(
            self.settings_boxes_frame,
            values=["Celsius (°C)", "Fahrenheit (°F)", "Kelvin (K)"],
            command=self.on_temp_unit_changed,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.temp_unit_opt.pack(fill=ctk.X, pady=(0, 8))

        # Emissionsgrad
        ctk.CTkLabel(self.settings_boxes_frame, text="Emissionsgrad (ε)", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        self.emissivity_entry = ctk.CTkEntry(
            self.settings_boxes_frame,
            placeholder_text="0.98",
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER_INPUT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.emissivity_entry.insert(0, "0.98")
        self.emissivity_entry.pack(fill=ctk.X, pady=(0, 8))
        self.emissivity_entry.bind("<FocusOut>", self.on_emissivity_changed)
        self.emissivity_entry.bind("<Return>", self.on_emissivity_changed)

        # Exportordner
        ctk.CTkLabel(self.settings_boxes_frame, text="Export-Verzeichnis", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(2, 2))
        export_row = ctk.CTkFrame(self.settings_boxes_frame, fg_color="transparent")
        export_row.pack(fill=ctk.X, pady=(0, 4))
        self.export_path_entry = ctk.CTkEntry(
            export_row,
            placeholder_text="Export-Pfad",
            font=ctk.CTkFont(size=11),
            fg_color=COLOR_BG_INPUT,
            border_color=COLOR_BORDER_INPUT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.export_path_entry.insert(0, config.OUTPUT_DIR)
        self.export_path_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        self.export_path_entry.bind("<FocusOut>", self.on_export_path_changed)
        self.export_path_entry.bind("<Return>", self.on_export_path_changed)

        self.export_browse_btn = ctk.CTkButton(
            export_row,
            text="...",
            width=28,
            height=28,
            command=self.browse_export_path,
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_BG_MAIN
        )
        self.export_browse_btn.pack(side=ctk.RIGHT, padx=(4, 0))

        # Berechnungs-Backend
        ctk.CTkLabel(self.settings_boxes_frame, text="Berechnungs-Backend", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(8, 2))
        self.backend_opt = ctk.CTkOptionMenu(
            self.settings_boxes_frame,
            values=["Automatisch (Schnellstes)", "Erzwinge Rust-CPU-Core", "Erzwinge PyTorch-GPU", "Erzwinge Python-Fallback"],
            command=self.on_backend_ui_changed,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_INPUT,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=28
        )
        self.backend_opt.pack(fill=ctk.X, pady=(0, 8))

        # Design-Umschalter
        self.theme_btn = ctk.CTkButton(
            self.settings_boxes_frame,
            text="Design wechseln (Dunkel / Hell)",
            command=self.toggle_appearance_mode,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BG_CARD,
            border_width=1,
            border_color=COLOR_PRIMARY_ACCENT,
            height=30,
            corner_radius=6
        )
        self.theme_btn.pack(fill=ctk.X, pady=(8, 4))

        # Sektion: Haupt-Steuerung
        self.load_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Wärmebild laden",
            command=self.load_file,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color="#FFFFFF", # Weißer Text für optimalen Kontrast auf Indigo
            height=40,
            corner_radius=8
        )
        self.load_btn.pack(fill=ctk.X, pady=(0, 15))

        # Sektion: Aktionen & Export (Einklappbar)
        self.actions_visible = False
        self.actions_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD)
        self.actions_card.pack(fill=ctk.X, pady=(0, 15))

        self.toggle_actions_btn = ctk.CTkButton(
            self.actions_card,
            text="📁 Aktionen & Berichte  ▸",
            command=self.toggle_actions_visibility,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_BORDER_CARD,
            height=32,
            anchor="w",
            corner_radius=12
        )
        self.toggle_actions_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.actions_container = ctk.CTkFrame(self.actions_card, fg_color="transparent")
        # Wird initial nicht gepackt (eingeklappt)

        self.batch_btn = ctk.CTkButton(
            self.actions_container,
            text="Ordner-Stapelverarbeitung",
            command=self.run_batch_processing,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BG_CARD,
            border_width=1,
            border_color=COLOR_PRIMARY_ACCENT,
            height=32,
            corner_radius=6
        )
        self.batch_btn.pack(fill=ctk.X, pady=4)

        # Sektion: Farbpalette
        palette_lbl = ctk.CTkLabel(
            self.sidebar_scroll,
            text="FARBPALETTE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT
        )
        palette_lbl.pack(padx=5, pady=(5, 2), anchor="w")
        
        self.palette_menu = ctk.CTkOptionMenu(
            self.sidebar_scroll,
            values=["Graustufen", "Regenbogen (Jet)", "Inferno", "Heiß (Hot)"],
            command=self.on_palette_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY_ACCENT,
            button_hover_color=COLOR_HOVER_ACCENT,
            text_color=COLOR_TEXT_PRIMARY,
            height=32,
            corner_radius=6
        )
        self.palette_menu.pack(fill=ctk.X, pady=(0, 15))

        # Sektion: Pipeline Parameter (Einklappbar)
        self.param_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD)
        self.param_card.pack(fill=ctk.X, pady=(0, 15))

        self.toggle_param_btn = ctk.CTkButton(
            self.param_card,
            text="📊 Parameter einblenden  ▸",
            command=self.toggle_pipeline_parameters,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BORDER_CARD,
            height=32,
            anchor="w",
            corner_radius=12
        )
        self.toggle_param_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.param_sliders_frame = ctk.CTkFrame(self.param_card, fg_color="transparent")
        self.parameters_visible = False

        self.sigma_k_slider, self.sigma_k_val = make_slider(self.param_sliders_frame, "Threshold-Faktor (sigma_k)", 1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1)
        self.tophat_slider, self.tophat_val = make_slider(self.param_sliders_frame, "Top-Hat Kernel (%)", 0.01, 0.15, config.DEFAULT_TOPHAT_FACTOR, 0.005)
        self.min_area_slider, self.min_area_val = make_slider(self.param_sliders_frame, "Min. Fläche (%)", 0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001)
        self.min_circ_slider, self.min_circ_val = make_slider(self.param_sliders_frame, "Min. Circularity", 0.01, 0.50, config.DEFAULT_MIN_CIRCULARITY, 0.005)
        self.otsu_min_slider, self.otsu_min_val = make_slider(self.param_sliders_frame, "Otsu Min Schwellenwert", 10.0, 100.0, config.DEFAULT_OTSU_MIN, 1.0)
        self.otsu_max_slider, self.otsu_max_val = make_slider(self.param_sliders_frame, "Otsu Max Schwellenwert", 50.0, 150.0, config.DEFAULT_OTSU_MAX, 1.0)
        self.erosion_slider, self.erosion_val = make_slider(self.param_sliders_frame, "Erosions-Faktor", 0.01, 0.20, config.DEFAULT_DIST_EROSION_FACTOR, 0.005)
        self.temp_offset_slider, self.temp_offset_val = make_slider(self.param_sliders_frame, "Temp-Offset (Kalibrierung)", -50.0, 50.0, 0.0, 0.5)

        self.mad_switch = ctk.CTkSwitch(
            self.param_sliders_frame,
            text="Robustes MAD-Thresholding",
            command=self.update_params,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        if config.DEFAULT_USE_MAD:
            self.mad_switch.select()
        else:
            self.mad_switch.deselect()
        self.mad_switch.pack(fill=ctk.X, padx=10, pady=(5, 5))

        self.asymmetry_switch = ctk.CTkSwitch(
            self.param_sliders_frame,
            text="Kontralat. Asymmetrie (>2.2°C)",
            command=self.update_params,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold")
        )
        if config.DEFAULT_ENABLE_ASYMMETRY:
            self.asymmetry_switch.select()
        else:
            self.asymmetry_switch.deselect()
        self.asymmetry_switch.pack(fill=ctk.X, padx=10, pady=(0, 10))

        # Sliders bindings
        self.sigma_k_slider.configure(command=self.update_params)
        self.tophat_slider.configure(command=self.update_params)
        self.min_area_slider.configure(command=self.update_params)
        self.min_circ_slider.configure(command=self.update_params)
        self.otsu_min_slider.configure(command=self.update_params)
        self.otsu_max_slider.configure(command=self.update_params)
        self.erosion_slider.configure(command=self.update_params)
        self.temp_offset_slider.configure(command=self.update_params)

        # Sektion: Analyse-Info & Status
        self.info_card = ctk.CTkFrame(self.sidebar_scroll, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD)
        self.info_card.pack(fill=ctk.X, pady=(0, 15), ipady=8)

        self.filename_label = ctk.CTkLabel(self.info_card, text="Datei: Keine", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.filename_label.pack(fill=ctk.X, padx=15, pady=(10, 4))

        self.backend_label = ctk.CTkLabel(self.info_card, text="Backend: Erkennung...", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.backend_label.pack(fill=ctk.X, padx=15, pady=4)

        self.status_label = ctk.CTkLabel(self.info_card, text="Status: Bereit", font=ctk.CTkFont(size=12, slant="italic"), text_color=COLOR_TEXT_SECONDARY, anchor="w")
        self.status_label.pack(fill=ctk.X, padx=15, pady=4)

        self.hotspot_label = ctk.CTkLabel(self.info_card, text="Hotspots: --", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w")
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=4)

        self.pixel_info_label = ctk.CTkLabel(self.info_card, text="Pixel-Info: --", font=ctk.CTkFont(size=11, slant="italic"), text_color=COLOR_TEXT_SECONDARY, anchor="w", justify="left")
        self.pixel_info_label.pack(fill=ctk.X, padx=15, pady=(4, 10))

        # Dokumentations-Ordner-Button
        self.open_dir_btn = ctk.CTkButton(
            self.actions_container,
            text="Ergebnisordner öffnen",
            command=self.open_output_dir,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BG_CARD,
            border_width=1,
            border_color=COLOR_PRIMARY_ACCENT,
            height=32,
            corner_radius=6
        )
        self.open_dir_btn.pack(fill=ctk.X, pady=4)

        # HTML-Bericht-Button
        self.export_report_btn = ctk.CTkButton(
            self.actions_container,
            text="HTML-Bericht exportieren",
            command=self.export_html_report,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BG_CARD,
            border_width=1,
            border_color=COLOR_PRIMARY_ACCENT,
            height=32,
            corner_radius=6
        )
        self.export_report_btn.pack(fill=ctk.X, pady=4)

        # Bereinigen-Button
        self.clean_dir_btn = ctk.CTkButton(
            self.actions_container,
            text="Ergebnisordner bereinigen",
            command=self.clean_output_dir,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            fg_color="transparent",
            text_color="#EF4444",
            hover_color=("#2D1A22", "#fee2e2"),
            border_width=1,
            border_color="#EF4444",
            height=32,
            corner_radius=6
        )
        self.clean_dir_btn.pack(fill=ctk.X, pady=4)

        # Footer & Hilfe
        disclaimer_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Kein Ersatz für ärztliche Diagnose",
            font=ctk.CTkFont(family="Arial", size=9),
            text_color=COLOR_TEXT_MUTED
        )
        disclaimer_lbl.pack(side=ctk.BOTTOM, pady=(0, 10))

        footer_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="© 2026 Jona Noack · Jugend forscht",
            font=ctk.CTkFont(family="Arial", size=10),
            text_color=COLOR_TEXT_MUTED
        )
        footer_lbl.pack(side=ctk.BOTTOM, pady=(0, 2))

        help_row = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
        help_row.pack(side=ctk.BOTTOM, pady=(0, 10))

        self.info_btn = ctk.CTkButton(
            help_row,
            text="📖 Anleitung",
            command=self.show_info_window,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_BG_CARD,
            width=110,
            height=26,
            corner_radius=4
        )
        self.info_btn.pack(side=ctk.LEFT, padx=4)

        self.about_btn = ctk.CTkButton(
            help_row,
            text="ℹ️ Über Ignite",
            command=self.show_about_window,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=COLOR_TEXT_SECONDARY,
            hover_color=COLOR_BG_CARD,
            width=100,
            height=26,
            corner_radius=4
        )
        self.about_btn.pack(side=ctk.LEFT, padx=4)

        # ── 2. RECHTER HAUPTBEREICH (Tabview & Willkommensbildschirm) ──────────
        content_frame = ctk.CTkFrame(self.root, fg_color=COLOR_BG_MAIN, corner_radius=0)
        content_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        # CTkTabview erstellen und konfigurieren (wird erst nach Laden eines Bildes gepackt)
        self.tabview = ctk.CTkTabview(
            content_frame,
            fg_color="transparent",
            segmented_button_selected_color=COLOR_PRIMARY_ACCENT,
            segmented_button_selected_hover_color=COLOR_HOVER_ACCENT,
            segmented_button_unselected_color=COLOR_BG_CARD,
            segmented_button_unselected_hover_color=COLOR_BORDER_CARD,
            text_color=COLOR_TEXT_PRIMARY
        )

        # Willkommensbildschirm (Welcome Screen) erstellen
        self.welcome_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        
        # Zentrierter Container
        center_container = ctk.CTkFrame(
            self.welcome_frame,
            width=720,
            height=540,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        center_container.place(relx=0.5, rely=0.5, anchor="center")
        center_container.pack_propagate(False)

        # Logo
        welcome_logo_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        if os.path.exists(welcome_logo_path):
            try:
                logo_img = Image.open(welcome_logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(100, 100))
                logo_lbl = ctk.CTkLabel(center_container, image=logo_ctk, text="")
                logo_lbl.pack(pady=(45, 12))
            except Exception:
                ctk.CTkLabel(center_container, text="", height=110).pack()
        else:
            ctk.CTkLabel(center_container, text="", height=110).pack()

        # Titel & Beschreibung
        ctk.CTkLabel(
            center_container,
            text="Willkommen bei IGNITE",
            font=ctk.CTkFont(family=FONT_FAMILY, size=34, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(pady=(10, 4))

        ctk.CTkLabel(
            center_container,
            text="Medical Imaging Suite  ·  Jugend forscht 2026",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            center_container,
            text="Ein intelligentes System zur automatischen Erkennung thermischer Anomalien\nund Entzündungsprozessen an Füßen und Gelenken.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            text_color=COLOR_TEXT_SECONDARY,
            justify="center"
        ).pack(pady=(0, 30))

        # Laden-Button (mit weißem Text für optimalen Kontrast auf Indigo)
        welcome_load_btn = ctk.CTkButton(
            center_container,
            text="Wärmebild laden und analysieren",
            command=self.load_file,
            font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color="#FFFFFF",
            height=44,
            width=320,
            corner_radius=8
        )
        welcome_load_btn.pack(pady=10)

        # Schritte-Erklärung
        steps_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        steps_frame.pack(fill=ctk.X, padx=40, pady=(35, 20))
        steps_frame.grid_columnconfigure(0, weight=1)
        steps_frame.grid_columnconfigure(1, weight=1)
        steps_frame.grid_columnconfigure(2, weight=1)

        features = [
            ("📁 1. Bild laden", "Wähle ein Infrarotbild aus."),
            ("⚡ 2. Analyse", "Erkennung via Rust & GPU."),
            ("📊 3. Statistik", "Symmetrie & ROI-Prüfung.")
        ]

        for idx, (f_title, f_desc) in enumerate(features):
            box = ctk.CTkFrame(
                steps_frame,
                fg_color=COLOR_BG_MAIN,
                corner_radius=8,
                border_width=1,
                border_color=COLOR_BORDER_CARD
            )
            box.grid(row=0, column=idx, padx=8, sticky="nsew")
            
            ctk.CTkLabel(box, text=f_title, font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_PRIMARY_ACCENT).pack(pady=(8, 2), padx=8)
            ctk.CTkLabel(box, text=f_desc, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY, wraplength=170, justify="center").pack(pady=(0, 8), padx=8)

        # Loading Overlay (für Hintergrund-Verarbeitung)
        self.loading_overlay = ctk.CTkFrame(content_frame, fg_color="transparent")
        
        loading_card = ctk.CTkFrame(
            self.loading_overlay,
            width=500,
            height=300,
            fg_color=COLOR_BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        loading_card.place(relx=0.5, rely=0.5, anchor="center")
        loading_card.pack_propagate(False)
        
        self.loading_title_lbl = ctk.CTkLabel(
            loading_card,
            text="IGNITE-Pipeline läuft...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT
        )
        self.loading_title_lbl.pack(pady=(45, 10))
        
        self.loading_step_lbl = ctk.CTkLabel(
            loading_card,
            text="Initialisiere Berechnungen...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.loading_step_lbl.pack(pady=5)
        
        self.loading_pbar = ctk.CTkProgressBar(
            loading_card,
            width=360,
            height=5,
            fg_color=COLOR_BG_MAIN,
            progress_color=COLOR_PRIMARY_ACCENT,
            corner_radius=2
        )
        self.loading_pbar.set(0.0)
        self.loading_pbar.pack(pady=25)

        # Register Tabs
        self.tabview.add("Gesamtübersicht")
        self.tabview.add("1. Originalbild")
        self.tabview.add("2. Hintergrund-Maske")
        self.tabview.add("3. Lokale Hitze-Differenz")
        self.tabview.add("4. Erkannte Hotspots")
        self.tabview.add("5. Temperatur-Verteilung")
        self.tabview.add("6. Detail-Analyse")

        # ── TAB 1: Gesamtübersicht (2x2-Grid) ──────────────────────────────────
        grid_frame = ctk.CTkFrame(self.tabview.tab("Gesamtübersicht"), fg_color="transparent")
        grid_frame.pack(fill=ctk.BOTH, expand=True)

        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(1, weight=1)

        steps = [
            ("1. Originalbild",              0, 0),
            ("2. Hintergrund-Maske",         0, 1),
            ("3. Lokale Hitze-Differenz",    1, 0),
            ("4. Erkannte Hotspots (Rust)",  1, 1),
        ]

        for name, row, col in steps:
            panel_frame = ctk.CTkFrame(
                grid_frame,
                fg_color=COLOR_BG_CARD,
                corner_radius=12, # Größere Ecken für modernen Card-Look
                border_width=1,
                border_color=COLOR_BORDER_CARD
            )
            panel_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            title = ctk.CTkLabel(
                panel_frame,
                text=name,
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=15, pady=(12, 4))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="\n🌡️\n\nBEREIT FÜR ANALYSE\n\nBitte laden Sie ein Wärmebild über die Seitenleiste.\n",
                font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                text_color=COLOR_TEXT_MUTED,
                fg_color=COLOR_BG_MAIN,
                corner_radius=8
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))
            self.panels[name] = lbl

            # Bind mouse hover events
            lbl.bind("<Motion>", lambda e, n=name, is_grid=True: self.on_image_hover(e, n, is_grid))
            lbl.bind("<Leave>", self.on_image_leave)
            
            # Bind ROI interactive selection events
            lbl.bind("<ButtonPress-1>", lambda e, n=name, is_grid=True: self.on_roi_start(e, n, is_grid))
            lbl.bind("<B1-Motion>", lambda e, n=name, is_grid=True: self.on_roi_drag(e, n, is_grid))
            lbl.bind("<ButtonRelease-1>", lambda e, n=name, is_grid=True: self.on_roi_end(e, n, is_grid))

        # ── TAB 2-5: Einzelansichten (Full-size) ──────────────────────────────
        tab_mapping = {
            "1. Originalbild": "1. Originalbild",
            "2. Hintergrund-Maske": "2. Hintergrund-Maske",
            "3. Lokale Hitze-Differenz": "3. Lokale Hitze-Differenz",
            "4. Erkannte Hotspots (Rust)": "4. Erkannte Hotspots"
        }

        for step_name, tab_name in tab_mapping.items():
            panel_frame = ctk.CTkFrame(
                self.tabview.tab(tab_name),
                fg_color=COLOR_BG_CARD,
                corner_radius=12,
                border_width=1,
                border_color=COLOR_BORDER_CARD
            )
            panel_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

            title = ctk.CTkLabel(
                panel_frame,
                text=step_name,
                font=ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=20, pady=(15, 5))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="\n\n🌡️\n\nNoch kein Wärmebild geladen.\n\nBitte laden Sie eine Bilddatei über die linke Seitenleiste.\n",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13),
                text_color=COLOR_TEXT_MUTED,
                fg_color=COLOR_BG_MAIN,
                corner_radius=8
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
            self.panels_full[step_name] = lbl

            # Bind mouse hover events
            lbl.bind("<Motion>", lambda e, n=step_name, is_grid=False: self.on_image_hover(e, n, is_grid))
            lbl.bind("<Leave>", self.on_image_leave)
            
            # Bind ROI interactive selection events
            lbl.bind("<ButtonPress-1>", lambda e, n=step_name, is_grid=False: self.on_roi_start(e, n, is_grid))
            lbl.bind("<B1-Motion>", lambda e, n=step_name, is_grid=False: self.on_roi_drag(e, n, is_grid))
            lbl.bind("<ButtonRelease-1>", lambda e, n=step_name, is_grid=False: self.on_roi_end(e, n, is_grid))

        # ── TAB 5: Temperatur-Verteilung (Histogramm & Statistiken) ──────────
        hist_tab = self.tabview.tab("5. Temperatur-Verteilung")
        hist_tab.grid_columnconfigure(0, weight=3)  # Canvas nimmt 75% der Breite
        hist_tab.grid_columnconfigure(1, weight=1)  # Zahlenstatistik nimmt 25%
        hist_tab.grid_rowconfigure(0, weight=1)

        # Histogramm-Zeichenfläche
        canvas_panel = ctk.CTkFrame(
            hist_tab,
            fg_color=COLOR_BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        canvas_panel.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.title_hist = ctk.CTkLabel(
            canvas_panel,
            text="Statistisches Intensitätshistogramm",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.title_hist.pack(fill=ctk.X, padx=20, pady=(15, 5))

        self.hist_container = ctk.CTkFrame(canvas_panel, fg_color=COLOR_BG_MAIN, corner_radius=6)
        self.hist_container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Statistiken-Seitenleiste im Tab
        stats_panel = ctk.CTkFrame(
            hist_tab,
            fg_color=COLOR_BG_CARD,
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER_CARD
        )
        stats_panel.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        title_stats = ctk.CTkLabel(
            stats_panel,
            text="MESSWERTE & STATISTIK",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT,
            anchor="w"
        )
        title_stats.pack(fill=ctk.X, padx=15, pady=(15, 10))

        # Statistiken-Felder definieren (inklusive Symmetrievergleich)
        self.stats_labels = {}
        self.stats_title_labels = {}
        self.stats_divider_label = None
        
        stat_items = [
            ("Fußoberfläche (Pixel)", "pixel_count"),
            ("Mittelwert Fußhitze (µ)", "mean"),
            ("Standardabweichung (σ)", "std"),
            ("Hotspot-Grenze (µ + k*σ)", "threshold"),
            ("Maximaler Hitzewert", "max_val"),
            ("Hotspot-Pixel", "hotspots"),
            ("Prozentualer Anteil", "percentage"),
            ("---------------------------------", "divider"),
            ("Mittelwert Links (L)", "mean_left"),
            ("Mittelwert Rechts (R)", "mean_right"),
            ("Symmetrie-Delta (Δ)", "delta"),
            ("Symmetriestatus", "status_symmetry")
        ]

        for display_name, key in stat_items:
            # Trennlinien-Handling
            if key == "divider":
                self.stats_divider_label = ctk.CTkLabel(
                    stats_panel,
                    text="KLINISCHE SYMMETRIE (L/R)",
                    font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
                    text_color=COLOR_PRIMARY_ACCENT,
                    anchor="w"
                )
                self.stats_divider_label.pack(fill=ctk.X, padx=15, pady=(15, 2))
                continue

            lbl_title = ctk.CTkLabel(
                stats_panel,
                text=display_name,
                font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
                text_color=COLOR_TEXT_SECONDARY,
                anchor="w"
            )
            lbl_title.pack(fill=ctk.X, padx=15, pady=(6, 1))
            self.stats_title_labels[key] = lbl_title

            lbl_val = ctk.CTkLabel(
                stats_panel,
                text="--",
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, padx=15, pady=(0, 6))
            self.stats_labels[key] = lbl_val

        # ── TAB 6: Detail-Analyse ──────────────────────────────────────────
        detail_tab = self.tabview.tab("6. Detail-Analyse")
        self.detail_panel = ctk.CTkFrame(detail_tab, fg_color=COLOR_BG_CARD, corner_radius=8, border_width=1, border_color=COLOR_BORDER_CARD)
        self.detail_panel.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        self.detail_title = ctk.CTkLabel(
            self.detail_panel,
            text="Detail-Analyse der Messergebnisse",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.detail_title.pack(fill=ctk.X, padx=20, pady=(20, 10))

        self.detail_content_frame = ctk.CTkFrame(self.detail_panel, fg_color=COLOR_BG_MAIN, corner_radius=6)
        self.detail_content_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Initialen Inhalt zeichnen
        self.update_detail_tab()

        # Willkommensseite initial anzeigen
        self.show_welcome_screen()

    def show_welcome_screen(self) -> None:
        """Blendet die Analyse-Tabs aus und zeigt einen ansprechenden Willkommensbildschirm."""
        self.tabview.pack_forget()
        self.welcome_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

    def hide_welcome_screen(self) -> None:
        """Blendet den Willkommensbildschirm aus und zeigt die Analyse-Tabs."""
        self.welcome_frame.pack_forget()
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

    def on_analysis_mode_changed(self, mode: str) -> None:
        """Wird aufgerufen, wenn der Analysemodus gewechselt wird."""


        # Titel im Histogramm-Tab anpassen
        if mode == "Podologische Symmetrieanalyse":
            self.title_hist.configure(text="Statistisches Intensitätshistogramm (Exklusiv über Fußoberfläche)")
        else:
            self.title_hist.configure(text="Statistisches Intensitätshistogramm (Analysierte Oberfläche)")

        # Aktualisiere Detail-Tab-Inhalt
        self.update_detail_tab()

        # Starte die Pipeline neu, falls ein Bild geladen ist
        if self.current_filepath:
            self.process_pipeline()

    def update_detail_tab(self) -> None:
        """Baut den Inhalt des Detail-Tabs dynamisch auf, basierend auf dem gewählten Modus."""
        # Lösche vorherige Widgets im Inhaltsbereich
        for widget in self.detail_content_frame.winfo_children():
            widget.destroy()

        mode = self.analysis_mode_opt.get()

        # Einheit bestimmen
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"

        if mode == "Podologische Symmetrieanalyse":
            self.detail_title.configure(text="Detaillierter Zonen-Symmetrie-Vergleich (3-Zonen-Modell)")

            # Spalten konfigurieren
            self.detail_content_frame.grid_columnconfigure(0, weight=2)
            self.detail_content_frame.grid_columnconfigure(1, weight=1)
            self.detail_content_frame.grid_columnconfigure(2, weight=1)
            self.detail_content_frame.grid_columnconfigure(3, weight=1)
            self.detail_content_frame.grid_columnconfigure(4, weight=2)

            headers = ["Anatomische Zone", "Links (L)", "Rechts (R)", "Differenz (\u0394)", "Diagnose"]
            for col_idx, text in enumerate(headers):
                lbl = ctk.CTkLabel(
                    self.detail_content_frame, 
                    text=text, 
                    font=ctk.CTkFont(family="Arial", size=12, weight="bold"), 
                    text_color=COLOR_PRIMARY_ACCENT
                )
                lbl.grid(row=0, column=col_idx, padx=10, pady=12, sticky="w" if col_idx==0 or col_idx==4 else "")

            # Zeilen erstellen
            self.zonal_row_labels = {}
            zones = [("Vorfuß (Zehen / Ballen)", "fore"), ("Mittelfuß (Gewölbe)", "mid"), ("Ferse (Rückfuß)", "heel")]
            for row_idx, (display_name, key) in enumerate(zones, start=1):
                lbl_name = ctk.CTkLabel(self.detail_content_frame, text=display_name, font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
                lbl_name.grid(row=row_idx, column=0, padx=10, pady=12, sticky="w")
                
                lbl_l = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color=COLOR_TEXT_PRIMARY)
                lbl_l.grid(row=row_idx, column=1, padx=10, pady=12, sticky="")
                
                lbl_r = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color=COLOR_TEXT_PRIMARY)
                lbl_r.grid(row=row_idx, column=2, padx=10, pady=12, sticky="")
                
                lbl_d = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY)
                lbl_d.grid(row=row_idx, column=3, padx=10, pady=12, sticky="")
                
                lbl_diag = ctk.CTkLabel(self.detail_content_frame, text="Keine Messdaten vorhanden", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color=COLOR_TEXT_SECONDARY)
                lbl_diag.grid(row=row_idx, column=4, padx=10, pady=12, sticky="w")
                
                self.zonal_row_labels[key] = {"l": lbl_l, "r": lbl_r, "d": lbl_d, "diag": lbl_diag}
                
            # Wenn bereits berechnete Zonalwerte vorliegen, diese eintragen
            if hasattr(self, "zonal_stats") and self.zonal_stats.get("left", {}).get("exists") and self.zonal_stats.get("right", {}).get("exists"):
                for key in ["fore", "mid", "heel"]:
                    l_v = self.zonal_stats["left"][key]
                    r_v = self.zonal_stats["right"][key]
                    d_v = abs(l_v - r_v)
                    
                    l_v_str = self.to_temp_str(l_v)
                    r_v_str = self.to_temp_str(r_v)
                    d_v_str = self.to_delta_str(d_v)
                    
                    if d_v >= 15.0:
                        z_diag = "Asymmetrie detektiert \u2013 Abkl\u00e4rung empfohlen"
                        z_color = "#FF0055"
                    elif d_v >= 10.0:
                        z_diag = "Grenzwert \u2013 Verlaufsbeobachtung"
                        z_color = "#FFA500"
                    else:
                        z_diag = "Symmetrisch \u2013 Unauff\u00e4llig"
                        z_color = "#10B981"
                        
                    self.zonal_row_labels[key]["l"].configure(text=l_v_str)
                    self.zonal_row_labels[key]["r"].configure(text=r_v_str)
                    self.zonal_row_labels[key]["d"].configure(text=d_v_str, text_color=z_color)
                    self.zonal_row_labels[key]["diag"].configure(text=z_diag, text_color=z_color)

        else:
            self.detail_title.configure(text="Detaillierte Analyse der gefundenen Hotspots")

            # Scrollbare Tabelle für Hotspots im allgemeinen Modus
            scroll_frame = ctk.CTkScrollableFrame(self.detail_content_frame, fg_color="transparent")
            scroll_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

            scroll_frame.grid_columnconfigure(0, weight=1)
            scroll_frame.grid_columnconfigure(1, weight=2)
            scroll_frame.grid_columnconfigure(2, weight=2)
            scroll_frame.grid_columnconfigure(3, weight=2)
            scroll_frame.grid_columnconfigure(4, weight=3)

            headers = ["Hotspot ID", "Fläche (Pixel)", f"Mittelwert Hitze ({unit_str})", f"Maximalwert Hitze ({unit_str})", "Klinischer Befund"]
            for col_idx, text in enumerate(headers):
                lbl = ctk.CTkLabel(
                     scroll_frame, 
                     text=text, 
                     font=ctk.CTkFont(family="Arial", size=12, weight="bold"), 
                     text_color=COLOR_PRIMARY_ACCENT
                )
                lbl.grid(row=0, column=col_idx, padx=10, pady=12, sticky="w" if col_idx==0 or col_idx==4 else "")

            # Wenn Hotspots vorliegen, diese eintragen
            hotspots = getattr(self, "general_hotspots", [])
            if hotspots:
                for idx, hs in enumerate(hotspots, start=1):
                    area = hs["area"]
                    mean_temp = hs["mean_temp"]
                    max_temp = hs["max_temp"]
                    
                    mean_temp_str = self.to_temp_str(mean_temp)
                    max_temp_str = self.to_temp_str(max_temp)
                    
                    if area >= 150 or mean_temp >= 180:
                        diag_text = "Klinisch relevant \u2013 Abkl\u00e4rung empfohlen"
                        diag_color = "#FF0055"
                    elif area >= 50 or mean_temp >= 140:
                        diag_text = "Grenzwertig \u2013 Verlaufsbeobachtung"
                        diag_color = "#FFA500"
                    else:
                        diag_text = "Geringfügig (Unbedenklich)"
                        diag_color = "#10B981"

                    ctk.CTkLabel(scroll_frame, text=f"H#{hs['index']}", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY).grid(row=idx, column=0, padx=10, pady=8, sticky="w")
                    ctk.CTkLabel(scroll_frame, text=f"{area:,} px", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY).grid(row=idx, column=1, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=mean_temp_str, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY).grid(row=idx, column=2, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=max_temp_str, font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_PRIMARY).grid(row=idx, column=3, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=diag_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=diag_color).grid(row=idx, column=4, padx=10, pady=8, sticky="w")
            else:
                lbl_no = ctk.CTkLabel(scroll_frame, text="Keine Hotspots detektiert oder Bild noch nicht geladen.", font=ctk.CTkFont(size=13, slant="italic"), text_color=COLOR_TEXT_SECONDARY)
                lbl_no.grid(row=1, column=0, columnspan=5, padx=20, pady=30, sticky="nsew")

    def draw_general_annotations(self, img: np.ndarray, body_mask: np.ndarray, hotspots_mask: np.ndarray) -> np.ndarray:
        """Erzeugt Bounding-Boxen und Labels für einzelne erkannte Hotspots im allgemeinen Modus."""
        palette = self.palette_menu.get()
        if palette == "Regenbogen (Jet)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        elif palette == "Inferno":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        elif palette == "Heiß (Hot)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_HOT)
        else:  # Graustufen
            annotated = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # Rote Hotspots einmischen
        red_img = np.zeros_like(annotated)
        red_img[:] = [85, 0, 255]
        blended = cv2.addWeighted(annotated, 0.3, red_img, 0.7, 0)
        annotated = np.where(hotspots_mask[:, :, None] == 255, blended, annotated).astype(np.uint8)

        # Finde zusammenhängende Komponenten in der Hotspot-Maske
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(hotspots_mask)
        
        raw_hotspots = []
        for i in range(1, num_labels):
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]
            
            component_mask = (labels == i)
            mean_intensity = np.mean(img[component_mask]) if np.sum(component_mask) > 0 else 0.0
            max_intensity = np.max(img[component_mask]) if np.sum(component_mask) > 0 else 0.0
            
            raw_hotspots.append({
                "area": area,
                "mean_temp": mean_intensity,
                "max_temp": max_intensity,
                "bbox": (x, y, w, h),
                "center": centroids[i]
            })
            
        # Sortiere nach Fläche (groß -> klein)
        raw_hotspots.sort(key=lambda x: x["area"], reverse=True)
        
        self.general_hotspots = []
        for idx, hs in enumerate(raw_hotspots, start=1):
            hs["index"] = idx
            self.general_hotspots.append(hs)
            
            # Zeichne Bounding Box (Türkis/Cyan in BGR: B=255, G=165, R=0)
            x, y, w, h = hs["bbox"]
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 165, 0), 1)
            cv2.putText(annotated, f"H#{idx}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1, cv2.LINE_AA)
            
        return annotated

    def open_output_dir(self) -> None:
        """Öffnet den Ausgabeordner mit den gespeicherten Schritten im Dateimanager."""
        try:
            abs_path = os.path.abspath(config.OUTPUT_DIR)
            if not os.path.exists(abs_path):
                config.init_output_dir()
            os.startfile(abs_path)
        except Exception as e:
            messagebox.showerror("Fehler", f"Ausgabeordner konnte nicht geöffnet werden:\n{e}")

    def clean_output_dir(self) -> None:
        """Löscht alle generierten Dateien (.png, .npy, .html) aus dem Ausgabeordner und setzt die UI zurück."""
        if not os.path.exists(config.OUTPUT_DIR):
            messagebox.showinfo("Bereinigung", "Ausgabeordner existiert nicht. Keine Bereinigung notwendig.")
            return

        confirm = messagebox.askyesno(
            "Ausgabeordner bereinigen",
            "Möchten Sie wirklich alle exportierten Berichte und Zwischenschritte aus dem Ergebnisordner löschen?"
        )
        if not confirm:
            return

        try:
            files_removed = 0
            for item in os.listdir(config.OUTPUT_DIR):
                item_path = os.path.join(config.OUTPUT_DIR, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    files_removed += 1
                elif os.path.isdir(item_path):
                    for subitem in os.listdir(item_path):
                        subitem_path = os.path.join(item_path, subitem)
                        if os.path.isfile(subitem_path):
                            os.remove(subitem_path)
                            files_removed += 1
                    try:
                        os.rmdir(item_path)
                    except Exception as e:
                        logging.debug(f"Fehler ignoriert: {e}")

            messagebox.showinfo("Bereinigung erfolgreich", f"Erfolgreich {files_removed} Dateien gelöscht.")
            
            # UI zurücksetzen
            self.current_filepath = None
            self.current_raw_original = None
            self.current_raw_mask = None
            self.current_images.clear()
            self.pil_cache.clear()
            
            for name, lbl in self.panels.items():
                lbl.configure(image="", text="\n🌡️\n\nBEREIT FÜR ANALYSE\n\nBitte laden Sie ein Wärmebild über die Seitenleiste.\n")
            for name, lbl in self.panels_full.items():
                lbl.configure(image="", text="\n\n🌡️\n\nNoch kein Wärmebild geladen.\n\nBitte laden Sie eine Bilddatei über die linke Seitenleiste.\n")
                
            self.filename_label.configure(text="Datei: Keine", text_color=COLOR_TEXT_PRIMARY)
            self.hotspot_label.configure(text="Hotspots: --", text_color=COLOR_TEXT_PRIMARY)
            self.pixel_info_label.configure(text="Pixel-Info: --", text_color=COLOR_TEXT_SECONDARY)
            self.status_label.configure(text="Status: Bereit", text_color=COLOR_TEXT_SECONDARY)
            
            for widget in self.hist_container.winfo_children():
                widget.destroy()
            
            self.update_detail_tab()
            self.show_welcome_screen()

        except Exception as e:
            messagebox.showerror("Fehler bei der Bereinigung", f"Ein Fehler ist aufgetreten:\n{e}")

    def load_file(self) -> None:
        """Öffnet einen Datei-Dialog und startet die Pipeline bei Dateiauswahl."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Bilddateien", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif")]
        )
        if file_path:
            self.hide_welcome_screen()
            self.current_filepath = file_path
            self.filename_label.configure(
                text=f"Datei: {os.path.basename(file_path)}",
                text_color=COLOR_PRIMARY_ACCENT
            )
            self.process_pipeline()

    def toggle_pipeline_parameters(self) -> None:
        """Blendet die Pipeline-Parameter in der Seitenleiste ein oder aus."""
        if self.parameters_visible:
            self.param_sliders_frame.pack_forget()
            self.toggle_param_btn.configure(text="📊 Parameter einblenden  ▸")
            self.parameters_visible = False
        else:
            self.param_sliders_frame.pack(fill=ctk.X, padx=12, pady=(4, 8))
            self.toggle_param_btn.configure(text="📊 Parameter ausblenden  ▾")
            self.parameters_visible = True

    def update_params(self, event=None) -> None:
        """Sammelt alle Slider-Werte und startet die Pipeline neu (debounced)."""
        sk = self.sigma_k_slider.get()
        th = self.tophat_slider.get()
        ma = self.min_area_slider.get()
        mc = self.min_circ_slider.get()
        omin = int(self.otsu_min_slider.get())
        omax = int(self.otsu_max_slider.get())
        er = self.erosion_slider.get()
        to = self.temp_offset_slider.get()
        
        # Labels aktualisieren
        self.sigma_k_val.configure(text=f"{sk:.1f}")
        self.tophat_val.configure(text=f"{th*100:.1f} %")
        self.min_area_val.configure(text=f"{ma*100:.3f} %")
        self.min_circ_val.configure(text=f"{mc:.3f}")
        self.otsu_min_val.configure(text=str(omin))
        self.otsu_max_val.configure(text=str(omax))
        self.erosion_val.configure(text=f"{er*100:.1f} %")
        self.temp_offset_val.configure(text=f"{to:+.1f}")
        
        if self.current_filepath:
            # Slider-Bewegungen debouncen: Falls ein altes Update aussteht, abbrechen.
            # 350 ms Wartezeit: kurze Pausen beim Slider-Ziehen lösen keine Neu-Analyse aus.
            # Verhindert Thread-Stacking bei schneller Slider-Bewegung (Rust: ~30ms pro Lauf).
            if hasattr(self, "_param_update_job") and self._param_update_job:
                self.root.after_cancel(self._param_update_job)
            self._param_update_job = self.root.after(350, self.process_pipeline)

    def on_calibration_changed(self, event=None) -> None:
        """Wird aufgerufen, wenn die Kamera-Kalibrierungswerte geändert werden."""
        try:
            t_min = float(self.t_min_entry.get().replace(",", "."))
            t_max = float(self.t_max_entry.get().replace(",", "."))
            if t_max <= t_min:
                self.calib_status_lbl.configure(
                    text="⚠ T-Max muss größer als T-Min sein!", text_color="#EF4444"
                )
                return
            self.t_min_celsius = t_min
            self.t_max_celsius = t_max
            resolution = (t_max - t_min) / 255.0
            self.calib_status_lbl.configure(
                text=f"Bereich: {t_min:.1f}°C – {t_max:.1f}°C  |  Aufl.: {resolution:.3f}°C/px",
                text_color="#3F3F46"
            )
            # Pipeline neu starten, falls Bild geladen
            if self.current_filepath:
                self.process_pipeline()
        except ValueError:
            self.calib_status_lbl.configure(
                text="⚠ Ungültige Eingabe (nur Zahlen erlaubt)", text_color="#EF4444"
            )



    def convert_celsius_to_unit(self, val_c: float) -> float:
        """Konvertiert einen Celsius-Wert unter Berücksichtigung von Emissionsgrad in die Ziel-Einheit."""
        k = val_c + 273.15
        eps = getattr(self, "emissivity", 0.98)
        if eps <= 0:
            eps = 0.98
        k_corr = k / (eps ** 0.25)
        c_corr = k_corr - 273.15
        
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return c_corr * 1.8 + 32.0
        elif "Kelvin" in unit:
            return k_corr
        return c_corr

    def convert_delta_to_unit(self, delta_c: float) -> float:
        """Konvertiert ein Celsius-Delta unter Berücksichtigung von Emissionsgrad in die Ziel-Einheit."""
        eps = getattr(self, "emissivity", 0.98)
        if eps <= 0:
            eps = 0.98
        delta_c_corr = delta_c / (eps ** 0.25)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return delta_c_corr * 1.8
        return delta_c_corr

    def to_temp_val(self, raw_val: float) -> float:
        """Konvertiert einen Raw-Pixelwert in die ausgewählte Temperatureinheit unter Berücksichtigung von Emissionsgrad."""
        # Basis-Celsius: T_min + x * (T_max - T_min) / 255
        temp_c = self.t_min_celsius + (raw_val / 255.0) * (self.t_max_celsius - self.t_min_celsius)
        
        # Emissionsgrad-Korrektur (Stefan-Boltzmann-Gesetz auf absolute Temperatur in Kelvin)
        temp_k = temp_c + 273.15
        eps = getattr(self, "emissivity", 0.98)
        if eps <= 0:
            eps = 0.98
        temp_k_corr = temp_k / (eps ** 0.25)
        temp_c_corr = temp_k_corr - 273.15
        
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return temp_c_corr * 1.8 + 32.0
        elif "Kelvin" in unit:
            return temp_k_corr
        return temp_c_corr

    def to_temp_str(self, raw_val: float) -> str:
        """Gibt den Temperaturwert formatiert mit der ausgewählten Einheit zurück."""
        val = self.to_temp_val(raw_val)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"
        return f"{val:.2f} {unit_str}"

    def to_delta_val(self, raw_delta: float) -> float:
        """Konvertiert ein Raw-Pixel-Delta in das Temperatur-Delta der ausgewählten Einheit."""
        delta_c = (self.t_max_celsius - self.t_min_celsius) / 255.0 * raw_delta
        eps = getattr(self, "emissivity", 0.98)
        if eps <= 0:
            eps = 0.98
        delta_c_corr = delta_c / (eps ** 0.25)
        
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return delta_c_corr * 1.8
        return delta_c_corr

    def to_delta_str(self, raw_delta: float) -> str:
        """Gibt das Temperatur-Delta formatiert mit der ausgewählten Einheit zurück."""
        val = self.to_delta_val(raw_delta)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"
        return f"{val:.2f} {unit_str}"

    def on_temp_unit_changed(self, unit: str) -> None:
        """Behandelt die Änderung der Temperatureinheit."""
        if self.current_filepath:
            self.process_pipeline()
        else:
            self.update_detail_tab()
            self.draw_histogram()

    def on_emissivity_changed(self, event=None) -> None:
        """Behandelt die Änderung des Emissionsgrads."""
        try:
            val = float(self.emissivity_entry.get().replace(",", "."))
            if not (0.1 <= val <= 1.0):
                raise ValueError()
            self.emissivity = val
            if self.current_filepath:
                self.process_pipeline()
        except ValueError:
            self.emissivity_entry.delete(0, tk.END)
            self.emissivity_entry.insert(0, f"{self.emissivity:.2f}")
            messagebox.showerror("Fehler", "Der Emissionsgrad muss eine Zahl zwischen 0.1 und 1.0 sein.")

    def on_export_path_changed(self, event=None) -> None:
        """Behandelt die manuelle Pfadänderung des Exportordners."""
        path = self.export_path_entry.get().strip()
        if path:
            config.OUTPUT_DIR = path
            config.init_output_dir()
            global AUDIT_LOG_FILE
            config.AUDIT_TRAIL_PATH = os.path.join(config.OUTPUT_DIR, "ignite_audit_trail.csv")
            AUDIT_LOG_FILE = config.AUDIT_TRAIL_PATH

    def browse_export_path(self) -> None:
        """Öffnet den Verzeichnisauswahldialog zur Wahl des Exportordners."""
        path = filedialog.askdirectory(title="Exportordner wählen")
        if path:
            self.export_path_entry.delete(0, tk.END)
            self.export_path_entry.insert(0, path)
            self.on_export_path_changed()

    def toggle_settings_visibility(self) -> None:
        """Blendet die Systemeinstellungen in der Seitenleiste ein oder aus."""
        if self.settings_visible:
            self.settings_boxes_frame.pack_forget()
            self.toggle_settings_btn.configure(text="⚙️ Systemeinstellungen  ▸")
            self.settings_visible = False
        else:
            self.settings_boxes_frame.pack(fill=ctk.X, padx=12, pady=(4, 8))
            self.toggle_settings_btn.configure(text="⚙️ Systemeinstellungen  ▾")
            self.settings_visible = True

    def toggle_actions_visibility(self) -> None:
        """Blendet die Aktionen-Buttons ein oder aus."""
        if self.actions_visible:
            self.actions_container.pack_forget()
            self.toggle_actions_btn.configure(text="📁 Aktionen & Berichte  ▸")
            self.actions_visible = False
        else:
            self.actions_container.pack(fill=ctk.X, padx=12, pady=(4, 8))
            self.toggle_actions_btn.configure(text="📁 Aktionen & Berichte  ▾")
            self.actions_visible = True



    def draw_foot_annotations(self, img: np.ndarray, body_mask: np.ndarray, hotspots_mask: np.ndarray) -> np.ndarray:
        """Erzeugt anatomische Bounding-Boxen und 3-Zonen-Unterteilung."""
        palette = self.palette_menu.get()
        if palette == "Regenbogen (Jet)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        elif palette == "Inferno":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        elif palette == "Heiß (Hot)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_HOT)
        else:  # Graustufen
            annotated = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        h_orig, w_orig = img.shape[:2]
        mid_x = w_orig // 2

        # Rote Hotspots einmischen
        red_img = np.zeros_like(annotated)
        red_img[:] = [85, 0, 255]
        blended = cv2.addWeighted(annotated, 0.3, red_img, 0.7, 0)
        annotated = np.where(hotspots_mask[:, :, None] == 255, blended, annotated).astype(np.uint8)

        # Vertikale Trennlinie
        cv2.line(annotated, (mid_x, 0), (mid_x, h_orig), (100, 116, 139), 1, cv2.LINE_AA)

        self.zonal_stats = {
            "left": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False},
            "right": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False}
        }

        # ── Linker Fuß (Left) ────────────────────────────────────────────────
        left_y, left_x = np.where(body_mask[:, :mid_x] > 0)
        if len(left_y) > 0:
            min_y, max_y = left_y.min(), left_y.max()
            min_x, max_x = left_x.min(), left_x.max()
            
            cv2.rectangle(annotated, (min_x, min_y), (max_x, max_y), (0, 255, 100), 1)
            cv2.putText(annotated, "L-Fuss BBox", (min_x, min_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 100), 1, cv2.LINE_AA)
            
            h_zone = (max_y - min_y) // 3
            z1_y1, z1_y2 = min_y, min_y + h_zone
            z2_y1, z2_y2 = min_y + h_zone, min_y + 2*h_zone
            z3_y1, z3_y2 = min_y + 2*h_zone, max_y
            
            cv2.line(annotated, (min_x, z1_y2), (max_x, z1_y2), (255, 165, 0), 1, cv2.LINE_AA)
            cv2.line(annotated, (min_x, z2_y2), (max_x, z2_y2), (255, 165, 0), 1, cv2.LINE_AA)
            
            # Zonal Masken
            z1_m = np.zeros_like(body_mask)
            z1_m[z1_y1:z1_y2, :mid_x] = body_mask[z1_y1:z1_y2, :mid_x]
            z2_m = np.zeros_like(body_mask)
            z2_m[z2_y1:z2_y2, :mid_x] = body_mask[z2_y1:z2_y2, :mid_x]
            z3_m = np.zeros_like(body_mask)
            z3_m[z3_y1:z3_y2, :mid_x] = body_mask[z3_y1:z3_y2, :mid_x]
            
            self.zonal_stats["left"]["fore"] = np.mean(img[z1_m > 0]) if np.sum(z1_m) > 0 else 0.0
            self.zonal_stats["left"]["mid"] = np.mean(img[z2_m > 0]) if np.sum(z2_m) > 0 else 0.0
            self.zonal_stats["left"]["heel"] = np.mean(img[z3_m > 0]) if np.sum(z3_m) > 0 else 0.0
            self.zonal_stats["left"]["exists"] = True
            
            unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
            unit_char = "C"
            if "Fahrenheit" in unit:
                unit_char = "F"
            elif "Kelvin" in unit:
                unit_char = "K"
            
            val_vf_l = self.to_temp_val(self.zonal_stats["left"]["fore"])
            val_mf_l = self.to_temp_val(self.zonal_stats["left"]["mid"])
            val_f_l = self.to_temp_val(self.zonal_stats["left"]["heel"])
            
            cv2.putText(annotated, f"VF: {val_vf_l:.1f} {unit_char}", (min_x + 3, z1_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"MF: {val_mf_l:.1f} {unit_char}", (min_x + 3, z2_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"F: {val_f_l:.1f} {unit_char}", (min_x + 3, max_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # ── Rechter Fuß (Right) ──────────────────────────────────────────────
        right_y, right_x = np.where(body_mask[:, mid_x:] > 0)
        if len(right_y) > 0:
            min_y, max_y = right_y.min(), right_y.max()
            min_x, max_x = right_x.min() + mid_x, right_x.max() + mid_x
            
            cv2.rectangle(annotated, (min_x, min_y), (max_x, max_y), (0, 255, 100), 1)
            cv2.putText(annotated, "R-Fuss BBox", (min_x, min_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 100), 1, cv2.LINE_AA)
            
            h_zone = (max_y - min_y) // 3
            z1_y1, z1_y2 = min_y, min_y + h_zone
            z2_y1, z2_y2 = min_y + h_zone, min_y + 2*h_zone
            z3_y1, z3_y2 = min_y + 2*h_zone, max_y
            
            cv2.line(annotated, (min_x, z1_y2), (max_x, z1_y2), (255, 165, 0), 1, cv2.LINE_AA)
            cv2.line(annotated, (min_x, z2_y2), (max_x, z2_y2), (255, 165, 0), 1, cv2.LINE_AA)
            
            # Zonal Masken
            z1_m = np.zeros_like(body_mask)
            z1_m[z1_y1:z1_y2, mid_x:] = body_mask[z1_y1:z1_y2, mid_x:]
            z2_m = np.zeros_like(body_mask)
            z2_m[z2_y1:z2_y2, mid_x:] = body_mask[z2_y1:z2_y2, mid_x:]
            z3_m = np.zeros_like(body_mask)
            z3_m[z3_y1:z3_y2, mid_x:] = body_mask[z3_y1:z3_y2, mid_x:]
            
            self.zonal_stats["right"]["fore"] = np.mean(img[z1_m > 0]) if np.sum(z1_m) > 0 else 0.0
            self.zonal_stats["right"]["mid"] = np.mean(img[z2_m > 0]) if np.sum(z2_m) > 0 else 0.0
            self.zonal_stats["right"]["heel"] = np.mean(img[z3_m > 0]) if np.sum(z3_m) > 0 else 0.0
            self.zonal_stats["right"]["exists"] = True
            
            val_vf_r = self.to_temp_val(self.zonal_stats["right"]["fore"])
            val_mf_r = self.to_temp_val(self.zonal_stats["right"]["mid"])
            val_f_r = self.to_temp_val(self.zonal_stats["right"]["heel"])
            
            cv2.putText(annotated, f"VF: {val_vf_r:.1f} {unit_char}", (min_x + 3, z1_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"MF: {val_mf_r:.1f} {unit_char}", (min_x + 3, z2_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"F: {val_f_r:.1f} {unit_char}", (min_x + 3, max_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # ── Kontralaterale Asymmetrie-Analyse (Armstrong Goldstandard) ────────
        if hasattr(self, "asymmetry_switch") and self.asymmetry_switch.get() == 1:
            asym_res = image_processing.compute_contralateral_asymmetry(
                img, body_mask, self.t_min_celsius, self.t_max_celsius, config.ASYMMETRY_THRESHOLD_C
            )
            self.asymmetry_results = asym_res
            delta_t = asym_res["delta_t_c"]
            is_asym = asym_res["is_asymmetric"]
            
            banner_h = 32
            banner_bg = (0, 0, 180) if is_asym else (0, 140, 0)
            cv2.rectangle(annotated, (0, 0), (w_orig, banner_h), banner_bg, -1)
            
            status_symbol = "WARNUNG" if is_asym else "OK"
            banner_txt = f"KONTRALATERALE ASYMMETRIE: Delta-T = {delta_t:.1f} deg C [{status_symbol} > {config.ASYMMETRY_THRESHOLD_C} deg C Goldstandard]" if is_asym else f"KONTRALATERALE SYMMETRIE: Delta-T = {delta_t:.1f} deg C [{status_symbol} <= {config.ASYMMETRY_THRESHOLD_C} deg C]"
            cv2.putText(annotated, banner_txt, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        return annotated

    def show_loading_overlay(self) -> None:
        """Zeigt das Lade-Overlay über dem Hauptbereich."""
        self.welcome_frame.pack_forget()
        self.tabview.pack_forget()
        self.loading_overlay.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        self.root.update_idletasks()

    def hide_loading_overlay(self) -> None:
        """Blendet das Lade-Overlay aus und stellt den korrekten Hauptbereich wieder her."""
        self.loading_overlay.pack_forget()
        if self.current_filepath:
            self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)
        else:
            self.welcome_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        self.root.update_idletasks()

    def update_loading_progress(self, val: float, msg: str) -> None:
        """Aktualisiert die Fortschrittsanzeige im Overlay."""
        self.loading_pbar.set(val)
        self.loading_step_lbl.configure(text=msg)
        self.root.update_idletasks()

    def process_pipeline(self) -> None:
        """Führt die Analyse-Pipeline asynchron im Hintergrund aus, um die GUI flüssig zu halten."""
        if not self.current_filepath:
            return

        # Wenn bereits ein Job läuft, flaggen wir eine anschließende Neuberechnung
        if hasattr(self, "_pipeline_running") and self._pipeline_running:
            self._pipeline_needs_rerun = True
            return

        self._pipeline_running = True
        self._pipeline_needs_rerun = False

        self.show_loading_overlay()
        self.update_loading_progress(0.15, "Lade thermografische Rohdaten...")

        # Parameter lokal kopieren
        params = {
            "file_path": self.current_filepath,
            "sk": self.sigma_k_slider.get(),
            "th": self.tophat_slider.get(),
            "ma": self.min_area_slider.get(),
            "mc": self.min_circ_slider.get(),
            "omin": int(self.otsu_min_slider.get()),
            "omax": int(self.otsu_max_slider.get()),
            "er": self.erosion_slider.get(),
            "to": self.temp_offset_slider.get(),
            "use_mad": self.mad_switch.get() == 1,
            "t_min": self.t_min_celsius,
            "t_max": self.t_max_celsius,
            "mode": self.analysis_mode_opt.get()
        }

        def worker():
            try:
                # 1. Kalibrierung
                self.root.after(0, lambda: self.update_loading_progress(0.35, "Applikation der Kalibrierung (Temp-Offset)..."))
                img = image_processing.load_thermal_image(params["file_path"])
                
                range_c = params["t_max"] - params["t_min"]
                if range_c <= 0:
                    range_c = 20.0
                raw_offset = int(round(params["to"] * 255.0 / range_c))
                
                calibrated_img = np.clip(img.astype(np.int16) + raw_offset, 0, 255).astype(np.uint8)
                
                storage.save_image_step(calibrated_img, "1", "original", params["file_path"])
                storage.save_data_step(calibrated_img, "1", "original", params["file_path"])

                # 2. Rust/GPU Pipeline ausführen
                self.root.after(0, lambda: self.update_loading_progress(0.60, "Suche Hotspots (Denoising & Top-Hat Differenz)..."))
                diff_img, hotspot_mask = image_processing.run_rust_pipeline(
                    calibrated_img, params["sk"], params["th"], params["ma"], params["mc"], params["omin"], params["omax"], params["er"], use_mad=params["use_mad"]
                )

                # 3. Maske und Speicherung
                self.root.after(0, lambda: self.update_loading_progress(0.80, "Speichere Analyseergebnisse und Zwischenbilder..."))
                body_mask_vis = (diff_img > 0).astype(np.uint8) * 255

                storage.save_image_step(body_mask_vis, "2", "mask", params["file_path"])
                storage.save_data_step(body_mask_vis, "2", "mask", params["file_path"])

                storage.save_image_step(diff_img, "3", "local_heat_diff", params["file_path"])
                storage.save_data_step(diff_img, "3", "local_heat_diff_raw", params["file_path"])

                storage.save_image_step(hotspot_mask, "4", "dynamic_hotspots", params["file_path"])
                storage.save_data_step(hotspot_mask, "4", "dynamic_hotspots_raw", params["file_path"])

                # Auf Hauptthread abschließen
                self.root.after(0, lambda: self.on_pipeline_done(
                    calibrated_img, body_mask_vis, diff_img, hotspot_mask, params
                ))

            except Exception as e:
                self.root.after(0, lambda err=e: self.on_pipeline_failed(err))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def on_pipeline_done(self, calibrated_img, body_mask_vis, diff_img, hotspot_mask, params):
        self.current_raw_original = calibrated_img
        self.current_raw_mask = hotspot_mask

        # 4. Overlays zeichnen (sicher auf dem Hauptthread)
        self.update_loading_progress(0.90, "Rendere Auswertungsoverlays und Statistiken...")
        if params["mode"] == "Podologische Symmetrieanalyse":
            annotated_overlay = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
        else:
            annotated_overlay = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
            
        overlay_rgb = cv2.cvtColor(annotated_overlay, cv2.COLOR_BGR2RGB)

        # Panels aktualisieren
        self.display_image_in_panel(calibrated_img, "1. Originalbild")
        self.display_image_in_panel(body_mask_vis, "2. Hintergrund-Maske")
        self.display_image_in_panel(diff_img, "3. Lokale Hitze-Differenz")
        self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

        # Histogramm & Zonal Update
        self.draw_histogram()
        
        # Detail-Tab updaten (stellt sicher, dass die Tabelle befüllt wird!)
        self.update_detail_tab()

        # Hotspot Count & UI Label
        hotspot_count = int(hotspot_mask.sum()) // 255
        self.update_backend_label()

        if hotspot_count == 0:
            hotspot_color = COLOR_TEXT_PRIMARY
            hotspot_text = "0 Pixel (Normal)"
        elif hotspot_count < 150:
            hotspot_color = COLOR_WARNING
            hotspot_text = f"{hotspot_count} Pixel (Verdacht)"
        else:
            hotspot_color = COLOR_DANGER
            hotspot_text = f"{hotspot_count} Pixel (Entzündung)"

        self.hotspot_label.configure(
            text=f"Hotspots: {hotspot_text}",
            text_color=hotspot_color
        )

        self.status_label.configure(
            text="Status: ✓ Berechnet",
            text_color=COLOR_SUCCESS
        )

        # Audit-Trail Eintrag schreiben
        try:
            max_px_val = float(np.max(calibrated_img[hotspot_mask > 0])) if np.any(hotspot_mask > 0) else 0.0
            max_temp_c = pixel_to_celsius(max_px_val, params["t_min"], params["t_max"])
            write_audit_entry({
                "Zeitstempel": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Patienten-ID": "n.a.",
                "Analysemodus": params["mode"],
                "Bilddatei": os.path.basename(params["file_path"]),
                "sigma_k": round(params["sk"], 2),
                "tophat_factor": round(params["th"], 4),
                "T_min_C": params["t_min"],
                "T_max_C": params["t_max"],
                "Hotspot_Pixel": hotspot_count,
                "Max_Temp_C": round(max_temp_c, 2),
                "Symmetrie_Delta": round(
                    abs(self.zonal_stats.get("left", {}).get("fore", 0.0) -
                        self.zonal_stats.get("right", {}).get("fore", 0.0)), 2
                ) if params["mode"] == "Podologische Symmetrieanalyse" else "n.a.",
                "Operator": "Jugend forscht",
            })
        except Exception as audit_err:
            print(f"[AUDIT] Fehler: {audit_err}")

        # Loading-Screen ausblenden
        self.hide_loading_overlay()

        self._pipeline_running = False
        if self._pipeline_needs_rerun:
            self.process_pipeline()

    def on_pipeline_failed(self, error):
        self.hide_loading_overlay()
        self._pipeline_running = False
        self.status_label.configure(text="Status: Hinweis", text_color="#EF4444")
        self.backend_label.configure(text="Backend: Aktiv", text_color="#3B82F6")
        self.hotspot_label.configure(text="Hotspots: 0 px", text_color="#9CA3AF")
        
        err_msg = str(error)
        if "Body-Mask ist leer" in err_msg or "kein Körper im Bild" in err_msg:
            messagebox.showwarning(
                "Kein Gewebe erkannt",
                "Das Wärmebild enthält keine verwertbaren Körperkonturen.\n\n"
                "Mögliche Ursachen:\n"
                "• Die Aufnahme zeigt nur den kühlen Hintergrund.\n"
                "• Die Otsu-Schwellenwerte sind zu restriktiv eingestellt.\n\n"
                "Empfehlung: Passe den Kameraabstand an oder reduziere den minimalen Otsu-Schwellenwert."
            )
        else:
            messagebox.showerror("Analyse-Fehler", f"Fehler bei der Wärmebildverarbeitung:\n{err_msg}")

    def update_backend_label(self) -> None:
        """Fragt das aktive Backend ab und formatiert die Labelanzeige in der GUI."""
        backend_info = image_processing.get_active_backend()
        if "GPU (CUDA," in backend_info:
            gpu_name = backend_info.split(",", 1)[1].strip().replace(")", "")
            backend_disp = f"GPU: {gpu_name}"
        else:
            backend_disp = backend_info

        forced = self.backend_var.get()
        if forced != "auto":
            backend_disp = f"{backend_disp} (Erzwungen)"

        self.backend_label.configure(
            text=f"Backend: {backend_disp}",
            text_color=COLOR_PRIMARY_ACCENT
        )

    def display_image_in_panel(self, cv_img: np.ndarray, panel_name: str, update_cache: bool = True) -> None:
        """Zeigt ein OpenCV-Bild in dem Grid-Panel und dem Full-size-Panel an."""
        if update_cache:
            self.current_images[panel_name] = cv_img

            if panel_name == "1. Originalbild":
                palette = self.palette_menu.get()
                if palette == "Regenbogen (Jet)":
                    color_img = cv2.applyColorMap(cv_img, cv2.COLORMAP_JET)
                    rgb_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)
                elif palette == "Inferno":
                    color_img = cv2.applyColorMap(cv_img, cv2.COLORMAP_INFERNO)
                    rgb_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)
                elif palette == "Heiß (Hot)":
                    color_img = cv2.applyColorMap(cv_img, cv2.COLORMAP_HOT)
                    rgb_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2RGB)
                else:
                    rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
            else:
                if len(cv_img.shape) == 2:
                    rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
                else:
                    rgb_img = cv_img

            # LRU-Cache-Limit prüfen und ältesten Eintrag verdrängen wenn nötig
            self.pil_cache[panel_name] = Image.fromarray(rgb_img)
            self.pil_cache.move_to_end(panel_name)  # Als MRU markieren
            while len(self.pil_cache) > self._PIL_CACHE_MAXSIZE:
                self.pil_cache.popitem(last=False)  # Ältesten (LRU) entfernen

        pil_img = self.pil_cache.get(panel_name)
        if pil_img is None:
            return

        # 1. Grid Panel
        lbl_grid = self.panels[panel_name]
        w_grid = max(lbl_grid.winfo_width() - 30, 100)
        h_grid = max(lbl_grid.winfo_height() - 30, 100)
        if w_grid <= 100 or h_grid <= 100:
            w_grid, h_grid = 420, 280

        pil_grid = pil_img.copy()
        pil_grid.thumbnail((w_grid, h_grid))
        img_tk_grid = ctk.CTkImage(light_image=pil_grid, dark_image=pil_grid, size=pil_grid.size)
        lbl_grid.configure(image=img_tk_grid, text="")
        lbl_grid.image = img_tk_grid

        # 2. Fullsize Panel
        lbl_full = self.panels_full[panel_name]
        w_full = max(lbl_full.winfo_width() - 40, 100)
        h_full = max(lbl_full.winfo_height() - 40, 100)
        if w_full <= 100 or h_full <= 100:
            w_full, h_full = 800, 500

        pil_full = pil_img.copy()
        pil_full.thumbnail((w_full, h_full))
        img_tk_full = ctk.CTkImage(light_image=pil_full, dark_image=pil_full, size=pil_full.size)
        lbl_full.configure(image=img_tk_full, text="")
        lbl_full.image = img_tk_full

    def on_window_configure(self, event) -> None:
        """Handler für Größenänderungen des Hauptfensters. Führt ein debounctes Redraw aus."""
        if event.widget == self.root and self.current_images:
            if self.resize_job:
                self.root.after_cancel(self.resize_job)
            self.resize_job = self.root.after(150, self.redraw_all_images)

    def redraw_all_images(self) -> None:
        """Zeichnet alle geladenen Bilder passend zur neuen Fenstergröße neu."""
        for name, cv_img in self.current_images.items():
            self.display_image_in_panel(cv_img, name, update_cache=False)
        self.draw_histogram()

    def toggle_appearance_mode(self) -> None:
        """Schaltet das Design der Anwendung zwischen Light Mode und Dark Mode um."""
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

    def on_backend_changed(self) -> None:
        """Wird ausgelöst, wenn das Berechnungs-Backend im Menü geändert wird."""
        forced_val = self.backend_var.get()
        image_processing.FORCED_BACKEND = forced_val
        self.update_backend_label()

        if self.current_filepath:
            self.process_pipeline()

    def on_backend_ui_changed(self, choice: str) -> None:
        """Wird aufgerufen, wenn das Berechnungs-Backend im UI-Dropdown geändert wird."""
        mapping = {
            "Automatisch (Schnellstes)": "auto",
            "Erzwinge Rust-CPU-Core": "rust",
            "Erzwinge PyTorch-GPU": "gpu",
            "Erzwinge Python-Fallback": "python"
        }
        val = mapping.get(choice, "auto")
        self.backend_var.set(val)
        self.on_backend_changed()

    def on_palette_changed(self, value: str) -> None:
        """Wird ausgelöst, wenn die Falschfarbenpalette geändert wird."""
        if self.current_raw_original is not None:
            self.display_image_in_panel(self.current_raw_original, "1. Originalbild")
            
            if self.current_raw_mask is not None:
                body_mask_vis = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) * 255
                if self.analysis_mode_opt.get() == "Podologische Symmetrieanalyse":
                    overlay_img = self.draw_foot_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)
                else:
                    overlay_img = self.draw_general_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)
                overlay_rgb = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB)
                self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

    def on_image_hover(self, event, panel_name: str, is_grid: bool) -> None:
        """Digitaler Pixel-Inspektor für exakte Hitzewerte."""
        if self.current_raw_original is None:
            return

        lbl = self.panels[panel_name] if is_grid else self.panels_full[panel_name]
        lbl_w = lbl.winfo_width()
        lbl_h = lbl.winfo_height()
        
        orig_h, orig_w = self.current_raw_original.shape[:2]
        
        pad = 30 if is_grid else 40
        w_avail = max(lbl_w - pad, 100)
        h_avail = max(lbl_h - pad, 100)
        
        if w_avail <= 100 or h_avail <= 100:
            return
            
        ratio = min(w_avail / orig_w, h_avail / orig_h)
        img_w = int(orig_w * ratio)
        img_h = int(orig_h * ratio)
        
        offset_x = (lbl_w - img_w) / 2
        offset_y = (lbl_h - img_h) / 2
        
        mx = event.x - offset_x
        my = event.y - offset_y
        
        if 0 <= mx < img_w and 0 <= my < img_h:
            orig_x = int(mx * (orig_w / img_w))
            orig_y = int(my * (orig_h / img_h))
            
            orig_x = min(max(orig_x, 0), orig_w - 1)
            orig_y = min(max(orig_y, 0), orig_h - 1)
            
            val = self.current_raw_original[orig_y, orig_x]
            temp_str = self.to_temp_str(float(val))

            is_hotspot = False
            if self.current_raw_mask is not None:
                is_hotspot = self.current_raw_mask[orig_y, orig_x] > 0

            hotspot_str = "Hotspot detektiert" if is_hotspot else "Unauffällig"
            hotspot_color = "#FF0055" if is_hotspot else "#0EA5E9"

            self.pixel_info_label.configure(
                text=f"X={orig_x}, Y={orig_y}  |  {temp_str}  (px={val})\nBefund: {hotspot_str}",
                text_color=hotspot_color
            )
        else:
            self.pixel_info_label.configure(text="Pixel: außerhalb des Bildes", text_color="#71717A")

    def on_image_leave(self, event) -> None:
        """Setzt den Pixel-Inspektor zurück, wenn die Maus das Bild verlässt."""
        self.pixel_info_label.configure(text="Pixel-Info: --", text_color="#71717A")

    def map_event_to_image_coords(self, event, panel_name: str, is_grid: bool) -> tuple[int | None, int | None]:
        """Übersetzt Widget-Mauskoordinaten in die originalen Pixel-Koordinaten des Bildes."""
        if self.current_raw_original is None:
            return None, None

        lbl = self.panels[panel_name] if is_grid else self.panels_full[panel_name]
        lbl_w = lbl.winfo_width()
        lbl_h = lbl.winfo_height()
        
        orig_h, orig_w = self.current_raw_original.shape[:2]
        
        pad = 30 if is_grid else 40
        w_avail = max(lbl_w - pad, 100)
        h_avail = max(lbl_h - pad, 100)
        
        if w_avail <= 100 or h_avail <= 100:
            return None, None
            
        ratio = min(w_avail / orig_w, h_avail / orig_h)
        img_w = int(orig_w * ratio)
        img_h = int(orig_h * ratio)
        
        offset_x = (lbl_w - img_w) / 2
        offset_y = (lbl_h - img_h) / 2
        
        mx = event.x - offset_x
        my = event.y - offset_y
        
        if 0 <= mx < img_w and 0 <= my < img_h:
            orig_x = int(mx * (orig_w / img_w))
            orig_y = int(my * (orig_h / img_h))
            orig_x = min(max(orig_x, 0), orig_w - 1)
            orig_y = min(max(orig_y, 0), orig_h - 1)
            return orig_x, orig_y
            
        return None, None

    def on_roi_start(self, event, panel_name: str, is_grid: bool) -> None:
        """Erfasst den Startpunkt beim Zeichnen einer ROI."""
        if self.current_raw_original is None:
            return
        x_orig, y_orig = self.map_event_to_image_coords(event, panel_name, is_grid)
        if x_orig is not None and y_orig is not None:
            self.roi_start_x = x_orig
            self.roi_start_y = y_orig
            self.roi_active_panel = panel_name
            self.roi_active_is_grid = is_grid
            self.drawing_roi = True

    def on_roi_drag(self, event, panel_name: str, is_grid: bool) -> None:
        """Zeichnet live ein temporäres grünes Rechteck beim Ziehen der Maus."""
        if not getattr(self, "drawing_roi", False) or getattr(self, "roi_active_panel", None) != panel_name:
            return
        
        x_orig, y_orig = self.map_event_to_image_coords(event, panel_name, is_grid)
        if x_orig is not None and y_orig is not None:
            self.roi_current_x = x_orig
            self.roi_current_y = y_orig
            self.draw_temp_roi_on_panel(panel_name, is_grid, self.roi_start_x, self.roi_start_y, x_orig, y_orig)

    def on_roi_end(self, event, panel_name: str, is_grid: bool) -> None:
        """Schließt das Zeichnen der ROI ab und berechnet die lokalen Statistiken."""
        if not getattr(self, "drawing_roi", False) or getattr(self, "roi_active_panel", None) != panel_name:
            return
        
        self.drawing_roi = False
        x_orig, y_orig = self.map_event_to_image_coords(event, panel_name, is_grid)
        if x_orig is not None and y_orig is not None:
            self.roi_end_x = x_orig
            self.roi_end_y = y_orig
            self.calculate_and_show_roi_stats(self.roi_start_x, self.roi_start_y, self.roi_end_x, self.roi_end_y)
        else:
            self.calculate_and_show_roi_stats(self.roi_start_x, self.roi_start_y, self.roi_current_x, self.roi_current_y)
        
        # Originalbild wiederherstellen
        self.redraw_all_images()

    def draw_temp_roi_on_panel(self, panel_name: str, is_grid: bool, x1: int, y1: int, x2: int, y2: int) -> None:
        """Zeichnet ein Rechteck direkt auf das gecachte PIL-Bild und aktualisiert das UI-Widget."""
        pil_orig = self.pil_cache.get(panel_name)
        if pil_orig is None:
            return
            
        from PIL import ImageDraw
        pil_copy = pil_orig.copy()
        draw = ImageDraw.Draw(pil_copy)
        
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        
        # Grünes Rechteck zeichnen (outline und width)
        draw.rectangle([min_x, min_y, max_x, max_y], outline="#10B981", width=3)
        
        # 1. Grid Panel aktualisieren
        lbl_grid = self.panels[panel_name]
        w_grid = max(lbl_grid.winfo_width() - 30, 100)
        h_grid = max(lbl_grid.winfo_height() - 30, 100)
        if w_grid <= 100 or h_grid <= 100:
            w_grid, h_grid = 420, 280

        pil_grid = pil_copy.copy()
        pil_grid.thumbnail((w_grid, h_grid))
        img_tk_grid = ctk.CTkImage(light_image=pil_grid, dark_image=pil_grid, size=pil_grid.size)
        lbl_grid.configure(image=img_tk_grid, text="")
        lbl_grid.image = img_tk_grid

        # 2. Fullsize Panel aktualisieren
        lbl_full = self.panels_full[panel_name]
        w_full = max(lbl_full.winfo_width() - 40, 100)
        h_full = max(lbl_full.winfo_height() - 40, 100)
        if w_full <= 100 or h_full <= 100:
            w_full, h_full = 800, 500

        pil_full = pil_copy.copy()
        pil_full.thumbnail((w_full, h_full))
        img_tk_full = ctk.CTkImage(light_image=pil_full, dark_image=pil_full, size=pil_full.size)
        lbl_full.configure(image=img_tk_full, text="")
        lbl_full.image = img_tk_full

    def calculate_and_show_roi_stats(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Berechnet T-Min, T-Max, Durchschnitt, Standardabweichung und Hotspots für die ROI."""
        if self.current_raw_original is None:
            return
            
        min_x = max(0, min(x1, x2))
        max_x = min(self.current_raw_original.shape[1] - 1, max(x1, x2))
        min_y = max(0, min(y1, y2))
        max_y = min(self.current_raw_original.shape[0] - 1, max(y1, y2))
        
        if min_x == max_x or min_y == max_y:
            return
            
        roi_patch = self.current_raw_original[min_y:max_y+1, min_x:max_x+1]
        
        # Maske ermitteln
        roi_mask_patch = None
        if self.current_raw_mask is not None:
            roi_mask_patch = self.current_raw_mask[min_y:max_y+1, min_x:max_x+1]
                
        val_min = float(np.min(roi_patch))
        val_max = float(np.max(roi_patch))
        val_mean = float(np.mean(roi_patch))
        val_std = float(np.std(roi_patch))
        
        temp_min = pixel_to_celsius(val_min, self.t_min_celsius, self.t_max_celsius)
        temp_max = pixel_to_celsius(val_max, self.t_min_celsius, self.t_max_celsius)
        temp_mean = pixel_to_celsius(val_mean, self.t_min_celsius, self.t_max_celsius)
        temp_std = (val_std / 255.0) * (self.t_max_celsius - self.t_min_celsius)
        
        hotspot_px = 0
        if roi_mask_patch is not None:
            hotspot_px = int(np.sum(roi_mask_patch > 0))
            
        self.update_roi_sidebar_ui(min_x, min_y, max_x, max_y, temp_min, temp_max, temp_mean, temp_std, hotspot_px)

    def update_roi_sidebar_ui(self, x1, y1, x2, y2, t_min, t_max, t_mean, t_std, hotspots) -> None:
        """Baut den Inhalt des ROI-Statistik-Panels dynamisch auf."""
        for w in self.roi_stats_frame.winfo_children():
            w.destroy()
            
        self.roi_info_lbl.pack_forget()
        self.roi_stats_frame.pack(fill=ctk.X, padx=12, pady=4)
        
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"
            
        def format_temp(val_c):
            val_converted = self.convert_celsius_to_unit(val_c) if hasattr(self, "convert_celsius_to_unit") else val_c
            return f"{val_converted:.2f} {unit_str}"
            
        def format_delta(val_c_delta):
            val_converted = (val_c_delta * 1.8) if "Fahrenheit" in unit else val_c_delta
            return f"{val_converted:.2f} {unit_str}"

        ctk.CTkLabel(self.roi_stats_frame, text=f"Bereich: [{x1},{y1}] bis [{x2},{y2}]", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_PRIMARY_ACCENT, anchor="w").pack(fill=ctk.X, pady=2)
        
        grid = ctk.CTkFrame(self.roi_stats_frame, fg_color="transparent")
        grid.pack(fill=ctk.X, pady=4)
        
        stats = [
            ("Max. Temp:", format_temp(t_max)),
            ("Min. Temp:", format_temp(t_min)),
            ("Mittelwert (µ):", format_temp(t_mean)),
            ("Abweichung (σ):", format_delta(t_std)),
            ("Hotspot-Pixel:", f"{hotspots} px")
        ]
        
        for name, val in stats:
            row = ctk.CTkFrame(grid, fg_color="transparent")
            row.pack(fill=ctk.X, pady=1)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=10, weight="bold"), text_color=COLOR_TEXT_SECONDARY, anchor="w").pack(side=ctk.LEFT)
            ctk.CTkLabel(row, text=val, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side=ctk.RIGHT)

        btn_reset = ctk.CTkButton(
            self.roi_stats_frame,
            text="ROI zurücksetzen",
            command=self.reset_roi_analysis,
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            text_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_BORDER_CARD,
            border_width=1,
            border_color=COLOR_BORDER_CARD,
            height=24,
            corner_radius=4
        )
        btn_reset.pack(fill=ctk.X, pady=(6, 2))

    def reset_roi_analysis(self) -> None:
        """Setzt die ROI-Analyse zurück."""
        for w in self.roi_stats_frame.winfo_children():
            w.destroy()
        self.roi_stats_frame.pack_forget()
        self.roi_info_lbl.pack(fill=ctk.X, padx=12, pady=4)
        self.redraw_all_images()

    def draw_histogram(self) -> None:
        """Zeichnet das statistische Matplotlib-Histogramm exklusiv über der Körperoberfläche."""
        if self.current_raw_original is None:
            return

        body_mask = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) if "2. Hintergrund-Maske" in self.current_images else None
        if body_mask is None or np.sum(body_mask) == 0:
            return

        img = self.current_raw_original
        pixels = img[body_mask > 0]
        if len(pixels) == 0:
            return

        # Statistiken (in Raw-Werten für Berechnung, °C für Anzeige)
        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        threshold = mean_val + self.sigma_k_slider.get() * std_val

        # Einheit bestimmen
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"

        # Dynamische Konvertierung für Statistiken
        mean_disp = self.to_temp_val(mean_val)
        std_disp = self.to_delta_val(std_val)
        thresh_disp = self.to_temp_val(threshold)
        max_disp = self.to_temp_val(float(np.max(pixels)))

        # Vektorisierte Konvertierung der Pixeldaten mittels Numpy (effizient)
        temp_c = self.t_min_celsius + (pixels / 255.0) * (self.t_max_celsius - self.t_min_celsius)
        temp_k = temp_c + 273.15
        eps = getattr(self, "emissivity", 0.98)
        if eps <= 0:
            eps = 0.98
        temp_k_corr = temp_k / (eps ** 0.25)
        temp_c_corr = temp_k_corr - 273.15
        
        if "Fahrenheit" in unit:
            pixels_disp = temp_c_corr * 1.8 + 32.0
        elif "Kelvin" in unit:
            pixels_disp = temp_k_corr
        else:
            pixels_disp = temp_c_corr

        # Clear previous matplotlib drawing
        for widget in self.hist_container.winfo_children():
            widget.destroy()

        # Matplotlib Styling je nach aktivem Designmode (Light/Dark)
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            bg_fig = "#0B0F19" # Match dark COLOR_BG_CARD
            bg_ax = "#0B0F19"
            color_text = "#F8FAFC"
            color_tick = "#94A3B8"
            color_grid = "#1E293B"
            color_spine = "#1E293B"
            bg_legend = "#070A13"
        else:
            bg_fig = "#FFFFFF" # Match light COLOR_BG_CARD
            bg_ax = "#FFFFFF"
            color_text = "#0F172A"
            color_tick = "#475569"
            color_grid = "#E2E8F0"
            color_spine = "#E2E8F0"
            bg_legend = "#F1F5F9"

        # Matplotlib Figure erstellen
        fig = Figure(figsize=(6, 3.8), dpi=100, facecolor=bg_fig)
        ax = fig.add_subplot(111, facecolor=bg_ax)

        # Histogramm plotten
        ax.hist(pixels_disp, bins=128, color=COLOR_PRIMARY_ACCENT, alpha=0.7, edgecolor="none")

        # Hilfslinien
        ax.axvline(mean_disp, color=("#18181B" if mode != "Dark" else "#F4F4F5"), linestyle="--", linewidth=1.5,
                   label=f"Mittelwert \u03bc ({mean_disp:.1f} {unit_str})")
        ax.axvline(thresh_disp, color="#FF0055", linestyle="-.", linewidth=2.0,
                   label=f"Grenzwert µ+k\u03c3 ({thresh_disp:.1f} {unit_str})")

        # Achsen-Styling
        ax.spines['bottom'].set_color(color_spine)
        ax.spines['top'].set_color(color_spine)
        ax.spines['left'].set_color(color_spine)
        ax.spines['right'].set_color(color_spine)
        ax.tick_params(colors=color_tick, labelsize=8)
        ax.set_xlabel(f"Temperatur ({unit_str})", color=color_text, fontsize=9, fontweight="bold")
        ax.set_ylabel("Häufigkeit", color=color_text, fontsize=9, fontweight="bold")
        ax.legend(facecolor=bg_legend, edgecolor=color_spine, labelcolor=color_text, fontsize=8)
        ax.grid(color=color_grid, linestyle=":", linewidth=0.5)

        fig.tight_layout()

        # Canvas einbetten
        canvas_widget = FigureCanvasTkAgg(fig, master=self.hist_container)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # ── Statistiken-Labels updaten ──────────────────────────────
        self.stats_labels["pixel_count"].configure(text=f"{len(pixels):,} px")
        self.stats_labels["mean"].configure(text=f"{mean_disp:.2f} {unit_str}")
        self.stats_labels["std"].configure(text=f"{std_disp:.2f} {unit_str}")
        self.stats_labels["threshold"].configure(text=f"{thresh_disp:.2f} {unit_str}")
        self.stats_labels["max_val"].configure(text=f"{max_disp:.2f} {unit_str}")

        hotspot_count = int(self.current_raw_mask.sum()) // 255 if self.current_raw_mask is not None else 0
        self.stats_labels["hotspots"].configure(
            text=f"{hotspot_count} px",
            text_color="#FF0055" if hotspot_count > 0 else COLOR_TEXT_PRIMARY
        )

        percentage = (hotspot_count / len(pixels)) * 100 if len(pixels) > 0 else 0
        self.stats_labels["percentage"].configure(
            text=f"{percentage:.3f} %",
            text_color="#FF0055" if hotspot_count > 0 else COLOR_TEXT_PRIMARY
        )


        # ── Titel & Metriken je nach Modus anpassen ──────────────────────────
        mode_analysis = self.analysis_mode_opt.get()

        if mode_analysis == "Podologische Symmetrieanalyse":
            self.stats_title_labels["pixel_count"].configure(text="Fußoberfläche (Pixel)")
            self.stats_title_labels["mean"].configure(text="Mittelwert Fußhitze (µ)")
            if self.stats_divider_label:
                self.stats_divider_label.configure(text="KLINISCHE SYMMETRIE (L/R)")
            self.stats_title_labels["mean_left"].configure(text="Mittelwert Links (L)")
            self.stats_title_labels["mean_right"].configure(text="Mittelwert Rechts (R)")
            self.stats_title_labels["delta"].configure(text="Symmetrie-Delta (Δ)")
            self.stats_title_labels["status_symmetry"].configure(text="Symmetriestatus")

            # Symmetrievergleich berechnen
            h_orig, w_orig = img.shape[:2]
            mid_x = w_orig // 2
            
            left_mask = np.zeros_like(body_mask)
            left_mask[:, :mid_x] = body_mask[:, :mid_x]
            right_mask = np.zeros_like(body_mask)
            right_mask[:, mid_x:] = body_mask[:, mid_x:]
            
            left_pixels = img[left_mask > 0]
            right_pixels = img[right_mask > 0]
            
            if len(left_pixels) > 0 and len(right_pixels) > 0:
                mean_l = np.mean(left_pixels)
                mean_r = np.mean(right_pixels)
                delta = abs(mean_l - mean_r)
                
                # Dynamische Einheitenumrechnung
                mean_l_disp = self.to_temp_val(mean_l)
                mean_r_disp = self.to_temp_val(mean_r)
                delta_disp = self.to_delta_val(delta)

                if delta >= 15.0:
                    sym_status = "Asymmetrie detektiert \u2013 Bitte abkl\u00e4ren"
                    sym_color = "#FF0055"
                else:
                    sym_status = "Symmetrisch \u2013 Unauff\u00e4llig"
                    sym_color = "#10B981"

                self.stats_labels["mean_left"].configure(text=f"{mean_l_disp:.2f} {unit_str}")
                self.stats_labels["mean_right"].configure(text=f"{mean_r_disp:.2f} {unit_str}")
                self.stats_labels["delta"].configure(text=f"{delta_disp:.2f} {unit_str}", text_color=sym_color)
                self.stats_labels["status_symmetry"].configure(text=sym_status, text_color=sym_color)
            else:
                self.stats_labels["mean_left"].configure(text="--")
                self.stats_labels["mean_right"].configure(text="--")
                self.stats_labels["delta"].configure(text="--", text_color=COLOR_TEXT_PRIMARY)
                self.stats_labels["status_symmetry"].configure(text="Keine Messdaten vorhanden", text_color=COLOR_TEXT_PRIMARY)

        else:
            self.stats_title_labels["pixel_count"].configure(text="Objektoberfläche (Pixel)")
            self.stats_title_labels["mean"].configure(text="Mittelwert Hitze (µ)")
            if self.stats_divider_label:
                self.stats_divider_label.configure(text="HOTSPOT-METRIKEN")
            self.stats_title_labels["mean_left"].configure(text="Anzahl Hotspots")
            self.stats_title_labels["mean_right"].configure(text="Größte Hotspot-Fläche")
            self.stats_title_labels["delta"].configure(text="Durchschn. Hotspot-Hitze")
            self.stats_title_labels["status_symmetry"].configure(text="Globaler Befund")

            # Allgemeine Hotspot-Statistiken
            hotspots = getattr(self, "general_hotspots", [])
            num_hotspots = len(hotspots)
            max_area = hotspots[0]["area"] if num_hotspots > 0 else 0
            avg_temp = np.mean([hs["mean_temp"] for hs in hotspots]) if num_hotspots > 0 else 0.0
            
            if hotspot_count == 0:
                diag_status = "Unauff\u00e4llig \u2013 Kein Befund"
                diag_color = "#10B981"
            elif hotspot_count < 150:
                diag_status = "Grenzwertig \u2013 Verlaufsbeobachtung"
                diag_color = "#FFA500"
            else:
                diag_status = "Klinisch auff\u00e4llig \u2013 Weiteres Monitoring"
                diag_color = "#FF0055"
                
            self.stats_labels["mean_left"].configure(text=f"{num_hotspots}")
            self.stats_labels["mean_right"].configure(text=f"{max_area:,} px")
            
            # Dynamische Einheitenumrechnung
            avg_temp_disp = self.to_temp_val(avg_temp) if num_hotspots > 0 else 0.0
            
            self.stats_labels["delta"].configure(
                text=f"{avg_temp_disp:.2f} {unit_str}" if num_hotspots > 0 else f"0.00 {unit_str}",
                text_color=diag_color if num_hotspots > 0 else COLOR_TEXT_PRIMARY
            )
            self.stats_labels["status_symmetry"].configure(text=diag_status, text_color=diag_color)



    def save_active_view(self) -> None:
        """Exportiert das aktuell angezeigte Bild des aktiven Tabs als PNG."""
        tab_name = self.tabview.get()
        
        if tab_name in ("Gesamtübersicht", "5. Temperatur-Verteilung", "6. Detail-Analyse"):
            messagebox.showwarning("Exportieren", "Bitte wählen Sie einen der Bild-Tabs (1–4) aus, um das Bild zu exportieren.")
            return
            
        if self.current_raw_original is None:
            messagebox.showwarning("Exportieren", "Keine Bilddaten zum Exportieren vorhanden.")
            return

        img_to_save = None
        
        if tab_name == "1. Originalbild":
            palette = self.palette_menu.get()
            if palette == "Regenbogen (Jet)":
                img_to_save = cv2.applyColorMap(self.current_raw_original, cv2.COLORMAP_JET)
            elif palette == "Inferno":
                img_to_save = cv2.applyColorMap(self.current_raw_original, cv2.COLORMAP_INFERNO)
            elif palette == "Heiß (Hot)":
                img_to_save = cv2.applyColorMap(self.current_raw_original, cv2.COLORMAP_HOT)
            else:
                img_to_save = self.current_raw_original
        elif tab_name == "2. Hintergrund-Maske":
            img_to_save = self.current_images.get("2. Hintergrund-Maske")
        elif tab_name == "3. Lokale Hitze-Differenz":
            img_to_save = self.current_images.get("3. Lokale Hitze-Differenz")
        elif tab_name == "4. Erkannte Hotspots":
            palette = self.palette_menu.get()
            body_mask_vis = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) * 255
            if self.analysis_mode_opt.get() == "Podologische Symmetrieanalyse":
                img_to_save = self.draw_foot_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)
            else:
                img_to_save = self.draw_general_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)

        if img_to_save is None:
            messagebox.showerror("Fehler", "Bild konnte nicht vorbereitet werden.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-Bild", "*.png"), ("JPEG-Bild", "*.jpg;*.jpeg")],
            initialfile=f"{tab_name.replace(' ', '_').replace('.', '')}.png"
        )
        
        if file_path:
            try:
                cv2.imwrite(file_path, img_to_save)
                messagebox.showinfo("Erfolg", "Bild erfolgreich exportiert!")
            except Exception as e:
                messagebox.showerror("Fehler", f"Bild konnte nicht gespeichert werden:\n{e}")

    def export_html_report(self) -> None:
        """Generiert einen detaillierten HTML-Analysebericht im Ausgabeordner."""
        if self.current_filepath is None or self.current_raw_original is None:
            messagebox.showwarning("Exportieren", "Bitte laden Sie zuerst ein Bild.")
            return

        try:
            base_name = os.path.splitext(os.path.basename(self.current_filepath))[0]
            report_filename = f"report_{base_name}.html"
            report_filepath = os.path.join(config.OUTPUT_DIR, report_filename)
            
            body_mask = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) if "2. Hintergrund-Maske" in self.current_images else None
            if body_mask is None or np.sum(body_mask) == 0:
                messagebox.showerror("Fehler", "Objektmaske nicht gefunden. Bericht kann nicht erstellt werden.")
                return
                
            pixels = self.current_raw_original[body_mask > 0]
            mean_val = np.mean(pixels)
            std_val = np.std(pixels)
            threshold = mean_val + self.sigma_k_slider.get() * std_val
            hotspot_count = int(self.current_raw_mask.sum()) // 255 if self.current_raw_mask is not None else 0
            
            # Symmetrie
            h_orig, w_orig = self.current_raw_original.shape[:2]
            mid_x = w_orig // 2
            
            left_mask = np.zeros_like(body_mask)
            left_mask[:, :mid_x] = body_mask[:, :mid_x]
            right_mask = np.zeros_like(body_mask)
            right_mask[:, mid_x:] = body_mask[:, mid_x:]
            
            left_pixels = self.current_raw_original[left_mask > 0]
            right_pixels = self.current_raw_original[right_mask > 0]
            
            mean_l, mean_r, delta = 0.0, 0.0, 0.0
            sym_status, sym_color = "Keine Messdaten vorhanden", "#94A3B8"
            
            if len(left_pixels) > 0 and len(right_pixels) > 0:
                mean_l = np.mean(left_pixels)
                mean_r = np.mean(right_pixels)
                delta = abs(mean_l - mean_r)
                if delta >= 15.0:
                    sym_status = "ASYMMETRIE DETEKTIERT (Entzündungsverdacht!)"
                    sym_color = "#FF0055"
                else:
                    sym_status = "NORMAL (Temperatursymmetrisch)"
                    sym_color = "#10B981"
            
            # Dateiname für Bericht festlegen (ohne Patientendaten)
            report_filename = f"report_{base_name}.html"
            report_filepath = os.path.join(config.OUTPUT_DIR, report_filename)

            backend_info = image_processing.get_active_backend()
            forced = self.backend_var.get()
            if forced != "auto":
                backend_info = f"{backend_info} (Erzwungen)"

            # Einheit bestimmen
            unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
            unit_str = "°C"
            if "Fahrenheit" in unit:
                unit_str = "°F"
            elif "Kelvin" in unit:
                unit_str = "K"

            # Werte berechnen in Ziel-Einheit
            mean_l_disp = self.to_temp_val(mean_l)
            mean_r_disp = self.to_temp_val(mean_r)
            mean_val_disp = self.to_temp_val(mean_val)
            threshold_disp = self.to_temp_val(threshold)
            delta_disp = self.to_delta_val(abs(mean_l - mean_r))
            std_disp = self.to_delta_val(std_val)

            # Zonal für Report umrechnen
            l_f = self.to_temp_val(self.zonal_stats.get("left", {}).get("fore", 0.0))
            r_f = self.to_temp_val(self.zonal_stats.get("right", {}).get("fore", 0.0))
            l_m = self.to_temp_val(self.zonal_stats.get("left", {}).get("mid", 0.0))
            r_m = self.to_temp_val(self.zonal_stats.get("right", {}).get("mid", 0.0))
            l_h = self.to_temp_val(self.zonal_stats.get("left", {}).get("heel", 0.0))
            r_h = self.to_temp_val(self.zonal_stats.get("right", {}).get("heel", 0.0))

            df_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("fore", 0.0) - self.zonal_stats.get("right", {}).get("fore", 0.0)))
            dm_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("mid", 0.0) - self.zonal_stats.get("right", {}).get("mid", 0.0)))
            dh_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("heel", 0.0) - self.zonal_stats.get("right", {}).get("heel", 0.0)))

            # HTML generieren
            self._write_individual_html_report(
                report_filepath, base_name, os.path.basename(self.current_filepath), mean_val_disp, std_disp,
                threshold_disp, hotspot_count, len(pixels), mean_l_disp, mean_r_disp, delta_disp, sym_status, sym_color,
                l_f, r_f, l_m, r_m, l_h, r_h, df_disp, dm_disp, dh_disp,
                "n.a.", "n.a.", "n.a.", "n.a.", backend_info, self.analysis_mode_opt.get(),
                p_icd="—", operator="Jugend forscht",
                t_min_c=self.t_min_celsius, t_max_c=self.t_max_celsius, unit_str=unit_str
            )
            
            messagebox.showinfo("Export erfolgreich", f"Der HTML-Bericht wurde erfolgreich gespeichert:\n{report_filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Bericht konnte nicht exportiert werden:\n{e}")

    def _write_individual_html_report(
        self, filepath, base_name, filename, mean, std, thresh, hotspots, foot_pixels,
        mean_l, mean_r, delta, sym_status, sym_color,
        lf, rf, lm, rm, lh, rh, df, dm, dh,
        p_name="Unbekannt", p_age="Unbekannt", p_diab="Nicht angegeben", p_notes="Keine",
        backend_info="auto", analysis_mode="Klinische Allgemeinanalyse",
        p_icd="—", operator="Nicht angegeben", t_min_c=20.0, t_max_c=40.0, unit_str="°C"
    ):
        """Hilfsfunktion zum Schreiben einer detailreichen HTML-Berichtsdatei."""
        def get_badge_style(color_hex):
            color_hex = color_hex.upper()
            if "10B981" in color_hex or "GREEN" in color_hex:
                return "background-color: rgba(16, 185, 129, 0.1); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.2);"
            elif "FFA500" in color_hex or "F59E0B" in color_hex or "ORANGE" in color_hex:
                return "background-color: rgba(245, 158, 11, 0.1); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.2);"
            else:
                return "background-color: rgba(239, 68, 68, 0.1); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.2);"

        gdpr_badge = ""
        if p_name.startswith("ANON-"):
            gdpr_badge = """
            <div class="meta-item">
                <div class="meta-label">Datenschutz-Status</div>
                <div class="meta-value">
                    <span class="status-badge" style="background-color: rgba(16, 185, 129, 0.1); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.2);">DSGVO-konform pseudonymisiert</span>
                </div>
            </div>"""

        if analysis_mode == "Podologische Symmetrieanalyse":
            h1_title = "IGNITE Medical Imaging Suite – Podologisches Thermografiebefund"
            mean_title = "Mittl. Temperatur Fußoberfläche"
            diabetes_html = f"""
            <div class="meta-item">
                <div class="meta-label">Diabetes-Klassifizierung</div>
                <div class="meta-value">{p_diab}</div>
            </div>"""
            hotspots_percentage_label = f"{hotspots} Pixel ({(hotspots / foot_pixels) * 100 if foot_pixels > 0 else 0:.3f} %)"
            symmetry_or_hotspots_meta = f"""
            <div class="meta-item">
                <div class="meta-label">Symmetrie-Delta (Δ)</div>
                <div class="meta-value" style="color: #EF4444; font-weight: bold;">{delta:.2f} {unit_str}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Klinischer Symmetriestatus</div>
                <div class="meta-value">
                    <span class="status-badge" style="{get_badge_style(sym_color)}">{sym_status}</span>
                </div>
            </div>"""
            
            vf_color = '#FF0055' if df>=15 else ('#FFA500' if df>=10 else '#10B981')
            vf_text = 'Auffällig (Inflammationsverdacht)' if df>=15 else ('Grenzwertig' if df>=10 else 'Normal')
            
            mf_color = '#FF0055' if dm>=15 else ('#FFA500' if dm>=10 else '#10B981')
            mf_text = 'Auffällig (Inflammationsverdacht)' if dm>=15 else ('Grenzwertig' if dm>=10 else 'Normal')
            
            f_color = '#FF0055' if dh>=15 else ('#FFA500' if dh>=10 else '#10B981')
            f_text = 'Auffällig (Inflammationsverdacht)' if dh>=15 else ('Grenzwertig' if dh>=10 else 'Normal')

            table_html = f"""
            <h2>3-Zonen-Symmetrie-Analyse (Links vs. Rechts)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Anatomische Zone</th>
                        <th>Links (L) ({unit_str})</th>
                        <th>Rechts (R) ({unit_str})</th>
                        <th>Differenz (Δ) ({unit_str})</th>
                        <th>Zonale Diagnose</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><b>Vorfuß (Zehen / Ballen)</b></td>
                        <td>{lf:.2f}</td>
                        <td>{rf:.2f}</td>
                        <td>{df:.2f}</td>
                        <td><span class="status-badge" style="{get_badge_style(vf_color)}">{vf_text}</span></td>
                    </tr>
                    <tr>
                        <td><b>Mittelfuß (Gewölbe)</b></td>
                        <td>{lm:.2f}</td>
                        <td>{rm:.2f}</td>
                        <td>{dm:.2f}</td>
                        <td><span class="status-badge" style="{get_badge_style(mf_color)}">{mf_text}</span></td>
                    </tr>
                    <tr>
                        <td><b>Ferse (Rückfuß)</b></td>
                        <td>{lh:.2f}</td>
                        <td>{rh:.2f}</td>
                        <td>{dh:.2f}</td>
                        <td><span class="status-badge" style="{get_badge_style(f_color)}">{f_text}</span></td>
                    </tr>
                </tbody>
            </table>"""
            overlay_caption = "4. Erkannte Hotspots (Overlay mit BBoxes & Zonen)"
        else:
            h1_title = "IGNITE // Medizinisches Entzündungsprotokoll (Allgemein)"
            mean_title = "Mittelwert Objekthitze (µ)"
            diabetes_html = ""
            hotspots_percentage_label = f"{hotspots} Pixel"
            
            general_hs = getattr(self, "general_hotspots", [])
            num_hotspots = len(general_hs)
            avg_temp = np.mean([hs["mean_temp"] for hs in general_hs]) if num_hotspots > 0 else 0.0
            avg_temp_disp = self.to_temp_val(avg_temp) if num_hotspots > 0 else 0.0
            
            if hotspots == 0:
                diag_status = "Unauff\u00e4llig \u2013 Kein Befund"
                diag_color = "#10B981"
            elif hotspots < 150:
                diag_status = "Grenzwertig \u2013 Verlaufsbeobachtung"
                diag_color = "#FFA500"
            else:
                diag_status = "Klinisch auff\u00e4llig \u2013 Weiteres Monitoring"
                diag_color = "#FF0055"
                
            symmetry_or_hotspots_meta = f"""
            <div class="meta-item">
                <div class="meta-label">Anzahl Hotspots</div>
                <div class="meta-value" style="font-weight: bold; color: #EF4444;">{num_hotspots}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Durchschnittliche Hotspot-Hitze</div>
                <div class="meta-value" style="font-weight: bold; color: #EF4444;">{avg_temp_disp:.2f} {unit_str}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Globaler Befund</div>
                <div class="meta-value">
                    <span class="status-badge" style="{get_badge_style(diag_color)}">{diag_status}</span>
                </div>
            </div>"""
            
            hotspots_rows = ""
            if general_hs:
                for hs in general_hs:
                    area = hs["area"]
                    mean_temp = hs["mean_temp"]
                    max_temp = hs["max_temp"]
                    
                    mean_temp_disp = self.to_temp_val(mean_temp)
                    max_temp_disp = self.to_temp_val(max_temp)
                    
                    if area >= 150 or mean_temp >= 180:
                        diag_text = "Klinisch relevant \u2013 Abkl\u00e4rung empfohlen"
                        diag_color = "#FF0055"
                    elif area >= 50 or mean_temp >= 140:
                        diag_text = "Grenzwertig \u2013 Verlaufsbeobachtung"
                        diag_color = "#FFA500"
                    else:
                        diag_text = "Geringfügig (Unbedenklich)"
                        diag_color = "#10B981"
                        
                    hotspots_rows += f"""
                    <tr>
                        <td><b>H#{hs['index']}</b></td>
                        <td>{area:,} px</td>
                        <td>{mean_temp_disp:.2f}</td>
                        <td>{max_temp_disp:.2f}</td>
                        <td><span class="status-badge" style="{get_badge_style(diag_color)}">{diag_text}</span></td>
                    </tr>"""
            else:
                hotspots_rows = """
                <tr>
                    <td colspan="5" style="text-align: center; color: #71717A; font-style: italic;">Keine Hotspots im Bild detektiert.</td>
                </tr>"""
                
            table_html = f"""
            <h2>Hotspot-Detektions-Details</h2>
            <table>
                <thead>
                    <tr>
                        <th>Hotspot ID</th>
                        <th>Fläche (Pixel)</th>
                        <th>Mittelwert Hitze ({unit_str})</th>
                        <th>Maximalwert Hitze ({unit_str})</th>
                        <th>Klinischer Befund</th>
                    </tr>
                </thead>
                <tbody>
                    {hotspots_rows}
                </tbody>
            </table>"""
            overlay_caption = "4. Erkannte Hotspots (Overlay mit nummerierten BBoxes)"

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE - Analysebericht ({base_name})</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #09090B;
            color: #FAF5FF;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: #18181B;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
            border: 1px solid #27272A;
        }}
        h1 {{
            color: #FAF5FF;
            margin-top: 0;
            border-bottom: 1px solid #27272A;
            padding-bottom: 20px;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.025em;
        }}
        h2 {{
            color: #EF4444;
            margin-top: 40px;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid #27272A;
            padding-bottom: 10px;
        }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
            background-color: #09090B;
            padding: 24px;
            border-radius: 8px;
            border: 1px solid #27272A;
        }}
        .meta-item {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .meta-label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #71717A;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}
        .meta-value {{
            font-size: 14px;
            color: #F4F4F5;
        }}
        .image-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: #09090B;
            border-radius: 8px;
            padding: 16px;
            border: 1px solid #27272A;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .card h3 {{
            color: #FAF5FF;
            margin: 0;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .card img {{
            max-width: 100%;
            border-radius: 6px;
            border: 1px solid #27272A;
            background-color: #09090B;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: #09090B;
            border-radius: 8px;
            border: 1px solid #27272A;
            overflow: hidden;
        }}
        th, td {{
            padding: 14px 18px;
            text-align: left;
            font-size: 13px;
        }}
        th {{
            background-color: #18181B;
            color: #EF4444;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid #27272A;
        }}
        td {{
            color: #FAF5FF;
            border-bottom: 1px solid #27272A;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.025em;
        }}
        .report-link {{
            color: #EF4444;
            text-decoration: none;
            font-weight: 600;
        }}
        .report-link:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 60px;
            text-align: center;
            font-size: 11px;
            color: #52525B;
            border-top: 1px solid #27272A;
            padding-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{h1_title}</h1>

        <h2>Diagnostische Parameter &amp; Globale Statistik</h2>
        <div class="metadata-grid">
            <div class="meta-item">
                <div class="meta-label">Analysierte Bilddatei</div>
                <div class="meta-value">{filename}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Berechnungs-Backend</div>
                <div class="meta-value">{backend_info}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Kamerakalibrierung</div>
                <div class="meta-value">{self.convert_celsius_to_unit(t_min_c):.1f} {unit_str} – {self.convert_celsius_to_unit(t_max_c):.1f} {unit_str}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">{mean_title} ({unit_str})</div>
                <div class="meta-value">{mean:.2f} {unit_str}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Standardabweichung (σ)</div>
                <div class="meta-value">{std:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Hotspot-Detektionsgrenze</div>
                <div class="meta-value">{thresh:.2f} {unit_str} (µ + k*σ)</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Erkannte Hotspots</div>
                <div class="meta-value">
                    <span class="status-badge" style="{get_badge_style(sym_color)}">{hotspots_percentage_label}</span>
                </div>
            </div>
            {symmetry_or_hotspots_meta}
        </div>

        {table_html}

        <h2>Visualisierung der Verarbeitungsschritte</h2>
        <div class="image-grid">
            <div class="card">
                <h3>1. Originalbild (Kalibriert)</h3>
                <img src="steps/{base_name}_step1_original.png" alt="Originalbild">
            </div>
            <div class="card">
                <h3>2. Hintergrund-Maske (Segmentierung)</h3>
                <img src="steps/{base_name}_step2_mask.png" alt="Hintergrund-Maske">
            </div>
            <div class="card">
                <h3>3. Lokale Hitze-Differenz (Top-Hat)</h3>
                <img src="steps/{base_name}_step3_local_heat_diff.png" alt="Lokale Hitze-Differenz">
            </div>
            <div class="card">
                <h3>{overlay_caption}</h3>
                <img src="steps/{base_name}_step4_dynamic_hotspots.png" alt="Erkannte Hotspots">
            </div>
        </div>

        <div style="margin-top: 16px; padding: 12px; background: rgba(239,68,68,0.05); border: 1px solid rgba(239,68,68,0.15); border-radius: 6px;">
            <p style="color: #71717A; font-size: 11px; margin: 0; line-height: 1.6;">
                <strong style="color: #EF4444;">Hinweis:</strong>
                Dieser automatisch generierte Analysebericht dient ausschließlich der wissenschaftlichen Forschung und Dokumentation im Rahmen von Jugend forscht.
            </p>
        </div>

        <div class="footer">
            <strong>IGNITE Medical Imaging Suite v{APP_VERSION}</strong> &nbsp;&middot;&nbsp; Entwickelt von Jona Noack &nbsp;&middot;&nbsp; Jugend forscht 2026<br>
            Automatisch generierter Analysebericht &nbsp;&middot;&nbsp; Erstellt: {__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
            <br><br>
            <em>Rechtlicher Hinweis: Dieser Bericht wurde von einer nicht-zertifizierten Forschungssoftware erstellt und ist kein zugelassenes Medizinprodukt.<br>
            Er ersetzt keine qualifizierte ärztliche Untersuchung oder Diagnose. Alle Ergebnisse sind rein wissenschaftlich-analytischer Natur.</em>
        </div>
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _write_batch_summary_html(self, filepath, patients_processed, analysis_mode="Klinische Allgemeinanalyse"):
        """Schreibt das HTML Dashboard für die Stapelverarbeitung."""
        total = len(patients_processed)
        critical = sum(1 for p in patients_processed if "KRITISCH" in p["status"])
        warn = sum(1 for p in patients_processed if "BEOBACHTUNG" in p["status"])
        normal = total - critical - warn

        def get_badge_style(color_hex):
            color_hex = color_hex.upper()
            if "10B981" in color_hex or "GREEN" in color_hex:
                return "background-color: rgba(16, 185, 129, 0.1); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.2);"
            elif "FFA500" in color_hex or "F59E0B" in color_hex or "ORANGE" in color_hex:
                return "background-color: rgba(245, 158, 11, 0.1); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.2);"
            else:
                return "background-color: rgba(239, 68, 68, 0.1); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.2);"

        rows_html = ""
        for p in patients_processed:
            if analysis_mode == "Podologische Symmetrieanalyse":
                delta_col = f"{p['delta']:.2f}"
                zonal_col = f"{p['max_zonal_delta']:.2f}"
            else:
                delta_col = f"{int(p['delta'])}"
                zonal_col = f"{int(p['max_zonal_delta']):,} px"

            rows_html += f"""
            <tr>
                <td><b>{p['filename']}</b></td>
                <td>{p['hotspots']} px</td>
                <td>{delta_col}</td>
                <td>{zonal_col}</td>
                <td><span class="status-badge" style="{get_badge_style(p['color'])}">{p['status']}</span></td>
                <td><a class="report-link" href="{p['report']}" target="_blank">Bericht öffnen &#x2197;</a></td>
            </tr>"""

        if analysis_mode == "Podologische Symmetrieanalyse":
            th_delta = "Globales Delta (Δ)"
            th_zonal = "Max. Zonal-Delta"
        else:
            th_delta = "Anzahl Hotspots"
            th_zonal = "Größte Hotspot-Fläche"

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE - Stapelverarbeitungs-Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #09090B;
            color: #FAF5FF;
            margin: 0;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #18181B;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
            border: 1px solid #27272A;
        }}
        h1 {{
            color: #FAF5FF;
            margin-top: 0;
            border-bottom: 1px solid #27272A;
            padding-bottom: 20px;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.025em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background-color: #09090B;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            border: 1px solid #27272A;
        }}
        .stat-label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #71717A;
            margin-bottom: 8px;
            font-weight: 600;
            letter-spacing: 0.05em;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.025em;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #09090B;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #27272A;
            margin-top: 20px;
        }}
        th, td {{
            padding: 14px 18px;
            text-align: left;
            font-size: 13px;
        }}
        th {{
            background-color: #18181B;
            color: #EF4444;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid #27272A;
        }}
        td {{
            color: #FAF5FF;
            border-bottom: 1px solid #27272A;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.025em;
        }}
        .report-link {{
            color: #EF4444;
            text-decoration: none;
            font-weight: 600;
        }}
        .report-link:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 60px;
            text-align: center;
            font-size: 11px;
            color: #52525B;
            border-top: 1px solid #27272A;
            padding-top: 24px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IGNITE // Stapelverarbeitungs-Übersicht</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Gesamt Verarbeitet</div>
                <div class="stat-value" style="color: #EF4444;">{total}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Entzündung (Kritisch)</div>
                <div class="stat-value" style="color: #EF4444;">{critical}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Beobachtung (Verdacht)</div>
                <div class="stat-value" style="color: #F59E0B;">{warn}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Gesunde Befunde</div>
                <div class="stat-value" style="color: #10B981;">{normal}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Wärmebild-Datei</th>
                    <th>Hotspots (Fläche)</th>
                    <th>{th_delta}</th>
                    <th>{th_zonal}</th>
                    <th>Klinischer Befund</th>
                    <th>Detaillierter Bericht</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
 
        <div class="footer">
            IGNITE // Jugend forscht 2026 - Diagnostische Reihenuntersuchung
        </div>
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)


    def run_batch_processing(self) -> None:
        """Führt eine Stapelverarbeitung für einen ganzen Ordner an Wärmebildern aus."""
        src_dir = filedialog.askdirectory(title="Quellordner für Stapelverarbeitung wählen")
        if not src_dir:
            return
            
        dest_dir = filedialog.askdirectory(title="Ausgabeordner für Berichte wählen")
        if not dest_dir:
            return

        valid_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif")
        image_files = [f for f in os.listdir(src_dir) if f.lower().endswith(valid_exts)]
        
        if not image_files:
            messagebox.showinfo("Keine Bilder", "Keine gültigen Bilddateien im Quellordner gefunden.")
            return

        progress_win = ctk.CTkToplevel(self.root)
        progress_win.title("Stapelverarbeitung läuft")
        progress_win.geometry("400x180")
        progress_win.resizable(False, False)
        progress_win.configure(fg_color="#09090B")
        progress_win.transient(self.root)
        
        lbl_title = ctk.CTkLabel(progress_win, text="Stapelverarbeitung läuft...", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_PRIMARY_ACCENT)
        lbl_title.pack(pady=(20, 10))
        
        lbl_status = ctk.CTkLabel(progress_win, text="Initialisiere...", text_color="#F4F4F5")
        lbl_status.pack(pady=5)
        
        pbar = ctk.CTkProgressBar(progress_win, width=300, fg_color="#18181B", progress_color=COLOR_PRIMARY_ACCENT)
        pbar.set(0.0)
        pbar.pack(pady=10)
        
        self.root.update()

        # Parameter abrufen
        sk = self.sigma_k_slider.get()
        th = self.tophat_slider.get()
        ma = self.min_area_slider.get()
        mc = self.min_circ_slider.get()
        omin = int(self.otsu_min_slider.get())
        omax = int(self.otsu_max_slider.get())
        er = self.erosion_slider.get()
        to = self.temp_offset_slider.get()
        t_max_celsius = self.t_max_celsius
        t_min_celsius = self.t_min_celsius
        analysis_mode = self.analysis_mode_opt.get()

        def worker():
            patients_processed = []

            for idx, filename in enumerate(image_files):
                def update_ui(i=idx, f=filename):
                    pbar.set((i + 1) / len(image_files))
                    lbl_status.configure(text=f"Verarbeite: {f} ({i+1}/{len(image_files)})")
                
                self.root.after(0, update_ui)
                
                filepath = os.path.join(src_dir, filename)
                
                try:
                    img = image_processing.load_thermal_image(filepath)
                    
                    range_c = t_max_celsius - t_min_celsius
                    if range_c <= 0:
                        range_c = 20.0
                    raw_offset = int(round(to * 255.0 / range_c))
                    
                    calibrated_img = np.clip(img.astype(np.int16) + raw_offset, 0, 255).astype(np.uint8)
                    
                    diff_img, hotspot_mask = image_processing.run_rust_pipeline(
                        calibrated_img, sk, th, ma, mc, omin, omax, er, use_mad=self.mad_switch.get() == 1
                    )
                    
                    body_mask_vis = (diff_img > 0).astype(np.uint8) * 255
                    hotspot_count = int(hotspot_mask.sum()) // 255
                    
                    steps_dir = os.path.join(dest_dir, "steps")
                    os.makedirs(steps_dir, exist_ok=True)
                    
                    base_name = os.path.splitext(filename)[0]
                    
                    cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step1_original.png"), calibrated_img)
                    cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step2_mask.png"), body_mask_vis)
                    cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step3_local_heat_diff.png"), diff_img)
                    
                    # Overlay erzeugen & speichern
                    if analysis_mode == "Podologische Symmetrieanalyse":
                        overlay_img = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                    else:
                        overlay_img = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                    cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step4_dynamic_hotspots.png"), overlay_img)
                    
                    body_mask = body_mask_vis > 0
                    pixels = calibrated_img[body_mask]
                    mean_val = np.mean(pixels) if len(pixels) > 0 else 0.0
                    
                    if analysis_mode == "Podologische Symmetrieanalyse":
                        # Left vs Right
                        h_orig, w_orig = calibrated_img.shape[:2]
                        mid_x = w_orig // 2
                        
                        left_mask = np.zeros_like(body_mask)
                        left_mask[:, :mid_x] = body_mask[:, :mid_x]
                        right_mask = np.zeros_like(body_mask)
                        right_mask[:, mid_x:] = body_mask[:, mid_x:]
                        
                        left_pixels = calibrated_img[left_mask > 0]
                        right_pixels = calibrated_img[right_mask > 0]
                        
                        mean_l = np.mean(left_pixels) if len(left_pixels) > 0 else 0.0
                        mean_r = np.mean(right_pixels) if len(right_pixels) > 0 else 0.0
                        delta = abs(mean_l - mean_r)
                        
                        # Zonal Analyse
                        # Left
                        left_y, left_x = np.where(body_mask[:, :mid_x] > 0)
                        l_fore_m, l_mid_m, l_heel_m = 0.0, 0.0, 0.0
                        if len(left_y) > 0:
                            l_min_y, l_max_y = left_y.min(), left_y.max()
                            l_hz = (l_max_y - l_min_y) // 3
                            l_f_m = np.zeros_like(body_mask)
                            l_f_m[l_min_y:l_min_y+l_hz, :mid_x] = body_mask[l_min_y:l_min_y+l_hz, :mid_x]
                            l_m_m = np.zeros_like(body_mask)
                            l_m_m[l_min_y+l_hz:l_min_y+2*l_hz, :mid_x] = body_mask[l_min_y+l_hz:l_min_y+2*l_hz, :mid_x]
                            l_h_m = np.zeros_like(body_mask)
                            l_h_m[l_min_y+2*l_hz:l_max_y, :mid_x] = body_mask[l_min_y+2*l_hz:l_max_y, :mid_x]
                            
                            l_fore_m = np.mean(calibrated_img[l_f_m > 0]) if np.sum(l_f_m) > 0 else 0.0
                            l_mid_m = np.mean(calibrated_img[l_m_m > 0]) if np.sum(l_m_m) > 0 else 0.0
                            l_heel_m = np.mean(calibrated_img[l_h_m > 0]) if np.sum(l_h_m) > 0 else 0.0
                            
                        # Right
                        right_y, right_x = np.where(body_mask[:, mid_x:] > 0)
                        r_fore_m, r_mid_m, r_heel_m = 0.0, 0.0, 0.0
                        if len(right_y) > 0:
                            r_min_y, r_max_y = right_y.min(), right_y.max()
                            r_hz = (r_max_y - r_min_y) // 3
                            r_f_m = np.zeros_like(body_mask)
                            r_f_m[r_min_y:r_min_y+r_hz, mid_x:] = body_mask[r_min_y:r_min_y+r_hz, mid_x:]
                            r_m_m = np.zeros_like(body_mask)
                            r_m_m[r_min_y+r_hz:r_min_y+2*r_hz, mid_x:] = body_mask[r_min_y+r_hz:r_min_y+2*r_hz, mid_x:]
                            r_h_m = np.zeros_like(body_mask)
                            r_h_m[r_min_y+2*r_hz:r_max_y, mid_x:] = body_mask[r_min_y+2*r_hz:r_max_y, mid_x:]
                            
                            r_fore_m = np.mean(calibrated_img[r_f_m > 0]) if np.sum(r_f_m) > 0 else 0.0
                            r_mid_m = np.mean(calibrated_img[r_m_m > 0]) if np.sum(r_m_m) > 0 else 0.0
                            r_heel_m = np.mean(calibrated_img[r_h_m > 0]) if np.sum(r_h_m) > 0 else 0.0

                        d_fore = abs(l_fore_m - r_fore_m)
                        d_mid = abs(l_mid_m - r_mid_m)
                        d_heel = abs(l_heel_m - r_heel_m)
                        
                        max_zonal_delta = max(d_fore, d_mid, d_heel)
                        if delta >= 15.0 or hotspot_count >= 150 or max_zonal_delta >= 15.0:
                            status_text = "Klinisch auffällig \u2013 Weiteres Monitoring"
                            status_color = "#FF0055"
                        elif delta >= 10.0 or hotspot_count > 0 or max_zonal_delta >= 10.0:
                            status_text = "Grenzwertig \u2013 Verlaufsbeobachtung"
                            status_color = "#FFA500"
                        else:
                            status_text = "Symmetrisch \u2013 Unauffällig"
                            status_color = "#10B981"
                    else:
                        # General mode calculations
                        mean_l, mean_r = 0.0, 0.0
                        l_fore_m, r_fore_m, l_mid_m, r_mid_m, l_heel_m, r_heel_m = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
                        d_fore, d_mid, d_heel = 0.0, 0.0, 0.0
                        
                        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(hotspot_mask)
                        num_hotspots = max(0, num_labels - 1)
                        max_area = 0
                        for i in range(1, num_labels):
                            max_area = max(max_area, stats[i, cv2.CC_STAT_AREA])
                            
                        delta = float(num_hotspots)
                        max_zonal_delta = float(max_area)

                        if hotspot_count >= 150:
                            status_text = "Klinisch auffällig \u2013 Weiteres Monitoring"
                            status_color = "#FF0055"
                        elif hotspot_count > 0:
                            status_text = "Grenzwertig \u2013 Verlaufsbeobachtung"
                            status_color = "#FFA500"
                        else:
                            status_text = "Unauffällig \u2013 Kein Befund"
                            status_color = "#10B981"
                            
                    patient_report_filename = f"report_{base_name}.html"
                    patient_report_path = os.path.join(dest_dir, patient_report_filename)
                    
                    self._write_individual_html_report(
                        patient_report_path, base_name, filename, mean_val, np.std(pixels) if len(pixels)>0 else 0.0,
                        mean_val + sk * np.std(pixels) if len(pixels)>0 else 0.0, hotspot_count, len(pixels),
                        mean_l, mean_r, delta, status_text, status_color, l_fore_m, r_fore_m, l_mid_m, r_mid_m, l_heel_m, r_heel_m,
                        d_fore, d_mid, d_heel, p_name="Patient_"+base_name, backend_info=image_processing.get_active_backend(),
                        analysis_mode=analysis_mode
                    )
                    
                    patients_processed.append({
                        "filename": filename,
                        "base_name": base_name,
                        "hotspots": hotspot_count,
                        "delta": delta,
                        "max_zonal_delta": max_zonal_delta,
                        "status": status_text,
                        "color": status_color,
                        "report": patient_report_filename
                    })
                    
                except Exception as e:
                    print(f"Error processing {filename}: {e}")

            summary_path = os.path.join(dest_dir, "batch_report.html")
            self._write_batch_summary_html(summary_path, patients_processed, analysis_mode)

            def on_done():
                progress_win.destroy()
                try:
                    os.startfile(os.path.abspath(dest_dir))
                except Exception as e:
                    logging.debug(f"Fehler ignoriert: {e}")
                messagebox.showinfo(
                    "Stapelverarbeitung beendet",
                    f"Erfolgreich {len(patients_processed)} Wärmebilder verarbeitet!\n\n"
                    f"Zentraler Ergebnisbericht: batch_report.html"
                )

            self.root.after(0, on_done)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def show_info_window(self) -> None:
        """Öffnet ein Informations-Fenster über die Funktionsweise des Systems."""
        if hasattr(self, "info_win") and self.info_win.winfo_exists():
            self.info_win.focus()
            return

        self.info_win = ctk.CTkToplevel(self.root)
        self.info_win.title("Über IGNITE & Funktionsweise")
        self.info_win.geometry("620x540")
        self.info_win.minsize(550, 420)
        self.info_win.configure(fg_color="#09090B")
        
        self.info_win.transient(self.root)
        self.info_win.after(100, lambda: self.info_win.focus_force())
        
        title_lbl = ctk.CTkLabel(
            self.info_win,
            text="IGNITE – Entzündungsdetektion",
            font=ctk.CTkFont(family="Arial", size=20, weight="bold"),
            text_color=COLOR_PRIMARY_ACCENT
        )
        title_lbl.pack(pady=(20, 10))
        
        txt = ctk.CTkTextbox(
            self.info_win,
            fg_color="#18181B",
            text_color="#F4F4F5",
            font=ctk.CTkFont(family="Arial", size=13),
            wrap="word"
        )
        txt.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        info_text = (
            "IGNITE ist eine Software zur automatisierten Entzündungsdetektion (Hotspot-Erkennung) "
            "in thermografischen Aufnahmen zur Früherkennung lokaler Entzündungsherde.\n\n"
            "Die Anwendung bietet zwei verschiedene Analysemodi:\n"
            "- Allgemeine Analyse: Erkennt und visualisiert beliebige lokale Entzündungsherde am Körper "
            "(z. B. Hände, Gelenke, Rücken). Die erkannten Hotspots werden markiert und vermessen.\n"
            "- Podologische Symmetrieanalyse: Spezifischer klinischer Symmetrievergleich beider Füße (3-Zonen-Modell) "
            "zur Früherkennung des Diabetischen Fußsyndroms.\n\n"
            "Die mathematische Pipeline besteht aus 5 Stufen:\n\n"
            "1. Dynamische Kernel:\n"
            "Berechnet ungerade Strukturierungselemente basierend auf der Bildbreite (Standard: tophat_factor % für Top-Hat, 2 % für Geometriefilter).\n\n"
            "2. Adaptive Body-Mask:\n"
            "Otsu-Binarisierung mit Sicherheits-Schwellenwert-Eingrenzung auf den Bereich [otsu_min, otsu_max], um auch kältere Extremitäten zuverlässig zu erfassen. Es folgt eine euklidische Distanztransformation (Chamfer-3-4-Metrik) und eine adaptive Erosion zur Rauschüberwindung.\n\n"
            "3. Top-Hat-Transformation:\n"
            "Führt ein morphologisches Opening durch und subtrahiert dieses vom Originalbild, um lokale Helligkeitsspitzen (Hitze) präzise zu isolieren.\n\n"
            "4. Statistischer Schwellenwert (µ + k*σ + Absoluthitze-Filter):\n"
            "Berechnet Mittelwert µ und Standardabweichung σ der Top-Hat-Differenz exklusiv über Körper-Pixel. Filtert mit einem Schwellenwert von µ + k*σ und verlangt zusätzlich, dass die absolute Helligkeit über der durchschnittlichen Temperatur liegt. Dies eliminiert Falsch-Positive vollständig.\n\n"
            "5. Geometrischer Rauschfilter:\n"
            "Connected-Component-Analyse. Filtert Komponenten nach Mindestfläche und Circularity zur Entfernung von Punktrauschen.\n\n"
            "Backend-System:\n"
            "- GPU-Pfad: PyTorch CUDA (< 10 ms)\n"
            "- CPU-Pfad: Rust-native Multi-threading via Rayon (~30 ms)\n"
            "- Fallback-Pfad: OpenCV Python (~80 ms)"
        )
        txt.insert("0.0", info_text)
        txt.configure(state="disabled")

    def show_about_window(self) -> None:
        """Zeigt einen professionellen Info-Dialog über das Produkt."""
        about_win = ctk.CTkToplevel(self.root)
        about_win.title("IGNITE Medical Imaging Suite – Über diese Software")
        about_win.geometry("480x360")
        about_win.resizable(False, False)
        about_win.configure(fg_color="#09090B")
        about_win.transient(self.root)
        about_win.after(100, lambda: about_win.focus_force())

        # Logo
        icon_png_path = get_resource_path(os.path.join("icon", "LogoRund.png"))
        if os.path.exists(icon_png_path):
            try:
                logo_img = Image.open(icon_png_path)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(56, 56))
                logo_lbl = ctk.CTkLabel(about_win, image=logo_ctk, text="")
                logo_lbl.pack(pady=(28, 6))
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        ctk.CTkLabel(
            about_win,
            text="IGNITE Medical Imaging Suite",
            font=ctk.CTkFont(family="Arial", size=18, weight="bold"),
            text_color="#FAF5FF"
        ).pack(pady=(4, 2))

        ctk.CTkLabel(
            about_win,
            text=f"Version {APP_VERSION}  ·  Thermografische Entzündungsdetektion",
            font=ctk.CTkFont(family="Arial", size=11),
            text_color="#71717A"
        ).pack(pady=(0, 16))

        sep = ctk.CTkFrame(about_win, fg_color="#27272A", height=1)
        sep.pack(fill=ctk.X, padx=30, pady=(0, 16))

        ctk.CTkLabel(
            about_win,
            text=(
                "Entwickelt von Jona Noack im Rahmen von Jugend forscht 2026.\n"
                "Hybrides Hochleistungssystem: Python · Rust (Rayon) · PyTorch CUDA"
            ),
            font=ctk.CTkFont(family="Arial", size=12),
            text_color="#A1A1AA",
            justify="center",
            wraplength=400
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            about_win,
            text="HINWEIS: Dieses System ist kein zugelassenes Medizinprodukt.\nAlle Analysen dienen ausschließlich der wissenschaftlichen Forschung.\nKein Ersatz für qualifizierte ärztliche Diagnose.",
            font=ctk.CTkFont(family="Arial", size=10),
            text_color="#52525B",
            justify="center",
            wraplength=420
        ).pack(pady=(0, 20))

        ctk.CTkButton(
            about_win,
            text="Schließen",
            command=about_win.destroy,
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color="#09090B",
            height=34,
            width=120,
            corner_radius=6
        ).pack()
