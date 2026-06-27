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
        self.root.title("IGNITE // Jugend forscht – Entzündungsdetektion")
        self.root.geometry("1300x850")
        self.root.minsize(1100, 750)
        self.root.configure(fg_color="#0B0F19")

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
        
        lbl_title = ctk.CTkLabel(top_row, text=label_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#94A3B8")
        lbl_title.pack(side=ctk.LEFT)
        
        val_lbl = ctk.CTkLabel(top_row, text=str(default_val), font=ctk.CTkFont(size=11), text_color="#0EA5E9")
        val_lbl.pack(side=ctk.RIGHT)
        
        slider = ctk.CTkSlider(
            frame, 
            from_=from_, 
            to=to, 
            number_of_steps=int((to - from_)/resolution), 
            fg_color="#1E293B", 
            progress_color="#0EA5E9", 
            button_color="#0EA5E9"
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
        sidebar_frame = ctk.CTkFrame(self.root, width=320, corner_radius=0, fg_color="#0B0F19")
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
            font=ctk.CTkFont(family="Arial", size=28, weight="bold"),
            text_color="#0EA5E9"
        )
        title_lbl.pack(padx=20, pady=pady_title, anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Entzündungsdetektion via Thermografie",
            font=ctk.CTkFont(family="Arial", size=12, slant="italic"),
            text_color="#E2E8F0"
        )
        subtitle_lbl.pack(padx=20, pady=(0, 15), anchor="w")

        # Trennlinie
        divider = ctk.CTkFrame(sidebar_frame, height=2, fg_color="#1E293B")
        divider.pack(fill=ctk.X, padx=20, pady=(0, 15))

        # Scrollbare Steuerleiste für Parameter
        self.sidebar_scroll = ctk.CTkScrollableFrame(
            sidebar_frame, 
            fg_color="transparent",
            scrollbar_button_color="#1E293B",
            scrollbar_button_hover_color="#334155"
        )
        self.sidebar_scroll.pack(fill=ctk.BOTH, expand=True, padx=10, pady=5)

        # Sektion: Patienten-Daten
        patient_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        patient_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        patient_title = ctk.CTkLabel(patient_card, text="PATIENTEN-DATEN", font=ctk.CTkFont(size=11, weight="bold"), text_color="#0EA5E9")
        patient_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.patient_name_entry = ctk.CTkEntry(patient_card, placeholder_text="Name / Patient-ID", font=ctk.CTkFont(size=12), fg_color="#0B0F19", border_color="#334155", height=28)
        self.patient_name_entry.pack(fill=ctk.X, padx=12, pady=4)

        self.patient_age_entry = ctk.CTkEntry(patient_card, placeholder_text="Alter (Jahre)", font=ctk.CTkFont(size=12), fg_color="#0B0F19", border_color="#334155", height=28)
        self.patient_age_entry.pack(fill=ctk.X, padx=12, pady=4)

        self.patient_diabetes_opt = ctk.CTkOptionMenu(
            patient_card, 
            values=["Kein Diabetes", "Diabetes Typ 1", "Diabetes Typ 2"], 
            font=ctk.CTkFont(size=12), 
            fg_color="#0B0F19", 
            button_color="#0EA5E9", 
            button_hover_color="#0284C7", 
            text_color="#E2E8F0", 
            height=28
        )
        self.patient_diabetes_opt.pack(fill=ctk.X, padx=12, pady=4)

        self.patient_notes_entry = ctk.CTkEntry(patient_card, placeholder_text="Klinische Notizen", font=ctk.CTkFont(size=12), fg_color="#0B0F19", border_color="#334155", height=28)
        self.patient_notes_entry.pack(fill=ctk.X, padx=12, pady=(4, 8))

        # Sektion: Steuerung Buttons
        ctrl_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="transparent")
        ctrl_card.pack(fill=ctk.X, pady=(0, 15))

        self.load_btn = ctk.CTkButton(
            ctrl_card,
            text="Wärmebild laden",
            command=self.load_file,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            fg_color="#0EA5E9",
            hover_color="#0284C7",
            text_color="#0B0F19",
            height=38,
            corner_radius=8
        )
        self.load_btn.pack(fill=ctk.X, pady=4)

        self.batch_btn = ctk.CTkButton(
            ctrl_card,
            text="Ordner-Stapelverarbeitung",
            command=self.run_batch_processing,
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            fg_color="transparent",
            text_color="#0EA5E9",
            hover_color="#1E293B",
            border_width=1,
            border_color="#0EA5E9",
            height=34,
            corner_radius=8
        )
        self.batch_btn.pack(fill=ctk.X, pady=4)

        # Sektion: Farbpalette
        palette_lbl = ctk.CTkLabel(
            self.sidebar_scroll,
            text="FARBPALETTE",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#0EA5E9"
        )
        palette_lbl.pack(padx=5, pady=(5, 2), anchor="w")
        
        self.palette_menu = ctk.CTkOptionMenu(
            self.sidebar_scroll,
            values=["Graustufen", "Regenbogen (Jet)", "Inferno", "Heiß (Hot)"],
            command=self.on_palette_changed,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="#1E293B",
            button_color="#0EA5E9",
            button_hover_color="#0284C7",
            text_color="#E2E8F0",
            height=32,
            corner_radius=8
        )
        self.palette_menu.pack(fill=ctk.X, pady=(0, 15))

        # Sektion: Pipeline Parameter
        param_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        param_card.pack(fill=ctk.X, pady=(0, 15), ipady=6)

        param_title = ctk.CTkLabel(param_card, text="PIPELINE-PARAMETER", font=ctk.CTkFont(size=11, weight="bold"), text_color="#0EA5E9")
        param_title.pack(padx=12, pady=(8, 4), anchor="w")

        self.sigma_k_slider, self.sigma_k_val = self.make_slider(param_card, "Threshold-Faktor (sigma_k)", 1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1)
        self.tophat_slider, self.tophat_val = self.make_slider(param_card, "Top-Hat Kernel (%)", 0.01, 0.15, config.DEFAULT_TOPHAT_FACTOR, 0.005)
        self.min_area_slider, self.min_area_val = self.make_slider(param_card, "Min. Fläche (%)", 0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001)
        self.min_circ_slider, self.min_circ_val = self.make_slider(param_card, "Min. Circularity", 0.001, 0.100, config.DEFAULT_MIN_CIRCULARITY, 0.002)
        self.otsu_min_slider, self.otsu_min_val = self.make_slider(param_card, "Otsu Min Schwellenwert", 10.0, 100.0, config.DEFAULT_OTSU_MIN, 1.0)
        self.otsu_max_slider, self.otsu_max_val = self.make_slider(param_card, "Otsu Max Schwellenwert", 50.0, 150.0, config.DEFAULT_OTSU_MAX, 1.0)
        self.erosion_slider, self.erosion_val = self.make_slider(param_card, "Erosions-Faktor", 0.01, 0.20, config.DEFAULT_DIST_EROSION_FACTOR, 0.005)
        self.temp_offset_slider, self.temp_offset_val = self.make_slider(param_card, "Temp-Offset (Kalibrierung)", -50.0, 50.0, 0.0, 0.5)

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
        self.info_card = ctk.CTkFrame(self.sidebar_scroll, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        self.info_card.pack(fill=ctk.X, pady=(0, 15), ipady=8)

        self.filename_label = ctk.CTkLabel(self.info_card, text="Datei: Keine", font=ctk.CTkFont(size=13), text_color="#E2E8F0", anchor="w")
        self.filename_label.pack(fill=ctk.X, padx=15, pady=(10, 4))

        self.backend_label = ctk.CTkLabel(self.info_card, text="Backend: Erkennung...", font=ctk.CTkFont(size=13), text_color="#E2E8F0", anchor="w")
        self.backend_label.pack(fill=ctk.X, padx=15, pady=4)

        self.status_label = ctk.CTkLabel(self.info_card, text="Status: Bereit", font=ctk.CTkFont(size=13, slant="italic"), text_color="#E2E8F0", anchor="w")
        self.status_label.pack(fill=ctk.X, padx=15, pady=4)

        self.hotspot_label = ctk.CTkLabel(self.info_card, text="Hotspots: --", font=ctk.CTkFont(size=14, weight="bold"), text_color="#E2E8F0", anchor="w")
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=4)

        self.pixel_info_label = ctk.CTkLabel(self.info_card, text="Pixel-Info: --", font=ctk.CTkFont(size=12, slant="italic"), text_color="#94A3B8", anchor="w", justify="left")
        self.pixel_info_label.pack(fill=ctk.X, padx=15, pady=(4, 10))

        # Dokumentations-Ordner-Button
        self.open_dir_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="Ergebnisordner öffnen",
            command=self.open_output_dir,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="transparent",
            text_color="#0EA5E9",
            hover_color="#1E293B",
            border_width=1,
            border_color="#0EA5E9",
            height=32,
            corner_radius=8
        )
        self.open_dir_btn.pack(fill=ctk.X, pady=4)

        # HTML-Bericht-Button
        self.export_report_btn = ctk.CTkButton(
            self.sidebar_scroll,
            text="HTML-Bericht exportieren",
            command=self.export_html_report,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="transparent",
            text_color="#0EA5E9",
            hover_color="#1E293B",
            border_width=1,
            border_color="#0EA5E9",
            height=32,
            corner_radius=8
        )
        self.export_report_btn.pack(fill=ctk.X, pady=4)

        # Footer
        footer_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Entwickelt von Jona Noack\nJugend forscht 2026 | v0.1.0",
            font=ctk.CTkFont(family="Arial", size=10),
            text_color="#475569"
        )
        footer_lbl.pack(side=ctk.BOTTOM, pady=15)

        # ── 2. RECHTER HAUPTBEREICH (Tabview) ─────────────────────────────────
        content_frame = ctk.CTkFrame(self.root, fg_color="#0B0F19", corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # CTkTabview erstellen und konfigurieren
        self.tabview = ctk.CTkTabview(
            content_frame,
            fg_color="transparent",
            segmented_button_selected_color="#0EA5E9",
            segmented_button_selected_hover_color="#0284C7",
            segmented_button_unselected_color="#1E293B",
            segmented_button_unselected_hover_color="#334155",
            text_color="#E2E8F0"
        )
        self.tabview.pack(fill=ctk.BOTH, expand=True, padx=15, pady=15)

        # Register Tabs
        self.tabview.add("Gesamtübersicht")
        self.tabview.add("1. Originalbild")
        self.tabview.add("2. Hintergrund-Maske")
        self.tabview.add("3. Lokale Hitze-Differenz")
        self.tabview.add("4. Erkannte Hotspots")
        self.tabview.add("5. Temperatur-Verteilung")
        self.tabview.add("6. Zonale Analyse")

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
                fg_color="#1E293B",
                corner_radius=12,
                border_width=1,
                border_color="#334155"
            )
            panel_frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            title = ctk.CTkLabel(
                panel_frame,
                text=name,
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color="#E2E8F0",
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=15, pady=(10, 2))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="Warte auf Bilddaten...",
                font=ctk.CTkFont(family="Arial", size=12),
                text_color="#94A3B8",
                fg_color="#0B0F19",
                corner_radius=8
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
                fg_color="#1E293B",
                corner_radius=12,
                border_width=1,
                border_color="#334155"
            )
            panel_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

            title = ctk.CTkLabel(
                panel_frame,
                text=step_name,
                font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
                text_color="#E2E8F0",
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=20, pady=(15, 5))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="Warte auf Bilddaten...",
                font=ctk.CTkFont(family="Arial", size=14),
                text_color="#94A3B8",
                fg_color="#0B0F19",
                corner_radius=8
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
            fg_color="#1E293B",
            corner_radius=12,
            border_width=1,
            border_color="#334155"
        )
        canvas_panel.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        title_hist = ctk.CTkLabel(
            canvas_panel,
            text="Statistisches Intensitätshistogramm (Exklusiv über Fußoberfläche)",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color="#E2E8F0",
            anchor="w"
        )
        title_hist.pack(fill=ctk.X, padx=20, pady=(15, 5))

        self.hist_container = ctk.CTkFrame(canvas_panel, fg_color="#0B0F19", corner_radius=8)
        self.hist_container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Statistiken-Seitenleiste im Tab
        stats_panel = ctk.CTkFrame(
            hist_tab,
            fg_color="#1E293B",
            corner_radius=12,
            border_width=1,
            border_color="#334155"
        )
        stats_panel.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        title_stats = ctk.CTkLabel(
            stats_panel,
            text="MESSWERTE & STATISTIK",
            font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
            text_color="#0EA5E9",
            anchor="w"
        )
        title_stats.pack(fill=ctk.X, padx=15, pady=(15, 10))

        # Statistiken-Felder definieren (inklusive Symmetrievergleich)
        self.stats_labels = {}
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
                lbl_title = ctk.CTkLabel(
                    stats_panel,
                    text="KLINISCHE SYMMETRIE (L/R)",
                    font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
                    text_color="#0EA5E9",
                    anchor="w"
                )
                lbl_title.pack(fill=ctk.X, padx=15, pady=(15, 2))
                continue

            lbl_title = ctk.CTkLabel(
                stats_panel,
                text=display_name,
                font=ctk.CTkFont(family="Arial", size=10, weight="bold"),
                text_color="#94A3B8",
                anchor="w"
            )
            lbl_title.pack(fill=ctk.X, padx=15, pady=(6, 1))

            lbl_val = ctk.CTkLabel(
                stats_panel,
                text="--",
                font=ctk.CTkFont(family="Arial", size=13, weight="bold"),
                text_color="#E2E8F0",
                anchor="w"
            )
            lbl_val.pack(fill=ctk.X, padx=15, pady=(0, 6))
            self.stats_labels[key] = lbl_val

        # ── TAB 6: Zonale Analyse ──────────────────────────────────────────
        zonal_tab = self.tabview.tab("6. Zonale Analyse")
        zonal_panel = ctk.CTkFrame(zonal_tab, fg_color="#1E293B", corner_radius=12, border_width=1, border_color="#334155")
        zonal_panel.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        title_zonal = ctk.CTkLabel(
            zonal_panel,
            text="Detaillierter Zonen-Symmetrie-Vergleich (3-Zonen-Modell)",
            font=ctk.CTkFont(family="Arial", size=15, weight="bold"),
            text_color="#E2E8F0",
            anchor="w"
        )
        title_zonal.pack(fill=ctk.X, padx=20, pady=(20, 10))

        table_frame = ctk.CTkFrame(zonal_panel, fg_color="#0B0F19", corner_radius=8)
        table_frame.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))

        table_frame.grid_columnconfigure(0, weight=2)
        table_frame.grid_columnconfigure(1, weight=1)
        table_frame.grid_columnconfigure(2, weight=1)
        table_frame.grid_columnconfigure(3, weight=1)
        table_frame.grid_columnconfigure(4, weight=2)

        # Headers
        headers = ["Anatomische Zone", "Links (L)", "Rechts (R)", "Differenz (\u0394)", "Diagnose"]
        for col_idx, text in enumerate(headers):
            lbl = ctk.CTkLabel(table_frame, text=text, font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#0EA5E9")
            lbl.grid(row=0, column=col_idx, padx=10, pady=12, sticky="w" if col_idx==0 or col_idx==4 else "")

        # Rows
        self.zonal_row_labels = {}
        zones = [("Vorfuß (Zehen / Ballen)", "fore"), ("Mittelfuß (Gewölbe)", "mid"), ("Ferse (Rückfuß)", "heel")]
        for row_idx, (display_name, key) in enumerate(zones, start=1):
            lbl_name = ctk.CTkLabel(table_frame, text=display_name, font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#E2E8F0")
            lbl_name.grid(row=row_idx, column=0, padx=10, pady=12, sticky="w")
            
            lbl_l = ctk.CTkLabel(table_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color="#E2E8F0")
            lbl_l.grid(row=row_idx, column=1, padx=10, pady=12, sticky="")
            
            lbl_r = ctk.CTkLabel(table_frame, text="--", font=ctk.CTkFont(family="Arial", size=12), text_color="#E2E8F0")
            lbl_r.grid(row=row_idx, column=2, padx=10, pady=12, sticky="")
            
            lbl_d = ctk.CTkLabel(table_frame, text="--", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#E2E8F0")
            lbl_d.grid(row=row_idx, column=3, padx=10, pady=12, sticky="")
            
            lbl_diag = ctk.CTkLabel(table_frame, text="Keine Daten", font=ctk.CTkFont(family="Arial", size=12, weight="bold"), text_color="#94A3B8")
            lbl_diag.grid(row=row_idx, column=4, padx=10, pady=12, sticky="w")
            
            self.zonal_row_labels[key] = {"l": lbl_l, "r": lbl_r, "d": lbl_d, "diag": lbl_diag}

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
                text_color="#0EA5E9"
            )
            self.process_pipeline()

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
            self.status_label.configure(text="Pipeline läuft...", text_color="#0EA5E9")
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
            annotated_overlay = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
            overlay_rgb = cv2.cvtColor(annotated_overlay, cv2.COLOR_BGR2RGB)
            self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

            # Histogramm & Zonal Update
            self.draw_histogram()

            # Hotspot Count & UI Label
            hotspot_count = int(hotspot_mask.sum()) // 255
            self.update_backend_label()

            if hotspot_count == 0:
                hotspot_color = "#E2E8F0"
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
                text_color="#0EA5E9"
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
            text_color="#0EA5E9"
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
                overlay_img = self.draw_foot_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)
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
            self.pixel_info_label.configure(text="Pixel: außerhalb des Bildes", text_color="#94A3B8")

    def on_image_leave(self, event) -> None:
        """Setzt den Pixel-Inspektor zurück, wenn die Maus das Bild verlässt."""
        self.pixel_info_label.configure(text="Pixel-Info: --", text_color="#94A3B8")

    def draw_histogram(self) -> None:
        """Zeichnet das statistische Matplotlib-Histogramm exklusiv über der Fußfläche."""
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

        # Matplotlib Figure erstellen
        fig = Figure(figsize=(6, 3.8), dpi=100, facecolor="#0B0F19")
        ax = fig.add_subplot(111, facecolor="#0B0F19")

        # Histogramm plotten
        ax.hist(pixels, bins=256, range=(0, 256), color="#0EA5E9", alpha=0.7, edgecolor="none")
        
        # Hilfslinien
        ax.axvline(mean_val, color="#E2E8F0", linestyle="--", linewidth=1.5, label=f"Mittelwert \u03bc ({mean_val:.1f})")
        ax.axvline(threshold, color="#FF0055", linestyle="-.", linewidth=2.0, label=f"Grenzwert µ+k\u03c3 ({threshold:.1f})")

        # Achsen-Styling
        ax.spines['bottom'].set_color('#334155')
        ax.spines['top'].set_color('#334155')
        ax.spines['left'].set_color('#334155')
        ax.spines['right'].set_color('#334155')
        ax.tick_params(colors='#94A3B8', labelsize=8)
        ax.set_xlabel("Pixel-Intensitätswert", color="#E2E8F0", fontsize=9, fontweight="bold")
        ax.set_ylabel("Häufigkeit", color="#E2E8F0", fontsize=9, fontweight="bold")
        ax.legend(facecolor="#1E293B", edgecolor="#334155", labelcolor="#E2E8F0", fontsize=8)
        ax.grid(color="#1E293B", linestyle=":", linewidth=0.5)

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
            text_color="#FF0055" if hotspot_count > 0 else "#E2E8F0"
        )
        
        percentage = (hotspot_count / len(pixels)) * 100 if len(pixels) > 0 else 0
        self.stats_labels["percentage"].configure(
            text=f"{percentage:.3f} %", 
            text_color="#FF0055" if hotspot_count > 0 else "#E2E8F0"
        )

        # ── Symmetrievergleich berechnen ──────────────────────────────────
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
            self.stats_labels["delta"].configure(text="--", text_color="#E2E8F0")
            self.stats_labels["status_symmetry"].configure(text="Keine Daten", text_color="#E2E8F0")

        # ── ZONEN TABELLE AKTUALISIEREN ──────────────────────────────────
        if self.zonal_stats.get("left", {}).get("exists") and self.zonal_stats.get("right", {}).get("exists"):
            for key in ["fore", "mid", "heel"]:
                l_v = self.zonal_stats["left"][key]
                r_v = self.zonal_stats["right"][key]
                d_v = abs(l_v - r_v)
                
                if d_v >= 15.0:
                    z_diag = "ASymmetrisch (Auffällig)"
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

    def save_active_view(self) -> None:
        """Exportiert das aktuell angezeigte Bild des aktiven Tabs als PNG."""
        tab_name = self.tabview.get()
        
        if tab_name in ("Gesamtübersicht", "5. Temperatur-Verteilung", "6. Zonale Analyse"):
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
            img_to_save = self.draw_foot_annotations(self.current_raw_original, body_mask_vis, self.current_raw_mask)

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
                messagebox.showerror("Fehler", "Fußmaske nicht gefunden. Bericht kann nicht erstellt werden.")
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
            
            hotspot_color = "#FF0055" if hotspot_count > 0 else "#E2E8F0"
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
                p_name, p_age, p_diab, p_notes, backend_info
            )
            
            messagebox.showinfo("Export erfolgreich", f"Der HTML-Bericht wurde erfolgreich gespeichert:\n{report_filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Bericht konnte nicht exportiert werden:\n{e}")

    def _write_individual_html_report(
        self, filepath, base_name, filename, mean, std, thresh, hotspots, foot_pixels,
        mean_l, mean_r, delta, sym_status, sym_color,
        lf, rf, lm, rm, lh, rh, df, dm, dh,
        p_name="Unbekannt", p_age="Unbekannt", p_diab="Nicht angegeben", p_notes="Keine",
        backend_info="auto"
    ):
        """Hilfsfunktion zum Schreiben einer detailreichen HTML-Berichtsdatei."""
        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE - Analysebericht ({base_name})</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0F172A;
            color: #F8FAFC;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #1E293B;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            border: 1px solid #334155;
        }}
        h1 {{
            color: #38BDF8;
            margin-top: 0;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
            font-size: 28px;
        }}
        h2 {{
            color: #E2E8F0;
            margin-top: 30px;
            font-size: 20px;
            border-left: 4px solid #0EA5E9;
            padding-left: 10px;
        }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
            background-color: #0F172A;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #334155;
        }}
        .meta-item {{
            display: flex;
            flex-direction: column;
        }}
        .meta-label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #38BDF8;
            font-weight: bold;
            margin-bottom: 4px;
        }}
        .meta-value {{
            font-size: 15px;
            color: #E2E8F0;
        }}
        .image-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: #0F172A;
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #334155;
            text-align: center;
        }}
        .card h3 {{
            color: #94A3B8;
            margin-top: 0;
            margin-bottom: 12px;
            font-size: 14px;
            text-align: left;
        }}
        .card img {{
            max-width: 100%;
            border-radius: 8px;
            border: 1px solid #1E293B;
            background-color: #020617;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            background-color: #0F172A;
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #1E293B;
            color: #38BDF8;
            font-weight: bold;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #64748B;
            border-top: 1px solid #334155;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IGNITE // Medizinisches Entzündungsprotokoll</h1>
        
        <h2>Patientendaten</h2>
        <div class="metadata-grid">
            <div class="meta-item">
                <div class="meta-label">Patienten-Name / ID</div>
                <div class="meta-value" style="font-weight: bold; color: #38BDF8;">{p_name}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Alter</div>
                <div class="meta-value">{p_age} Jahre</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Diabetes-Klassifizierung</div>
                <div class="meta-value">{p_diab}</div>
            </div>
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
                <div class="meta-label">Mittelwert Fußoberfläche (µ)</div>
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
                <div class="meta-value" style="color: {sym_color}; font-weight: bold;">{hotspots} Pixel ({(hotspots / foot_pixels) * 100 if foot_pixels > 0 else 0:.3f} %)</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Symmetrie-Delta (Δ)</div>
                <div class="meta-value" style="color: {sym_color}; font-weight: bold;">{delta:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Klinischer Symmetriestatus</div>
                <div class="meta-value" style="color: {sym_color}; font-weight: bold;">{sym_status}</div>
            </div>
        </div>

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
                    <td style="color: {'#FF0055' if df>=15 else ('#FFA500' if df>=10 else '#10B981')}; font-weight: bold;">
                        {('Auffällig (Inflammationsverdacht)' if df>=15 else ('Grenzwertig' if df>=10 else 'Normal'))}
                    </td>
                </tr>
                <tr>
                    <td><b>Mittelfuß (Gewölbe)</b></td>
                    <td>{lm:.2f}</td>
                    <td>{rm:.2f}</td>
                    <td>{dm:.2f}</td>
                    <td style="color: {'#FF0055' if dm>=15 else ('#FFA500' if dm>=10 else '#10B981')}; font-weight: bold;">
                        {('Auffällig (Inflammationsverdacht)' if dm>=15 else ('Grenzwertig' if dm>=10 else 'Normal'))}
                    </td>
                </tr>
                <tr>
                    <td><b>Ferse (Rückfuß)</b></td>
                    <td>{lh:.2f}</td>
                    <td>{rh:.2f}</td>
                    <td>{dh:.2f}</td>
                    <td style="color: {'#FF0055' if dh>=15 else ('#FFA500' if dh>=10 else '#10B981')}; font-weight: bold;">
                        {('Auffällig (Inflammationsverdacht)' if dh>=15 else ('Grenzwertig' if dh>=10 else 'Normal'))}
                    </td>
                </tr>
            </tbody>
        </table>

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
                <h3>4. Erkannte Hotspots (Overlay mit BBoxes & Zonen)</h3>
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

    def _write_batch_summary_html(self, filepath, patients_processed):
        """Schreibt das HTML Dashboard für die Stapelverarbeitung."""
        total = len(patients_processed)
        critical = sum(1 for p in patients_processed if "KRITISCH" in p["status"])
        warn = sum(1 for p in patients_processed if "BEOBACHTUNG" in p["status"])
        normal = total - critical - warn

        rows_html = ""
        for p in patients_processed:
            rows_html += f"""
            <tr>
                <td><b>{p['filename']}</b></td>
                <td>{p['hotspots']} px</td>
                <td>{p['delta']:.2f}</td>
                <td>{p['max_zonal_delta']:.2f}</td>
                <td><span class="status-badge" style="background-color: {p['color']};">{p['status']}</span></td>
                <td><a class="report-link" href="{p['report']}" target="_blank">Bericht öffnen ↗</a></td>
            </tr>"""

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE - Stapelverarbeitungs-Dashboard</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0F172A;
            color: #F8FAFC;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #1E293B;
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            border: 1px solid #334155;
        }}
        h1 {{
            color: #38BDF8;
            margin-top: 0;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
            font-size: 28px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background-color: #0F172A;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border: 1px solid #334155;
        }}
        .stat-label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #94A3B8;
            margin-bottom: 5px;
            font-weight: bold;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #0F172A;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #334155;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #1E293B;
            color: #38BDF8;
            font-weight: bold;
        }}
        .status-badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            color: #0F172A;
        }}
        .report-link {{
            color: #38BDF8;
            text-decoration: none;
            font-weight: bold;
        }}
        .report-link:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #64748B;
            border-top: 1px solid #334155;
            padding-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IGNITE // Stapelverarbeitungs-Übersicht</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Gesamt Verarbeitet</div>
                <div class="stat-value" style="color: #38BDF8;">{total}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Entzündung (Kritisch)</div>
                <div class="stat-value" style="color: #FF0055;">{critical}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Beobachtung (Verdacht)</div>
                <div class="stat-value" style="color: #FFA500;">{warn}</div>
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
                    <th>Globales Delta (Δ)</th>
                    <th>Max. Zonal-Delta</th>
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
        progress_win.configure(fg_color="#0B0F19")
        progress_win.transient(self.root)
        
        lbl_title = ctk.CTkLabel(progress_win, text="Stapelverarbeitung läuft...", font=ctk.CTkFont(size=14, weight="bold"), text_color="#0EA5E9")
        lbl_title.pack(pady=(20, 10))
        
        lbl_status = ctk.CTkLabel(progress_win, text="Initialisiere...", text_color="#E2E8F0")
        lbl_status.pack(pady=5)
        
        pbar = ctk.CTkProgressBar(progress_win, width=300, fg_color="#1E293B", progress_color="#0EA5E9")
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
                overlay_img = self.draw_foot_annotations(calibrated_img, body_mask_vis, hotspot_mask)
                cv2.imwrite(os.path.join(steps_dir, f"{base_name}_step4_dynamic_hotspots.png"), overlay_img)
                
                body_mask = body_mask_vis > 0
                pixels = calibrated_img[body_mask]
                mean_val = np.mean(pixels) if len(pixels) > 0 else 0.0
                
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
                    
                patient_report_filename = f"report_{base_name}.html"
                patient_report_path = os.path.join(dest_dir, patient_report_filename)
                
                self._write_individual_html_report(
                    patient_report_path, base_name, filename, mean_val, np.std(pixels) if len(pixels)>0 else 0.0,
                    mean_val + sk * np.std(pixels) if len(pixels)>0 else 0.0, hotspot_count, len(pixels),
                    mean_l, mean_r, delta, status_text, status_color, l_fore_m, r_fore_m, l_mid_m, r_mid_m, l_heel_m, r_heel_m,
                    d_fore, d_mid, d_heel, p_name="Patient_"+base_name, backend_info=image_processing.get_active_backend()
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
        self._write_batch_summary_html(summary_path, patients_processed)

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
        self.info_win.configure(fg_color="#0B0F19")
        
        self.info_win.transient(self.root)
        self.info_win.after(100, lambda: self.info_win.focus_force())
        
        title_lbl = ctk.CTkLabel(
            self.info_win,
            text="IGNITE – Entzündungsdetektion",
            font=ctk.CTkFont(family="Arial", size=20, weight="bold"),
            text_color="#0EA5E9"
        )
        title_lbl.pack(pady=(20, 10))
        
        txt = ctk.CTkTextbox(
            self.info_win,
            fg_color="#1E293B",
            text_color="#E2E8F0",
            font=ctk.CTkFont(family="Arial", size=13),
            wrap="word"
        )
        txt.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        info_text = (
            "IGNITE ist eine Software zur automatisierten Entzündungsdetektion (Hotspot-Erkennung) "
            "in thermografischen Fußaufnahmen zur Früherkennung des Diabetischen Fußsyndroms.\n\n"
            "Die mathematische Pipeline besteht aus 5 Stufen:\n\n"
            "1. Dynamische Kernel:\n"
            "Berechnet ungerade Strukturierungselemente basierend auf der Bildbreite (Standard: tophat_factor % für Top-Hat, 2 % für Geometriefilter).\n\n"
            "2. Adaptive Body-Mask:\n"
            "Otsu-Binarisierung mit Sicherheits-Schwellenwert-Eingrenzung auf den Bereich [otsu_min, otsu_max], um auch kältere Extremitäten (Zehen) zuverlässig zu erfassen. Es folgt eine euklidische Distanztransformation (Chamfer-3-4-Metrik) und eine adaptive Erosion zur Rauschelminierung.\n\n"
            "3. Top-Hat-Transformation:\n"
            "Führt ein morphologisches Opening durch und subtrahiert dieses vom Originalbild, um lokale Helligkeitsspitzen (Hitze) präzise zu isolieren.\n\n"
            "4. Statistischer Schwellenwert (µ + k*σ + Absoluthitze-Filter):\n"
            "Berechnet Mittelwert µ und Standardabweichung σ der Top-Hat-Differenz exklusiv über Körper-Pixel. Filtert mit einem Schwellenwert von µ + k*σ und verlangt zusätzlich, dass die absolute Helligkeit über der durchschnittlichen Fußtemperatur liegt. Dies eliminiert Falsch-Positive an gesunden Zehen vollständig.\n\n"
            "5. Geometrischer Rauschfilter:\n"
            "Connected-Component-Analyse. Filtert Komponenten nach Mindestfläche und Circularity zur Entfernung von Punktrauschen und Linienartefakten.\n\n"
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