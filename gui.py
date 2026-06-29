# -*- coding: utf-8 -*-
"""gui.py – CustomTkinter-Frontend für das Ignite Entzündungsdetektions-System.

Dieses Modul stellt das grafische Benutzer-Interface des Jugend-forscht-Projekts
"Ignite" bereit. Die Bildverarbeitung wird vollständig an das native Rust-Core-Modul
`ignite_core` oder die GPU-beschleunigte PyTorch-Pipeline delegiert.
"""

import os
import tkinter as tk
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


def get_resource_path(relative_path: str) -> str:
    """Gibt den absoluten Pfad zu einer Ressource zurück, passend für PyInstaller-EXEn."""
    import sys
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class IgniteApp:
    """Haupt-Anwendungsklasse für das Ignite Thermografie-Analyse-System.

    Verwaltet das Hauptfenster unter Verwendung von CustomTkinter, die Seitenleiste
    für Steuerelemente und Statistiken sowie die fünf Bild-Anzeige-Tabs und das
    Temperatur-Histogramm-Tab.
    """

    def __init__(self, root: ctk.CTk) -> None:
        """Initialisiert die Ignite-Anwendung.

        Args:
            root: Das CustomTkinter-Hauptfenster-Objekt.
        """
        self.root = root
        self.root.title("IGNITE // Entzündungsdetektion")
        self.root.geometry("1300x850")
        self.root.minsize(1100, 750)
        self.root.configure(fg_color="#09090B")

        # Setze das Anwendungs-Icon (Favicon)
        icon_path = get_resource_path(os.path.join("icon", "LogoRund.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Ausgabe-Verzeichnis für Jury-Dokumentation anlegen
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
        
        self.resize_job: str | None = None

        self.setup_ui()
        self.setup_menu()

        # Bind-Event für dynamische Skalierung bei Fenster-Größenänderungen (Debounced)
        self.root.bind("<Configure>", self.on_window_configure)

        # Aktives Backend beim Start abfragen
        self.update_backend_label()

    def setup_menu(self) -> None:
        """Erstellt und konfiguriert die obere Menüleiste (Datei, Optionen, Hilfe)."""
        menubar = tk.Menu(self.root)

        # ── DATEI-MENÜ ────────────────────────────────────────────────────────
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Wärmebild laden...", command=self.load_file)
        file_menu.add_command(label="Ordner-Stapelverarbeitung...", command=self.run_batch_processing)
        file_menu.add_command(label="Aktive Ansicht exportieren...", command=self.save_active_view)
        file_menu.add_command(label="HTML-Bericht exportieren", command=self.export_html_report)
        file_menu.add_command(label="Ergebnisordner öffnen", command=self.open_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.root.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)

        # ── OPTIONEN-MENÜ ─────────────────────────────────────────────────────
        options_menu = tk.Menu(menubar, tearoff=0)
        
        # Design-Umschalter
        options_menu.add_command(
            label="Design wechseln (Light/Dark)", 
            command=self.toggle_appearance_mode
        )
        options_menu.add_separator()

        # Backend-Erzwingungs-Untermenü
        self.backend_var = tk.StringVar(value="auto")
        backend_menu = tk.Menu(options_menu, tearoff=0)
        backend_menu.add_radiobutton(
            label="Automatisch (Schnellstes)", 
            variable=self.backend_var, 
            value="auto", 
            command=self.on_backend_changed
        )
        backend_menu.add_radiobutton(
            label="Erzwinge Rust-CPU-Core", 
            variable=self.backend_var, 
            value="rust", 
            command=self.on_backend_changed
        )
        backend_menu.add_radiobutton(
            label="Erzwinge PyTorch-GPU", 
            variable=self.backend_var, 
            value="gpu", 
            command=self.on_backend_changed
        )
        backend_menu.add_radiobutton(
            label="Erzwinge Python-Fallback", 
            variable=self.backend_var, 
            value="python", 
            command=self.on_backend_changed
        )
        
        options_menu.add_cascade(label="Berechnungs-Backend", menu=backend_menu)
        menubar.add_cascade(label="Optionen", menu=options_menu)

        # ── HILFE-MENÜ ────────────────────────────────────────────────────────
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Funktionsweise...", command=self.show_info_window)
        help_menu.add_command(label="Über Ignite...", command=self.show_about_window)
        menubar.add_cascade(label="Hilfe", menu=help_menu)

        # Menüleiste im Hauptfenster registrieren
        self.root.config(menu=menubar)

    def make_slider(self, master, label_text, from_, to, default_val, resolution=0.01):
        """Erstellt ein Steuerelement mit Slider und dynamischer Werteanzeige."""
        frame = ctk.CTkFrame(master, fg_color="transparent")
        frame.pack(fill=ctk.X, pady=6)
        
        top_row = ctk.CTkFrame(frame, fg_color="transparent")
        top_row.pack(fill=ctk.X)
        
        lbl_title = ctk.CTkLabel(top_row, text=label_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#71717A")
        lbl_title.pack(side=ctk.LEFT)
        
        val_lbl = ctk.CTkLabel(top_row, text=str(default_val), font=ctk.CTkFont(size=11), text_color="#06B6D4")
        val_lbl.pack(side=ctk.RIGHT)
        
        slider = ctk.CTkSlider(
            frame, 
            from_=from_, 
            to=to, 
            number_of_steps=int((to - from_)/resolution), 
            fg_color="#27272A", 
            progress_color="#06B6D4", 
            button_color="#06B6D4",
            button_hover_color="#0891B2"
        )
        slider.set(default_val)
        slider.pack(fill=ctk.X, pady=2)
        
        return slider, val_lbl

    def setup_ui(self) -> None:
        """Erstellt das moderne Interface mit Sidebar und Tabview-Bildanzeige."""
        # Haupt-Grid
        self.root.grid_columnconfigure(0, weight=0)  # Sidebar behält feste Breite
        self.root.grid_columnconfigure(1, weight=1)  # Tab-Inhalt dehnt sich aus
        self.root.grid_rowconfigure(0, weight=1)

        # ── 1. LINKE SEITENLEISTE ─────────────────────────────────────────────
        sidebar_frame = ctk.CTkFrame(self.root, width=320, corner_radius=0, fg_color="#09090B")
        sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
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
            except Exception:
                pass

        # App-Header
        title_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="IGNITE",
            font=ctk.CTkFont(family="Arial", size=26, weight="bold"),
            text_color="#FAF5FF"
        )
        title_lbl.pack(padx=20, pady=pady_title, anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Entzündungsdetektion via Thermografie",
            font=ctk.CTkFont(family="Arial", size=11),
            text_color="#71717A"
        )
        subtitle_lbl.pack(padx=20, pady=(0, 20), anchor="w")

        # Scrollbare Steuerleiste für Parameter
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar_frame, 
            fg_color="transparent",
            scrollbar_button_color="#27272A",
            scrollbar_button_hover_color="#3F3F46"
        )
        self.sidebar_scroll.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        # Sektion: Analyse-Modus
        mode_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        mode_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        mode_title = ctk.CTkLabel(mode_card, text="🔍 ANALYSEMODUS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#06B6D4")
        mode_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.analysis_mode_opt = ctk.CTkOptionMenu(
            mode_card, 
            values=["Allgemeine Analyse", "Fuß-Symmetrieanalyse"], 
            command=self.on_analysis_mode_changed,
            font=ctk.CTkFont(size=12), 
            fg_color="#09090B", 
            button_color="#06B6D4", 
            button_hover_color="#0891B2", 
            text_color="#F4F4F5", 
            height=28
        )
        self.analysis_mode_opt.pack(fill=ctk.X, padx=12, pady=(4, 8))

        # Sektion: Patienten-Daten
        patient_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        patient_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        patient_title = ctk.CTkLabel(patient_card, text="👤 PATIENTEN-DATEN", font=ctk.CTkFont(size=10, weight="bold"), text_color="#06B6D4")
        patient_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.patient_name_entry = ctk.CTkEntry(patient_card, placeholder_text="Name / Patient-ID", font=ctk.CTkFont(size=12), fg_color="#09090B", border_color="#27272A", text_color="#F4F4F5", height=28)
        self.patient_name_entry.pack(fill=ctk.X, padx=12, pady=4)

        self.patient_age_entry = ctk.CTkEntry(patient_card, placeholder_text="Alter (Jahre)", font=ctk.CTkFont(size=12), fg_color="#09090B", border_color="#27272A", text_color="#F4F4F5", height=28)
        self.patient_age_entry.pack(fill=ctk.X, padx=12, pady=4)

        self.patient_diabetes_opt = ctk.CTkOptionMenu(
            patient_card, 
            values=["Kein Diabetes", "Diabetes Typ 1", "Diabetes Typ 2"], 
            font=ctk.CTkFont(size=12), 
            fg_color="#09090B", 
            button_color="#06B6D4", 
            button_hover_color="#0891B2", 
            text_color="#F4F4F5", 
            height=28
        )
        # Nicht packen da Allgemeine Analyse der Standard ist

        self.patient_notes_entry = ctk.CTkEntry(patient_card, placeholder_text="Klinische Notizen", font=ctk.CTkFont(size=12), fg_color="#09090B", border_color="#27272A", text_color="#F4F4F5", height=28)
        self.patient_notes_entry.pack(fill=ctk.X, padx=12, pady=(4, 8))

        # Sektion: Steuerung Buttons
        ctrl_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        ctrl_card.pack(fill=ctk.X, pady=(0, 15))

        self.load_btn = ctk.CTkButton(
            ctrl_card,
            text="Wärmebild laden",
            command=self.load_file,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            fg_color="#06B6D4",
            hover_color="#0891B2",
            text_color="#09090B",
            height=38,
            corner_radius=6
        )
        self.load_btn.pack(fill=ctk.X, pady=4)

        self.batch_btn = ctk.CTkButton(
            ctrl_card,
            text="Ordner-Stapelverarbeitung",
            command=self.run_batch_processing,
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            fg_color="transparent",
            text_color="#06B6D4",
            hover_color="#18181B",
            border_width=1,
            border_color="#06B6D4",
            height=34,
            corner_radius=6
        )
        self.batch_btn.pack(fill=ctk.X, pady=4)

        # Sektion: Farbpalette
        palette_lbl = ctk.CTkLabel(
            self.sidebar_scroll,
            text="FARBPALETTE",
            font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
            text_color="#06B6D4"
        )
        palette_lbl.pack(padx=5, pady=(5, 2), anchor="w")
        
        self.palette_menu = ctk.CTkOptionMenu(
            self.sidebar_scroll,
            values=["Graustufen", "Regenbogen (Jet)", "Inferno", "Heiß (Hot)"],
            command=self.on_palette_changed,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="#18181B",
            button_color="#06B6D4",
            button_hover_color="#0891B2",
            text_color="#F4F4F5",
            height=32,
            corner_radius=6
        )
        self.palette_menu.pack(fill=ctk.X, pady=(0, 15))

        # Sektion: Pipeline Parameter (Einklappbar)
        self.param_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        self.param_card.pack(fill=ctk.X, pady=(0, 15))

        self.toggle_param_btn = ctk.CTkButton(
            self.param_card,
            text="⚙️ Parameter einblenden",
            command=self.toggle_pipeline_parameters,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="transparent",
            text_color="#06B6D4",
            hover_color="#27272A",
            height=32,
            anchor="w",
            corner_radius=8
        )
        self.toggle_param_btn.pack(fill=ctk.X, padx=4, pady=4)

        self.param_sliders_frame = ctk.CTkFrame(self.param_card, fg_color="transparent")
        self.parameters_visible = False

        self.sigma_k_slider, self.sigma_k_val = self.make_slider(self.param_sliders_frame, "Threshold-Faktor (sigma_k)", 1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1)
        self.tophat_slider, self.tophat_val = self.make_slider(self.param_sliders_frame, "Top-Hat Kernel (%)", 0.01, 0.15, config.DEFAULT_TOPHAT_FACTOR, 0.005)
        self.min_area_slider, self.min_area_val = self.make_slider(self.param_sliders_frame, "Min. Fläche (%)", 0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001)
        self.min_circ_slider, self.min_circ_val = self.make_slider(self.param_sliders_frame, "Min. Circularity", 0.001, 0.100, config.DEFAULT_MIN_CIRCULARITY, 0.002)
        self.otsu_min_slider, self.otsu_min_val = self.make_slider(self.param_sliders_frame, "Otsu Min Schwellenwert", 10.0, 100.0, config.DEFAULT_OTSU_MIN, 1.0)
        self.otsu_max_slider, self.otsu_max_val = self.make_slider(self.param_sliders_frame, "Otsu Max Schwellenwert", 50.0, 150.0, config.DEFAULT_OTSU_MAX, 1.0)
        self.erosion_slider, self.erosion_val = self.make_slider(self.param_sliders_frame, "Erosions-Faktor", 0.01, 0.20, config.DEFAULT_DIST_EROSION_FACTOR, 0.005)
        self.temp_offset_slider, self.temp_offset_val = self.make_slider(self.param_sliders_frame, "Temp-Offset (Kalibrierung)", -50.0, 50.0, 0.0, 0.5)

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
        self.info_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        self.info_card.pack(fill=ctk.X, pady=(0, 15), ipady=8)

        self.filename_label = ctk.CTkLabel(self.info_card, text="Datei: Keine", font=ctk.CTkFont(size=12), text_color="#F4F4F5", anchor="w")
        self.filename_label.pack(fill=ctk.X, padx=15, pady=(10, 4))

        self.backend_label = ctk.CTkLabel(self.info_card, text="Backend: Erkennung...", font=ctk.CTkFont(size=12), text_color="#F4F4F5", anchor="w")
        self.backend_label.pack(fill=ctk.X, padx=15, pady=4)

        self.status_label = ctk.CTkLabel(self.info_card, text="Status: Bereit", font=ctk.CTkFont(size=12, slant="italic"), text_color="#A1A1AA", anchor="w")
        self.status_label.pack(fill=ctk.X, padx=15, pady=4)

        self.hotspot_label = ctk.CTkLabel(self.info_card, text="Hotspots: --", font=ctk.CTkFont(size=13, weight="bold"), text_color="#F4F4F5", anchor="w")
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=4)

        self.pixel_info_label = ctk.CTkLabel(self.info_card, text="Pixel-Info: --", font=ctk.CTkFont(size=11, slant="italic"), text_color="#71717A", anchor="w", justify="left")
        self.pixel_info_label.pack(fill=ctk.X, padx=15, pady=(4, 10))

        # Dokumentations-Ordner-Button
        self.open_dir_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Ergebnisordner öffnen",
            command=self.open_output_dir,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="transparent",
            text_color="#06B6D4",
            hover_color="#18181B",
            border_width=1,
            border_color="#27272A",
            height=32,
            corner_radius=6
        )
        self.open_dir_btn.pack(fill=ctk.X, pady=4)

        # HTML-Bericht-Button
        self.export_report_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="HTML-Bericht exportieren",
            command=self.export_html_report,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="transparent",
            text_color="#06B6D4",
            hover_color="#18181B",
            border_width=1,
            border_color="#27272A",
            height=32,
            corner_radius=6
        )
        self.export_report_btn.pack(fill=ctk.X, pady=4)

        # Footer
        footer_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Jona Noack | Jugend forscht 2026",
            font=ctk.CTkFont(family="Arial", size=10),
            text_color="#52525B"
        )
        footer_lbl.pack(side=ctk.BOTTOM, pady=15)

        # ── 2. RECHTER HAUPTBEREICH (Tabview) ─────────────────────────────────
        content_frame = ctk.CTkFrame(self.root, fg_color="#09090B", corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # CTkTabview erstellen und konfigurieren
        self.tabview = ctk.CTkTabview(
            content_frame,
            fg_color="transparent",
            segmented_button_selected_color="#06B6D4",
            segmented_button_selected_hover_color="#0891B2",
            segmented_button_unselected_color="#18181B",
            segmented_button_unselected_hover_color="#27272A",
            text_color="#F4F4F5"
        )
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

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
                fg_color="#18181B",
                corner_radius=8,
                border_width=1,
                border_color="#27272A"
            )
            panel_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            title = ctk.CTkLabel(
                panel_frame,
                text=name,
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color="#F4F4F5",
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=15, pady=(10, 2))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="Warte auf Bilddaten...",
                font=ctk.CTkFont(family="Arial", size=12),
                text_color="#71717A",
                fg_color="#09090B",
                corner_radius=6
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))
            self.panels[name] = lbl

            # Bind mouse hover events
            lbl.bind("<Motion>", lambda e, n=name, is_grid=True: self.on_image_hover(e, n, is_grid))
            lbl.bind("<Leave>", self.on_image_leave)

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
                fg_color="#18181B",
                corner_radius=8,
                border_width=1,
                border_color="#27272A"
            )
            panel_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

            title = ctk.CTkLabel(
                panel_frame,
                text=step_name,
                font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
                text_color="#F4F4F5",
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=20, pady=(15, 5))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="Warte auf Bilddaten...",
                font=ctk.CTkFont(family="Arial", size=14),
                text_color="#71717A",
                fg_color="#09090B",
                corner_radius=6
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
            self.panels_full[step_name] = lbl

            # Bind mouse hover events
            lbl.bind("<Motion>", lambda e, n=step_name, is_grid=False: self.on_image_hover(e, n, is_grid))
            lbl.bind("<Leave>", self.on_image_leave)

        # ── TAB 5: Temperatur-Verteilung (Histogramm & Statistiken) ──────────
        hist_tab = self.tabview.tab("5. Temperatur-Verteilung")
        hist_tab.grid_columnconfigure(0, weight=3)  # Canvas nimmt 75% der Breite
        hist_tab.grid_columnconfigure(1, weight=1)  # Zahlenstatistik nimmt 25%
        hist_tab.grid_rowconfigure(0, weight=1)

        # Histogramm-Zeichenfläche
        canvas_panel = ctk.CTkFrame(
            hist_tab,
            fg_color="#18181B",
            corner_radius=8,
            border_width=1,
            border_color="#27272A"
        )
        canvas_panel.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.title_hist = ctk.CTkLabel(
            canvas_panel,
            text="Statistisches Intensitätshistogramm",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color="#F4F4F5",
            anchor="w"
        )
        self.title_hist.pack(fill=ctk.X, padx=20, pady=(15, 5))

        self.hist_container = ctk.CTkFrame(canvas_panel, fg_color="#09090B", corner_radius=6)
        self.hist_container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Statistiken-Seitenleiste im Tab
        stats_panel = ctk.CTkFrame(
            hist_tab,
            fg_color="#18181B",
            corner_radius=8,
            border_width=1,
            border_color="#27272A"
        )
        stats_panel.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        title_stats = ctk.CTkLabel(
            stats_panel,
            text="MESSWERTE & STATISTIK",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            text_color="#06B6D4",
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
                    text_color="#06B6D4",
                    anchor="w"
                )
                self.stats_divider_label.pack(fill=ctk.X, padx=15, pady=(15, 2))
                continue

            lbl_title = ctk.CTkLabel(
                stats_panel,
                text=display_name,
                font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
                text_color="#71717A",
                anchor="w"
            )
            lbl_title.pack(fill=ctk.X, padx=15, pady=(6, 1))
            self.stats_title_labels[key] = lbl_title

            lbl_val = ctk.CTkLabel(
                stats_panel,
                text="--",
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color="#F4F4F5",
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, padx=15, pady=(0, 6))
            self.stats_labels[key] = lbl_val

        # ── TAB 6: Detail-Analyse ──────────────────────────────────────────
        detail_tab = self.tabview.tab("6. Detail-Analyse")
        self.detail_panel = ctk.CTkFrame(detail_tab, fg_color="#18181B", corner_radius=8, border_width=1, border_color="#27272A")
        self.detail_panel.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        self.detail_title = ctk.CTkLabel(
            self.detail_panel,
            text="Detail-Analyse der Messergebnisse",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            text_color="#F4F4F5",
            anchor="w"
        )
        self.detail_title.pack(fill=ctk.X, padx=20, pady=(20, 10))

        self.detail_content_frame = ctk.CTkFrame(self.detail_panel, fg_color="#09090B", corner_radius=6)
        self.detail_content_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Initialen Inhalt zeichnen
        self.update_detail_tab()

    def on_analysis_mode_changed(self, mode: str) -> None:
        """Wird aufgerufen, wenn der Analysemodus gewechselt wird."""
        if mode == "Fuß-Symmetrieanalyse":
            # Diabetes-Dropdown wieder einblenden (vor den Notizen)
            self.patient_notes_entry.pack_forget()
            self.patient_diabetes_opt.pack(fill=ctk.X, padx=12, pady=4)
            self.patient_notes_entry.pack(fill=ctk.X, padx=12, pady=(4, 8))
        else:
            self.patient_diabetes_opt.pack_forget()

        # Titel im Histogramm-Tab anpassen
        if mode == "Fuß-Symmetrieanalyse":
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

        if mode == "Fuß-Symmetrieanalyse":
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
                    text_color="#00B4D8"
                )
                lbl.grid(row=0, column=col_idx, padx=10, pady=12, sticky="w" if col_idx==0 or col_idx==4 else "")

            # Zeilen erstellen
            self.zonal_row_labels = {}
            zones = [("Vorfuß (Zehen / Ballen)", "fore"), ("Mittelfuß (Gewölbe)", "mid"), ("Ferse (Rückfuß)", "heel")]
            for row_idx, (display_name, key) in enumerate(zones, start=1):
                lbl_name = ctk.CTkLabel(self.detail_content_frame, text=display_name, font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#F1F5F9")
                lbl_name.grid(row=row_idx, column=0, padx=10, pady=12, sticky="w")
                
                lbl_l = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color="#F1F5F9")
                lbl_l.grid(row=row_idx, column=1, padx=10, pady=12, sticky="")
                
                lbl_r = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color="#F1F5F9")
                lbl_r.grid(row=row_idx, column=2, padx=10, pady=12, sticky="")
                
                lbl_d = ctk.CTkLabel(self.detail_content_frame, text="--", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#F1F5F9")
                lbl_d.grid(row=row_idx, column=3, padx=10, pady=12, sticky="")
                
                lbl_diag = ctk.CTkLabel(self.detail_content_frame, text="Keine Daten", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#94A3B8")
                lbl_diag.grid(row=row_idx, column=4, padx=10, pady=12, sticky="w")
                
                self.zonal_row_labels[key] = {"l": lbl_l, "r": lbl_r, "d": lbl_d, "diag": lbl_diag}
                
            # Wenn bereits berechnete Zonalwerte vorliegen, diese eintragen
            if hasattr(self, "zonal_stats") and self.zonal_stats.get("left", {}).get("exists") and self.zonal_stats.get("right", {}).get("exists"):
                for key in ["fore", "mid", "heel"]:
                    l_v = self.zonal_stats["left"][key]
                    r_v = self.zonal_stats["right"][key]
                    d_v = abs(l_v - r_v)
                    
                    if d_v >= 15.0:
                        z_diag = "Asymmetrisch (Auffällig)"
                        z_color = "#FF0055"
                    elif d_v >= 10.0:
                        z_diag = "Leichte Abweichung"
                        z_color = "#FFA500"
                    else:
                        z_diag = "Normal (Symmetrisch)"
                        z_color = "#10B981"
                        
                    self.zonal_row_labels[key]["l"].configure(text=f"{l_v:.2f}")
                    self.zonal_row_labels[key]["r"].configure(text=f"{r_v:.2f}")
                    self.zonal_row_labels[key]["d"].configure(text=f"{d_v:.2f}", text_color=z_color)
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

            headers = ["Hotspot ID", "Fläche (Pixel)", "Mittelwert Hitze", "Maximalwert Hitze", "Klinischer Befund"]
            for col_idx, text in enumerate(headers):
                lbl = ctk.CTkLabel(
                    scroll_frame, 
                    text=text, 
                    font=ctk.CTkFont(family="Arial", size=12, weight="bold"), 
                    text_color="#00B4D8"
                )
                lbl.grid(row=0, column=col_idx, padx=10, pady=12, sticky="w" if col_idx==0 or col_idx==4 else "")

            # Wenn Hotspots vorliegen, diese eintragen
            hotspots = getattr(self, "general_hotspots", [])
            if hotspots:
                for idx, hs in enumerate(hotspots, start=1):
                    area = hs["area"]
                    mean_temp = hs["mean_temp"]
                    
                    if area >= 150 or mean_temp >= 180:
                        diag_text = "Akut entzündlich (Kritisch)"
                        diag_color = "#FF0055"
                    elif area >= 50 or mean_temp >= 140:
                        diag_text = "Grenzwertig (Beobachtung)"
                        diag_color = "#FFA500"
                    else:
                        diag_text = "Geringfügig (Unbedenklich)"
                        diag_color = "#10B981"

                    ctk.CTkLabel(scroll_frame, text=f"H#{hs['index']}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#F1F5F9").grid(row=idx, column=0, padx=10, pady=8, sticky="w")
                    ctk.CTkLabel(scroll_frame, text=f"{area:,} px", font=ctk.CTkFont(size=12), text_color="#F1F5F9").grid(row=idx, column=1, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=f"{mean_temp:.2f}", font=ctk.CTkFont(size=12), text_color="#F1F5F9").grid(row=idx, column=2, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=f"{hs['max_temp']:.0f}", font=ctk.CTkFont(size=12), text_color="#F1F5F9").grid(row=idx, column=3, padx=10, pady=8)
                    ctk.CTkLabel(scroll_frame, text=diag_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=diag_color).grid(row=idx, column=4, padx=10, pady=8, sticky="w")
            else:
                lbl_no = ctk.CTkLabel(scroll_frame, text="Keine Hotspots detektiert oder Bild noch nicht geladen.", font=ctk.CTkFont(size=13, slant="italic"), text_color="#94A3B8")
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

    def load_file(self) -> None:
        """Öffnet einen Datei-Dialog und startet die Pipeline bei Dateiauswahl."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Bilddateien", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif")]
        )
        if file_path:
            self.current_filepath = file_path
            self.filename_label.configure(
                text=f"Datei: {os.path.basename(file_path)}",
                text_color="#06B6D4"
            )
            self.process_pipeline()

    def toggle_pipeline_parameters(self) -> None:
        """Blendet die Pipeline-Parameter in der Seitenleiste ein oder aus."""
        if self.parameters_visible:
            self.param_sliders_frame.pack_forget()
            self.toggle_param_btn.configure(text="⚙️ Parameter einblenden")
            self.parameters_visible = False
        else:
            self.param_sliders_frame.pack(fill=ctk.X, padx=12, pady=(4, 8))
            self.toggle_param_btn.configure(text="⚙️ Parameter ausblenden")
            self.parameters_visible = True

    def update_params(self, event=None) -> None:
        """Sammelt alle Slider-Werte und startet die Pipeline neu."""
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
            self.process_pipeline()

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
            
            cv2.putText(annotated, f"VF: {self.zonal_stats['left']['fore']:.1f}", (min_x + 3, z1_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"MF: {self.zonal_stats['left']['mid']:.1f}", (min_x + 3, z2_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"F: {self.zonal_stats['left']['heel']:.1f}", (min_x + 3, max_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

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
            
            cv2.putText(annotated, f"VF: {self.zonal_stats['right']['fore']:.1f}", (min_x + 3, z1_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"MF: {self.zonal_stats['right']['mid']:.1f}", (min_x + 3, z2_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated, f"F: {self.zonal_stats['right']['heel']:.1f}", (min_x + 3, max_y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)

        return annotated

    def process_pipeline(self) -> None:
        """Führt die Analyse-Pipeline aus und aktualisiert alle Panels in allen Tabs."""
        if not self.current_filepath:
            return

        try:
            self.status_label.configure(text="Pipeline läuft...", text_color="#06B6D4")
            self.root.update_idletasks()

            # Parameter laden
            sk = self.sigma_k_slider.get()
            th = self.tophat_slider.get()
            ma = self.min_area_slider.get()
            mc = self.min_circ_slider.get()
            omin = int(self.otsu_min_slider.get())
            omax = int(self.otsu_max_slider.get())
            er = self.erosion_slider.get()
            to = self.temp_offset_slider.get()

            # Bild laden und kalibrieren (Offset addieren)
            img = image_processing.load_thermal_image(self.current_filepath)
            calibrated_img = np.clip(img.astype(np.int16) + int(to), 0, 255).astype(np.uint8)
            self.current_raw_original = calibrated_img

            storage.save_image_step(calibrated_img, "1", "original", self.current_filepath)
            storage.save_data_step(calibrated_img, "1", "original", self.current_filepath)

            # Pipeline ausführen
            diff_img, hotspot_mask = image_processing.run_rust_pipeline(
                calibrated_img, sk, th, ma, mc, omin, omax, er
            )
            self.current_raw_mask = hotspot_mask

            # Body-Maske ableiten
            body_mask_vis = (diff_img > 0).astype(np.uint8) * 255

            # Ergebnisse speichern
            storage.save_image_step(body_mask_vis, "2", "mask", self.current_filepath)
            storage.save_data_step(body_mask_vis, "2", "mask", self.current_filepath)

            storage.save_image_step(diff_img, "3", "local_heat_diff", self.current_filepath)
            storage.save_data_step(diff_img, "3", "local_heat_diff_raw", self.current_filepath)

            storage.save_image_step(hotspot_mask, "4", "dynamic_hotspots", self.current_filepath)
            storage.save_data_step(hotspot_mask, "4", "dynamic_hotspots_raw", self.current_filepath)

            # Panels 1-3 aktualisieren
            self.display_image_in_panel(calibrated_img, "1. Originalbild")
            self.display_image_in_panel(body_mask_vis, "2. Hintergrund-Maske")
            self.display_image_in_panel(diff_img, "3. Lokale Hitze-Differenz")

            # Panel 4: Annotiertes overlay mit BBoxes & Zonen
            if self.analysis_mode_opt.get() == "Fuß-Symmetrieanalyse":
                annotated_overlay = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
            else:
                annotated_overlay = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                
            overlay_rgb = cv2.cvtColor(annotated_overlay, cv2.COLOR_BGR2RGB)
            self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

            # Histogramm & Zonal Update
            self.draw_histogram()

            # Hotspot Count & UI Label
            hotspot_count = int(hotspot_mask.sum()) // 255
            self.update_backend_label()

            if hotspot_count == 0:
                hotspot_color = "#F1F5F9"
                hotspot_text = "0 Pixel (Normal)"
            elif hotspot_count < 150:
                hotspot_color = "#FFA500"
                hotspot_text = f"{hotspot_count} Pixel (Verdacht)"
            else:
                hotspot_color = "#FF0055"
                hotspot_text = f"{hotspot_count} Pixel (Entzündung)"

            self.hotspot_label.configure(
                text=f"Hotspots: {hotspot_text}",
                text_color=hotspot_color
            )

            self.status_label.configure(
                text="Status: ✓ Berechnet",
                text_color="#06B6D4"
            )

        except Exception as e:
            self.status_label.configure(text="Status: Fehler!", text_color="#EF4444")
            self.backend_label.configure(text="Backend: Fehler", text_color="#EF4444")
            self.hotspot_label.configure(text="Hotspots: Fehler", text_color="#EF4444")
            messagebox.showerror("Fehler", f"Pipeline-Fehler:\n{e}")

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
            text_color="#06B6D4"
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

        pil_img = Image.fromarray(rgb_img)

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

    def on_palette_changed(self, value: str) -> None:
        """Wird ausgelöst, wenn die Falschfarbenpalette geändert wird."""
        if self.current_raw_original is not None:
            self.display_image_in_panel(self.current_raw_original, "1. Originalbild")
            
            if self.current_raw_mask is not None:
                body_mask_vis = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) * 255
                if self.analysis_mode_opt.get() == "Fuß-Symmetrieanalyse":
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
            
            is_hotspot = False
            if self.current_raw_mask is not None:
                is_hotspot = self.current_raw_mask[orig_y, orig_x] > 0
                
            hotspot_str = "JA (Entzündung!)" if is_hotspot else "Nein"
            hotspot_color = "#FF0055" if is_hotspot else "#0EA5E9"
            
            self.pixel_info_label.configure(
                text=f"Pixel: X={orig_x}, Y={orig_y}\nWert: {val} | Hotspot: {hotspot_str}",
                text_color=hotspot_color
            )
        else:
            self.pixel_info_label.configure(text="Pixel: außerhalb des Bildes", text_color="#71717A")

    def on_image_leave(self, event) -> None:
        """Setzt den Pixel-Inspektor zurück, wenn die Maus das Bild verlässt."""
        self.pixel_info_label.configure(text="Pixel-Info: --", text_color="#71717A")

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

        # Statistiken
        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        threshold = mean_val + self.sigma_k_slider.get() * std_val

        # Clear previous matplotlib drawing
        for widget in self.hist_container.winfo_children():
            widget.destroy()

        # Matplotlib Figure erstellen (abgestimmt auf neues Dunkelgrau #09090B)
        fig = Figure(figsize=(6, 3.8), dpi=100, facecolor="#09090B")
        ax = fig.add_subplot(111, facecolor="#09090B")

        # Histogramm plotten (mit neuem Cyan #06B6D4)
        ax.hist(pixels, bins=256, range=(0, 256), color="#06B6D4", alpha=0.7, edgecolor="none")
        
        # Hilfslinien
        ax.axvline(mean_val, color="#F4F4F5", linestyle="--", linewidth=1.5, label=f"Mittelwert \u03bc ({mean_val:.1f})")
        ax.axvline(threshold, color="#FF0055", linestyle="-.", linewidth=2.0, label=f"Grenzwert µ+k\u03c3 ({threshold:.1f})")

        # Achsen-Styling
        ax.spines['bottom'].set_color('#27272A')
        ax.spines['top'].set_color('#27272A')
        ax.spines['left'].set_color('#27272A')
        ax.spines['right'].set_color('#27272A')
        ax.tick_params(colors='#71717A', labelsize=8)
        ax.set_xlabel("Pixel-Intensitätswert", color="#F4F4F5", fontsize=9, fontweight="bold")
        ax.set_ylabel("Häufigkeit", color="#F4F4F5", fontsize=9, fontweight="bold")
        ax.legend(facecolor="#18181B", edgecolor="#27272A", labelcolor="#F4F4F5", fontsize=8)
        ax.grid(color="#18181B", linestyle=":", linewidth=0.5)

        fig.tight_layout()

        # Canvas einbetten
        canvas_widget = FigureCanvasTkAgg(fig, master=self.hist_container)
        canvas_widget.draw()
        canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # ── Statistiken-Labels updaten ──────────────────────────────────
        self.stats_labels["pixel_count"].configure(text=f"{len(pixels):,} px")
        self.stats_labels["mean"].configure(text=f"{mean_val:.2f}")
        self.stats_labels["std"].configure(text=f"{std_val:.2f}")
        self.stats_labels["threshold"].configure(text=f"{threshold:.2f}")
        self.stats_labels["max_val"].configure(text=f"{np.max(pixels)}")
        
        hotspot_count = int(self.current_raw_mask.sum()) // 255 if self.current_raw_mask is not None else 0
        self.stats_labels["hotspots"].configure(
            text=f"{hotspot_count} px", 
            text_color="#FF0055" if hotspot_count > 0 else "#F4F4F5"
        )
        
        percentage = (hotspot_count / len(pixels)) * 100 if len(pixels) > 0 else 0
        self.stats_labels["percentage"].configure(
            text=f"{percentage:.3f} %", 
            text_color="#FF0055" if hotspot_count > 0 else "#F4F4F5"
        )

        # ── Titel & Metriken je nach Modus anpassen ──────────────────────────
        mode = self.analysis_mode_opt.get()

        if mode == "Fuß-Symmetrieanalyse":
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
                
                if delta >= 15.0:
                    sym_status = "ASYMMETRIE (Entzündungsverdacht!)"
                    sym_color = "#FF0055"
                else:
                    sym_status = "NORMAL (Symmetrisch)"
                    sym_color = "#10B981"
                    
                self.stats_labels["mean_left"].configure(text=f"{mean_l:.2f}")
                self.stats_labels["mean_right"].configure(text=f"{mean_r:.2f}")
                self.stats_labels["delta"].configure(text=f"{delta:.2f}", text_color=sym_color)
                self.stats_labels["status_symmetry"].configure(text=sym_status, text_color=sym_color)
            else:
                self.stats_labels["mean_left"].configure(text="--")
                self.stats_labels["mean_right"].configure(text="--")
                self.stats_labels["delta"].configure(text="--", text_color="#F4F4F5")
                self.stats_labels["status_symmetry"].configure(text="Keine Daten", text_color="#F4F4F5")

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
                diag_status = "NORMAL (Kein Befund)"
                diag_color = "#10B981"
            elif hotspot_count < 150:
                diag_status = "BEOBACHTUNG (Verdacht)"
                diag_color = "#FFA500"
            else:
                diag_status = "KRITISCH (Entzündung!)"
                diag_color = "#FF0055"
                
            self.stats_labels["mean_left"].configure(text=f"{num_hotspots}")
            self.stats_labels["mean_right"].configure(text=f"{max_area:,} px")
            self.stats_labels["delta"].configure(text=f"{avg_temp:.2f}", text_color=diag_color if num_hotspots > 0 else "#F4F4F5")
            self.stats_labels["status_symmetry"].configure(text=diag_status, text_color=diag_color)

        # Detail-Tab (Tab 6) direkt mitaktualisieren
        self.update_detail_tab()

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
            if self.analysis_mode_opt.get() == "Fuß-Symmetrieanalyse":
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
            sym_status, sym_color = "Keine Daten", "#94A3B8"
            
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
            
            # Patient Info auslesen
            p_name = self.patient_name_entry.get().strip() or "Unbekannt"
            p_age = self.patient_age_entry.get().strip() or "Unbekannt"
            p_diab = self.patient_diabetes_opt.get()
            p_notes = self.patient_notes_entry.get().strip() or "Keine Notizen"
            
            backend_info = image_processing.get_active_backend()
            forced = self.backend_var.get()
            if forced != "auto":
                backend_info = f"{backend_info} (Erzwungen)"

            # Zonal für Report
            l_f = self.zonal_stats.get("left", {}).get("fore", 0.0)
            r_f = self.zonal_stats.get("right", {}).get("fore", 0.0)
            l_m = self.zonal_stats.get("left", {}).get("mid", 0.0)
            r_m = self.zonal_stats.get("right", {}).get("mid", 0.0)
            l_h = self.zonal_stats.get("left", {}).get("heel", 0.0)
            r_h = self.zonal_stats.get("right", {}).get("heel", 0.0)

            # HTML generieren
            self._write_individual_html_report(
                report_filepath, base_name, os.path.basename(self.current_filepath), mean_val, std_val,
                threshold, hotspot_count, len(pixels), mean_l, mean_r, delta, sym_status, sym_color,
                l_f, r_f, l_m, r_m, l_h, r_h, abs(l_f - r_f), abs(l_m - r_m), abs(l_h - r_h),
                p_name, p_age, p_diab, p_notes, backend_info, self.analysis_mode_opt.get()
            )
            
            messagebox.showinfo("Export erfolgreich", f"Der HTML-Bericht wurde erfolgreich gespeichert:\n{report_filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Bericht konnte nicht exportiert werden:\n{e}")

    def _write_individual_html_report(
        self, filepath, base_name, filename, mean, std, thresh, hotspots, foot_pixels,
        mean_l, mean_r, delta, sym_status, sym_color,
        lf, rf, lm, rm, lh, rh, df, dm, dh,
        p_name="Unbekannt", p_age="Unbekannt", p_diab="Nicht angegeben", p_notes="Keine",
        backend_info="auto", analysis_mode="Allgemeine Analyse"
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

        if analysis_mode == "Fuß-Symmetrieanalyse":
            h1_title = "IGNITE // Medizinisches Entzündungsprotokoll (Füße)"
            mean_title = "Mittelwert Fußoberfläche (µ)"
            diabetes_html = f"""
            <div class="meta-item">
                <div class="meta-label">Diabetes-Klassifizierung</div>
                <div class="meta-value">{p_diab}</div>
            </div>"""
            hotspots_percentage_label = f"{hotspots} Pixel ({(hotspots / foot_pixels) * 100 if foot_pixels > 0 else 0:.3f} %)"
            symmetry_or_hotspots_meta = f"""
            <div class="meta-item">
                <div class="meta-label">Symmetrie-Delta (Δ)</div>
                <div class="meta-value" style="color: #06B6D4; font-weight: bold;">{delta:.2f}</div>
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
                        <th>Links (L)</th>
                        <th>Rechts (R)</th>
                        <th>Differenz (Δ)</th>
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
            
            if hotspots == 0:
                diag_status = "NORMAL (Kein Befund)"
                diag_color = "#10B981"
            elif hotspots < 150:
                diag_status = "BEOBACHTUNG (Verdacht)"
                diag_color = "#FFA500"
            else:
                diag_status = "KRITISCH (Entzündung!)"
                diag_color = "#FF0055"
                
            symmetry_or_hotspots_meta = f"""
            <div class="meta-item">
                <div class="meta-label">Anzahl Hotspots</div>
                <div class="meta-value" style="font-weight: bold; color: #06B6D4;">{num_hotspots}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Durchschnittliche Hotspot-Hitze</div>
                <div class="meta-value" style="font-weight: bold; color: #06B6D4;">{avg_temp:.2f}</div>
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
                    if area >= 150 or mean_temp >= 180:
                        diag_text = "Akut entzündlich (Kritisch)"
                        diag_color = "#FF0055"
                    elif area >= 50 or mean_temp >= 140:
                        diag_text = "Grenzwertig (Beobachtung)"
                        diag_color = "#FFA500"
                    else:
                        diag_text = "Geringfügig (Unbedenklich)"
                        diag_color = "#10B981"
                        
                    hotspots_rows += f"""
                    <tr>
                        <td><b>H#{hs['index']}</b></td>
                        <td>{area:,} px</td>
                        <td>{mean_temp:.2f}</td>
                        <td>{hs['max_temp']:.0f}</td>
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
                        <th>Mittelwert Hitze</th>
                        <th>Maximalwert Hitze</th>
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
            color: #06B6D4;
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
            color: #06B6D4;
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
            color: #06B6D4;
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
        
        <h2>Patientendaten</h2>
        <div class="metadata-grid">
            <div class="meta-item">
                <div class="meta-label">Patienten-Name / ID</div>
                <div class="meta-value" style="font-weight: bold; color: #06B6D4;">{p_name}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Alter</div>
                <div class="meta-value">{p_age} Jahre</div>
            </div>
            {diabetes_html}
            <div class="meta-item">
                <div class="meta-label">Klinische Notizen</div>
                <div class="meta-value">{p_notes}</div>
            </div>
        </div>

        <h2>Diagnostische Parameter & globale Statistik</h2>
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
                <div class="meta-label">{mean_title}</div>
                <div class="meta-value">{mean:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Standardabweichung (σ)</div>
                <div class="meta-value">{std:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Hotspot-Detektionsgrenze</div>
                <div class="meta-value">{thresh:.2f} (µ + k*σ)</div>
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

        <div class="footer">
            Entwickelt von Jona Noack | Jugend forscht 2026<br>
            Dieser medizinische Analysebericht wurde automatisch von der IGNITE-Diagnosesoftware generiert.
        </div>
    </div>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

    def _write_batch_summary_html(self, filepath, patients_processed, analysis_mode="Allgemeine Analyse"):
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
            if analysis_mode == "Fuß-Symmetrieanalyse":
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

        if analysis_mode == "Fuß-Symmetrieanalyse":
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
            color: #06B6D4;
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
            color: #06B6D4;
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
                <div class="stat-value" style="color: #06B6D4;">{total}</div>
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
        
        lbl_title = ctk.CTkLabel(progress_win, text="Stapelverarbeitung läuft...", font=ctk.CTkFont(size=14, weight="bold"), text_color="#06B6D4")
        lbl_title.pack(pady=(20, 10))
        
        lbl_status = ctk.CTkLabel(progress_win, text="Initialisiere...", text_color="#F4F4F5")
        lbl_status.pack(pady=5)
        
        pbar = ctk.CTkProgressBar(progress_win, width=300, fg_color="#18181B", progress_color="#06B6D4")
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

        patients_processed = []

        for idx, filename in enumerate(image_files):
            pbar.set((idx + 1) / len(image_files))
            lbl_status.configure(text=f"Verarbeite: {filename} ({idx+1}/{len(image_files)})")
            progress_win.update()
            
            filepath = os.path.join(src_dir, filename)
            
            try:
                img = image_processing.load_thermal_image(filepath)
                calibrated_img = np.clip(img.astype(np.int16) + int(to), 0, 255).astype(np.uint8)
                
                diff_img, hotspot_mask = image_processing.run_rust_pipeline(
                    calibrated_img, sk, th, ma, mc, omin, omax, er
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
                if self.analysis_mode_opt.get() == "Fuß-Symmetrieanalyse":
                    overlay_img = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                else:
                    overlay_img = self.draw_general_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step4_dynamic_hotspots.png"), overlay_img)
                
                body_mask = body_mask_vis > 0
                pixels = calibrated_img[body_mask]
                mean_val = np.mean(pixels) if len(pixels) > 0 else 0.0
                
                if self.analysis_mode_opt.get() == "Fuß-Symmetrieanalyse":
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
                        status_text = "KRITISCH (Entzündung!)"
                        status_color = "#FF0055"
                    elif delta >= 10.0 or hotspot_count > 0 or max_zonal_delta >= 10.0:
                        status_text = "BEOBACHTUNG (Verdacht)"
                        status_color = "#FFA500"
                    else:
                        status_text = "NORMAL (Symmetrisch)"
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
                        status_text = "KRITISCH (Entzündung!)"
                        status_color = "#FF0055"
                    elif hotspot_count > 0:
                        status_text = "BEOBACHTUNG (Verdacht)"
                        status_color = "#FFA500"
                    else:
                        status_text = "NORMAL (Unauffällig)"
                        status_color = "#10B981"
                        
                patient_report_filename = f"report_{base_name}.html"
                patient_report_path = os.path.join(dest_dir, patient_report_filename)
                
                self._write_individual_html_report(
                    patient_report_path, base_name, filename, mean_val, np.std(pixels) if len(pixels)>0 else 0.0,
                    mean_val + sk * np.std(pixels) if len(pixels)>0 else 0.0, hotspot_count, len(pixels),
                    mean_l, mean_r, delta, status_text, status_color, l_fore_m, r_fore_m, l_mid_m, r_mid_m, l_heel_m, r_heel_m,
                    d_fore, d_mid, d_heel, p_name="Patient_"+base_name, backend_info=image_processing.get_active_backend(),
                    analysis_mode=self.analysis_mode_opt.get()
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
        self._write_batch_summary_html(summary_path, patients_processed, self.analysis_mode_opt.get())

        progress_win.destroy()
        
        try:
            os.startfile(os.path.abspath(dest_dir))
        except Exception:
            pass
            
        messagebox.showinfo(
            "Stapelverarbeitung beendet",
            f"Erfolgreich {len(patients_processed)} Wärmebilder verarbeitet!\n\n"
            f"Zentraler Ergebnisbericht: batch_report.html"
        )

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
            text_color="#06B6D4"
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
            "- Fuß-Symmetrieanalyse: Spezifischer klinischer Symmetrievergleich beider Füße (3-Zonen-Modell) "
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
        """Zeigt einen Info-Dialog über das Projekt an."""
        messagebox.showinfo(
            "Über IGNITE",
            "IGNITE – Entzündungsdetektion via Thermografie\n"
            "Version 0.1.0 (Jury-Ready Release)\n\n"
            "Entwickelt von Jona Noack für den Wettbewerb 'Jugend forscht 2026'.\n\n"
            "Ein hocheffizientes Hybridsystem aus Python, Rust-Native Multi-threading und PyTorch GPU-Beschleunigung."
        )