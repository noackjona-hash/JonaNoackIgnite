"""gui.py – Tkinter-Frontend für das Ignite Entzündungsdetektions-System.

Dieses Modul stellt das grafische Benutzer-Interface des Jugend-forscht-Projekts
"Ignite" bereit. Die Bildverarbeitung wird vollständig an das native Rust-Core-Modul
`ignite_core` delegiert (via `image_processing.run_rust_pipeline`).

Architektur:
    IgniteApp (Tkinter) → image_processing.py → ignite_core.pyd (Rust)

Pipeline-Ergebnisse:
    Panel 1: Originalbild (direkt aus Datei)
    Panel 2: Body-Mask (via Rust: Distanztransformation)
    Panel 3: Lokales Differenzbild (via Rust: Top-Hat-Transformation)
    Panel 4: Hotspot-Overlay (via Rust: µ+2σ + Geometriefilter, rot markiert)
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os

import cv2
import numpy as np
from PIL import Image, ImageTk

import config
import image_processing
import storage


class IgniteApp:
    """Haupt-Anwendungsklasse für das Ignite Thermografie-Analyse-System.

    Verwaltet das Tkinter-Hauptfenster, die vier Anzeige-Panels und den
    vollständigen Verarbeitungs-Workflow von der Dateiauswahl bis zur
    Pipeline-Ausführung und Ergebnisspeicherung.

    Attributes:
        root:             Tkinter-Hauptfenster.
        current_filepath: Pfad zur aktuell geladenen Wärmebild-Datei.
        panels:           Dictionary {Panel-Name → tk.Label} für die Bildanzeige.
        status_lbl:       Statusleiste im oberen Frame.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialisiert die Ignite-Anwendung.

        Args:
            root: Das Tkinter-Hauptfenster-Objekt.
        """
        self.root = root
        self.root.title("Ignite – Entzündungsdetektion via Thermografie")
        self.root.geometry("1000x750")
        self.root.configure(bg="#f7fafc")

        # Ausgabe-Verzeichnis für Jury-Dokumentation anlegen
        config.init_output_dir()

        self.current_filepath: str | None = None
        self.setup_ui()

    def setup_ui(self) -> None:
        """Erstellt und konfiguriert alle UI-Elemente des Hauptfensters.

        Layout:
            - Oberer Frame: Titelleiste, Lade-Button, Statusanzeige
            - Unterer Bereich: 2×2-Grid mit vier Bildanzeige-Panels
        """
        # ── Oberer Frame (Titelleiste) ────────────────────────────────────
        top_frame = tk.Frame(self.root, bg="#2d3748")
        top_frame.pack(fill=tk.X, padx=0, pady=0, ipady=10)

        title_lbl = tk.Label(
            top_frame,
            text="IGNITE // Jugend forscht",
            font=("Arial", 14, "bold"),
            fg="#ffffff",
            bg="#2d3748",
        )
        title_lbl.pack(side=tk.LEFT, padx=15, pady=5)

        load_btn = tk.Button(
            top_frame,
            text="Wärmebild laden",
            command=self.load_file,
            font=("Arial", 10, "bold"),
            fg="#2d3748",
            bg="#e2e8f0",
            relief=tk.FLAT,
            padx=10,
            pady=5,
        )
        load_btn.pack(side=tk.LEFT, padx=20, pady=5)

        self.status_lbl = tk.Label(
            top_frame,
            text="Bereit. Bitte Wärmebild einlesen.",
            fg="#a0aec0",
            bg="#2d3748",
            font=("Arial", 10, "italic"),
        )
        self.status_lbl.pack(side=tk.RIGHT, padx=15, pady=8)

        # ── 2×2-Grid mit Bild-Panels ──────────────────────────────────────
        self.display_frame = tk.Frame(self.root, bg="#f7fafc")
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.panels: dict[str, tk.Label] = {}
        steps = [
            ("1. Originalbild",              0, 0),
            ("2. Hintergrund-Maske",         0, 1),
            ("3. Lokale Hitze-Differenz",    1, 0),
            ("4. Erkannte Hotspots (Rust)",  1, 1),
        ]

        for name, row, col in steps:
            frame = tk.LabelFrame(
                self.display_frame,
                text=name,
                font=("Arial", 11, "bold"),
                bg="#ffffff",
                fg="#2d3748",
                bd=1,
                relief=tk.SOLID,
            )
            frame.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")

            lbl = tk.Label(
                frame,
                text="Warte auf Daten...",
                bg="#edf2f7",
                font=("Arial", 10),
                fg="#718096",
            )
            lbl.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            self.panels[name] = lbl

        # Gleichmäßige Gewichtung der Grid-Zellen
        self.display_frame.grid_columnconfigure(0, weight=1)
        self.display_frame.grid_columnconfigure(1, weight=1)
        self.display_frame.grid_rowconfigure(0, weight=1)
        self.display_frame.grid_rowconfigure(1, weight=1)

    def load_file(self) -> None:
        """Öffnet einen Datei-Dialog und startet die Pipeline bei Dateiauswahl.

        Unterstützte Formate: PNG, JPG/JPEG, BMP, TIFF/TIF.
        Aktualisiert die Statusleiste mit dem gewählten Dateinamen.
        """
        file_path = filedialog.askopenfilename(
            filetypes=[("Bilddateien", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif")]
        )
        if file_path:
            self.current_filepath = file_path
            self.status_lbl.config(
                text=f"Datei: {os.path.basename(file_path)}", fg="#48bb78"
            )
            self.process_pipeline()

    def process_pipeline(self) -> None:
        """Führt die vollständige Analyse-Pipeline aus und aktualisiert alle Panels.

        Pipeline-Schritte:
            1. Bild laden (load_thermal_image mit Umlaut-Workaround)
            2. Rust-Core: Body-Mask + Differenzbild + Hotspot-Maske
               (Features A–E: Distanz-Erosion, Top-Hat, µ+2σ, Geometriefilter)
            3. Overlay-Visualisierung erstellen
            4. Alle vier Panels aktualisieren
            5. Alle Zwischenergebnisse für die Jury-Dokumentation speichern

        Alle Fehler werden in einem Dialogfenster angezeigt ohne die Anwendung
        zum Absturz zu bringen.

        Notes:
            Die Body-Mask wird für Panel 2 aus dem Rust-Core-internen Ergebnis
            rekonstruiert, indem die Hotspot-Maske mit dem Differenzbild kombiniert
            wird. Das genaue Body-Mask-Bild wird durch den Rust-Core berechnet.
        """
        if not self.current_filepath:
            return

        try:
            # ── Schritt 1: Wärmebild laden ─────────────────────────────────
            img = image_processing.load_thermal_image(self.current_filepath)
            storage.save_image_step(img, "1", "original", self.current_filepath)
            storage.save_data_step(img, "1", "original", self.current_filepath)

            # ── Schritt 2: Rust-Core Pipeline ausführen ────────────────────
            # Delegiert an ignite_core.process_thermal_pipeline (Rust)
            # Gibt zurück: (diff_img, hotspot_mask) als NumPy-Arrays
            self.status_lbl.config(text="Rust-Pipeline läuft...", fg="#ed8936")
            self.root.update_idletasks()  # GUI sofort aktualisieren

            diff_img, hotspot_mask = image_processing.run_rust_pipeline(img)

            # ── Schritt 3: Body-Maske für Panel 2 ableiten ────────────────
            # Die Body-Mask ist intern im Rust-Core, für die GUI-Darstellung
            # leiten wir sie aus dem Differenzbild ab (Pixel > 0 = Körper).
            # Dies ist ausreichend für die visuelle Panel-Anzeige.
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
            pil_img.thumbnail((450, 300))
            img_tk = ImageTk.PhotoImage(image=pil_img)

            self.panels["4. Erkannte Hotspots (Rust)"].config(image=img_tk, text="")
            self.panels["4. Erkannte Hotspots (Rust)"].image = img_tk  # Referenz halten!

            # ── Schritt 7: Status aktualisieren ────────────────────────────
            hotspot_count = int(hotspot_mask.sum()) // 255
            backend_info = image_processing.get_active_backend()

            self.status_lbl.config(
                text=f"✓ Fertig – {hotspot_count} Hotspot-Pixel erkannt | {backend_info}",
                fg="#48bb78",
            )

            messagebox.showinfo(
                "Pipeline Abgeschlossen",
                f"Erfolg! Alle Schritte wurden im Ordner '{config.OUTPUT_DIR}' gesichert.\n\n"
                f"Erkannte Hotspot-Pixel: {hotspot_count}\n"
                f"Backend: {backend_info}",
            )

        except Exception as e:
            self.status_lbl.config(text="Fehler aufgetreten!", fg="#fc8181")
            messagebox.showerror("Fehler", f"Pipeline-Fehler:\n{e}")

    def display_image_in_panel(self, cv_img: np.ndarray, panel_name: str) -> None:
        """Zeigt ein Graustufen-OpenCV-Bild in einem Panel an.

        Konvertiert von OpenCV-Graustufen (H, W) zu PIL-RGB für die Tkinter-Anzeige.
        Skaliert das Bild auf maximal 450×300 Pixel (Seitenverhältnis erhalten).

        Args:
            cv_img:     OpenCV-Graustufen-Bild, shape (H, W), dtype=uint8.
            panel_name: Schlüssel im `self.panels`-Dictionary.
        """
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_GRAY2RGB)
        pil_img = Image.fromarray(rgb_img)
        pil_img.thumbnail((450, 300))
        img_tk = ImageTk.PhotoImage(image=pil_img)
        self.panels[panel_name].config(image=img_tk, text="")
        self.panels[panel_name].image = img_tk  # Referenz halten, sonst GC!