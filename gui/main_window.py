# -*- coding: utf-8 -*-
"""gui/main_window.py – Master Coordinator for IGNITE Medical Imaging Suite.

Clean, modular, Google Material 3 architecture connecting Header, Navigation Rail,
Dashboard, Single Inspection, Analytics, Podology, Batch and Settings views.
"""

from __future__ import annotations
import os
import sys
import logging
from tkinter import filedialog
from typing import Optional, Any
import customtkinter as ctk

import config
import image_processing
from gui.theme import (
    COLOR_BG_APP,
    COLOR_BG_NAV,
    COLOR_BG_CARD,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.components.header import TopAppBar
from gui.components.navigation import NavigationRail
from gui.views.dashboard_view import DashboardView
from gui.views.single_view import SingleInspectView
from gui.views.analytics_view import AnalyticsView
from gui.views.podology_view import PodologyView
from gui.views.batch_view import BatchView
from gui.views.settings_view import SettingsView
from gui.widgets.toast import ToastManager
from gui.widgets.command_palette import CommandPalette
from gui.widgets.dialogs import AboutModal, HelpModal, PatientExportModal
from gui.services.processing_service import ThermalProcessingService
from gui.services.export_service import ExportService
from utils import get_resource_path

APP_VERSION = "3.2.0"


class IgniteApp:
    """Hauptanwendung für IGNITE – Google Material 3 Medical Imaging Suite."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title(f"IGNITE Medical Imaging Suite v{APP_VERSION} – Thermografische Analyse")
        self.root.configure(fg_color=COLOR_BG_APP)

        self._apply_geometry()
        self._set_app_icon()

        config.init_output_dir()

        # State
        self.current_image_path: Optional[str] = None
        self.current_result: Optional[dict[str, Any]] = None
        self.palette_name: str = "Google Turbo"
        self.analysis_mode: str = "Klinische Allgemeinanalyse"
        self.t_min_c: float = config.DEFAULT_TEMP_MIN
        self.t_max_c: float = config.DEFAULT_TEMP_MAX
        self.emissivity: float = config.SKIN_EMISSIVITY

        self._debounce_job: Optional[str] = None
        self._resize_job: Optional[str] = None

        # Toast Manager
        self.toast = ToastManager(self.root)

        # ── 1. Layout-Grid aufbauen ──────────────────────────────────────────
        self.root.grid_rowconfigure(0, weight=0)  # Top App Bar
        self.root.grid_rowconfigure(1, weight=1)  # Main Workspace
        self.root.grid_rowconfigure(2, weight=0)  # Status Bar
        self.root.grid_columnconfigure(0, weight=0, minsize=230)  # Navigation Rail
        self.root.grid_columnconfigure(1, weight=1)  # View Container

        # ── 2. Top App Bar ───────────────────────────────────────────────────
        self.header = TopAppBar(
            self.root,
            on_load_click=self.load_file,
            on_search_click=self.open_command_palette,
            on_theme_click=self.toggle_appearance_mode,
            on_info_click=self.show_about_dialog
        )
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")

        # ── 3. Navigation Rail (Links) ───────────────────────────────────────
        self.nav_rail = NavigationRail(
            self.root,
            on_nav_change=self.switch_view,
            on_export_report=self.request_export_report
        )
        self.nav_rail.grid(row=1, column=0, sticky="nsew")

        # ── 4. Haupt-View-Container ──────────────────────────────────────────
        self.view_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.view_container.grid(row=1, column=1, sticky="nsew")
        self.view_container.grid_rowconfigure(0, weight=1)
        self.view_container.grid_columnconfigure(0, weight=1)

        # Views instanziieren
        self.views: dict[str, ctk.CTkFrame] = {}

        self.dashboard_view = DashboardView(
            self.view_container,
            on_load_click=self.load_file,
            on_inspect_panel=self._on_inspect_from_dashboard,
            on_palette_change=self._on_palette_changed,
            on_mode_change=self._on_mode_changed,
            on_load_demo=self.load_demo_image
        )
        self.views["dashboard"] = self.dashboard_view

        self.single_view = SingleInspectView(
            self.view_container,
            on_load_click=self.load_file
        )
        self.views["single"] = self.single_view

        self.analytics_view = AnalyticsView(self.view_container)
        self.views["analytics"] = self.analytics_view

        self.podology_view = PodologyView(self.view_container)
        self.views["podology"] = self.podology_view

        self.settings_view = SettingsView(
            self.view_container,
            on_param_changed=self._on_settings_param_changed,
            on_backend_changed=self._on_backend_changed,
            on_notify=self._show_toast
        )
        self.views["settings"] = self.settings_view

        self.batch_view = BatchView(
            self.view_container,
            get_current_params=self.settings_view.get_params,
            on_notify=self._show_toast
        )
        self.views["batch"] = self.batch_view

        # Standard-View aktivieren
        self.current_view_key = "dashboard"
        self.dashboard_view.grid(row=0, column=0, sticky="nsew")

        # ── 5. Status-Leiste (Unten) ─────────────────────────────────────────
        self._build_status_bar()

        # ── 6. Event-Bindings & Shortcuts ────────────────────────────────────
        self._bind_shortcuts()
        self.root.bind("<Configure>", self._on_window_resize)

    def _apply_geometry(self) -> None:
        """Setzt eine proportionierte Startgröße passend zur Bildschirmauflösung."""
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w = max(1100, min(1440, int(sw * 0.85)))
            h = max(720, min(920, int(sh * 0.85)))
            x = (sw - w) // 2
            y = (sh - h) // 2
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.root.minsize(1180, 720)
        except Exception:
            self.root.geometry("1300x840")
            self.root.minsize(1180, 720)

    def _set_app_icon(self) -> None:
        icon_path = get_resource_path(os.path.join("icon", "LogoRund.ico"))
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception as e:
                logging.debug(f"Icon konnte nicht geladen werden: {e}")

    def _build_status_bar(self) -> None:
        self.status_bar = ctk.CTkFrame(
            self.root,
            height=28,
            corner_radius=0,
            fg_color=COLOR_BG_NAV,
            border_width=0
        )
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_bar.pack_propagate(False)

        # Trennlinie oben
        ctk.CTkFrame(self.status_bar, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(side=ctk.TOP, fill=ctk.X)

        # Linker Bereich: Status-Punkt + Text
        left_box = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        left_box.pack(side=ctk.LEFT, padx=16, pady=2)

        self.sb_dot = ctk.CTkFrame(left_box, width=6, height=6, corner_radius=3, fg_color=COLOR_SUCCESS)
        self.sb_dot.pack(side=ctk.LEFT, padx=(0, 6), pady=4)

        self.sb_status_lbl = ctk.CTkLabel(
            left_box,
            text="Bereit",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.sb_status_lbl.pack(side=ctk.LEFT)

        # Rechter Bereich: Shortcuts & Fortschrittsbalken
        right_box = ctk.CTkFrame(self.status_bar, fg_color="transparent")
        right_box.pack(side=ctk.RIGHT, padx=16, pady=2)

        self.sb_progress = ctk.CTkProgressBar(
            right_box,
            width=100,
            height=4,
            fg_color=COLOR_OUTLINE_VARIANT,
            progress_color=COLOR_PRIMARY
        )
        self.sb_progress.set(0.0)

        ctk.CTkLabel(
            right_box,
            text="Ctrl+K  Befehle  ·  Ctrl+O  Öffnen  ·  Ctrl+E  Export  ·  F5  Analyse",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT, padx=(10, 0))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda e: self.load_file())
        self.root.bind("<Control-O>", lambda e: self.load_file())
        self.root.bind("<Control-k>", lambda e: self.open_command_palette())
        self.root.bind("<Control-K>", lambda e: self.open_command_palette())
        self.root.bind("<Control-p>", lambda e: self.open_command_palette())
        self.root.bind("<Control-P>", lambda e: self.open_command_palette())
        self.root.bind("<Control-e>", lambda e: self.request_export_report())
        self.root.bind("<Control-E>", lambda e: self.request_export_report())
        self.root.bind("<Control-t>", lambda e: self.toggle_appearance_mode())
        self.root.bind("<Control-T>", lambda e: self.toggle_appearance_mode())
        self.root.bind("<F5>", lambda e: self.run_pipeline())
        self.root.bind("<Control-r>", lambda e: self.run_pipeline())
        self.root.bind("<Control-R>", lambda e: self.run_pipeline())

    def switch_view(self, key: str) -> None:
        """Wechselt die aktive Ansicht."""
        if key not in self.views or key == self.current_view_key:
            return

        # Alte View ausblenden
        self.views[self.current_view_key].grid_forget()

        # Neue View einblenden
        self.current_view_key = key
        target_view = self.views[key]
        target_view.grid(row=0, column=0, sticky="nsew")

        # View-spezifische Updates
        if self.current_result:
            if key == "dashboard":
                self.dashboard_view.show_results(self.current_result)
            elif key == "single":
                self.single_view.show_results(self.current_result, self.palette_name)
            elif key == "analytics":
                self.analytics_view.show_results(self.current_result)
            elif key == "podology":
                self.podology_view.show_results(self.current_result)

    def load_file(self) -> None:
        """Öffnet einen Datei-Dialog zum Laden eines Infrarotbildes."""
        file_path = filedialog.askopenfilename(
            title="Wärmebild zur Analyse auswählen",
            filetypes=[
                ("Alle unterstützten Wärmebilder", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif;*.flir"),
                ("FLIR Radiometrische Daten", "*.tiff;*.tif;*.flir"),
                ("Standard-Bilder (8-Bit)", "*.png;*.jpg;*.jpeg;*.bmp"),
                ("Alle Dateien", "*.*")
            ]
        )
        if file_path:
            self.current_image_path = file_path
            fname = os.path.basename(file_path)
            self.nav_rail.update_loaded_file(fname)
            self._set_status(f"Datei geladen: {fname}", is_loading=False)
            self.run_pipeline()

    def load_demo_image(self, file_path: str) -> None:
        """Lädt ein Beispieldaten-Wärmebild direkt mit 1 Klick."""
        abs_p = get_resource_path(file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(abs_p):
            abs_p = os.path.abspath(file_path)

        if os.path.exists(abs_p):
            self.current_image_path = abs_p
            fname = os.path.basename(abs_p)
            self.nav_rail.update_loaded_file(fname)
            self._set_status(f"Demo geladen: {fname}", is_loading=False)
            self.run_pipeline()
            self.toast.show(f"Beispielbild '{fname}' erfolgreich geladen.", level="success")
        else:
            self.toast.show(f"Beispielbild nicht gefunden: {file_path}", level="error")

    def run_pipeline(self) -> None:
        """Startet die Bildverarbeitungs-Pipeline im Hintergrund."""
        if not self.current_image_path:
            self.toast.show("Bitte wähle zuerst ein Wärmebild aus.", level="info")
            return

        self._set_status("Berechne Analyse-Pipeline...", is_loading=True)

        params = self.settings_view.get_params()

        ThermalProcessingService.process_async(
            image_path=self.current_image_path,
            params=params,
            t_min_c=self.t_min_c,
            t_max_c=self.t_max_c,
            analysis_mode=self.analysis_mode,
            colormap_name=self.palette_name,
            emissivity=self.emissivity,
            on_progress=self._on_pipeline_progress,
            on_success=self._on_pipeline_success,
            on_error=self._on_pipeline_error
        )

    def _on_pipeline_progress(self, progress: float, message: str) -> None:
        self.root.after(0, lambda: self._update_progress_ui(progress, message))

    def _update_progress_ui(self, progress: float, message: str) -> None:
        self.sb_progress.pack(side=ctk.RIGHT, padx=(0, 10))
        self.sb_progress.set(progress)
        self.sb_status_lbl.configure(text=message)

    def _on_pipeline_success(self, result: dict[str, Any]) -> None:
        self.root.after(0, lambda: self._apply_pipeline_results(result))

    def _apply_pipeline_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        self.sb_progress.pack_forget()

        hotspots = result.get("hotspot_pixel_count", 0)
        asym = result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)

        if hotspots > 0 or asym.get("is_asymmetric"):
            self.sb_dot.configure(fg_color=COLOR_DANGER)
            status_msg = f"Analyse abgeschlossen – {hotspots:,} Hotspot-Pixel (ΔT={delta_t:.1f}°C)"
        else:
            self.sb_dot.configure(fg_color=COLOR_SUCCESS)
            status_msg = f"Analyse abgeschlossen – Unauffälliger Normalbefund (ΔT={delta_t:.1f}°C)"

        self.sb_status_lbl.configure(text=status_msg)
        self.header.update_backend_badge()

        # Aktive View aktualisieren
        if self.current_view_key == "dashboard":
            self.dashboard_view.show_results(result)
        elif self.current_view_key == "single":
            self.single_view.show_results(result, self.palette_name)
        elif self.current_view_key == "analytics":
            self.analytics_view.show_results(result)
        elif self.current_view_key == "podology":
            self.podology_view.show_results(result)

    def _on_pipeline_error(self, error: Exception) -> None:
        self.root.after(0, lambda: self._apply_pipeline_error(error))

    def _apply_pipeline_error(self, error: Exception) -> None:
        self.sb_progress.pack_forget()
        self.sb_dot.configure(fg_color=COLOR_DANGER)
        self.sb_status_lbl.configure(text=f"Fehler: {error}")
        self.toast.show(f"Pipeline-Fehler: {error}", level="error", duration_ms=6000)

    def _on_inspect_from_dashboard(self, stage_key: str) -> None:
        """Öffnet die Einzelbild-Inspektion direkt für eine bestimmte Stufe."""
        self.nav_rail.select_tab("single", notify=False)
        self.switch_view("single")
        if self.current_result:
            self.single_view.show_results(self.current_result, self.palette_name, target_stage=stage_key)

    def _on_palette_changed(self, palette_name: str) -> None:
        self.palette_name = palette_name
        if self.current_result:
            self.dashboard_view.redraw_images()
            self.single_view.set_palette(palette_name)

    def _on_mode_changed(self, mode: str) -> None:
        self.analysis_mode = mode
        if self.current_image_path:
            self.run_pipeline()

    def _on_settings_param_changed(self) -> None:
        """Debounced Pipeline-Neuberechnung wenn Regler in Einstellungen bewegt werden."""
        if self._debounce_job:
            self.root.after_cancel(self._debounce_job)
        if self.current_image_path:
            self._debounce_job = self.root.after(250, self.run_pipeline)

    def _on_backend_changed(self, val: str) -> None:
        self.header.update_backend_badge()
        if self.current_image_path:
            self.run_pipeline()

    def _on_window_resize(self, event) -> None:
        if event.widget == self.root and self.current_result:
            if self._resize_job:
                self.root.after_cancel(self._resize_job)
            self._resize_job = self.root.after(120, self._redraw_active_view)

    def _redraw_active_view(self) -> None:
        if not self.current_result:
            return
        if self.current_view_key == "dashboard":
            self.dashboard_view.redraw_images()
        elif self.current_view_key == "single":
            self.single_view.redraw()
        elif self.current_view_key == "podology":
            self.podology_view.redraw()

    def _set_status(self, text: str, is_loading: bool = False) -> None:
        self.sb_status_lbl.configure(text=text)
        self.sb_dot.configure(fg_color=COLOR_PRIMARY if is_loading else COLOR_SUCCESS)

    def _show_toast(self, message: str, level: str = "info") -> None:
        self.toast.show(message, level=level)

    def toggle_appearance_mode(self) -> None:
        """Schaltet zwischen Google Light und Dark Mode um."""
        curr = ctk.get_appearance_mode()
        new_mode = "Light" if curr == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.root.after(50, self._redraw_active_view)

    def open_command_palette(self) -> None:
        """Öffnet die Befehlspalette."""
        commands = [
            {"label": "Wärmebild öffnen…",              "desc": "Neue Infrarot-Aufnahme laden",         "shortcut": "Ctrl+O", "action": self.load_file},
            {"label": "Beispiel: Diabetischer Fuß",      "desc": "Lade Testbild 4 (Asymmetrie-Befund)", "shortcut": "", "action": lambda: self.load_demo_image("test-data/bild (4).jpeg")},
            {"label": "Beispiel: Entzündungsherd",      "desc": "Lade Testbild 1 (Lokaler Hotspot)",   "shortcut": "", "action": lambda: self.load_demo_image("test-data/bild (1).jpeg")},
            {"label": "Beispiel: Normalbefund",         "desc": "Lade Testbild 15 (Physiologischer Fuß)","shortcut": "", "action": lambda: self.load_demo_image("test-data/bild (15).jpeg")},
            {"label": "Analyse neu berechnen",           "desc": "Pipeline mit aktuellen Parametern ausführen", "shortcut": "F5", "action": self.run_pipeline},
            {"label": "HTML-Befundbericht exportieren",  "desc": "Klinischen Bericht als HTML speichern", "shortcut": "Ctrl+E", "action": self.request_export_report},
            {"label": "Ansicht: Dashboard",              "desc": "4-Stufen Pipeline-Übersicht öffnen",   "shortcut": "",       "action": lambda: self.nav_rail.select_tab("dashboard")},
            {"label": "Ansicht: Inspektion & ROI",       "desc": "Einzelbild und ROI-Messung öffnen",    "shortcut": "",       "action": lambda: self.nav_rail.select_tab("single")},
            {"label": "Ansicht: Statistik-Histogramm",   "desc": "Temperatur-Verteilung und Metriken",   "shortcut": "",       "action": lambda: self.nav_rail.select_tab("analytics")},
            {"label": "Ansicht: Podologie & Zonen",      "desc": "3-Zonen Fußthermografie & Symmetrie",  "shortcut": "",       "action": lambda: self.nav_rail.select_tab("podology")},
            {"label": "Ansicht: Serienanalyse",          "desc": "Stapelverarbeitung über Bildordner starten", "shortcut": "",       "action": lambda: self.nav_rail.select_tab("batch")},
            {"label": "Ansicht: Einstellungen",          "desc": "Algorithmus-Parameter anpassen",       "shortcut": "",       "action": lambda: self.nav_rail.select_tab("settings")},
            {"label": "Farbpalette: Turbo",              "desc": "Hochdynamische Turbo-Palette",         "shortcut": "",       "action": lambda: self._on_palette_changed("Turbo")},
            {"label": "Farbpalette: Graustufen",         "desc": "Monochrome Temperatur-Intensität",    "shortcut": "",       "action": lambda: self._on_palette_changed("Graustufen")},
            {"label": "Farbpalette: Inferno",            "desc": "Thermische Strahlungsfarben",          "shortcut": "",       "action": lambda: self._on_palette_changed("Inferno")},
            {"label": "Design wechseln (Hell/Dunkel)",   "desc": "Erscheinungsmodus umschalten",         "shortcut": "Ctrl+T", "action": self.toggle_appearance_mode},
            {"label": "Bedienungsanleitung anzeigen",    "desc": "Dokumentation und Schnelleinstieg",    "shortcut": "",       "action": self.show_help_dialog},
            {"label": "Über IGNITE",                     "desc": "Versions- und Projektinformationen",   "shortcut": "",       "action": self.show_about_dialog},
        ]
        palette = CommandPalette(self.root, commands)
        palette.grab_set()

    def request_export_report(self) -> None:
        if not self.current_result:
            self.toast.show("Bitte lade zuerst ein Wärmebild zur Analyse.", level="warning")
            return

        modal = PatientExportModal(self.root, on_submit=self._do_export_report)
        modal.grab_set()

    def _do_export_report(self, p_name: str, p_dob: str, operator: str, notes: str) -> None:
        if not self.current_result:
            return

        try:
            report_path = ExportService.generate_html_report(
                analysis_result=self.current_result,
                patient_name=p_name,
                patient_dob=p_dob,
                operator=operator,
                notes=notes
            )
            self.toast.show(f"Bericht erfolgreich exportiert: {os.path.basename(report_path)}", level="success")
        except Exception as e:
            self.toast.show(f"Export fehlgeschlagen: {e}", level="error")

    def show_about_dialog(self) -> None:
        modal = AboutModal(self.root)
        modal.grab_set()

    def show_help_dialog(self) -> None:
        modal = HelpModal(self.root)
        modal.grab_set()
