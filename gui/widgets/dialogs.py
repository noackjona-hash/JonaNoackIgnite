# -*- coding: utf-8 -*-
"""gui/widgets/dialogs.py – High-Contrast Modals & Dialogs for IGNITE."""

from __future__ import annotations
import os
import sys
import threading
import webbrowser
import tkinter as tk
from typing import Callable, Optional, Any
import numpy as np
import customtkinter as ctk


from gui.theme import (
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_BG_CARD_HOVER,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card


class AboutModal(ctk.CTkToplevel):
    """Info-Dialog über IGNITE im High-Contrast Clinical Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("Über IGNITE")
        self.geometry("540x440")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        container = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(fill=ctk.BOTH, expand=True, padx=18, pady=18)

        # Header
        ctk.CTkLabel(
            inner,
            text="IGNITE Medical Imaging Suite",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(pady=(4, 2))

        import config
        app_ver = getattr(config, 'APP_VERSION', getattr(config, 'CANONICAL_APP_VERSION', ''))
        ctk.CTkLabel(
            inner,
            text=f"Version {app_ver} · Jugend forscht 2026 (Fachgebiet Arbeitswelt)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(pady=(0, 14))

        # Info Box
        info_card = make_material_card(inner, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        info_card.pack(fill=ctk.BOTH, expand=True, pady=(0, 14))

        info_inner = ctk.CTkFrame(info_card, fg_color="transparent")
        info_inner.pack(fill=ctk.BOTH, expand=True, padx=14, pady=12)

        bullets = [
            ("Rechen-Engine", "Rust (rayon/ndarray) + PyTorch CUDA GPU (<10ms)"),
            ("Radiometrie", "Stefan-Boltzmann Emissivitätskorrektur (ε=0.98)"),
            ("Podologie", "Kontralaterale Asymmetrie (>2.2°C Armstrong Goldstandard)"),
            ("Datenschutz", "Lokale In-Memory Verarbeitung & DSGVO SHA-256 Hashing"),
        ]

        for title, desc in bullets:
            row = ctk.CTkFrame(info_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=3)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side=ctk.LEFT)
            ctk.CTkLabel(row, text=desc, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_MUTED, anchor="e").pack(side=ctk.RIGHT)

        ctk.CTkLabel(
            inner,
            text="© 2026 Jona Noack · Forschungsprototyp (Kein zertifiziertes Medizinprodukt)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(pady=(0, 12))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(pady=(0, 0))

        ctk.CTkButton(
            btn_row,
            text="🔄 Nach Updates suchen",
            command=self._open_updater,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(side=tk.LEFT, padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=100
        ).pack(side=tk.LEFT)

    def _open_updater(self) -> None:
        self.destroy()
        UpdateModal(self.master)



class HelpModal(ctk.CTkToplevel):
    """Anleitungs- und Hilfedialog im High-Contrast Clinical Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("IGNITE – Bedienungsanleitung")
        self.geometry("640x500")
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        container = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            scroll,
            text="Bedienungsanleitung & Schnelleinstieg",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 12))

        steps = [
            ("1. Wärmebild öffnen", "Klicke oben rechts auf '+ Bild öffnen' (Ctrl+O) und wähle eine Infrarotdatei (.jpg, .png, .tiff, .flir) aus."),
            ("2. Dashboard-Übersicht", "Das 4-Stufen-Dashboard berechnet automatisch Originalbild, Körpermaske, Top-Hat Differenz und Hotspot-Overlay."),
            ("3. Live-ROI & Inspektion", "Wechsle zu 'Inspektion', um durch Aufziehen eines Rechtecks mit der Maus beliebige Zonen live auszumessen."),
            ("4. Podologische Symmetrie", "Im Tab 'Podologie' wird das 3-Zonen-Modell (Vorfuß, Mittelfuß, Ferse) mit dem klinischen 2.2 °C Grenzwert verglichen."),
            ("5. Bericht exportieren", "Klicke in der Seitenleiste auf 'Bericht exportieren' (Ctrl+E), um einen interaktiven Befundbericht zu speichern."),
            ("6. Tastenkombinationen", "Ctrl+K: Befehlssuche · Ctrl+O: Öffnen · Ctrl+E: Exportieren · F5: Neu berechnen.")
        ]

        for title, desc in steps:
            card = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
            card.pack(fill=ctk.X, pady=3)
            c_inner = ctk.CTkFrame(card, fg_color="transparent")
            c_inner.pack(fill=ctk.X, padx=14, pady=10)

            ctk.CTkLabel(c_inner, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(fill=ctk.X)
            ctk.CTkLabel(c_inner, text=desc, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_MUTED, anchor="w", wraplength=520, justify="left").pack(fill=ctk.X, pady=(2, 0))

        ctk.CTkButton(
            scroll,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=120
        ).pack(pady=(14, 6))


class PatientExportModal(ctk.CTkToplevel):
    """Dialog zur Eingabe von Patientendaten vor dem PDF/HTML-Report-Export."""

    def __init__(self, master, on_submit: Callable[[str, str, str, str], None], **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("Befundbericht exportieren")
        self.geometry("490x480")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        self.on_submit = on_submit

        container = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(fill=ctk.BOTH, expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            inner,
            text="Befundbericht exportieren",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 10))

        # Format-Auswahl
        ctk.CTkLabel(inner, text="Ausgabe-Format:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.format_seg = ctk.CTkSegmentedButton(
            inner,
            values=["PDF (.pdf)", "HTML (.html)", "DICOM (.dcm)", "Alle Formate"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            unselected_color=COLOR_BG_CARD_VARIANT,
            unselected_hover_color=COLOR_BG_CARD_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            height=30
        )
        self.format_seg.set("PDF (.pdf)")
        self.format_seg.pack(fill=ctk.X, pady=(2, 8))

        # Patienten-ID
        ctk.CTkLabel(inner, text="Patienten-Name / ID:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.patient_entry = ctk.CTkEntry(inner, placeholder_text="z. B. Max Mustermann oder ANON-001", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=30)
        self.patient_entry.pack(fill=ctk.X, pady=(2, 8))

        # Geburtsdatum
        ctk.CTkLabel(inner, text="Geburtsdatum (optional für SHA-256 Hash):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.dob_entry = ctk.CTkEntry(inner, placeholder_text="TT.MM.JJJJ", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=30)
        self.dob_entry.pack(fill=ctk.X, pady=(2, 8))

        # Untersucher
        ctk.CTkLabel(inner, text="Untersucher / Bediener:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.operator_entry = ctk.CTkEntry(inner, placeholder_text="Jugend forscht 2026", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=30)
        self.operator_entry.insert(0, "Jugend forscht 2026")
        self.operator_entry.pack(fill=ctk.X, pady=(2, 8))

        # Anmerkungen
        ctk.CTkLabel(inner, text="Klinische Anmerkungen:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(inner, placeholder_text="z. B. Postoperatives Monitoring / Hyperthermieverdacht", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE, height=30)
        self.notes_entry.pack(fill=ctk.X, pady=(2, 12))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill=ctk.X)

        ctk.CTkButton(
            btn_row,
            text="Abbrechen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=100
        ).pack(side=ctk.LEFT)

        ctk.CTkButton(
            btn_row,
            text="Bericht exportieren",
            command=self._on_save,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(side=ctk.RIGHT, fill=ctk.X, expand=True, padx=(10, 0))

    def _on_save(self) -> None:
        from utils import pseudonymize_patient
        raw_id = self.patient_entry.get().strip() or "Unbekannt"
        raw_dob = self.dob_entry.get().strip()
        op = self.operator_entry.get().strip() or "Jugend forscht"
        notes = self.notes_entry.get().strip()
        fmt = self.format_seg.get()

        # Sofortige DSGVO-konforme Pseudonymisierung vor Weitergabe
        if raw_id != "Unbekannt" and not raw_id.startswith("ANON-"):
            record_id = pseudonymize_patient(raw_id, raw_dob)
        else:
            record_id = raw_id

        self.destroy()
        self.on_submit(record_id, op, notes, fmt)


class Thermal3DViewerModal(ctk.CTkToplevel):
    """Interaktives 3D-Temperatur-Relief & Oberflächentopographie-Viewer."""

    def __init__(
        self,
        master,
        calibrated_image: np.ndarray,
        body_mask: Optional[np.ndarray] = None,
        t_min_c: float = 20.0,
        t_max_c: float = 40.0,
        palette_name: str = "turbo",
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.title("IGNITE – 3D Thermische Oberflächentopographie")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.configure(fg_color=COLOR_BG_APP)

        self.calibrated_image = calibrated_image
        self.body_mask = body_mask if body_mask is not None else np.ones_like(calibrated_image) * 255
        self.t_min_c = float(t_min_c)
        self.t_max_c = float(t_max_c)
        self.palette_name = palette_name.lower()

        # State
        self.elev: int = 40
        self.azim: int = -60
        self.z_scale: float = 1.0
        self.surface_mode: str = "Solid Mesh"

        self._canvas_tk = None
        self._build_ui()
        self._plot_3d()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=260)
        self.grid_rowconfigure(0, weight=1)

        # Plot Host (Links)
        self.plot_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.plot_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        self.plot_host = ctk.CTkFrame(self.plot_card, fg_color="transparent")
        self.plot_host.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # Steuerungsleiste (Rechts)
        ctrl_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        ctrl_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        ctrl_inner = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        ctrl_inner.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            ctrl_inner,
            text="3D-RELIEF STEUERUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 10))

        # Elevationswinkel
        ctk.CTkLabel(ctrl_inner, text="Blickwinkel Höhe (Elevation):", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.elev_lbl = ctk.CTkLabel(ctrl_inner, text="40°", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_PRIMARY)
        self.elev_lbl.pack(anchor="e")
        self.elev_slider = ctk.CTkSlider(ctrl_inner, from_=10, to=90, number_of_steps=80, command=self._on_elev_changed, height=16, progress_color=COLOR_PRIMARY, button_color=COLOR_PRIMARY)
        self.elev_slider.set(self.elev)
        self.elev_slider.pack(fill=ctk.X, pady=(0, 8))

        # Azimutwinkel
        ctk.CTkLabel(ctrl_inner, text="Drehwinkel (Azimut):", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.azim_lbl = ctk.CTkLabel(ctrl_inner, text="-60°", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_PRIMARY)
        self.azim_lbl.pack(anchor="e")
        self.azim_slider = ctk.CTkSlider(ctrl_inner, from_=-180, to=180, number_of_steps=360, command=self._on_azim_changed, height=16, progress_color=COLOR_PRIMARY, button_color=COLOR_PRIMARY)
        self.azim_slider.set(self.azim)
        self.azim_slider.pack(fill=ctk.X, pady=(0, 8))

        # Vertikale Überhöhung
        ctk.CTkLabel(ctrl_inner, text="Relief-Überhöhung (Z-Scale):", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.scale_lbl = ctk.CTkLabel(ctrl_inner, text="1.0×", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_PRIMARY)
        self.scale_lbl.pack(anchor="e")
        self.scale_slider = ctk.CTkSlider(ctrl_inner, from_=0.5, to=3.0, number_of_steps=25, command=self._on_scale_changed, height=16, progress_color=COLOR_PRIMARY, button_color=COLOR_PRIMARY)
        self.scale_slider.set(self.z_scale)
        self.scale_slider.pack(fill=ctk.X, pady=(0, 12))

        # Darstellungsmodus
        ctk.CTkLabel(ctrl_inner, text="Mesh-Modus:", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.mode_seg = ctk.CTkSegmentedButton(
            ctrl_inner,
            values=["Solid Mesh", "Drahtgitter"],
            command=self._on_mode_changed,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            selected_color=COLOR_PRIMARY,
            selected_hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=28
        )
        self.mode_seg.set("Solid Mesh")
        self.mode_seg.pack(fill=ctk.X, pady=(2, 14))

        # Stats-Card
        stats_card = make_material_card(ctrl_inner, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        stats_card.pack(fill=ctk.X, pady=(0, 14))

        sc_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        sc_inner.pack(fill=ctk.X, padx=10, pady=10)

        t_matrix = self.t_min_c + (self.calibrated_image.astype(np.float32) / 255.0) * (self.t_max_c - self.t_min_c)
        body_temps = t_matrix[self.body_mask > 0] if np.sum(self.body_mask > 0) > 0 else t_matrix
        min_t, mean_t, max_t = float(np.min(body_temps)), float(np.mean(body_temps)), float(np.max(body_temps))

        for lbl_t, val_t in [
            ("Peak-Temperatur (Gipfel):", f"{max_t:.2f} °C"),
            ("Mitteltemperatur:", f"{mean_t:.2f} °C"),
            ("Basaltemperatur (Tal):", f"{min_t:.2f} °C"),
            ("Thermischer Hub (ΔT):", f"{max_t - min_t:.2f} °C")
        ]:
            r = ctk.CTkFrame(sc_inner, fg_color="transparent")
            r.pack(fill=ctk.X, pady=1)
            ctk.CTkLabel(r, text=lbl_t, font=ctk.CTkFont(family=FONT_FAMILY, size=10), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            ctk.CTkLabel(r, text=val_t, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(side=ctk.RIGHT)

        # Snapshot Button
        ctk.CTkButton(
            ctrl_inner,
            text="📸 3D-Ansicht speichern",
            command=self._save_snapshot,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(fill=ctk.X, pady=(0, 6))

        ctk.CTkButton(
            ctrl_inner,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=30
        ).pack(fill=ctk.X)

    def _on_elev_changed(self, val: float) -> None:
        self.elev = int(round(val))
        self.elev_lbl.configure(text=f"{self.elev}°")
        self._plot_3d()

    def _on_azim_changed(self, val: float) -> None:
        self.azim = int(round(val))
        self.azim_lbl.configure(text=f"{self.azim}°")
        self._plot_3d()

    def _on_scale_changed(self, val: float) -> None:
        self.z_scale = float(val)
        self.scale_lbl.configure(text=f"{self.z_scale:.1f}×")
        self._plot_3d()

    def _on_mode_changed(self, mode: str) -> None:
        self.surface_mode = mode
        self._plot_3d()

    def _plot_3d(self) -> None:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        # Downsample für flüssiges 3D-Rendering (z. B. max 80x80 Gitter)
        h, w = self.calibrated_image.shape[:2]
        step = max(1, int(max(h, w) / 80))
        sub_img = self.calibrated_image[::step, ::step]
        sub_mask = self.body_mask[::step, ::step]

        sub_h, sub_w = sub_img.shape[:2]
        x = np.arange(0, sub_w)
        y = np.arange(0, sub_h)
        X, Y = np.meshgrid(x, y)

        # Temperaturmatrix
        Z = self.t_min_c + (sub_img.astype(np.float32) / 255.0) * (self.t_max_c - self.t_min_c)
        Z_scaled = Z * self.z_scale

        fig = plt.figure(figsize=(6.5, 5.5), dpi=100)
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#131923" if is_dark else "#FFFFFF"
        text_color = "#F8FAFC" if is_dark else "#0F172A"
        pane_color = "#1E293B" if is_dark else "#F1F5F9"

        fig.patch.set_facecolor(bg_color)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_facecolor(bg_color)

        cmap_map = {
            "turbo": "turbo",
            "inferno": "inferno",
            "ironbow": "magma",
            "jet": "jet",
            "hot": "hot"
        }
        active_cmap = cmap_map.get(self.palette_name, "turbo")

        if self.surface_mode == "Solid Mesh":
            surf = ax.plot_surface(
                X, Y, Z_scaled,
                cmap=active_cmap,
                edgecolor='none',
                rstride=1,
                cstride=1,
                antialiased=True,
                alpha=0.92
            )
        else:
            surf = ax.plot_wireframe(
                X, Y, Z_scaled,
                cmap=active_cmap,
                rstride=2,
                cstride=2,
                linewidth=0.6
            )

        ax.view_init(elev=self.elev, azim=self.azim)
        ax.set_xlabel("X (Pixel)", color=text_color, fontsize=8, labelpad=4)
        ax.set_ylabel("Y (Pixel)", color=text_color, fontsize=8, labelpad=4)
        ax.set_zlabel("Temperatur (°C)", color=text_color, fontsize=8, labelpad=4)
        ax.tick_params(colors=text_color, labelsize=7)

        # 3D Panes
        for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
            pane.set_facecolor(pane_color)
            pane.set_edgecolor(bg_color)

        fig.tight_layout()

        if self._canvas_tk:
            self._canvas_tk.get_tk_widget().destroy()

        self._canvas_tk = FigureCanvasTkAgg(fig, master=self.plot_host)
        self._canvas_tk.draw()
        self._canvas_tk.get_tk_widget().pack(fill="both", expand=True)
        self.fig = fig

    def _save_snapshot(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-Grafik", "*.png"), ("PDF-Dokument", "*.pdf"), ("JPEG", "*.jpg")],
            title="3D-Relief Snapshot speichern"
        )
        if path and hasattr(self, 'fig'):
            self.fig.savefig(path, dpi=200, bbox_inches='tight')


class DynamicPerfusionModal(ctk.CTkToplevel):
    """Interaktiver Kälteprovokations- und Wiedererwärmungs-Analyzer (Dynamic Thermal Recovery)."""

    def __init__(
        self,
        master,
        calibrated_image: np.ndarray,
        body_mask: Optional[np.ndarray] = None,
        t_min_c: float = 20.0,
        t_max_c: float = 40.0,
        palette_name: str = "turbo",
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)
        self.title("IGNITE – Dynamische Perfusions- & Wiedererwärmungsanalyse (Cold Stress Test)")
        self.geometry("960x720")
        self.minsize(860, 620)
        self.configure(fg_color=COLOR_BG_APP)

        self.calibrated_image = calibrated_image
        self.body_mask = body_mask if body_mask is not None else np.ones_like(calibrated_image) * 255
        self.t_min_c = float(t_min_c)
        self.t_max_c = float(t_max_c)
        self.palette_name = palette_name.lower()

        # Sequenz simulieren / generieren
        from gui.services.dynamic_perfusion_service import DynamicPerfusionService
        self.frames, self.time_points, self.mean_temps = DynamicPerfusionService.simulate_cold_stress_sequence(
            baseline_img=self.calibrated_image,
            body_mask=self.body_mask,
            num_frames=12,
            total_time_s=180.0
        )

        # Modellfittung
        self.fit_metrics = DynamicPerfusionService.fit_rewarming_curve(
            time_seconds=self.time_points,
            temperatures=np.array(self.mean_temps)
        )

        self.current_frame_idx = 0
        self._canvas_tk = None
        self._build_ui()
        self._update_view()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=290)
        self.grid_rowconfigure(0, weight=1)

        # Linker Bereich: Live-Plot der Wiedererwärmungskurve & Bildvorschau
        left_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        left_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        self.plot_host = ctk.CTkFrame(left_card, fg_color="transparent")
        self.plot_host.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # Rechter Bereich: Steuerung & Kinetik-Parameter
        right_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        right_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        r_inner = ctk.CTkFrame(right_card, fg_color="transparent")
        r_inner.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        ctk.CTkLabel(
            r_inner,
            text="WIEDERERWÄRMUNGS-KINETIK",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 10))

        # Zeit-Scrubber Slider
        ctk.CTkLabel(r_inner, text="Zeitpunkt t (s) nach Kältereiz:", font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.time_lbl = ctk.CTkLabel(r_inner, text=f"t = {self.time_points[0]:.0f} s", font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"), text_color=COLOR_PRIMARY)
        self.time_lbl.pack(anchor="e")

        self.time_slider = ctk.CTkSlider(
            r_inner,
            from_=0,
            to=len(self.time_points) - 1,
            number_of_steps=len(self.time_points) - 1,
            command=self._on_slider_moved,
            height=16,
            progress_color=COLOR_PRIMARY,
            button_color=COLOR_PRIMARY
        )
        self.time_slider.set(0)
        self.time_slider.pack(fill=ctk.X, pady=(0, 14))

        # Diagnose-Ergebnis Badge
        risk_box = make_material_card(r_inner, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        risk_box.pack(fill=ctk.X, pady=(0, 14))

        rb_inner = ctk.CTkFrame(risk_box, fg_color="transparent")
        rb_inner.pack(fill=ctk.X, padx=12, pady=12)

        ctk.CTkLabel(
            rb_inner,
            text="KLINISCHE BEWERTUNG",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w")

        ctk.CTkLabel(
            rb_inner,
            text=self.fit_metrics["classification"],
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=self.fit_metrics["color_hex"],
            wraplength=240,
            justify="left"
        ).pack(anchor="w", pady=(4, 0))

        # Kinetik Kennzahlen
        stats_card = make_material_card(r_inner, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        stats_card.pack(fill=ctk.X, pady=(0, 14))

        sc_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        sc_inner.pack(fill=ctk.X, padx=10, pady=10)

        for lbl_t, val_t in [
            ("Erwärmungsrate (k):", f"{self.fit_metrics['k_rate_min']:.3f} min⁻¹"),
            ("Halbwertszeit (t½):", f"{self.fit_metrics['half_time_s']:.1f} s"),
            ("Start-Temp (T₀):", f"{self.fit_metrics['t0_c']:.1f} °C"),
            ("Ziel-Temp (T_inf):", f"{self.fit_metrics['t_inf_c']:.1f} °C"),
            ("Modell-Güte (R²):", f"{self.fit_metrics['r_squared']:.4f}")
        ]:
            r = ctk.CTkFrame(sc_inner, fg_color="transparent")
            r.pack(fill=ctk.X, pady=1.5)
            ctk.CTkLabel(r, text=lbl_t, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY).pack(side=ctk.LEFT)
            ctk.CTkLabel(r, text=val_t, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(side=ctk.RIGHT)

        # Snapshot & Schließen
        ctk.CTkButton(
            r_inner,
            text="📸 Bericht exportieren",
            command=self._save_plot,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(fill=ctk.X, pady=(0, 6))

        ctk.CTkButton(
            r_inner,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=30
        ).pack(fill=ctk.X)

    def _on_slider_moved(self, val: float) -> None:
        idx = int(round(val))
        self.current_frame_idx = max(0, min(idx, len(self.time_points) - 1))
        self.time_lbl.configure(text=f"t = {self.time_points[self.current_frame_idx]:.0f} s")
        self._update_view()

    def _update_view(self) -> None:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#131923" if is_dark else "#FFFFFF"
        text_color = "#F8FAFC" if is_dark else "#0F172A"
        grid_color = "#334155" if is_dark else "#E2E8F0"

        fig, (ax_img, ax_curve) = plt.subplots(1, 2, figsize=(8.0, 4.8), dpi=100, gridspec_kw={'width_ratios': [1, 1.3]})
        fig.patch.set_facecolor(bg_color)

        # 1. Thermogramm zum ausgewählten Zeitpunkt
        cur_frame = self.frames[self.current_frame_idx]
        cur_t_c = 20.0 + (cur_frame.astype(np.float32) / 255.0) * 20.0

        ax_img.set_facecolor(bg_color)
        im = ax_img.imshow(cur_t_c, cmap=self.palette_name if self.palette_name in ['turbo', 'inferno', 'jet'] else 'turbo', vmin=20.0, vmax=38.0)
        ax_img.set_title(f"Thermogramm (t = {self.time_points[self.current_frame_idx]:.0f} s)", color=text_color, fontsize=10, pad=6)
        ax_img.axis('off')

        # 2. Wiedererwärmungskurve & Fit
        ax_curve.set_facecolor(bg_color)
        t_meas = self.fit_metrics["time_seconds"]
        y_meas = self.fit_metrics["measured_temps"]
        y_fit = self.fit_metrics["fitted_temps"]

        # Messpunkte
        ax_curve.scatter(t_meas, y_meas, color="#38BDF8", s=32, zorder=3, label="Gemessen")
        # Aktueller Punkt markieren
        ax_curve.scatter([self.time_points[self.current_frame_idx]], [self.mean_temps[self.current_frame_idx]], color="#EF4444", s=90, zorder=4, edgecolor="#FFFFFF", linewidth=1.5)

        # Exponentielle Modellkurve
        t_dense = np.linspace(0, max(t_meas), 100)
        k = self.fit_metrics["k_rate_s"]
        t0 = self.fit_metrics["t0_c"]
        t_inf = self.fit_metrics["t_inf_c"]
        y_dense = t_inf - (t_inf - t0) * np.exp(-k * t_dense)
        ax_curve.plot(t_dense, y_dense, color="#0284C7", linewidth=2.0, label=f"Pennes-Modell (R²={self.fit_metrics['r_squared']:.3f})")

        ax_curve.set_xlabel("Zeit nach Kältereiz t (s)", color=text_color, fontsize=9)
        ax_curve.set_ylabel("Mitteltemperatur (°C)", color=text_color, fontsize=9)
        ax_curve.set_title("Wiedererwärmungskinetik T(t)", color=text_color, fontsize=10, pad=6)
        ax_curve.grid(True, linestyle="--", alpha=0.5, color=grid_color)
        ax_curve.tick_params(colors=text_color, labelsize=8)
        for spine in ax_curve.spines.values():
            spine.set_color(grid_color)

        ax_curve.legend(loc="lower right", facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color, fontsize=8)

        fig.tight_layout()

        if self._canvas_tk:
            self._canvas_tk.get_tk_widget().destroy()

        self._canvas_tk = FigureCanvasTkAgg(fig, master=self.plot_host)
        self._canvas_tk.draw()
        self._canvas_tk.get_tk_widget().pack(fill="both", expand=True)
        self.fig = fig

    def _save_plot(self) -> None:
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG-Grafik", "*.png"), ("PDF-Dokument", "*.pdf")],
            title="Perfusionsanalyse speichern"
        )
        if path and hasattr(self, 'fig'):
            self.fig.savefig(path, dpi=200, bbox_inches='tight')


class UpdateModal(ctk.CTkToplevel):
    """Modernes Software-Update Modal für IGNITE im Google Material 3 Design."""

    def __init__(
        self,
        master,
        update_info: Optional[Any] = None,
        on_notify: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)

        self.title("IGNITE – Software-Update")
        self.geometry("600x520")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        self.update_info = update_info
        self.on_notify = on_notify
        self._cancel_event = threading.Event()
        self._is_downloading = False

        self._build_ui()

        if self.update_info is None:
            self._start_check()
        else:
            self._display_update_info()

    def _build_ui(self) -> None:
        container = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=14, pady=14)

        self.inner = ctk.CTkFrame(container, fg_color="transparent")
        self.inner.pack(fill=ctk.BOTH, expand=True, padx=18, pady=18)

        # Header
        ctk.CTkLabel(
            self.inner,
            text="IGNITE Software-Aktualisierung",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 2))

        ctk.CTkLabel(
            self.inner,
            text="Automatische Versionsprüfung & Release-Installation via GitHub",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(0, 14))

        # Dynamischer Inhalts-Container
        self.content_frame = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.content_frame.pack(fill=ctk.BOTH, expand=True)

        # Progress / Status-Bereich (initial verborgen)
        self.progress_frame = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.pbar = ctk.CTkProgressBar(self.progress_frame, height=8, progress_color=COLOR_PRIMARY)
        self.pbar.set(0.0)
        self.pbar.pack(fill=ctk.X, pady=(0, 4))
        
        self.lbl_progress = ctk.CTkLabel(
            self.progress_frame,
            text="Bereite Download vor...",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=10),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_progress.pack(anchor="w")

        # Footer Button-Bar
        self.button_bar = ctk.CTkFrame(self.inner, fg_color="transparent")
        self.button_bar.pack(fill=ctk.X, pady=(12, 0))

    def _start_check(self) -> None:
        """Führt die Versionsprüfung im Hintergrund-Thread durch."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        loading_box = make_material_card(self.content_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        loading_box.pack(fill=ctk.BOTH, expand=True, pady=10)

        ctk.CTkLabel(
            loading_box,
            text="🔄 Prüfe GitHub Releases auf neuere Versionen...",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(expand=True)

        def _do_check():
            import config
            from gui.services.update_service import UpdateService
            info = UpdateService.check_for_updates(
                current_version=getattr(config, "APP_VERSION", getattr(config, "CANONICAL_APP_VERSION", None)),
                repo=getattr(config, "GITHUB_REPO", UpdateService.DEFAULT_REPO)
            )
            self.after(0, lambda: self._on_check_finished(info))

        threading.Thread(target=_do_check, daemon=True).start()

    def _on_check_finished(self, info: Optional[Any]) -> None:
        self.update_info = info
        self._display_update_info()

    def _display_update_info(self) -> None:
        import webbrowser
        import config
        from gui.services.update_service import is_frozen_app

        for widget in self.content_frame.winfo_children():
            widget.destroy()
        for widget in self.button_bar.winfo_children():
            widget.destroy()

        cur_ver = getattr(config, "APP_VERSION", getattr(config, "CANONICAL_APP_VERSION", "4.0.3"))

        # Fall 1: Keine Verbindung oder Fehler
        if self.update_info is None:
            card = make_material_card(self.content_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
            card.pack(fill=ctk.BOTH, expand=True, pady=10, padx=4)

            ctk.CTkLabel(
                card,
                text="⚠️ Verbindung zu GitHub konnte nicht hergestellt werden.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
                text_color="#F59E0B"
            ).pack(pady=(20, 6))

            ctk.CTkLabel(
                card,
                text="Bitte überprüfe deine Internetverbindung oder versuche es später erneut.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_TEXT_MUTED
            ).pack(pady=(0, 20))

            ctk.CTkButton(
                self.button_bar,
                text="Erneut versuchen",
                command=self._start_check,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER,
                corner_radius=RADIUS_BUTTON,
                height=32
            ).pack(side=tk.LEFT)

            ctk.CTkButton(
                self.button_bar,
                text="Schließen",
                command=self.destroy,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=COLOR_BG_CARD_VARIANT,
                hover_color=COLOR_BG_CARD_HOVER,
                corner_radius=RADIUS_BUTTON,
                height=32
            ).pack(side=tk.RIGHT)
            return

        # Fall 2: Version ist aktuell
        if not self.update_info.is_newer:
            card = make_material_card(self.content_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
            card.pack(fill=ctk.BOTH, expand=True, pady=10, padx=4)

            ctk.CTkLabel(
                card,
                text=f"✓ Ihre Version v{cur_ver} ist auf dem neuesten Stand!",
                font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                text_color="#10B981"
            ).pack(pady=(24, 6))

            ctk.CTkLabel(
                card,
                text=f"Neuestes Release auf GitHub: {self.update_info.tag_name}\nKeine Aktualisierung erforderlich.",
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                text_color=COLOR_TEXT_MUTED,
                justify="center"
            ).pack(pady=(0, 24))

            ctk.CTkButton(
                self.button_bar,
                text="Auf GitHub ansehen",
                command=lambda: webbrowser.open(self.update_info.html_url),
                font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                fg_color=COLOR_BG_CARD_VARIANT,
                hover_color=COLOR_BG_CARD_HOVER,
                corner_radius=RADIUS_BUTTON,
                height=32
            ).pack(side=tk.LEFT)

            ctk.CTkButton(
                self.button_bar,
                text="Schließen",
                command=self.destroy,
                font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
                fg_color=COLOR_PRIMARY,
                hover_color=COLOR_PRIMARY_HOVER,
                corner_radius=RADIUS_BUTTON,
                height=32
            ).pack(side=tk.RIGHT)
            return

        # Fall 3: Neues Update verfügbar!
        # Versions-Vergleichs-Banner
        banner = make_material_card(self.content_frame, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        banner.pack(fill=ctk.X, pady=(0, 10))

        banner_inner = ctk.CTkFrame(banner, fg_color="transparent")
        banner_inner.pack(fill=ctk.X, padx=12, pady=10)

        # Aktuell vs Neu
        ver_row = ctk.CTkFrame(banner_inner, fg_color="transparent")
        ver_row.pack(fill=ctk.X)

        ctk.CTkLabel(
            ver_row,
            text=f"Aktuell: v{cur_ver}",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=tk.LEFT)

        ctk.CTkLabel(
            ver_row,
            text=" ➔ ",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(side=tk.LEFT, padx=6)

        ctk.CTkLabel(
            ver_row,
            text=f"Verfügbar: {self.update_info.tag_name}",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11, weight="bold"),
            text_color="#38BDF8"
        ).pack(side=tk.LEFT)

        # Asset-Info
        size_mb = self.update_info.asset_size / (1024 * 1024) if self.update_info.asset_size > 0 else 0
        asset_info_text = f"Asset: {self.update_info.asset_name}"
        if size_mb > 0:
            asset_info_text += f" ({size_mb:.1f} MB)"

        ctk.CTkLabel(
            banner_inner,
            text=asset_info_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w", pady=(4, 0))

        # Release Notes Label
        ctk.CTkLabel(
            self.content_frame,
            text="Versionshinweise / Changelog:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", pady=(4, 4))

        # Release Notes Scrollable Box
        notes_box = ctk.CTkScrollableFrame(
            self.content_frame,
            fg_color=COLOR_BG_CARD_VARIANT,
            corner_radius=RADIUS_CARD,
            height=140
        )
        notes_box.pack(fill=ctk.BOTH, expand=True, pady=(0, 6))

        notes_text = self.update_info.release_notes or "Keine detaillierten Versionshinweise angegeben."
        ctk.CTkLabel(
            notes_box,
            text=notes_text,
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_SECONDARY,
            justify="left",
            wraplength=520
        ).pack(anchor="w", padx=8, pady=8)

        # Button-Bar
        frozen = is_frozen_app()

        ctk.CTkButton(
            self.button_bar,
            text="Auf GitHub ansehen",
            command=lambda: webbrowser.open(self.update_info.html_url),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(side=tk.LEFT)

        ctk.CTkButton(
            self.button_bar,
            text="Später",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(side=tk.RIGHT, padx=(8, 0))

        btn_action_text = "Jetzt aktualisieren & neu starten" if frozen else "Installer herunterladen"
        self.btn_update = ctk.CTkButton(
            self.button_bar,
            text=btn_action_text,
            command=self._start_download_and_install,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34
        )
        self.btn_update.pack(side=tk.RIGHT)

    def _start_download_and_install(self) -> None:
        """Startet den Download des Release-Assets und die anschließende Installation."""
        if not self.update_info or not self.update_info.asset_url:
            if self.on_notify:
                self.on_notify("Fehler", "Keine gültige Download-URL gefunden.")
            return

        self._is_downloading = True
        self.btn_update.configure(state="disabled", text="Wird vorbereitet...")
        self.progress_frame.pack(fill=ctk.X, pady=(4, 8))

        def _worker():
            from gui.services.update_service import UpdateService, is_frozen_app

            def _on_progress(pct: float, current_b: int, total_b: int):
                cur_mb = current_b / (1024 * 1024)
                tot_mb = total_b / (1024 * 1024)
                self.after(0, lambda: self._update_progress_ui(pct, cur_mb, tot_mb))

            try:
                installer_file = UpdateService.download_update_asset(
                    asset_url=self.update_info.asset_url,
                    dest_filename=self.update_info.asset_name,
                    progress_callback=_on_progress,
                    cancel_event=self._cancel_event
                )

                self.after(0, lambda: self._on_download_complete(installer_file))

            except Exception as e:
                self.after(0, lambda: self._on_download_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_progress_ui(self, pct: float, cur_mb: float, tot_mb: float) -> None:
        self.pbar.set(pct)
        pct_int = int(pct * 100)
        self.lbl_progress.configure(
            text=f"Lade herunter: {cur_mb:.1f} MB / {tot_mb:.1f} MB ({pct_int}%)"
        )
        self.btn_update.configure(text=f"Download {pct_int}%...")

    def _on_download_complete(self, installer_path: str) -> None:
        import webbrowser
        from gui.services.update_service import UpdateService, is_frozen_app

        self.pbar.set(1.0)
        self.lbl_progress.configure(text="✓ Download erfolgreich abgeschlossen!")

        if is_frozen_app():
            self.lbl_progress.configure(text="Starte Setup-Programm & beende Anwendung...")
            self.after(600, lambda: UpdateService.apply_update(installer_path))
        else:
            # Im Entwickler-Modus Datei im Explorer anzeigen
            self.lbl_progress.configure(text=f"Gespeichert in: {installer_path}")
            if sys.platform.startswith("win"):
                os.system(f'explorer.exe /select,"{installer_path}"')
            if self.on_notify:
                self.on_notify("Download abgeschlossen", f"Installer gespeichert unter: {installer_path}")
            self.btn_update.configure(state="normal", text="Installer ausführen", command=lambda: UpdateService.apply_update(installer_path))

    def _on_download_error(self, err_msg: str) -> None:
        self._is_downloading = False
        self.lbl_progress.configure(text=f"❌ Download fehlgeschlagen: {err_msg}")
        self.btn_update.configure(state="normal", text="Erneut versuchen")
        if self.on_notify:
            self.on_notify("Update-Fehler", f"Download fehlgeschlagen: {err_msg}")


