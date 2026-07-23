# -*- coding: utf-8 -*-
"""dialogs.py – Dialogfenster und Modal-Viewer für IGNITE."""

import tkinter as tk
import customtkinter as ctk
from PIL import Image

from gui.theme import (
    COLOR_BG_MAIN,
    COLOR_BG_CARD,
    COLOR_BORDER_CARD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_PRIMARY_ACCENT,
    COLOR_HOVER_ACCENT,
    FONT_FAMILY
)

APP_VERSION = "1.0.0"

class FullscreenImageModal(ctk.CTkToplevel):
    """Modal-Dialog zur vergrößerten Inspektion von Einzelbildern."""

    def __init__(self, master, panel_name: str, pil_image: Image.Image, **kwargs):
        super().__init__(master, **kwargs)
        self.title(f"IGNITE – Detailansicht: {panel_name}")
        self.geometry("1000x700")
        self.minsize(800, 500)
        self.configure(fg_color=COLOR_BG_MAIN)

        self.panel_name = panel_name
        self.pil_image = pil_image

        top_bar = ctk.CTkFrame(self, height=40, fg_color=COLOR_BG_CARD, corner_radius=0)
        top_bar.pack(fill=ctk.X, side=ctk.TOP)
        
        ctk.CTkLabel(top_bar, text=f"🔍 Detailinspektion: {panel_name}", font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(side=ctk.LEFT, padx=15)
        
        close_btn = ctk.CTkButton(top_bar, text="Schließen ✕", width=90, height=28, command=self.destroy, fg_color=COLOR_PRIMARY_ACCENT, hover_color=COLOR_HOVER_ACCENT)
        close_btn.pack(side=ctk.RIGHT, padx=10, pady=6)

        self.img_lbl = ctk.CTkLabel(self, text="")
        self.img_lbl.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)
        
        self.bind("<Configure>", self._on_resize)
        self.after(50, self._render_image)

    def _on_resize(self, event=None):
        if event and event.widget == self:
            self._render_image()

    def _render_image(self):
        w = max(self.img_lbl.winfo_width() - 20, 200)
        h = max(self.img_lbl.winfo_height() - 20, 200)

        img_copy = self.pil_image.copy()
        img_copy.thumbnail((w, h))

        ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
        self.img_lbl.configure(image=ctk_img)
        self.img_lbl.image = ctk_img


class InstructionsModal(ctk.CTkToplevel):
    """Anleitungs- und Dokumentationsdialog."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.title("IGNITE – Anleitung & Hilfe")
        self.geometry("700x550")
        self.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG_CARD, corner_radius=12)
        container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(container, text="📖 Bedienungsanleitung IGNITE", font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(10, 15), padx=15)

        instructions = [
            ("1. Wärmebild laden", "Klicke in der linken Seitenleiste auf 'Wärmebild laden' und wähle ein 8-Bit- oder 16-Bit-Infrarotbild (.jpeg, .png, .tiff, .flir) aus."),
            ("2. Auswertungsmodus wählen", "Wähle zwischen 'Klinischer Allgemeinanalyse' und 'Podologischer Symmetrieanalyse'."),
            ("3. Parameter anpassen", "Öffne die 'Pipeline-Parameter', um den Threshold-Multiplikator (k), den Top-Hat-Kernel oder das robuste MAD-Thresholding einzustellen."),
            ("4. Kontralaterale Asymmetrie", "Aktiviere diekontralaterale Asymmetrie-Prüfung (>2.2 °C Goldstandard nach Armstrong) zur automatischen Entzündungserkennung."),
            ("5. Interaktive ROI-Analyse", "Ziehe auf einem beliebigen Bild im Hauptbereich mit der linken Maustaste ein Rechteck (ROI) auf, um Minimal-, Maximal- und Mittelwerte live einzusehen."),
            ("6. Berichte & Exports", "Nutze 'Aktionen & Berichte', um HTML-Klinikberichte, CSV-Patientenprotokolle oder annotierte Overlay-Grafiken zu generieren.")
        ]

        for title, desc in instructions:
            ctk.CTkLabel(container, text=title, font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"), text_color=COLOR_PRIMARY_ACCENT).pack(anchor="w", padx=15, pady=(8, 2))
            ctk.CTkLabel(container, text=desc, font=ctk.CTkFont(family=FONT_FAMILY, size=11), text_color=COLOR_TEXT_SECONDARY, wraplength=620, justify="left").pack(anchor="w", padx=15, pady=(0, 6))

        close_btn = ctk.CTkButton(self, text="Schließen", command=self.destroy, fg_color=COLOR_PRIMARY_ACCENT, hover_color=COLOR_HOVER_ACCENT)
        close_btn.pack(pady=(0, 15))


class AboutModal(ctk.CTkToplevel):
    """Über-Ignite Dialogfenster."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.title("Über IGNITE")
        self.geometry("550x420")
        self.configure(fg_color=COLOR_BG_MAIN)

        container = ctk.CTkFrame(self, fg_color=COLOR_BG_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDER_CARD)
        container.pack(fill=ctk.BOTH, expand=True, padx=20, pady=20)

        ctk.CTkLabel(container, text="IGNITE Medical Imaging Suite", font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(pady=(25, 4))
        ctk.CTkLabel(container, text=f"Version {APP_VERSION} · Jugend forscht 2026", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_PRIMARY_ACCENT).pack(pady=(0, 15))

        info_text = (
            "Entwickelt für die automatische Früherkennung thermischer Anomalien\n"
            "und Entzündungsprozessen in der Medizinischen Thermografie.\n\n"
            "• Hochleistungs-Core: Rust (ignite_core v1.0) & PyTorch CUDA\n"
            "• Physikalische Radiometrie: Stefan-Boltzmann-Strahlungsmodell (ε=0.98)\n"
            "• Datenschutz: 100% Lokale In-Memory-Verarbeitung (DSGVO / HIPAA)"
        )

        ctk.CTkLabel(container, text=info_text, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_SECONDARY, justify="center").pack(pady=10)

        ctk.CTkLabel(container, text="© 2026 Jona Noack · Alle Rechte vorbehalten", font=ctk.CTkFont(size=10), text_color=COLOR_TEXT_PRIMARY).pack(pady=(15, 15))

        close_btn = ctk.CTkButton(self, text="Schließen", command=self.destroy, fg_color=COLOR_PRIMARY_ACCENT, hover_color=COLOR_HOVER_ACCENT)
        close_btn.pack(pady=(0, 15))
