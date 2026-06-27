"""gui.py – CustomTkinter-Frontend für das Ignite Entzündungsdetektions-System.

Dieses Modul stellt das grafische Benutzer-Interface des Jugend-forscht-Projekts
"Ignite" bereit. Die Bildverarbeitung wird vollständig an das native Rust-Core-Modul
`ignite_core` oder die GPU-beschleunigte PyTorch-Pipeline delegiert.

Architektur:
    IgniteApp (CustomTkinter) → image_processing.py → ignite_core.pyd (Rust)
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
import numpy as np
from PIL import Image
import customtkinter as ctk

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
        self.root.geometry("1200x800")
        self.root.minsize(1050, 700)
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

    def setup_ui(self) -> None:
        """Erstellt das moderne Interface mit Sidebar und Tabview-Bildanzeige."""
        # Haupt-Grid
        self.root.grid_columnconfigure(0, weight=0)  # Sidebar behält feste Breite
        self.root.grid_columnconfigure(1, weight=1)  # Tab-Inhalt dehnt sich aus
        self.root.grid_rowconfigure(0, weight=1)

        # ── 1. LINKE SEITENLEISTE ─────────────────────────────────────────────
        sidebar_frame = ctk.CTkFrame(self.root, width=280, corner_radius=0, fg_color="#0B0F19")
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
        subtitle_lbl.pack(padx=20, pady=(0, 20), anchor="w")

        # Trennlinie
        divider = ctk.CTkFrame(sidebar_frame, height=2, fg_color="#1E293B")
        divider.pack(fill=ctk.X, padx=20, pady=(0, 20))

        # Sektion: Steuerung
        ctrl_title = ctk.CTkLabel(
            sidebar_frame,
            text="STEUERUNG",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#0EA5E9"
        )
        ctrl_title.pack(padx=20, pady=(0, 8), anchor="w")

        self.load_btn = ctk.CTkButton(
            sidebar_frame,
            text="Wärmebild laden",
            command=self.load_file,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            fg_color="#0EA5E9",
            hover_color="#0284C7",
            text_color="#0B0F19",
            height=40,
            corner_radius=8
        )
        self.load_btn.pack(fill=ctk.X, padx=20, pady=(0, 20))

        # Sektion: Farbpalette
        palette_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="FARBPALETTE (FALSCHFARBEN)",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#0EA5E9"
        )
        palette_lbl.pack(padx=20, pady=(0, 6), anchor="w")
        
        self.palette_menu = ctk.CTkOptionMenu(
            sidebar_frame,
            values=["Graustufen", "Regenbogen (Jet)", "Inferno", "Heiß (Hot)"],
            command=self.on_palette_changed,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="#1E293B",
            button_color="#0EA5E9",
            button_hover_color="#0284C7",
            text_color="#E2E8F0",
            height=35,
            corner_radius=8
        )
        self.palette_menu.pack(fill=ctk.X, padx=20, pady=(0, 20))

        # Sektion: Analyse-Info & Status
        info_title = ctk.CTkLabel(
            sidebar_frame,
            text="ANALYSE-DETAILS",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#0EA5E9"
        )
        info_title.pack(padx=20, pady=(0, 8), anchor="w")

        # Informations-Karte (Slate Gray background)
        self.info_card = ctk.CTkFrame(sidebar_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        self.info_card.pack(fill=ctk.X, padx=20, pady=(0, 15), ipady=8)

        self.filename_label = ctk.CTkLabel(
            self.info_card,
            text="Datei: Keine",
            font=ctk.CTkFont(family="Arial", size=13),
            text_color="#E2E8F0",
            anchor="w"
        )
        self.filename_label.pack(fill=ctk.X, padx=15, pady=(10, 4))

        self.backend_label = ctk.CTkLabel(
            self.info_card,
            text="Backend: Erkennung...",
            font=ctk.CTkFont(family="Arial", size=13),
            text_color="#E2E8F0",
            anchor="w"
        )
        self.backend_label.pack(fill=ctk.X, padx=15, pady=4)

        self.status_label = ctk.CTkLabel(
            self.info_card,
            text="Status: Bereit",
            font=ctk.CTkFont(family="Arial", size=13, slant="italic"),
            text_color="#E2E8F0",
            anchor="w"
        )
        self.status_label.pack(fill=ctk.X, padx=15, pady=4)

        self.hotspot_label = ctk.CTkLabel(
            self.info_card,
            text="Hotspots: --",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color="#E2E8F0",
            anchor="w"
        )
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=4)

        self.pixel_info_label = ctk.CTkLabel(
            self.info_card,
            text="Pixel-Info: --",
            font=ctk.CTkFont(family="Arial", size=12, slant="italic"),
            text_color="#94A3B8",
            anchor="w",
            justify="left"
        )
        self.pixel_info_label.pack(fill=ctk.X, padx=15, pady=(4, 10))

        # Dokumentations-Ordner-Button
        self.open_dir_btn = ctk.CTkButton(
            sidebar_frame,
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
        self.open_dir_btn.pack(fill=ctk.X, padx=20, pady=(0, 10))

        # HTML-Bericht-Button
        self.export_report_btn = ctk.CTkButton(
            sidebar_frame,
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
        self.export_report_btn.pack(fill=ctk.X, padx=20, pady=(0, 10))

        # Info-Button
        self.info_btn = ctk.CTkButton(
            sidebar_frame,
            text="Info & Funktionsweise",
            command=self.show_info_window,
            font=ctk.CTkFont(family="Arial", size=13),
            fg_color="transparent",
            text_color="#0EA5E9",
            hover_color="#1E293B",
            border_width=1,
            border_color="#0EA5E9",
            height=32,
            corner_radius=8
        )
        self.info_btn.pack(fill=ctk.X, padx=20, pady=(0, 20))

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

        # ── TAB 6: 5. Temperatur-Verteilung (Histogramm & Statistiken) ────────
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

        self.hist_canvas = ctk.CTkCanvas(canvas_panel, bg="#0B0F19", highlightthickness=0)
        self.hist_canvas.pack(fill=ctk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.hist_canvas.bind("<Configure>", lambda e: self.draw_histogram())

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
            ("Hotspot-Grenze (µ + 3σ)", "threshold"),
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

    def process_pipeline(self) -> None:
        """Führt die Analyse-Pipeline aus und aktualisiert alle Panels in allen Tabs."""
        if not self.current_filepath:
            return

        try:
            # ── Schritt 1: Wärmebild laden ─────────────────────────────────
            self.status_label.configure(text="Bild wird geladen...", text_color="#0EA5E9")
            self.root.update_idletasks()

            img = image_processing.load_thermal_image(self.current_filepath)
            self.current_raw_original = img
            storage.save_image_step(img, "1", "original", self.current_filepath)
            storage.save_data_step(img, "1", "original", self.current_filepath)

            # ── Schritt 2: Pipeline ausführen (Rust-Core, GPU oder Fallback) ──
            self.status_label.configure(text="Pipeline läuft...", text_color="#0EA5E9")
            self.root.update_idletasks()

            diff_img, hotspot_mask = image_processing.run_rust_pipeline(img)
            self.current_raw_mask = hotspot_mask

            # ── Schritt 3: Body-Maske für Panel 2 ableiten ────────────────
            body_mask_vis = (diff_img > 0).astype(np.uint8) * 255

            # ── Schritt 4: Ergebnisse speichern (Jury-Dokumentation) ───────
            storage.save_image_step(body_mask_vis, "2", "mask", self.current_filepath)
            storage.save_data_step(body_mask_vis, "2", "mask", self.current_filepath)

            storage.save_image_step(diff_img, "3", "local_heat_diff", self.current_filepath)
            storage.save_data_step(diff_img, "3", "local_heat_diff_raw", self.current_filepath)

            storage.save_image_step(hotspot_mask, "4", "dynamic_hotspots", self.current_filepath)
            storage.save_data_step(hotspot_mask, "4", "dynamic_hotspots_raw", self.current_filepath)

            # ── Schritt 5: Panels 1–3 aktualisieren ───────────────────────
            self.display_image_in_panel(img, "1. Originalbild")
            self.display_image_in_panel(body_mask_vis, "2. Hintergrund-Maske")
            self.display_image_in_panel(diff_img, "3. Lokale Hitze-Differenz")

            # ── Schritt 6: Panel 4 – Farb-Overlay mit roten Hotspots ───────
            palette = self.palette_menu.get()
            overlay_img = image_processing.create_hotspot_overlay(img, hotspot_mask, palette)
            overlay_rgb = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB)
            self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

            # ── Schritt 7: Histogramm zeichnen ─────────────────────────────
            self.draw_histogram()

            # ── Schritt 8: Status- & Statistik-Updates ─────────────────────
            hotspot_count = int(hotspot_mask.sum()) // 255
            self.update_backend_label()

            # Hotspot-Zähler farblich hervorheben (Pure Neon Red #FF0055)
            if hotspot_count == 0:
                hotspot_color = "#E2E8F0"
                hotspot_text = "0 Pixel (Keine Entzündung)"
            elif hotspot_count < 150:
                hotspot_color = "#FF5E8E"
                hotspot_text = f"{hotspot_count} Pixel (Verdacht)"
            else:
                hotspot_color = "#FF0055"
                hotspot_text = f"{hotspot_count} Pixel (Entzündung)"

            self.hotspot_label.configure(
                text=f"Hotspots: {hotspot_text}",
                text_color=hotspot_color
            )

            self.status_label.configure(
                text="Status: ✓ Fertig",
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

        # Falls Backend erzwungen wird, kennzeichnen
        forced = self.backend_var.get()
        if forced != "auto":
            backend_disp = f"{backend_disp} (Erzwungen)"

        self.backend_label.configure(
            text=f"Backend: {backend_disp}",
            text_color="#0EA5E9"
        )

    def display_image_in_panel(self, cv_img: np.ndarray, panel_name: str, update_cache: bool = True) -> None:
        """Zeigt ein OpenCV-Bild in dem Grid-Panel und dem Full-size-Panel an.

        Skaliert das Bild jeweils proportional an die Containergrößen an.
        """
        if update_cache:
            self.current_images[panel_name] = cv_img

        # Farbkonvertierung basierend auf der gewählten Farbpalette für das Originalbild
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
            else:  # Graustufen
                rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
        else:
            # Falls Graustufen, in RGB konvertieren
            if len(cv_img.shape) == 2:
                rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
            else:
                rgb_img = cv_img

        pil_img = Image.fromarray(rgb_img)

        # ── 1. Im Grid-Label darstellen ──────────────────────────────────────
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

        # ── 2. Im Fullsize-Label darstellen ──────────────────────────────────
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

        # Pipeline sofort neu berechnen, falls bereits ein Bild geladen ist
        if self.current_filepath:
            self.process_pipeline()

    def on_palette_changed(self, value: str) -> None:
        """Wird ausgelöst, wenn die Falschfarbenpalette geändert wird."""
        if self.current_raw_original is not None:
            # 1. Originalbild neu zeichnen (mit neuer Palette)
            self.display_image_in_panel(self.current_raw_original, "1. Originalbild")
            
            # 2. Hotspots-Overlay neu zeichnen (mit neuer Palette unterlegt)
            if self.current_raw_mask is not None:
                overlay_img = image_processing.create_hotspot_overlay(
                    self.current_raw_original, 
                    self.current_raw_mask, 
                    value
                )
                overlay_rgb = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB)
                self.display_image_in_panel(overlay_rgb, "4. Erkannte Hotspots (Rust)")

    def on_image_hover(self, event, panel_name: str, is_grid: bool) -> None:
        """Digitales Fadenkreuz / Pixel-Inspektor.

        Berechnet die relative Position der Maus auf dem Bild und zeigt den
        exakten Original-Pixelwert sowie den Hotspot-Status in der Seitenleiste an.
        """
        if self.current_raw_original is None:
            return

        lbl = self.panels[panel_name] if is_grid else self.panels_full[panel_name]
        lbl_w = lbl.winfo_width()
        lbl_h = lbl.winfo_height()
        
        orig_h, orig_w = self.current_raw_original.shape[:2]
        
        # Padding analog zur display_image_in_panel Logik
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
            
            # Hotspot-Prüfung
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
        """Zeichnet das statistische Histogramm der Fuß-Intensitäten auf dem Canvas."""
        if self.current_raw_original is None:
            return

        canvas = self.hist_canvas
        canvas.delete("all")

        w = canvas.winfo_width()
        h = canvas.winfo_height()

        # Fallback falls noch nicht fertig gerendert
        if w <= 10:
            w, h = 600, 380

        margin_left = 60
        margin_bottom = 40
        margin_top = 25
        margin_right = 20

        plot_w = w - margin_left - margin_right
        plot_h = h - margin_top - margin_bottom

        # Fuß-Körpermaske besorgen
        body_mask = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) if "2. Hintergrund-Maske" in self.current_images else None
        if body_mask is None or np.sum(body_mask) == 0:
            return

        img = self.current_raw_original
        pixels = img[body_mask > 0]
        if len(pixels) == 0:
            return

        # Histogramm berechnen
        hist = cv2.calcHist([img], [0], body_mask, [256], [0, 256]).flatten()
        max_val = max(hist)
        if max_val == 0:
            max_val = 1

        # Statistiken
        mean_val = np.mean(pixels)
        std_val = np.std(pixels)
        threshold = mean_val + 3.0 * std_val

        # ── 1. Gitter und Achsen beschriften ─────────────────────────────────
        # Y-Gitterlinien (Häufigkeit)
        for i in range(5):
            y = margin_top + plot_h - (i / 4) * plot_h
            canvas.create_line(margin_left, y, margin_left + plot_w, y, fill="#1E293B", dash=(2, 2))
            val_y = int((i / 4) * max_val)
            canvas.create_text(margin_left - 10, y, text=str(val_y), fill="#94A3B8", font=("Arial", 9), anchor="e")

        # X-Gitterlinien (Intensität / Temperatur)
        x_ticks = [0, 50, 100, 150, 200, 255]
        for tick in x_ticks:
            x = margin_left + (tick / 255) * plot_w
            canvas.create_line(x, margin_top, x, margin_top + plot_h, fill="#1E293B", dash=(2, 2))
            canvas.create_text(x, margin_top + plot_h + 12, text=str(tick), fill="#94A3B8", font=("Arial", 9), anchor="n")

        # Achsen-Namen zeichnen
        canvas.create_text(margin_left + plot_w / 2, margin_top + plot_h + 28, text="Temperatur-Intensitätswert (0 - 255)", fill="#E2E8F0", font=("Arial", 9, "bold"), anchor="n")

        # ── 2. Histogramm-Balken zeichnen ────────────────────────────────────
        bar_width = max(1, int(plot_w / 256))
        for i in range(256):
            if hist[i] == 0:
                continue
            x = margin_left + (i / 255) * plot_w
            bar_h = (hist[i] / max_val) * plot_h
            y = margin_top + plot_h - bar_h
            canvas.create_rectangle(x, margin_top + plot_h, x + bar_width, y, fill="#0EA5E9", outline="")

        # ── 3. Mathematische Grenzwert-Linien einzeichnen ──────────────────
        # Mittelwert-Linie (µ) in Soft White
        mx = margin_left + (mean_val / 255) * plot_w
        canvas.create_line(mx, margin_top, mx, margin_top + plot_h, fill="#E2E8F0", width=1.5, dash=(4, 2))
        canvas.create_text(mx + 5, margin_top + 10, text=f"Mittelwert µ ({mean_val:.1f})", fill="#E2E8F0", font=("Arial", 9, "bold"), anchor="w")

        # 3-Sigma Grenzwert-Linie (µ + 3σ) in Neon-Rot
        tx = margin_left + (min(threshold, 255) / 255) * plot_w
        canvas.create_line(tx, margin_top, tx, margin_top + plot_h, fill="#FF0055", width=2, dash=(6, 2))
        canvas.create_text(tx - 5, margin_top + 30, text=f"Schwellenwert µ+3σ ({threshold:.1f})", fill="#FF0055", font=("Arial", 9, "bold"), anchor="e")

        # Rahmen um Plot ziehen
        canvas.create_rectangle(margin_left, margin_top, margin_left + plot_w, margin_top + plot_h, outline="#334155")

        # ── 4. Seitenleisten-Labels updaten ──────────────────────────────────
        self.stats_labels["pixel_count"].configure(text=f"{len(pixels):,} px")
        self.stats_labels["mean"].configure(text=f"{mean_val:.2f}")
        self.stats_labels["std"].configure(text=f"{std_val:.2f}")
        self.stats_labels["threshold"].configure(text=f"{threshold:.2f} (µ + 3σ)")
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

        # ── 5. Symmetrievergleich berechnen & updaten ────────────────────────
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
            
            # Ein Delta von >= 15 Einheiten entspricht ca. 1.2°C Differenz (Verdacht)
            if delta >= 15.0:
                sym_status = "ASYMMETRIE DETEKTIERT (Entzündungsverdacht!)"
                sym_color = "#FF0055"
            else:
                sym_status = "NORMAL (Symmetrisch)"
                sym_color = "#10B981" # Green
                
            self.stats_labels["mean_left"].configure(text=f"{mean_l:.2f}")
            self.stats_labels["mean_right"].configure(text=f"{mean_r:.2f}")
            self.stats_labels["delta"].configure(text=f"{delta:.2f}", text_color=sym_color)
            self.stats_labels["status_symmetry"].configure(text=sym_status, text_color=sym_color)
        else:
            self.stats_labels["mean_left"].configure(text="--")
            self.stats_labels["mean_right"].configure(text="--")
            self.stats_labels["delta"].configure(text="--", text_color="#E2E8F0")
            self.stats_labels["status_symmetry"].configure(text="Keine Daten", text_color="#E2E8F0")

    def save_active_view(self) -> None:
        """Exportiert das aktuell angezeigte Bild des aktiven Tabs als PNG."""
        tab_name = self.tabview.get()
        
        if tab_name == "Gesamtübersicht" or tab_name == "5. Temperatur-Verteilung":
            messagebox.showwarning("Exportieren", "Bitte wählen Sie einen der Bild-Tabs (1–4) aus, um das Bild zu exportieren.")
            return
            
        if self.current_raw_original is None:
            messagebox.showwarning("Exportieren", "Keine Bilddaten zum Exportieren vorhanden.")
            return

        # Bestimmen, welches Bild exportiert werden soll
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
            if self.current_raw_mask is not None:
                img_to_save = image_processing.create_hotspot_overlay(
                    self.current_raw_original,
                    self.current_raw_mask,
                    palette
                )

        if img_to_save is None:
            messagebox.showerror("Fehler", "Bild konnte nicht vorbereitet werden.")
            return

        # Speicherort abfragen
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
            # Dateinamen und Pfade bestimmen
            base_name = os.path.splitext(os.path.basename(self.current_filepath))[0]
            report_filename = f"report_{base_name}.html"
            report_filepath = os.path.join(config.OUTPUT_DIR, report_filename)
            
            # Statistiken berechnen
            body_mask = (self.current_images.get("2. Hintergrund-Maske") > 0).astype(np.uint8) if "2. Hintergrund-Maske" in self.current_images else None
            if body_mask is None or np.sum(body_mask) == 0:
                messagebox.showerror("Fehler", "Fußmaske nicht gefunden. Bericht kann nicht erstellt werden.")
                return
                
            pixels = self.current_raw_original[body_mask > 0]
            mean_val = np.mean(pixels)
            std_val = np.std(pixels)
            threshold = mean_val + 3.0 * std_val
            hotspot_count = int(self.current_raw_mask.sum()) // 255 if self.current_raw_mask is not None else 0
            
            # Symmetrievergleich berechnen
            h_orig, w_orig = self.current_raw_original.shape[:2]
            mid_x = w_orig // 2
            
            left_mask = np.zeros_like(body_mask)
            left_mask[:, :mid_x] = body_mask[:, :mid_x]
            
            right_mask = np.zeros_like(body_mask)
            right_mask[:, mid_x:] = body_mask[:, mid_x:]
            
            left_pixels = self.current_raw_original[left_mask > 0]
            right_pixels = self.current_raw_original[right_mask > 0]
            
            mean_l = 0.0
            mean_r = 0.0
            delta = 0.0
            sym_status = "Keine Daten"
            sym_color = "#94A3B8"
            
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
            
            # Farbe für Hotspots bestimmen
            hotspot_color = "#FF0055" if hotspot_count > 0 else "#E2E8F0"
            
            # Backend bestimmen
            backend_info = image_processing.get_active_backend()
            forced = self.backend_var.get()
            if forced != "auto":
                backend_info = f"{backend_info} (Erzwungen)"

            # HTML-Inhalt schreiben
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
        
        <div class="metadata-grid">
            <div class="meta-item">
                <div class="meta-label">Analysierte Datei</div>
                <div class="meta-value">{os.path.basename(self.current_filepath)}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Berechnungs-Backend</div>
                <div class="meta-value">{backend_info}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Mittelwert Fußhitze (µ)</div>
                <div class="meta-value">{mean_val:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Standardabweichung (σ)</div>
                <div class="meta-value">{std_val:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Grenzschwellenwert (µ+3σ)</div>
                <div class="meta-value">{threshold:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Hotspot-Fläche</div>
                <div class="meta-value" style="color: {hotspot_color}; font-weight: bold;">{hotspot_count} Pixel ({(hotspot_count / len(pixels)) * 100:.3f} %)</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Mittelwert Links (L)</div>
                <div class="meta-value">{mean_l:.2f}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Mittelwert Rechts (R)</div>
                <div class="meta-value">{mean_r:.2f}</div>
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

        <div class="image-grid">
            <div class="card">
                <h3>1. Originalbild</h3>
                <img src="{base_name}_step1_original.png" alt="Originalbild">
            </div>
            <div class="card">
                <h3>2. Hintergrund-Maske (Fußsegmentierung)</h3>
                <img src="{base_name}_step2_mask.png" alt="Hintergrund-Maske">
            </div>
            <div class="card">
                <h3>3. Lokale Hitze-Differenz (Top-Hat)</h3>
                <img src="{base_name}_step3_local_heat_diff.png" alt="Lokale Hitze-Differenz">
            </div>
            <div class="card">
                <h3>4. Erkannte Hotspots (Overlay)</h3>
                <img src="{base_name}_step4_dynamic_hotspots.png" alt="Erkannte Hotspots">
            </div>
        </div>

        <div class="footer">
            Entwickelt von Jona Noack | Jugend forscht 2026<br>
            Dieser Bericht wurde automatisch von der IGNITE-Software generiert.
        </div>
    </div>
</body>
</html>"""

            with open(report_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
                
            messagebox.showinfo("Export erfolgreich", f"Der HTML-Bericht wurde erfolgreich gespeichert:\n{report_filename}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Bericht konnte nicht exportiert werden:\n{e}")

    def show_info_window(self) -> None:
        """Öffnet ein Informations-Fenster über die Funktionsweise des Systems."""
        if hasattr(self, "info_win") and self.info_win.winfo_exists():
            self.info_win.focus()
            return

        self.info_win = ctk.CTkToplevel(self.root)
        self.info_win.title("Über IGNITE & Funktionsweise")
        self.info_win.geometry("600x520")
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
            "in thermografischen Fußaufnahmen. Sie dient der Früherkennung des Diabetischen Fußsyndroms.\n\n"
            "Die mathematische Pipeline besteht aus 5 Stufen:\n\n"
            "Feature A – Dynamische Kernel:\n"
            "Berechnet ungerade Strukturierungselemente basierend auf der Bildbreite (Standard: 5 % für Top-Hat, 2 % für Geometriefilter).\n\n"
            "Feature B – Adaptive Body-Mask:\n"
            "Otsu-Binarisierung mit Sicherheits-Schwellenwert-Eingrenzung auf den Bereich [35, 50], um auch kältere Extremitäten (Zehen) zuverlässig zu erfassen. Es folgt eine euklidische Distanztransformation (Chamfer-3-4-Metrik) und eine 5% adaptive Erosion zur Rauschelminierung.\n\n"
            "Feature C – Top-Hat-Transformation:\n"
            "Führt ein morphologisches Opening durch und subtrahiert dieses vom Originalbild, um lokale Helligkeitsspitzen (Hitze) präzise zu isolieren.\n\n"
            "Feature D – Statistischer Schwellenwert (µ + 3σ + Absoluthitze-Filter):\n"
            "Berechnet Mittelwert µ und Standardabweichung σ der Top-Hat-Differenz exklusiv über Körper-Pixel. Filtert mit einem Schwellenwert von µ + 3.0σ (99.86% Konfidenz) und verlangt zusätzlich, dass die absolute Helligkeit über der durchschnittlichen Fußtemperatur liegt. Dies eliminiert Falsch-Positive an gesunden Zehen vollständig.\n\n"
            "Feature E – Geometrischer Rauschfilter:\n"
            "Führt eine Connected-Component-Analyse durch. Filtert Komponenten nach Mindestfläche (0.05 % der Körperoberfläche) und Circularity (C >= 0.01) zur Entfernung von Punktrauschen und Linienartefakten.\n\n"
            "Backend-System:\n"
            "- GPU-Pfad: PyTorch CUDA (< 10 ms)\n"
            "- CPU-Pfad: Rust-native Multi-threading via Rayon (~50 ms)"
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