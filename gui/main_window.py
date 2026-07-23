# -*- coding: utf-8 -*-
"""gui/main_window.py – CustomTkinter Frontend Coordinator for IGNITE Suite.

Dieses Modul stellt das Hauptfenster bereit und koordiniert die Untermodule
(gui.components, gui.widgets, gui.views, gui.services).
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

# Matplotlib Integration
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
from gui.components.header import TitleBarComponent

from gui.widgets.cards import (
    AnalysisModeCard,
    RoiCard,
    SystemSettingsCard,
    PipelineParametersCard,
    AnalysisInfoCard
)
from gui.views.dashboard import DashboardView
from gui.views.analysis import AnalysisView
from gui.views.dialogs import (
    FullscreenImageModal,
    InstructionsModal,
    AboutModal
)

from utils import pixel_to_celsius, pseudonymize_patient, get_resource_path
from audit_log import write_audit_entry

APP_VERSION = "1.0.0"


class IgniteApp:
    """Haupt-Anwendungsklasse für das IGNITE Thermografie-Analyse-System v1.0."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.overrideredirect(True)
        self.root.title(f"IGNITE Medical Imaging Suite v{APP_VERSION} – Thermografische Analyse")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 780)
        self.root.configure(fg_color=COLOR_BG_MAIN)

        icon_path = get_resource_path(os.path.join("icon", "LogoRund.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logging.debug(f"Fehler ignoriert: {e}")

        config.init_output_dir()

        # State-Variablen
        self.current_filepath: str | None = None
        self.panels: dict[str, ctk.CTkLabel] = {}
        self.panels_full: dict[str, ctk.CTkLabel] = {}

        self.current_raw_original: np.ndarray | None = None
        self.current_raw_mask: np.ndarray | None = None
        self.current_images: dict[str, np.ndarray] = {}
        self.zonal_stats: dict = {}
        self.general_hotspots: list = []

        self.t_min_celsius: float = config.DEFAULT_TEMP_MIN
        self.t_max_celsius: float = config.DEFAULT_TEMP_MAX
        self.dsgvo_anonymize: bool = False
        self.emissivity: float = 0.98

        self.resize_job: str | None = None
        self._PIL_CACHE_MAXSIZE = 20
        self.pil_cache: OrderedDict[str, Image.Image] = OrderedDict()

        # ROI State
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

        # ── 1. CUSTOM TITLEBAR HEADER COMPONENT ──────────────────────────────
        self.title_bar_component = TitleBarComponent(self.root)
        self.title_bar = self.title_bar_component.title_bar

        # ── 2. HAUPT-UI SETUP ────────────────────────────────────────────────
        self.setup_ui()

        # Bindings
        self.root.bind("<Configure>", self.on_window_configure)
        self.update_backend_label()

    def setup_ui(self) -> None:
        """Erstellt das moderne Interface mit Sidebar, Cards und Tabview-Bildanzeige."""
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=1)

        # ── LINKE SEITENLEISTE ───────────────────────────────────────────────
        sidebar_frame = ctk.CTkFrame(self.root, width=320, corner_radius=0, fg_color=COLOR_BG_MAIN)
        sidebar_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        sidebar_frame.grid_propagate(False)

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

        self.sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar_frame,
            fg_color="transparent",
            scrollbar_button_color="#27272A",
            scrollbar_button_hover_color="#3F3F46"
        )
        self.sidebar_scroll.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        # ── SIDEBAR CARDS WIDGETS ────────────────────────────────────────────
        self.mode_card_widget = AnalysisModeCard(self.sidebar_scroll, self.on_analysis_mode_changed)
        self.mode_card_widget.pack(fill=ctk.X, pady=(0, 15), ipady=6)
        self.analysis_mode_opt = self.mode_card_widget.option_menu

        self.roi_card_widget = RoiCard(self.sidebar_scroll)
        self.roi_card_widget.pack(fill=ctk.X, pady=(0, 15), ipady=6)
        self.roi_card = self.roi_card_widget
        self.roi_info_lbl = self.roi_card_widget.info_lbl
        self.roi_stats_frame = self.roi_card_widget.stats_frame

        self.settings_card_widget = SystemSettingsCard(
            self.sidebar_scroll,
            toggle_callback=self.toggle_settings_visibility,
            on_calibration_changed=self.on_calibration_changed,
            on_temp_unit_changed=self.on_temp_unit_changed,
            on_emissivity_changed=self.on_emissivity_changed,
            on_export_path_changed=self.on_export_path_changed,
            browse_export_callback=self.browse_export_path,
            on_backend_changed=self.on_backend_ui_changed,
            toggle_theme_callback=self.toggle_appearance_mode
        )
        self.settings_card_widget.pack(fill=ctk.X, pady=(0, 15), ipady=6)
        self.settings_card = self.settings_card_widget
        self.toggle_settings_btn = self.settings_card_widget.toggle_btn
        self.settings_boxes_frame = self.settings_card_widget.boxes_frame
        self.t_min_entry = self.settings_card_widget.t_min_entry
        self.t_max_entry = self.settings_card_widget.t_max_entry
        self.calib_status_lbl = self.settings_card_widget.calib_status_lbl
        self.temp_unit_opt = self.settings_card_widget.temp_unit_opt
        self.emissivity_entry = self.settings_card_widget.emissivity_entry
        self.export_path_entry = self.settings_card_widget.export_path_entry
        self.backend_opt = self.settings_card_widget.backend_opt
        self.settings_visible = False

        # Load button
        self.load_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Wärmebild laden",
            command=self.load_file,
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            fg_color=COLOR_PRIMARY_ACCENT,
            hover_color=COLOR_HOVER_ACCENT,
            text_color="#FFFFFF",
            height=40,
            corner_radius=8
        )
        self.load_btn.pack(fill=ctk.X, pady=(0, 15))

        # Aktionen Card (Einklappbar)
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

        # Palette Menu
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

        # Parameter Card
        self.param_card_widget = PipelineParametersCard(
            self.sidebar_scroll,
            toggle_callback=self.toggle_pipeline_parameters,
            update_params_callback=self.update_params
        )
        self.param_card_widget.pack(fill=ctk.X, pady=(0, 15))
        self.param_card = self.param_card_widget
        self.toggle_param_btn = self.param_card_widget.toggle_btn
        self.param_sliders_frame = self.param_card_widget.sliders_frame
        self.sigma_k_slider = self.param_card_widget.sigma_k_slider
        self.tophat_slider = self.param_card_widget.tophat_slider
        self.min_area_slider = self.param_card_widget.min_area_slider
        self.min_circ_slider = self.param_card_widget.min_circ_slider
        self.otsu_min_slider = self.param_card_widget.otsu_min_slider
        self.otsu_max_slider = self.param_card_widget.otsu_max_slider
        self.erosion_slider = self.param_card_widget.erosion_slider
        self.temp_offset_slider = self.param_card_widget.temp_offset_slider
        self.mad_switch = self.param_card_widget.mad_switch
        self.asymmetry_switch = self.param_card_widget.asymmetry_switch
        self.parameters_visible = False

        # Info Card
        self.info_card_widget = AnalysisInfoCard(self.sidebar_scroll)
        self.info_card_widget.pack(fill=ctk.X, pady=(0, 15), ipady=8)
        self.info_card = self.info_card_widget
        self.filename_label = self.info_card_widget.filename_label
        self.backend_label = self.info_card_widget.backend_label
        self.status_label = self.info_card_widget.status_label
        self.hotspot_label = self.info_card_widget.hotspot_label
        self.pixel_info_label = self.info_card_widget.pixel_info_label

        # Buttons in actions container
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

        # Footer
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

        # ── 3. RECHTER HAUPTBEREICH (Tabview & Dashboard) ───────────────────
        content_frame = ctk.CTkFrame(self.root, fg_color=COLOR_BG_MAIN, corner_radius=0)
        content_frame.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        self.tabview = ctk.CTkTabview(
            content_frame,
            fg_color="transparent",
            segmented_button_selected_color=COLOR_PRIMARY_ACCENT,
            segmented_button_selected_hover_color=COLOR_HOVER_ACCENT,
            segmented_button_unselected_color=COLOR_BG_CARD,
            segmented_button_unselected_hover_color=COLOR_BORDER_CARD,
            text_color=COLOR_TEXT_PRIMARY
        )

        # Welcome Frame
        self.welcome_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
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

        # Loading Overlay
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

        # ── 4. VIEWS SETUP (Dashboard & Analysis Views) ────────────────────
        self.dashboard_view = DashboardView(
            master_tab=self.tabview.tab("Gesamtübersicht"),
            hover_callback=self.on_image_hover,
            leave_callback=self.on_image_leave,
            roi_start_callback=self.on_roi_start,
            roi_drag_callback=self.on_roi_drag,
            roi_end_callback=self.on_roi_end
        )
        self.panels = self.dashboard_view.panels

        self.dashboard_view.setup_fullsize_tabs(
            tabview=self.tabview,
            hover_cb=self.on_image_hover,
            leave_cb=self.on_image_leave,
            roi_start_cb=self.on_roi_start,
            roi_drag_cb=self.on_roi_drag,
            roi_end_cb=self.on_roi_end
        )
        self.panels_full = self.dashboard_view.panels_full

        self.analysis_view = AnalysisView(self.tabview)
        self.title_hist = self.analysis_view.title_hist
        self.hist_container = self.analysis_view.hist_container
        self.stats_labels = self.analysis_view.stats_labels
        self.stats_title_labels = self.analysis_view.stats_title_labels
        self.stats_divider_label = self.analysis_view.stats_divider_label
        self.detail_panel = self.analysis_view.detail_panel
        self.detail_title = self.analysis_view.detail_title
        self.detail_content_frame = self.analysis_view.detail_content_frame

        self.update_detail_tab()
        self.show_welcome_screen()

    # ── TOGGLE & CALLBACKS ───────────────────────────────────────────────────

    def show_welcome_screen(self) -> None:
        self.tabview.pack_forget()
        self.welcome_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

    def hide_welcome_screen(self) -> None:
        self.welcome_frame.pack_forget()
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

    def toggle_settings_visibility(self) -> None:
        if self.settings_visible:
            self.settings_boxes_frame.pack_forget()
            self.toggle_settings_btn.configure(text="⚙️ Systemeinstellungen  ▸", text_color=COLOR_TEXT_SECONDARY)
            self.settings_visible = False
        else:
            self.settings_boxes_frame.pack(fill=ctk.X, padx=8, pady=(4, 8))
            self.toggle_settings_btn.configure(text="⚙️ Systemeinstellungen  ▾", text_color=COLOR_PRIMARY_ACCENT)
            self.settings_visible = True

    def toggle_actions_visibility(self) -> None:
        if self.actions_visible:
            self.actions_container.pack_forget()
            self.toggle_actions_btn.configure(text="📁 Aktionen & Berichte  ▸", text_color=COLOR_TEXT_SECONDARY)
            self.actions_visible = False
        else:
            self.actions_container.pack(fill=ctk.X, padx=8, pady=(4, 8))
            self.toggle_actions_btn.configure(text="📁 Aktionen & Berichte  ▾", text_color=COLOR_PRIMARY_ACCENT)
            self.actions_visible = True

    def toggle_pipeline_parameters(self) -> None:
        if self.parameters_visible:
            self.param_sliders_frame.pack_forget()
            self.toggle_param_btn.configure(text="📊 Parameter einblenden  ▸", text_color=COLOR_PRIMARY_ACCENT)
            self.parameters_visible = False
        else:
            self.param_sliders_frame.pack(fill=ctk.X, padx=8, pady=(4, 8))
            self.toggle_param_btn.configure(text="📊 Parameter ausblenden  ▾", text_color=COLOR_TEXT_SECONDARY)
            self.parameters_visible = True

    def on_calibration_changed(self, event=None) -> None:
        try:
            val_min = float(self.t_min_entry.get().replace(",", "."))
            val_max = float(self.t_max_entry.get().replace(",", "."))
            if val_max <= val_min:
                val_max = val_min + 1.0
            self.t_min_celsius = val_min
            self.t_max_celsius = val_max
            resolution = (val_max - val_min) / 255.0
            self.calib_status_lbl.configure(text=f"{val_min:.1f}°C – {val_max:.1f}°C  |  {resolution:.3f}°C/px")
            if self.current_filepath:
                self.redraw_all_images()
        except ValueError:
            pass

    def on_temp_unit_changed(self, choice: str) -> None:
        self.redraw_all_images()
        self.update_detail_tab()

    def on_emissivity_changed(self, event=None) -> None:
        try:
            val = float(self.emissivity_entry.get().replace(",", "."))
            if 0.1 <= val <= 1.0:
                self.emissivity = val
        except ValueError:
            pass

    def on_export_path_changed(self, event=None) -> None:
        path = self.export_path_entry.get().strip()
        if path and os.path.exists(path):
            config.OUTPUT_DIR = path

    def browse_export_path(self) -> None:
        path = filedialog.askdirectory(title="Export-Verzeichnis wählen")
        if path:
            self.export_path_entry.delete(0, ctk.END)
            self.export_path_entry.insert(0, path)
            config.OUTPUT_DIR = path

    def to_temp_val(self, raw_pixel_val: float) -> float:
        celsius = pixel_to_celsius(raw_pixel_val, self.t_min_celsius, self.t_max_celsius)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return celsius * 9.0 / 5.0 + 32.0
        elif "Kelvin" in unit:
            return celsius + 273.15
        return celsius

    def to_temp_str(self, raw_pixel_val: float) -> str:
        val = self.to_temp_val(raw_pixel_val)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return f"{val:.1f} °F"
        elif "Kelvin" in unit:
            return f"{val:.1f} K"
        return f"{val:.1f} °C"

    def to_delta_val(self, raw_delta_val: float) -> float:
        temp_range = max(1.0, self.t_max_celsius - self.t_min_celsius)
        delta_celsius = (raw_delta_val / 255.0) * temp_range
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return delta_celsius * 9.0 / 5.0
        return delta_celsius

    def to_delta_str(self, raw_delta_val: float) -> str:
        val = self.to_delta_val(raw_delta_val)
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            return f"{val:.1f} °F"
        elif "Kelvin" in unit:
            return f"{val:.1f} K"
        return f"{val:.1f} °C"

    def update_backend_label(self) -> None:
        active = image_processing.get_active_backend()
        forced = self.backend_var.get()
        if forced != "auto":
            active += " (Erzwungen)"
        self.backend_label.configure(text=f"Backend: {active}")

    def load_file(self) -> None:
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Alle unterstützten Wärmebilder", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif;*.flir"),
                ("FLIR Radiometrische Bilder", "*.tiff;*.tif;*.flir"),
                ("Standard Bilder (8-Bit)", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("Alle Dateien", "*.*")
            ]
        )
        if file_path:
            self.current_filepath = file_path
            self.filename_label.configure(text=f"Datei: {os.path.basename(file_path)}")
            self.process_pipeline()

    def process_pipeline(self) -> None:
        if not self.current_filepath:
            return
        self.show_loading_overlay()
        sk = self.sigma_k_slider.get()
        th = self.tophat_slider.get()
        ma = self.min_area_slider.get()
        mc = self.min_circ_slider.get()
        omin = int(self.otsu_min_slider.get())
        omax = int(self.otsu_max_slider.get())
        er = self.erosion_slider.get()
        to = self.temp_offset_slider.get()

        def worker():
            try:
                self.root.after(0, lambda: self.update_loading_progress(0.2, "Lade Wärmebild..."))
                img = image_processing.load_thermal_image(self.current_filepath)
                self.current_raw_original = img.copy()

                range_c = self.t_max_celsius - self.t_min_celsius
                if range_c <= 0:
                    range_c = 20.0
                raw_offset = int(round(to * 255.0 / range_c))
                calibrated_img = np.clip(img.astype(np.int16) + raw_offset, 0, 255).astype(np.uint8)

                self.root.after(0, lambda: self.update_loading_progress(0.5, "Führe Rust/GPU-Hotspot-Pipeline aus..."))
                diff_img, hotspot_mask = image_processing.run_rust_pipeline(
                    calibrated_img, sk, th, ma, mc, omin, omax, er, use_mad=self.mad_switch.get() == 1
                )

                self.current_raw_mask = hotspot_mask.copy()
                body_mask_vis = (diff_img > 0).astype(np.uint8) * 255

                self.root.after(0, lambda: self.update_loading_progress(0.8, "Generiere Farbanomalie-Overlay..."))
                if self.analysis_mode_opt.get() == "Podologische Symmetrieanalyse":
                    overlay_img = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                else:
                    overlay_img = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                overlay_rgb = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB)

                self.current_images = {
                    "1. Originalbild": calibrated_img,
                    "2. Hintergrund-Maske": body_mask_vis,
                    "3. Lokale Hitze-Differenz": diff_img,
                    "4. Erkannte Hotspots (Rust)": overlay_rgb
                }

                self.root.after(0, lambda: self.on_pipeline_done(hotspot_mask))
            except Exception as e:
                self.root.after(0, lambda err=e: self.on_pipeline_failed(err))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def update_loading_progress(self, progress: float, step_text: str) -> None:
        self.loading_pbar.set(progress)
        self.loading_step_lbl.configure(text=step_text)
        self.root.update_idletasks()

    def show_loading_overlay(self) -> None:
        self.welcome_frame.pack_forget()
        self.tabview.pack_forget()
        self.loading_overlay.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        self.root.update_idletasks()

    def hide_loading_overlay(self) -> None:
        self.loading_overlay.pack_forget()
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

    def on_pipeline_done(self, hotspot_mask: np.ndarray) -> None:
        self.hide_loading_overlay()
        self.update_backend_label()
        hotspot_count = int(hotspot_mask.sum()) // 255
        self.status_label.configure(text="Status: Analyse abgeschlossen ✓", text_color="#10B981")

        if hotspot_count > 0:
            self.hotspot_label.configure(text=f"Hotspots: {hotspot_count} Pixel", text_color="#FF0055")
        else:
            self.hotspot_label.configure(text="Hotspots: 0 (Unauffällig)", text_color="#10B981")

        for name, cv_img in self.current_images.items():
            self.display_image_in_panel(cv_img, name)

        self.draw_histogram()
        self.update_detail_tab()

    def on_pipeline_failed(self, error: Exception) -> None:
        self.hide_loading_overlay()
        self.status_label.configure(text="Status: Fehler in Pipeline ✕", text_color="#EF4444")
        messagebox.showerror("Pipeline-Fehler", f"Fehler bei der Bildverarbeitung:\n{error}")

    def update_params(self, val=None) -> None:
        self.sigma_k_val.configure(text=f"{self.sigma_k_slider.get():.1f}")
        self.tophat_val.configure(text=f"{self.tophat_slider.get()*100:.1f}%")
        self.min_area_val.configure(text=f"{self.min_area_slider.get()*100:.2f}%")
        self.min_circ_val.configure(text=f"{self.min_circ_slider.get():.2f}")
        self.otsu_min_val.configure(text=f"{int(self.otsu_min_slider.get())}")
        self.otsu_max_val.configure(text=f"{int(self.otsu_max_slider.get())}")
        self.erosion_val.configure(text=f"{self.erosion_slider.get()*100:.1f}%")
        self.temp_offset_val.configure(text=f"{self.temp_offset_slider.get():.1f}°C")

        if self.current_filepath:
            self.process_pipeline()

    def display_image_in_panel(self, cv_img: np.ndarray, panel_name: str, update_cache: bool = True) -> None:
        if cv_img is None:
            return

        cache_key = f"{panel_name}_{self.palette_menu.get()}_{cv_img.shape}"
        if cache_key in self.pil_cache:
            pil_img = self.pil_cache[cache_key]
            self.pil_cache.move_to_end(cache_key)
        else:
            palette = self.palette_menu.get()
            if len(cv_img.shape) == 2:
                if panel_name == "1. Originalbild":
                    if palette == "Regenbogen (Jet)":
                        color_cv = cv2.applyColorMap(cv_img, cv2.COLORMAP_JET)
                        pil_img = Image.fromarray(cv2.cvtColor(color_cv, cv2.COLOR_BGR2RGB))
                    elif palette == "Inferno":
                        color_cv = cv2.applyColorMap(cv_img, cv2.COLORMAP_INFERNO)
                        pil_img = Image.fromarray(cv2.cvtColor(color_cv, cv2.COLOR_BGR2RGB))
                    elif palette == "Heiß (Hot)":
                        color_cv = cv2.applyColorMap(cv_img, cv2.COLORMAP_HOT)
                        pil_img = Image.fromarray(cv2.cvtColor(color_cv, cv2.COLOR_BGR2RGB))
                    else:
                        pil_img = Image.fromarray(cv_img).convert("L")
                else:
                    pil_img = Image.fromarray(cv_img).convert("L")
            else:
                pil_img = Image.fromarray(cv_img)

            if update_cache:
                self.pil_cache[cache_key] = pil_img
                if len(self.pil_cache) > self._PIL_CACHE_MAXSIZE:
                    self.pil_cache.popitem(last=False)

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
        if event.widget == self.root and self.current_images:
            if self.resize_job:
                self.root.after_cancel(self.resize_job)
            self.resize_job = self.root.after(150, self.redraw_all_images)

    def redraw_all_images(self) -> None:
        for name, cv_img in self.current_images.items():
            self.display_image_in_panel(cv_img, name, update_cache=False)
        self.draw_histogram()

    def toggle_appearance_mode(self) -> None:
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("Light")
        else:
            ctk.set_appearance_mode("Dark")

    def on_backend_ui_changed(self, choice: str) -> None:
        mapping = {
            "Automatisch (Schnellstes)": "auto",
            "Erzwinge Rust-CPU-Core": "rust",
            "Erzwinge PyTorch-GPU": "gpu",
            "Erzwinge Python-Fallback": "python"
        }
        val = mapping.get(choice, "auto")
        self.backend_var.set(val)
        image_processing.FORCED_BACKEND = val
        self.update_backend_label()
        if self.current_filepath:
            self.process_pipeline()

    def on_palette_changed(self, value: str) -> None:
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

    def draw_foot_annotations(self, img: np.ndarray, body_mask: np.ndarray, hotspots_mask: np.ndarray) -> np.ndarray:
        palette = self.palette_menu.get()
        if palette == "Regenbogen (Jet)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        elif palette == "Inferno":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        elif palette == "Heiß (Hot)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_HOT)
        else:
            annotated = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        red_img = np.zeros_like(annotated)
        red_img[:] = [85, 0, 255]
        blended = cv2.addWeighted(annotated, 0.3, red_img, 0.7, 0)
        annotated = np.where(hotspots_mask[:, :, None] == 255, blended, annotated).astype(np.uint8)

        h_orig, w_orig = img.shape[:2]
        mid_x = w_orig // 2
        cv2.line(annotated, (mid_x, 0), (mid_x, h_orig), (255, 255, 255), 1, cv2.LINE_AA)

        unit_str = "°C"
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"
        unit_char = "F" if "Fahrenheit" in unit else ("K" if "Kelvin" in unit else "C")

        self.zonal_stats = {
            "left": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False},
            "right": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False}
        }

        # Left Foot
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

            val_vf_l = self.to_temp_val(self.zonal_stats["left"]["fore"])
            val_mf_l = self.to_temp_val(self.zonal_stats["left"]["mid"])
            val_f_l = self.to_temp_val(self.zonal_stats["left"]["heel"])

            cv2.putText(annotated, f"VF: {val_vf_l:.1f} {unit_char}", (min_x + 3, z1_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"MF: {val_mf_l:.1f} {unit_char}", (min_x + 3, z2_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"F: {val_f_l:.1f} {unit_char}", (min_x + 3, max_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        # Right Foot
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

        # Kontralaterale Asymmetrie
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

    def draw_general_annotations(self, img: np.ndarray, body_mask: np.ndarray, hotspots_mask: np.ndarray) -> np.ndarray:
        palette = self.palette_menu.get()
        if palette == "Regenbogen (Jet)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_JET)
        elif palette == "Inferno":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        elif palette == "Heiß (Hot)":
            annotated = cv2.applyColorMap(img, cv2.COLORMAP_HOT)
        else:
            annotated = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        red_img = np.zeros_like(annotated)
        red_img[:] = [85, 0, 255]
        blended = cv2.addWeighted(annotated, 0.3, red_img, 0.7, 0)
        annotated = np.where(hotspots_mask[:, :, None] == 255, blended, annotated).astype(np.uint8)

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

        raw_hotspots.sort(key=lambda x: x["area"], reverse=True)

        self.general_hotspots = []
        for idx, hs in enumerate(raw_hotspots, start=1):
            hs["index"] = idx
            self.general_hotspots.append(hs)

            x, y, w, h = hs["bbox"]
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 165, 0), 1)
            cv2.putText(annotated, f"H#{idx}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1, cv2.LINE_AA)

        return annotated

    def draw_histogram(self) -> None:
        if self.current_raw_original is None:
            return

        for child in self.hist_container.winfo_children():
            child.destroy()

        body_mask = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) if "2. Hintergrund-Maske" in self.current_images else None
        if body_mask is None or np.sum(body_mask) == 0:
            lbl = ctk.CTkLabel(self.hist_container, text="Keine Körper-Maske für Histogramm vorhanden.", text_color=COLOR_TEXT_MUTED)
            lbl.pack(expand=True)
            return

        img = self.current_raw_original
        pixels = img[body_mask > 0]
        if len(pixels) == 0:
            return

        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        thresh_val = mean_val + self.sigma_k_slider.get() * std_val
        max_val = np.max(pixels)

        pixels_disp = [self.to_temp_val(p) for p in pixels]
        mean_disp = self.to_temp_val(mean_val)
        thresh_disp = self.to_temp_val(thresh_val)
        max_disp = self.to_temp_val(max_val)
        std_disp = self.to_delta_val(std_val)

        unit_str = "°C"
        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"

        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            bg_fig = "#18181B"
            bg_ax = "#09090B"
            color_text = "#F4F4F5"
            color_tick = "#A1A1AA"
            color_grid = "#27272A"
            color_spine = "#27272A"
            bg_legend = "#18181B"
        else:
            bg_fig = "#F8FAFC"
            bg_ax = "#FFFFFF"
            color_text = "#0F172A"
            color_tick = "#475569"
            color_grid = "#E2E8F0"
            color_spine = "#E2E8F0"
            bg_legend = "#F1F5F9"

        fig = Figure(figsize=(6, 3.8), dpi=100, facecolor=bg_fig)
        ax = fig.add_subplot(111, facecolor=bg_ax)

        ax.hist(pixels_disp, bins=128, color=COLOR_PRIMARY_ACCENT, alpha=0.7, edgecolor="none")
        ax.axvline(mean_disp, color=("#18181B" if mode != "Dark" else "#F4F4F5"), linestyle="--", linewidth=1.5,
                   label=f"Mittelwert \u03bc ({mean_disp:.1f} {unit_str})")
        ax.axvline(thresh_disp, color="#FF0055", linestyle="-.", linewidth=2.0,
                   label=f"Grenzwert µ+k\u03c3 ({thresh_disp:.1f} {unit_str})")

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

        canvas_widget = FigureCanvasTkAgg(fig, master=self.hist_container)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Stats Sidebar inside Tab Update
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

                mean_l_disp = self.to_temp_val(mean_l)
                mean_r_disp = self.to_temp_val(mean_r)
                delta_disp = self.to_delta_val(delta)

                if delta >= 15.0:
                    sym_status = "Asymmetrie detektiert \u2013 Bitte abklären"
                    sym_color = "#FF0055"
                else:
                    sym_status = "Symmetrisch \u2013 Unauffällig"
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

            hotspots = getattr(self, "general_hotspots", [])
            num_hotspots = len(hotspots)
            max_area = hotspots[0]["area"] if num_hotspots > 0 else 0
            avg_temp = np.mean([hs["mean_temp"] for hs in hotspots]) if num_hotspots > 0 else 0.0

            if hotspot_count == 0:
                diag_status = "Unauffällig \u2013 Kein Befund"
                diag_color = "#10B981"
            elif hotspot_count < 150:
                diag_status = "Grenzwertig \u2013 Verlaufsbeobachtung"
                diag_color = "#FFA500"
            else:
                diag_status = "Klinisch auffällig \u2013 Weiteres Monitoring"
                diag_color = "#FF0055"

            self.stats_labels["mean_left"].configure(text=f"{num_hotspots}")
            self.stats_labels["mean_right"].configure(text=f"{max_area:,} px")

            avg_temp_disp = self.to_temp_val(avg_temp) if num_hotspots > 0 else 0.0
            self.stats_labels["delta"].configure(
                text=f"{avg_temp_disp:.2f} {unit_str}" if num_hotspots > 0 else f"0.00 {unit_str}",
                text_color=diag_color if num_hotspots > 0 else COLOR_TEXT_PRIMARY
            )
            self.stats_labels["status_symmetry"].configure(text=diag_status, text_color=diag_color)

    def on_analysis_mode_changed(self, mode: str) -> None:
        if mode == "Podologische Symmetrieanalyse":
            self.title_hist.configure(text="Statistisches Intensitätshistogramm (Exklusiv über Fußoberfläche)")
        else:
            self.title_hist.configure(text="Statistisches Intensitätshistogramm (Analysierte Oberfläche)")
        self.update_detail_tab()
        if self.current_filepath:
            self.process_pipeline()

    def update_detail_tab(self) -> None:
        for widget in self.detail_content_frame.winfo_children():
            widget.destroy()

        mode = self.analysis_mode_opt.get()

        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"

        if mode == "Podologische Symmetrieanalyse":
            self.detail_title.configure(text="Detaillierter Zonen-Symmetrie-Vergleich (3-Zonen-Modell)")

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

            if hasattr(self, "zonal_stats") and self.zonal_stats.get("left", {}).get("exists") and self.zonal_stats.get("right", {}).get("exists"):
                for key in ["fore", "mid", "heel"]:
                    l_v = self.zonal_stats["left"][key]
                    r_v = self.zonal_stats["right"][key]
                    d_v = abs(l_v - r_v)

                    l_v_str = self.to_temp_str(l_v)
                    r_v_str = self.to_temp_str(r_v)
                    d_v_str = self.to_delta_str(d_v)

                    if d_v >= 15.0:
                        z_diag = "Asymmetrie detektiert \u2013 Abklärung empfohlen"
                        z_color = "#FF0055"
                    elif d_v >= 10.0:
                        z_diag = "Grenzwert \u2013 Verlaufsbeobachtung"
                        z_color = "#FFA500"
                    else:
                        z_diag = "Symmetrisch \u2013 Unauffällig"
                        z_color = "#10B981"

                    self.zonal_row_labels[key]["l"].configure(text=l_v_str)
                    self.zonal_row_labels[key]["r"].configure(text=r_v_str)
                    self.zonal_row_labels[key]["d"].configure(text=d_v_str, text_color=z_color)
                    self.zonal_row_labels[key]["diag"].configure(text=z_diag, text_color=z_color)
        else:
            self.detail_title.configure(text="Detaillierte Analyse der gefundenen Hotspots")

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

            hotspots = getattr(self, "general_hotspots", [])
            if hotspots:
                for idx, hs in enumerate(hotspots, start=1):
                    area = hs["area"]
                    mean_temp = hs["mean_temp"]
                    max_temp = hs["max_temp"]

                    mean_temp_str = self.to_temp_str(mean_temp)
                    max_temp_str = self.to_temp_str(max_temp)

                    if area >= 150 or mean_temp >= 180:
                        diag_text = "Klinisch relevant \u2013 Abklärung empfohlen"
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

    # ── MOUSE HOVER & ROI INTERACTION ───────────────────────────────────────

    def on_image_hover(self, event, panel_name: str, is_grid: bool) -> None:
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
        self.pixel_info_label.configure(text="Pixel-Info: --", text_color="#71717A")

    def map_event_to_image_coords(self, event, panel_name: str, is_grid: bool) -> tuple[int | None, int | None]:
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
        if not self.drawing_roi or self.current_raw_original is None:
            return
        x_orig, y_orig = self.map_event_to_image_coords(event, panel_name, is_grid)
        if x_orig is not None and y_orig is not None:
            self.roi_current_x = x_orig
            self.roi_current_y = y_orig
            self.update_roi_live_preview()

    def on_roi_end(self, event, panel_name: str, is_grid: bool) -> None:
        if not self.drawing_roi or self.current_raw_original is None:
            return
        x_orig, y_orig = self.map_event_to_image_coords(event, panel_name, is_grid)
        if x_orig is not None and y_orig is not None:
            self.roi_end_x = x_orig
            self.roi_end_y = y_orig
            self.drawing_roi = False
            self.calculate_roi_statistics()

    def update_roi_live_preview(self) -> None:
        if self.current_raw_original is None:
            return
        x1, x2 = sorted([self.roi_start_x, self.roi_current_x])
        y1, y2 = sorted([self.roi_start_y, self.roi_current_y])

        if x2 - x1 < 2 or y2 - y1 < 2:
            return

        roi_pixels = self.current_raw_original[y1:y2, x1:x2]
        if len(roi_pixels) == 0:
            return

        min_val = np.min(roi_pixels)
        max_val = np.max(roi_pixels)
        mean_val = np.mean(roi_pixels)

        min_str = self.to_temp_str(float(min_val))
        max_str = self.to_temp_str(float(max_val))
        mean_str = self.to_temp_str(float(mean_val))

        self.roi_info_lbl.configure(
            text=f"Live-ROI: [{x1},{y1}] BIS [{x2},{y2}]\nMin: {min_str}  |  Max: {max_str}\nMittel: {mean_str}",
            text_color=COLOR_PRIMARY_ACCENT
        )

    def calculate_roi_statistics(self) -> None:
        if self.current_raw_original is None:
            return
        x1, x2 = sorted([self.roi_start_x, self.roi_end_x])
        y1, y2 = sorted([self.roi_start_y, self.roi_end_y])

        if x2 - x1 < 2 or y2 - y1 < 2:
            return

        roi_pixels = self.current_raw_original[y1:y2, x1:x2]
        if len(roi_pixels) == 0:
            return

        min_val = np.min(roi_pixels)
        max_val = np.max(roi_pixels)
        mean_val = np.mean(roi_pixels)
        std_val = np.std(roi_pixels)

        min_str = self.to_temp_str(float(min_val))
        max_str = self.to_temp_str(float(max_val))
        mean_str = self.to_temp_str(float(mean_val))
        std_str = self.to_delta_str(float(std_val))

        self.roi_info_lbl.configure(
            text=f"ROI-Ergebnis ({x2-x1}x{y2-y1} px):\nMin: {min_str}  |  Max: {max_str}\nµ: {mean_str}  |  σ: {std_str}",
            text_color="#10B981"
        )

    # ── DIALOGE & EXPORTS ───────────────────────────────────────────────────

    def show_info_window(self) -> None:
        InstructionsModal(self.root)

    def show_about_window(self) -> None:
        AboutModal(self.root)

    def open_output_dir(self) -> None:
        try:
            abs_path = os.path.abspath(config.OUTPUT_DIR)
            if not os.path.exists(abs_path):
                config.init_output_dir()
            os.startfile(abs_path)
        except Exception as e:
            messagebox.showerror("Fehler", f"Ausgabeordner konnte nicht geöffnet werden:\n{e}")

    def clean_output_dir(self) -> None:
        if messagebox.askyesno("Ordner bereinigen", "Möchten Sie alle gespeicherten Ausgabedateien im Ergebnisordner wirklich löschen?"):
            try:
                for file in os.listdir(config.OUTPUT_DIR):
                    file_path = os.path.join(config.OUTPUT_DIR, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                messagebox.showinfo("Bereinigt", "Der Ausgabeordner wurde erfolgreich bereinigt.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Bereinigen:\n{e}")

    def export_html_report(self) -> None:
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

            backend_info = image_processing.get_active_backend()
            forced = self.backend_var.get()
            if forced != "auto":
                backend_info = f"{backend_info} (Erzwungen)"

            unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
            unit_str = "°C"
            if "Fahrenheit" in unit:
                unit_str = "°F"
            elif "Kelvin" in unit:
                unit_str = "K"

            mean_l_disp = self.to_temp_val(mean_l)
            mean_r_disp = self.to_temp_val(mean_r)
            mean_val_disp = self.to_temp_val(mean_val)
            threshold_disp = self.to_temp_val(threshold)
            delta_disp = self.to_delta_val(abs(mean_l - mean_r))
            std_disp = self.to_delta_val(std_val)

            l_f = self.to_temp_val(self.zonal_stats.get("left", {}).get("fore", 0.0))
            r_f = self.to_temp_val(self.zonal_stats.get("right", {}).get("fore", 0.0))
            l_m = self.to_temp_val(self.zonal_stats.get("left", {}).get("mid", 0.0))
            r_m = self.to_temp_val(self.zonal_stats.get("right", {}).get("mid", 0.0))
            l_h = self.to_temp_val(self.zonal_stats.get("left", {}).get("heel", 0.0))
            r_h = self.to_temp_val(self.zonal_stats.get("right", {}).get("heel", 0.0))

            df_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("fore", 0.0) - self.zonal_stats.get("right", {}).get("fore", 0.0)))
            dm_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("mid", 0.0) - self.zonal_stats.get("right", {}).get("mid", 0.0)))
            dh_disp = self.to_delta_val(abs(self.zonal_stats.get("left", {}).get("heel", 0.0) - self.zonal_stats.get("right", {}).get("heel", 0.0)))

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
        else:
            h1_title = "IGNITE Medical Imaging Suite – Thermografischer Befundbericht"
            mean_title = "Mittl. Temperatur Objektoberfläche"
            diabetes_html = ""
            hotspots_percentage_label = f"{hotspots} Pixel ({(hotspots / foot_pixels) * 100 if foot_pixels > 0 else 0:.3f} %)"
            symmetry_or_hotspots_meta = f"""
            <div class="meta-item">
                <div class="meta-label">Hotspot-Anzahl</div>
                <div class="meta-value" style="color: #EF4444; font-weight: bold;">{hotspots} Pixel</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Globaler Befund</div>
                <div class="meta-value">
                    <span class="status-badge" style="{get_badge_style(sym_color)}">{sym_status}</span>
                </div>
            </div>"""

        now_str = datetime.datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE Befundbericht - {base_name}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #09090B; color: #F4F4F5; margin: 0; padding: 40px; }}
        .container {{ max-width: 960px; margin: 0 auto; background: #18181B; border: 1px solid #27272A; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #27272A; padding-bottom: 20px; margin-bottom: 24px; }}
        .title {{ font-size: 24px; font-weight: bold; color: #F4F4F5; }}
        .subtitle {{ font-size: 13px; color: #6366F1; margin-top: 4px; font-weight: 600; }}
        .meta-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 32px; background: #09090B; padding: 20px; border-radius: 8px; border: 1px solid #27272A; }}
        .meta-item {{ display: flex; flex-direction: column; }}
        .meta-label {{ font-size: 11px; text-transform: uppercase; color: #71717A; font-weight: bold; letter-spacing: 0.5px; }}
        .meta-value {{ font-size: 14px; color: #F4F4F5; margin-top: 2px; }}
        .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
        .section-title {{ font-size: 16px; font-weight: bold; color: #F4F4F5; margin-top: 32px; margin-bottom: 16px; border-left: 4px solid #6366F1; padding-left: 10px; }}
        .image-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 32px; }}
        .image-card {{ background: #09090B; border: 1px solid #27272A; border-radius: 8px; padding: 12px; text-align: center; }}
        .image-card img {{ max-width: 100%; height: auto; border-radius: 6px; border: 1px solid #27272A; }}
        .image-caption {{ font-size: 12px; font-weight: bold; color: #A1A1AA; margin-top: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; background: #09090B; border-radius: 8px; overflow: hidden; border: 1px solid #27272A; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #27272A; font-size: 13px; }}
        th {{ background-color: #18181B; color: #6366F1; font-weight: bold; text-transform: uppercase; font-size: 11px; }}
        tr:last-child td {{ border-bottom: none; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #27272A; font-size: 11px; color: #71717A; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="title">{h1_title}</div>
                <div class="subtitle">Automatische Thermografie-Analyse · IGNITE Engine ({backend_info})</div>
            </div>
            <div style="text-align: right; font-size: 12px; color: #71717A;">
                Erstellt am:<br><strong style="color: #F4F4F5;">{now_str}</strong>
            </div>
        </div>

        <div class="section-title">Stammdaten & Untersuchte Aufnahmen</div>
        <div class="meta-grid">
            <div class="meta-item"><div class="meta-label">Patienten-ID</div><div class="meta-value">{p_name}</div></div>
            <div class="meta-item"><div class="meta-label">Dateiname</div><div class="meta-value">{filename}</div></div>
            {gdpr_badge}
            <div class="meta-item"><div class="meta-label">Untersucher / Bediener</div><div class="meta-value">{operator}</div></div>
            <div class="meta-item"><div class="meta-label">Analysemodus</div><div class="meta-value">{analysis_mode}</div></div>
            {diabetes_html}
        </div>

        <div class="section-title">Klinische Messergebnisse</div>
        <div class="meta-grid">
            <div class="meta-item"><div class="meta-label">{mean_title}</div><div class="meta-value">{mean:.2f} {unit_str}</div></div>
            <div class="meta-item"><div class="meta-label">Standardabweichung (σ)</div><div class="meta-value">{std:.2f} {unit_str}</div></div>
            <div class="meta-item"><div class="meta-label">Berechnete Hotspot-Schwelle</div><div class="meta-value">{thresh:.2f} {unit_str}</div></div>
            <div class="meta-item"><div class="meta-label">Detektierte Hotspots</div><div class="meta-value">{hotspots_percentage_label}</div></div>
            {symmetry_or_hotspots_meta}
        </div>

        <div class="section-title">Visualisierung der 4 Pipeline-Stufen</div>
        <div class="image-grid">
            <div class="image-card">
                <img src="steps/{base_name}_step1_original.png" alt="Original">
                <div class="image-caption">Stufe 1: Original-Wärmebild</div>
            </div>
            <div class="image-card">
                <img src="steps/{base_name}_step2_mask.png" alt="Maske">
                <div class="image-caption">Stufe 2: Hintergrund-Maske</div>
            </div>
            <div class="image-card">
                <img src="steps/{base_name}_step3_local_heat_diff.png" alt="Differenz">
                <div class="image-caption">Stufe 3: Lokale Hitze-Differenz</div>
            </div>
            <div class="image-card">
                <img src="steps/{base_name}_step4_dynamic_hotspots.png" alt="Hotspots">
                <div class="image-caption">Stufe 4: Erkannte Hotspots (Rust)</div>
            </div>
        </div>

        <div class="footer">
            IGNITE Medical Imaging Suite v{APP_VERSION} // Jugend forscht 2026 // Kein zugelassenes Medizinprodukt.
        </div>
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _write_batch_summary_html(self, filepath, patients_processed, analysis_mode):
        now_str = datetime.datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")
        rows_html = ""

        if analysis_mode == "Podologische Symmetrieanalyse":
            th_delta = "Symmetrie-Delta (Δ)"
            th_zonal = "Max. Zonen-Delta"
        else:
            th_delta = "Hotspot-Anzahl"
            th_zonal = "Größte Fläche"

        unit = self.temp_unit_opt.get() if hasattr(self, "temp_unit_opt") else "Celsius (°C)"
        unit_str = "°C"
        if "Fahrenheit" in unit:
            unit_str = "°F"
        elif "Kelvin" in unit:
            unit_str = "K"

        for p in patients_processed:
            delta_val = p['delta']
            zonal_val = p['max_zonal_delta']
            if analysis_mode == "Podologische Symmetrieanalyse":
                delta_str = self.to_delta_str(delta_val)
                zonal_str = self.to_delta_str(zonal_val)
            else:
                delta_str = f"{int(delta_val)} px"
                zonal_str = f"{int(zonal_val)} px"

            rows_html += f"""
            <tr>
                <td><strong>{p['filename']}</strong></td>
                <td style="color: #EF4444; font-weight: bold;">{p['hotspots']} px</td>
                <td>{delta_str}</td>
                <td>{zonal_str}</td>
                <td><span style="display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; background-color: rgba(255,255,255,0.05); color: {p['color']}; border: 1px solid {p['color']}40;">{p['status']}</span></td>
                <td><a href="{p['report']}" style="color: #6366F1; text-decoration: none; font-weight: bold;">Bericht öffnen &rarr;</a></td>
            </tr>"""

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE Stapelverarbeitungs-Bericht</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #09090B; color: #F4F4F5; margin: 0; padding: 40px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #18181B; border: 1px solid #27272A; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #27272A; padding-bottom: 20px; margin-bottom: 24px; }}
        .title {{ font-size: 24px; font-weight: bold; color: #F4F4F5; }}
        .subtitle {{ font-size: 13px; color: #6366F1; margin-top: 4px; font-weight: 600; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #09090B; border-radius: 8px; overflow: hidden; border: 1px solid #27272A; }}
        th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid #27272A; font-size: 13px; }}
        th {{ background-color: #18181B; color: #6366F1; font-weight: bold; text-transform: uppercase; font-size: 11px; }}
        tr:last-child td {{ border-bottom: none; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #27272A; font-size: 11px; color: #71717A; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="title">IGNITE Stapelverarbeitungs-Gesamtbericht</div>
                <div class="subtitle">Automatische Serienuntersuchung · {len(patients_processed)} Wärmebilder verarbeitet</div>
            </div>
            <div style="text-align: right; font-size: 12px; color: #71717A;">
                Erstellt am:<br><strong style="color: #F4F4F5;">{now_str}</strong>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Wärmebild-Datei</th>
                    <th>Hotspots</th>
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

                    if analysis_mode == "Podologische Symmetrieanalyse":
                        overlay_img = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                    else:
                        overlay_img = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                    cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step4_dynamic_hotspots.png"), overlay_img)

                    body_mask = body_mask_vis > 0
                    pixels = calibrated_img[body_mask]
                    mean_val = np.mean(pixels) if len(pixels) > 0 else 0.0

                    if analysis_mode == "Podologische Symmetrieanalyse":
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
