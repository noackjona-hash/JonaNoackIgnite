# -*- coding: utf-8 -*-
"""gui/views/podology_view.py – Clinical Podology & Contralateral Asymmetry for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Optional, Any
import customtkinter as ctk
from PIL import Image
import numpy as np

import config
from gui.theme import (
    COLOR_BG_CARD,
    COLOR_BG_CARD_VARIANT,
    COLOR_BG_CARD_HOVER,
    COLOR_OUTLINE,
    COLOR_OUTLINE_VARIANT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_DANGER,
    COLOR_WARNING,
    COLOR_CONTAINER_GREEN,
    COLOR_CONTAINER_RED,
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card, make_display_ctk_image
from utils import pixel_to_celsius


class PodologyView(ctk.CTkFrame):
    """Klinische Podologie-, Asymmetrie- und 3-Zonen-Diagnostik im High-Contrast Workstation Design."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.current_result: Optional[dict[str, Any]] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)  # Linke Bildansicht
        self.grid_columnconfigure(1, weight=0, minsize=420)  # Rechter Befundbereich mit fester Mindestbreite
        self.grid_rowconfigure(0, weight=1)

        # ── Linke Spalte: Annotiertes Symmetrie-Bild ─────────────────────────
        self.img_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.img_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")

        # Header
        top_bar = ctk.CTkFrame(self.img_card, fg_color="transparent", height=46)
        top_bar.pack(fill=ctk.X, padx=14, pady=(10, 6))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar,
            text="KLINISCHES SYMMETRIE- & ZONENBILD",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(side=ctk.LEFT)

        self.region_badge = ctk.CTkLabel(
            top_bar,
            text="🦶 Füße & Podologie",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY
        )
        self.region_badge.pack(side=ctk.LEFT, padx=(12, 0))

        self.pca_lbl = ctk.CTkLabel(
            top_bar,
            text="PCA-Ausrichtung: Aktiv",
            font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11),
            text_color=COLOR_TEXT_MUTED
        )
        self.pca_lbl.pack(side=ctk.RIGHT)

        ctk.CTkFrame(self.img_card, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        self.img_lbl = ctk.CTkLabel(
            self.img_card,
            text="Keine Messdaten vorhanden",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.img_lbl.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # ── Rechte Spalte: Asymmetrie-Banner & 3-Zonen Tabelle ───────────────
        self.side_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.side_card.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")
        self.side_card.configure(width=420)

        scroll = ctk.CTkScrollableFrame(self.side_card, fg_color="transparent", width=390)
        scroll.pack(fill=ctk.BOTH, expand=True, padx=8, pady=10)

        # 1. Klinischer Goldstandard Banner
        ctk.CTkLabel(
            scroll,
            text="KLINISCHER SYMMETRIESTATUS",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(2, 6))

        self.asym_banner = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_CONTAINER_GREEN, border_width=1, border_color=COLOR_OUTLINE)
        self.asym_banner.pack(fill=ctk.X, padx=4, pady=(0, 14))

        b_inner = ctk.CTkFrame(self.asym_banner, fg_color="transparent")
        b_inner.pack(fill=ctk.X, padx=14, pady=12)

        self.asym_status_lbl = ctk.CTkLabel(
            b_inner,
            text="Physiologisch Symmetrisch",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_SUCCESS,
            anchor="w"
        )
        self.asym_status_lbl.pack(fill=ctk.X)

        self.asym_delta_lbl = ctk.CTkLabel(
            b_inner,
            text="Seiten-Differenz ΔT = 0.0 °C  (Grenzwert: 2.2 °C)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.asym_delta_lbl.pack(fill=ctk.X, pady=(2, 0))

        # 2. 3-Zonen Tabelle (PCA-Ausrichtung)
        ctk.CTkLabel(
            scroll,
            text="3-ZONEN TEMPERATUR-VERGLEICH (PCA-ENTZERRT)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=4, pady=(2, 6))

        self.zones_box = ctk.CTkFrame(scroll, fg_color="transparent")
        self.zones_box.pack(fill=ctk.X, padx=4)

        self.zone_rows = {}
        self.zone_title_lbls = {}
        self.zone_hint_lbls = {}

        zones = [
            ("fore", "Zone 1 (Vorfuß / Finger / Proximal)", "Druckstellen, Ulzera, Phalangen & Mikroläsionen"),
            ("mid",  "Zone 2 (Mittelfuß / Mittelhand / Patella)", "Längsgewölbe, Gelenkspalt, Charcot-Frühstadium"),
            ("heel", "Zone 3 (Ferse / Handwurzel / Distal)", "Calcaneus, Handwurzelknochen, Überlastung")
        ]

        for z_key, title, hint in zones:
            z_card = make_material_card(self.zones_box, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
            z_card.pack(fill=ctk.X, pady=4)

            z_inner = ctk.CTkFrame(z_card, fg_color="transparent")
            z_inner.pack(fill=ctk.X, padx=12, pady=10)

            t_lbl = ctk.CTkLabel(
                z_inner,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            t_lbl.pack(fill=ctk.X)
            self.zone_title_lbls[z_key] = t_lbl

            h_lbl = ctk.CTkLabel(
                z_inner,
                text=hint,
                font=ctk.CTkFont(family=FONT_FAMILY, size=10),
                text_color=COLOR_TEXT_MUTED,
                anchor="w"
            )
            h_lbl.pack(fill=ctk.X, pady=(1, 4))
            self.zone_hint_lbls[z_key] = h_lbl

            # Grid mit Werten L vs R vs Delta
            val_grid = ctk.CTkFrame(z_inner, fg_color="transparent")
            val_grid.pack(fill=ctk.X, pady=(2, 0))
            val_grid.grid_columnconfigure(0, weight=1)
            val_grid.grid_columnconfigure(1, weight=1)
            val_grid.grid_columnconfigure(2, weight=1)

            lbl_l = ctk.CTkLabel(
                val_grid,
                text="L: --.- °C",
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_l.grid(row=0, column=0, sticky="w", padx=(0, 4))

            lbl_r = ctk.CTkLabel(
                val_grid,
                text="R: --.- °C",
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"),
                text_color=COLOR_TEXT_PRIMARY,
                anchor="w"
            )
            lbl_r.grid(row=0, column=1, sticky="w", padx=4)

            lbl_d = ctk.CTkLabel(
                val_grid,
                text="Δ --.- °C",
                font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12, weight="bold"),
                text_color=COLOR_SUCCESS,
                anchor="e"
            )
            lbl_d.grid(row=0, column=2, sticky="e", padx=(4, 0))

            self.zone_rows[z_key] = (lbl_l, lbl_r, lbl_d)

        # 3. Cavanagh & Rodgers Plantar Arch Index (Biomechanik - nur bei Füßen)
        self.arch_header_lbl = ctk.CTkLabel(
            scroll,
            text="PLANTARER GEWÖLBE-INDEX (CAVANAGH & RODGERS)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        )
        self.arch_header_lbl.pack(fill=ctk.X, padx=4, pady=(10, 6))

        self.arch_card = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        self.arch_card.pack(fill=ctk.X, padx=4, pady=(0, 10))

        a_inner = ctk.CTkFrame(self.arch_card, fg_color="transparent")
        a_inner.pack(fill=ctk.X, padx=12, pady=10)

        self.arch_l_lbl = ctk.CTkLabel(
            a_inner,
            text="Linke Seite: AI = -- (Normal)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.arch_l_lbl.pack(fill=ctk.X)

        self.arch_r_lbl = ctk.CTkLabel(
            a_inner,
            text="Rechte Seite: AI = -- (Normal)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            anchor="w"
        )
        self.arch_r_lbl.pack(fill=ctk.X, pady=(2, 4))

        ctk.CTkLabel(
            a_inner,
            text="Index-Referenz: <0.21 Pes Cavus (Hohlfuß) | 0.21-0.26 Normal | >0.26 Pes Planus (Charcot-Senkfuß)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=9),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=340,
            justify="left"
        ).pack(fill=ctk.X)

        # 4. Fußnote mit wissenschaftlicher Referenz
        note_card = make_material_card(scroll, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        note_card.pack(fill=ctk.X, padx=4, pady=(10, 4))
        n_inner = ctk.CTkFrame(note_card, fg_color="transparent")
        n_inner.pack(fill=ctk.X, padx=12, pady=10)

        ctk.CTkLabel(
            n_inner,
            text="Wissenschaftlicher Leitlinien-Goldstandard",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            text_color=COLOR_PRIMARY,
            anchor="w"
        ).pack(fill=ctk.X)

        self.note_lbl = ctk.CTkLabel(
            n_inner,
            text="Schwellenwert nach Armstrong et al. (1997) & IWGDF Guidelines: Temperatur-Differenzen ΔT > 2.2 °C zwischen kontralateralen Regionen indizieren ein signifikant erhöhtes Risiko für diabetische Fußulzera.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED,
            anchor="w",
            wraplength=340,
            justify="left"
        )
        self.note_lbl.pack(fill=ctk.X, pady=(2, 0))

        # Dynamisches Wraplength-Update bei Resize
        def _on_scroll_resize(event):
            if event.width > 50:
                self.note_lbl.configure(wraplength=max(260, event.width - 48))
        scroll.bind("<Configure>", _on_scroll_resize)

    def show_results(self, result: dict[str, Any]) -> None:
        self.current_result = result
        t_min = result.get("t_min_c", 20.0)
        t_max = result.get("t_max_c", 40.0)

        region_key = result.get("anatomy_region", getattr(config, "DEFAULT_ANATOMY_REGION", "feet"))
        reg_info = getattr(config, "ANATOMICAL_REGIONS", {}).get(region_key, {})
        thresh_c = float(result.get("asym_results", {}).get("threshold_c", reg_info.get("asym_thresh_c", 2.2)))

        # Region Badge aktualisieren
        r_name = reg_info.get("name", "Anatomische Region")
        r_icon = reg_info.get("icon", "🩺")
        self.region_badge.configure(text=f"{r_icon} {r_name}")

        # 1. Asymmetrie-Banner aktualisieren
        asym = result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)
        is_asym = asym.get("is_asymmetric", False)

        if is_asym:
            self.asym_banner.configure(fg_color=COLOR_CONTAINER_RED)
            self.asym_status_lbl.configure(text="Pathologische Asymmetrie", text_color=COLOR_DANGER)
            self.asym_delta_lbl.configure(text=f"Seiten-Differenz ΔT = {delta_t:.1f} °C (> {thresh_c:.1f} °C Grenzwert)")
        else:
            self.asym_banner.configure(fg_color=COLOR_CONTAINER_GREEN)
            self.asym_status_lbl.configure(text="Physiologisch Symmetrisch", text_color=COLOR_SUCCESS)
            self.asym_delta_lbl.configure(text=f"Seiten-Differenz ΔT = {delta_t:.1f} °C (Normbereich <= {thresh_c:.1f} °C)")

        # PCA-Winkel anzeigen
        pca = result.get("pca_results")
        if pca and pca.get("left", {}).get("exists") and pca.get("right", {}).get("exists"):
            l_ang = pca["left"].get("angle_deg", 0.0)
            r_ang = pca["right"].get("angle_deg", 0.0)
            self.pca_lbl.configure(text=f"PCA-Achsen: L: {l_ang:+.1f}° | R: {r_ang:+.1f}° (Entzerrt)", text_color=COLOR_PRIMARY)
        else:
            self.pca_lbl.configure(text="PCA-Ausrichtung: Standard", text_color=COLOR_TEXT_MUTED)

        # Zonen-Titel dynamisch anpassen
        z1_name = reg_info.get("zone_1_name", "Zone 1")
        z2_name = reg_info.get("zone_2_name", "Zone 2")
        z3_name = reg_info.get("zone_3_name", "Zone 3")

        self.zone_title_lbls["fore"].configure(text=f"1. {z1_name}")
        self.zone_title_lbls["mid"].configure(text=f"2. {z2_name}")
        self.zone_title_lbls["heel"].configure(text=f"3. {z3_name}")

        # 2. 3-Zonen-Tabelle
        zonal = result.get("zonal_stats", {})
        if zonal.get("left", {}).get("exists") and zonal.get("right", {}).get("exists"):
            for z_key in ["fore", "mid", "heel"]:
                l_raw = zonal["left"][z_key]
                r_raw = zonal["right"][z_key]

                l_c = l_raw if l_raw < 100.0 else pixel_to_celsius(l_raw, t_min, t_max)
                r_c = r_raw if r_raw < 100.0 else pixel_to_celsius(r_raw, t_min, t_max)
                d_c = abs(l_c - r_c)

                lbl_l, lbl_r, lbl_d = self.zone_rows[z_key]
                lbl_l.configure(text=f"L: {l_c:.1f} °C")
                lbl_r.configure(text=f"R: {r_c:.1f} °C")

                d_color = COLOR_DANGER if d_c > thresh_c else COLOR_SUCCESS
                warn_sym = " ⚠️" if d_c > thresh_c else ""
                lbl_d.configure(text=f"Δ {d_c:.1f} °C{warn_sym}", text_color=d_color)

            # 3. Arch Index aktualisieren (nur bei Füßen)
            show_arch = reg_info.get("show_arch_index", region_key == "feet")
            if show_arch:
                self.arch_header_lbl.pack(fill=ctk.X, padx=4, pady=(10, 6))
                self.arch_card.pack(fill=ctk.X, padx=4, pady=(0, 10))

                ai_l = zonal["left"].get("arch_index")
                type_l = zonal["left"].get("arch_type", "Normal")
                code_l = zonal["left"].get("arch_code", "normal")
                col_l = COLOR_DANGER if code_l == "planus" else (COLOR_WARNING if code_l == "cavus" else COLOR_SUCCESS)
                if ai_l is not None:
                    self.arch_l_lbl.configure(text=f"Linker Fuß: AI = {ai_l:.3f} ({type_l})", text_color=col_l)

                ai_r = zonal["right"].get("arch_index")
                type_r = zonal["right"].get("arch_type", "Normal")
                code_r = zonal["right"].get("arch_code", "normal")
                col_r = COLOR_DANGER if code_r == "planus" else (COLOR_WARNING if code_r == "cavus" else COLOR_SUCCESS)
                if ai_r is not None:
                    self.arch_r_lbl.configure(text=f"Rechter Fuß: AI = {ai_r:.3f} ({type_r})", text_color=col_r)
            else:
                self.arch_header_lbl.pack_forget()
                self.arch_card.pack_forget()

        # 4. Leitlinien-Referenztext aktualisieren
        citation_text = reg_info.get("citation", "Klinische Asymmetrie-Richtlinien der medizinischen Thermografie.")
        self.note_lbl.configure(text=f"Leitlinie ({r_name}): {citation_text}. Temperaturschwelle ΔT > {thresh_c:.1f} °C.")

        # 5. Bild rendern
        self.redraw()

    def redraw(self) -> None:
        if not self.current_result:
            return

        raw_overlay = self.current_result["overlay_rgb"]
        pil_img = Image.fromarray(raw_overlay)

        self.img_lbl.update_idletasks()
        w = max(self.img_lbl.winfo_width() - 16, 300)
        h = max(self.img_lbl.winfo_height() - 16, 200)

        ctk_img = make_display_ctk_image(pil_img, w, h)
        self.img_lbl.configure(image=ctk_img, text="")
        self.img_lbl.image = ctk_img
