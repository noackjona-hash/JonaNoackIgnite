# -*- coding: utf-8 -*-
"""gui/widgets/dialogs.py – Google Material 3 Modals & Dialogs for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk

from gui.theme import (
    COLOR_BG_APP,
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_BLUE,
    COLOR_CONTAINER_GREEN,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
)
from gui.utils_ui import make_material_card


class AboutModal(ctk.CTkToplevel):
    """Google Material 3 Info-Dialog über IGNITE."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("Über IGNITE")
        self.geometry("540x440")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        container = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(fill=ctk.BOTH, expand=True, padx=24, pady=24)

        # Header
        ctk.CTkLabel(
            inner,
            text="🔬",
            font=ctk.CTkFont(size=36)
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            inner,
            text="IGNITE Medical Imaging Suite",
            font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack()

        ctk.CTkLabel(
            inner,
            text="v3.2 · Jugend forscht 2026 (Fachgebiet Arbeitswelt)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY
        ).pack(pady=(2, 14))

        # Info Box
        info_card = make_material_card(inner, corner_radius=10, fg_color=COLOR_BG_CARD_VARIANT)
        info_card.pack(fill=ctk.BOTH, expand=True, pady=(0, 16))

        info_inner = ctk.CTkFrame(info_card, fg_color="transparent")
        info_inner.pack(fill=ctk.BOTH, expand=True, padx=16, pady=12)

        bullets = [
            ("⚡ High-Performance Core", "Rust (rayon/ndarray) + PyTorch CUDA GPU (<10ms)"),
            ("🌡️ Radiometrie", "Stefan-Boltzmann Emissivitätskorrektur (ε=0.98)"),
            ("🦶 Diabetischer Fuß", "Kontralaterale Asymmetrie (>2.2°C Goldstandard)"),
            ("🛡️ Datenschutz", "Lokale In-Memory Verarbeitung & DSGVO SHA-256 Hashing"),
        ]

        for title, desc in bullets:
            row = ctk.CTkFrame(info_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=3)
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY, anchor="w").pack(side=ctk.LEFT)
            ctk.CTkLabel(row, text=desc, font=ctk.CTkFont(family=FONT_FAMILY, size=10), text_color=COLOR_TEXT_MUTED, anchor="e").pack(side=ctk.RIGHT)

        ctk.CTkLabel(
            inner,
            text="© 2026 Jona Noack · Forschungsprototyp (Kein zertifiziertes Medizinprodukt)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=9),
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
            corner_radius=18,
            height=34,
            width=120
        ).pack()


class HelpModal(ctk.CTkToplevel):
    """Google Material 3 Anleitungs- und Hilfedialog."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("IGNITE – Bedienungsanleitung")
        self.geometry("640x520")
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        container = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            scroll,
            text="📖 Bedienungsanleitung & Schnelleinstieg",
            font=ctk.CTkFont(family=FONT_FAMILY, size=18, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 14))

        steps = [
            ("1. Wärmebild öffnen", "Klicke oben rechts auf '+ Wärmebild öffnen' (Ctrl+O) und wähle eine Infrarotdatei (.jpg, .png, .tiff, .flir) aus."),
            ("2. Dashboard-Übersicht", "Das 4-Stufen-Dashboard berechnet automatisch Originalbild, Körpermaske, Top-Hat Differenz und Hotspot-Overlay."),
            ("3. Live-ROI & Inspektion", "Wechsle zu 'Inspektion', um durch Aufziehen eines Rechtecks mit der Maus beliebige Zonen live auszumessen."),
            ("4. Podologische Symmetrie", "Im Tab 'Podologie' wird das 3-Zonen-Modell (Vorfuß, Mittelfuß, Ferse) mit dem klinischen 2.2 °C Grenzwert verglichen."),
            ("5. HTML-Bericht exportieren", "Klicke in der Seitenleiste auf 'HTML-Bericht exportieren' (Ctrl+E), um einen interaktiven Befundbericht zu speichern."),
            ("6. Tastenkombinationen", "Ctrl+K: Befehlssuche · Ctrl+O: Öffnen · Ctrl+E: Exportieren · Ctrl+T: Dark/Light Mode · F5: Neu berechnen.")
        ]

        for title, desc in steps:
            card = make_material_card(scroll, corner_radius=10, fg_color=COLOR_BG_CARD_VARIANT)
            card.pack(fill=ctk.X, pady=4)
            c_inner = ctk.CTkFrame(card, fg_color="transparent")
            c_inner.pack(fill=ctk.X, padx=14, pady=10)

            ctk.CTkLabel(c_inner, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_PRIMARY, anchor="w").pack(fill=ctk.X)
            ctk.CTkLabel(c_inner, text=desc, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY, anchor="w", wraplength=520, justify="left").pack(fill=ctk.X, pady=(2, 0))

        ctk.CTkButton(
            scroll,
            text="Schließen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=18,
            height=34,
            width=120
        ).pack(pady=(16, 8))


class PatientExportModal(ctk.CTkToplevel):
    """Dialog zur Eingabe von Patientendaten vor dem HTML-Report-Export."""

    def __init__(self, master, on_submit: Callable[[str, str, str, str], None], **kwargs) -> None:
        super().__init__(master, **kwargs)

        self.title("Befundbericht exportieren")
        self.geometry("480x420")
        self.resizable(False, False)
        self.transient(master)
        self.configure(fg_color=COLOR_BG_APP)

        self.on_submit = on_submit

        container = make_material_card(self, corner_radius=16, fg_color=COLOR_BG_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            inner,
            text="📄 Befundbericht exportieren",
            font=ctk.CTkFont(family=FONT_FAMILY, size=16, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X, pady=(0, 12))

        # Patienten-ID
        ctk.CTkLabel(inner, text="Patienten-Name / ID:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.patient_entry = ctk.CTkEntry(inner, placeholder_text="z. B. Max Mustermann oder ANON-001", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.patient_entry.pack(fill=ctk.X, pady=(2, 10))

        # Geburtsdatum
        ctk.CTkLabel(inner, text="Geburtsdatum (optional für SHA-256 Hash):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.dob_entry = ctk.CTkEntry(inner, placeholder_text="TT.MM.JJJJ", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.dob_entry.pack(fill=ctk.X, pady=(2, 10))

        # Untersucher
        ctk.CTkLabel(inner, text="Untersucher / Bediener:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.operator_entry = ctk.CTkEntry(inner, placeholder_text="Jugend forscht 2026", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.operator_entry.insert(0, "Jugend forscht 2026")
        self.operator_entry.pack(fill=ctk.X, pady=(2, 10))

        # Anmerkungen
        ctk.CTkLabel(inner, text="Klinische Anmerkungen:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(inner, placeholder_text="z. B. Postoperatives Monitoring", font=ctk.CTkFont(family=FONT_FAMILY, size=12), fg_color=COLOR_BG_CARD_VARIANT, border_color=COLOR_OUTLINE)
        self.notes_entry.pack(fill=ctk.X, pady=(2, 16))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill=ctk.X)

        ctk.CTkButton(
            btn_row,
            text="Abbrechen",
            command=self.destroy,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=18,
            height=36,
            width=100
        ).pack(side=ctk.LEFT)

        ctk.CTkButton(
            btn_row,
            text="Bericht speichern",
            command=self._on_save,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=18,
            height=36
        ).pack(side=ctk.RIGHT, fill=ctk.X, expand=True, padx=(10, 0))

    def _on_save(self) -> None:
        p_name = self.patient_entry.get().strip() or "Unbekannt"
        p_dob = self.dob_entry.get().strip()
        op = self.operator_entry.get().strip() or "Jugend forscht"
        notes = self.notes_entry.get().strip()

        self.destroy()
        self.on_submit(p_name, p_dob, op, notes)
