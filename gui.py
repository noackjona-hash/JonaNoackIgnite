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


class IgniteApp:
    """Haupt-Anwendungsklasse für das Ignite Thermografie-Analyse-System.

    Verwaltet das Hauptfenster unter Verwendung von CustomTkinter, die Seitenleiste
    für Steuerelemente und Statistiken sowie die vier Bild-Anzeige-Panels.
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
        icon_path = os.path.join("icon", "LogoRund.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Ausgabe-Verzeichnis für Jury-Dokumentation anlegen
        config.init_output_dir()

        self.current_filepath: str | None = None
        self.panels: dict[str, ctk.CTkLabel] = {}
        
        self.setup_ui()
        
        # Aktives Backend beim Start abfragen und formatieren
        backend_info = image_processing.get_active_backend()
        if "GPU (CUDA," in backend_info:
            gpu_name = backend_info.split(",", 1)[1].strip().replace(")", "")
            backend_disp = f"GPU: {gpu_name}"
        else:
            backend_disp = backend_info
        self.backend_label.configure(text=f"Backend: {backend_disp}")

    def setup_ui(self) -> None:
        """Erstellt und konfiguriert das moderne zweispaltige Layout (Sidebar + Grid)."""
        # Konfiguration des Haupt-Grids
        self.root.grid_columnconfigure(0, weight=0)  # Sidebar behält feste Breite
        self.root.grid_columnconfigure(1, weight=1)  # Inhalt dehnt sich aus
        self.root.grid_rowconfigure(0, weight=1)

        # ── 1. LINKE SEITENLEISTE (Steuerung & Info) ─────────────────────────
        sidebar_frame = ctk.CTkFrame(self.root, width=280, corner_radius=0, fg_color="#0B0F19")
        sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar_frame.grid_propagate(False)

        # App-Logo
        icon_png_path = os.path.join("icon", "LogoRund.png")
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
        subtitle_lbl.pack(padx=20, pady=(0, 25), anchor="w")

        # Trennlinie
        divider = ctk.CTkFrame(sidebar_frame, height=2, fg_color="#1E293B")
        divider.pack(fill=ctk.X, padx=20, pady=(0, 25))

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
        self.load_btn.pack(fill=ctk.X, padx=20, pady=(0, 25))

        # Sektion: Analyse-Info & Status
        info_title = ctk.CTkLabel(
            sidebar_frame,
            text="ANALYSE-DETAILS",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color="#0EA5E9"
        )
        info_title.pack(padx=20, pady=(0, 8), anchor="w")

        # Informations-Karte
        self.info_card = ctk.CTkFrame(sidebar_frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        self.info_card.pack(fill=ctk.X, padx=20, pady=(0, 20), ipady=8)

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
        self.hotspot_label.pack(fill=ctk.X, padx=15, pady=(4, 10))

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
            height=35,
            corner_radius=8
        )
        self.open_dir_btn.pack(fill=ctk.X, padx=20, pady=(0, 20))

        # Footer
        footer_lbl = ctk.CTkLabel(
            sidebar_frame,
            text="Jugend forscht 2026\nEntzündungsdetektion v0.1.0",
            font=ctk.CTkFont(family="Arial", size=10),
            text_color="#475569"
        )
        footer_lbl.pack(side=ctk.BOTTOM, pady=20)

        # ── 2. RECHTER HAUPTBEREICH (Bild-Grid) ──────────────────────────────
        content_frame = ctk.CTkFrame(self.root, fg_color="#0B0F19", corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # 2x2 Grid-Gewichtung konfigurieren
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)

        steps = [
            ("1. Originalbild",              0, 0),
            ("2. Hintergrund-Maske",         0, 1),
            ("3. Lokale Hitze-Differenz",    1, 0),
            ("4. Erkannte Hotspots (Rust)",  1, 1),
        ]

        for name, row, col in steps:
            panel_frame = ctk.CTkFrame(
                content_frame,
                fg_color="#1E293B",
                corner_radius=12,
                border_width=1,
                border_color="#334155"
            )
            panel_frame.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")

            title = ctk.CTkLabel(
                panel_frame,
                text=name,
                font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
                text_color="#E2E8F0",
                anchor="w"
            )
            title.pack(fill=ctk.X, padx=15, pady=(12, 5))

            lbl = ctk.CTkLabel(
                panel_frame,
                text="Warte auf Bilddaten...",
                font=ctk.CTkFont(family="Arial", size=13),
                text_color="#94A3B8",
                fg_color="#0B0F19",
                corner_radius=8
            )
            lbl.pack(fill=ctk.BOTH, expand=True, padx=15, pady=(0, 15))
            self.panels[name] = lbl

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
        """Führt die vollständige Analyse-Pipeline aus und aktualisiert alle Panels."""
        if not self.current_filepath:
            return

        try:
            # ── Schritt 1: Wärmebild laden ─────────────────────────────────
            self.status_label.configure(text="Bild wird geladen...", text_color="#0EA5E9")
            self.root.update_idletasks()

            img = image_processing.load_thermal_image(self.current_filepath)
            storage.save_image_step(img, "1", "original", self.current_filepath)
            storage.save_data_step(img, "1", "original", self.current_filepath)

            # ── Schritt 2: Pipeline ausführen (Rust-Core oder GPU) ─────────
            self.status_label.configure(text="Pipeline läuft...", text_color="#0EA5E9")
            self.root.update_idletasks()

            diff_img, hotspot_mask = image_processing.run_rust_pipeline(img)

            # ── Schritt 3: Body-Maske für Panel 2 ableiten ────────────────
            body_mask_vis = (diff_img > 0).astype(np.uint8) * 255

            # ── Schritt 4: Ergebnisse speichern (Jury-Dokumentation) ───────
            storage.save_image_step(body_mask_vis, "2", "mask", self.current_filepath)
            storage.save_data_step(body_mask_vis, "2", "mask", self.current_filepath)

            storage.save_image_step(diff_img, "3", "local_heat_diff", self.current_filepath)
            storage.save_data_step(diff_img, "3", "local_heat_diff_raw", self.current_filepath)

            storage.save_image_step(hotspot_mask, "4", "dynamic_hotspots", self.current_filepath)
            storage.save_data_step(hotspot_mask, "4", "dynamic_hotspots_raw", self.current_filepath)

            # ── Schritt 5: Panels 1–3 aktualisieren (Graustufen) ──────────
            self.display_image_in_panel(img, "1. Originalbild")
            self.display_image_in_panel(body_mask_vis, "2. Hintergrund-Maske")
            self.display_image_in_panel(diff_img, "3. Lokale Hitze-Differenz")

            # ── Schritt 6: Panel 4 – Farb-Overlay mit roten Hotspots ───────
            overlay_img = image_processing.create_hotspot_overlay(img, hotspot_mask)
            overlay_rgb = cv2.cvtColor(overlay_img, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(overlay_rgb)
            
            # Bild passend für Grid-Zelle skalieren (ca. 420x280)
            pil_img.thumbnail((420, 280))
            w, h = pil_img.size
            img_tk = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))

            self.panels["4. Erkannte Hotspots (Rust)"].configure(image=img_tk, text="")
            self.panels["4. Erkannte Hotspots (Rust)"].image = img_tk  # Referenz halten!

            # ── Schritt 7: Status- & Statistik-Updates ─────────────────────
            hotspot_count = int(hotspot_mask.sum()) // 255
            backend_info = image_processing.get_active_backend()

            # Backend-Anzeige formatieren
            if "GPU (CUDA," in backend_info:
                gpu_name = backend_info.split(",", 1)[1].strip().replace(")", "")
                backend_disp = f"GPU: {gpu_name}"
            else:
                backend_disp = backend_info

            self.backend_label.configure(
                text=f"Backend: {backend_disp}",
                text_color="#0EA5E9"
            )

            # Hotspot-Zähler farblich hervorheben (Pure Neon Red #FF0055)
            if hotspot_count == 0:
                hotspot_color = "#E2E8F0"  # Weiß = keine Hotspots
                hotspot_text = "0 Pixel (Keine Entzündung)"
            elif hotspot_count < 150:
                hotspot_color = "#FF5E8E"  # Hellrot = kleiner Herd / Verdacht
                hotspot_text = f"{hotspot_count} Pixel (Verdacht)"
            else:
                hotspot_color = "#FF0055"  # Pure Neon Red = deutliche Entzündung
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

    def display_image_in_panel(self, cv_img: np.ndarray, panel_name: str) -> None:
        """Zeigt ein Graustufen-OpenCV-Bild in einem Panel an.

        Konvertiert das Bild in PIL, skaliert es und bettet es via CTkImage ein.
        """
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
        pil_img = Image.fromarray(rgb_img)
        
        # Bild passend für Grid-Zelle skalieren (ca. 420x280)
        pil_img.thumbnail((420, 280))
        w, h = pil_img.size
        
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))
        
        lbl = self.panels[panel_name]
        lbl.configure(image=ctk_img, text="")
        lbl.image = ctk_img  # Referenz halten!