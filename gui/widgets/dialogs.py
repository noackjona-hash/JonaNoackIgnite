# -*- coding: utf-8 -*-
"""gui/widgets/dialogs.py – High-Contrast Modals & Dialogs for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Optional
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

        ctk.CTkLabel(
            inner,
            text="Version 3.2.0 · Jugend forscht 2026 (Fachgebiet Arbeitswelt)",
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

        ctk.CTkButton(
            inner,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34,
            width=120
        ).pack()


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
            values=["PDF (.pdf)", "HTML (.html)", "Beide (PDF + HTML)"],
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
