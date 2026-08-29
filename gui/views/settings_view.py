# -*- coding: utf-8 -*-
"""gui/views/settings_view.py – Comprehensive High-Contrast Settings for IGNITE."""

from __future__ import annotations
import tkinter as tk
from typing import Callable, Any, Optional
import customtkinter as ctk

import config
import image_processing
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
    COLOR_PRIMARY_HOVER,
    COLOR_CONTAINER_ACTIVE,
    COLOR_CONTAINER_BLUE,
    FONT_FAMILY,
    FONT_FAMILY_MONO,
    RADIUS_CARD,
    RADIUS_BUTTON,
    RADIUS_BADGE,
)
from gui.utils_ui import make_material_card, make_slider_setting


class SettingsView(ctk.CTkFrame):
    """Umfassendes Einstellungs- und Parameter-Center im High-Contrast Clinical Design."""

    CATEGORIES = [
        ("algo",     "Algorithmus & Hotspots"),
        ("podology", "Podologie & Symmetrie"),
        ("radio",    "Radiometrie & Physik"),
        ("visual",   "Anzeige & Overlays"),
        ("hardware", "Performance & Engine"),
        ("privacy",  "Datenschutz & DSGVO"),
        ("updates",  "Updates & Version"),
    ]

    PRESETS = {
        "Standard (Jugend forscht 2026)": {
            "sigma_k": 3.0, "tophat_factor": 0.05, "min_area_factor": 0.0005,
            "min_circularity": 0.08, "otsu_min": 35, "otsu_max": 50, "dist_erosion_factor": 0.05,
            "use_mad": False, "enable_asymmetry": True, "asym_thresh": 2.2, "alpha": 0.5,
            "emissivity": 0.98, "refl_temp": 20.0, "cutoff_y": 0.65
        },
        "Hochempfindlich (Frühdiagnose)": {
            "sigma_k": 2.2, "tophat_factor": 0.04, "min_area_factor": 0.0002,
            "min_circularity": 0.04, "otsu_min": 30, "otsu_max": 45, "dist_erosion_factor": 0.03,
            "use_mad": False, "enable_asymmetry": True, "asym_thresh": 1.8, "alpha": 0.6,
            "emissivity": 0.98, "refl_temp": 20.0, "cutoff_y": 0.65
        },
        "Podologie / Diabetischer Fuß": {
            "sigma_k": 3.0, "tophat_factor": 0.06, "min_area_factor": 0.0008,
            "min_circularity": 0.10, "otsu_min": 35, "otsu_max": 55, "dist_erosion_factor": 0.05,
            "use_mad": True, "enable_asymmetry": True, "asym_thresh": 2.2, "alpha": 0.5,
            "emissivity": 0.98, "refl_temp": 20.0, "cutoff_y": 0.70
        },
        "Rauschunterdrückung (Robust)": {
            "sigma_k": 3.6, "tophat_factor": 0.05, "min_area_factor": 0.0012,
            "min_circularity": 0.14, "otsu_min": 40, "otsu_max": 65, "dist_erosion_factor": 0.08,
            "use_mad": True, "enable_asymmetry": True, "asym_thresh": 2.5, "alpha": 0.4,
            "emissivity": 0.98, "refl_temp": 20.0, "cutoff_y": 0.60
        }
    }

    def __init__(
        self,
        master,
        on_param_changed: Callable[[], None],
        on_backend_changed: Callable[[str], None],
        on_notify: Callable[[str, str], None],
        **kwargs
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_param_changed = on_param_changed
        self.on_backend_changed = on_backend_changed
        self.on_notify = on_notify

        self.active_category = "algo"
        self.sliders: dict[str, tuple[ctk.CTkSlider, ctk.CTkLabel]] = {}
        self.switches: dict[str, ctk.CTkSwitch] = {}
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.dropdowns: dict[str, ctk.CTkOptionMenu] = {}
        self._cat_buttons: dict[str, tuple[ctk.CTkFrame, ctk.CTkFrame, ctk.CTkLabel]] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=200)  # Linke Kategorie-Leiste
        self.grid_columnconfigure(1, weight=1)  # Rechter Einstellungsbereich
        self.grid_rowconfigure(0, weight=1)

        # ── 1. Linke Kategorien-Leiste ────────────────────────────────────────
        cat_card = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        cat_card.grid(row=0, column=0, padx=(14, 6), pady=14, sticky="nsew")
        cat_card.configure(width=200)
        cat_card.pack_propagate(False)

        cat_inner = ctk.CTkFrame(cat_card, fg_color="transparent")
        cat_inner.pack(fill=ctk.BOTH, expand=True, padx=10, pady=12)

        ctk.CTkLabel(
            cat_inner,
            text="EINSTELLUNGEN",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            anchor="w"
        ).pack(fill=ctk.X, padx=10, pady=(2, 8))

        for cat_id, title in self.CATEGORIES:
            btn_frame = ctk.CTkFrame(
                cat_inner,
                corner_radius=RADIUS_BUTTON,
                fg_color="transparent",
                height=38,
                cursor="hand2"
            )
            btn_frame.pack(fill=ctk.X, pady=2)
            btn_frame.pack_propagate(False)

            content = ctk.CTkFrame(btn_frame, fg_color="transparent")
            content.pack(fill=ctk.BOTH, expand=True, padx=8, pady=4)

            ind_bar = ctk.CTkFrame(content, width=3, corner_radius=2, fg_color="transparent")
            ind_bar.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 8), pady=2)

            lbl_title = ctk.CTkLabel(
                content,
                text=title,
                font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                text_color=COLOR_TEXT_SECONDARY,
                height=22,
                anchor="w"
            )
            lbl_title.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

            _cid = cat_id
            for w in [btn_frame, content, ind_bar, lbl_title]:
                w.bind("<Button-1>", lambda e, c=_cid: self.select_category(c))
                w.bind("<Enter>", lambda e, c=_cid: self._on_cat_hover(c, True))
                w.bind("<Leave>", lambda e, c=_cid: self._on_cat_hover(c, False))

            self._cat_buttons[cat_id] = (btn_frame, ind_bar, lbl_title)

        # Unten: Reset Defaults Button
        ctk.CTkButton(
            cat_inner,
            text="Standardwerte",
            command=self._reset_defaults,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(side=ctk.BOTTOM, fill=ctk.X, pady=(8, 0))

        # ── 2. Rechter Hauptbereich für Einstellungs-Panels ───────────────────
        self.right_container = make_material_card(self, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD)
        self.right_container.grid(row=0, column=1, padx=(6, 14), pady=14, sticky="nsew")

        # Header mit Presets & Suchzeile
        top_header = ctk.CTkFrame(self.right_container, fg_color="transparent", height=46)
        top_header.pack(fill=ctk.X, padx=16, pady=(10, 6))
        top_header.pack_propagate(False)

        self.cat_title_lbl = ctk.CTkLabel(
            top_header,
            text="Algorithmus & Hotspots",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.cat_title_lbl.pack(side=ctk.LEFT)

        # Preset Dropdown rechts
        self.preset_menu = ctk.CTkOptionMenu(
            top_header,
            values=list(self.PRESETS.keys()),
            command=self._apply_preset,
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_BG_CARD_VARIANT,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=30,
            width=230
        )
        self.preset_menu.pack(side=ctk.RIGHT)

        ctk.CTkLabel(
            top_header,
            text="Profil:",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            text_color=COLOR_TEXT_MUTED
        ).pack(side=ctk.RIGHT, padx=(0, 6))

        ctk.CTkFrame(self.right_container, height=1, fg_color=COLOR_OUTLINE_VARIANT).pack(fill=ctk.X)

        # Scrollbarer Inhalt für Einstellungs-Karten
        self.scroll_body = ctk.CTkScrollableFrame(self.right_container, fg_color="transparent")
        self.scroll_body.pack(fill=ctk.BOTH, expand=True, padx=14, pady=12)

        # Panels aufbauen
        self.category_panels: dict[str, ctk.CTkFrame] = {}
        self._build_algo_panel()
        self._build_podology_panel()
        self._build_radiometry_panel()
        self._build_visual_panel()
        self._build_hardware_panel()
        self._build_privacy_panel()
        self._build_updates_panel()

        self.select_category("algo")

    def _on_cat_hover(self, cat_id: str, is_hovering: bool) -> None:
        if cat_id == self.active_category:
            return
        frame, _, _ = self._cat_buttons[cat_id]
        frame.configure(fg_color=COLOR_BG_CARD_HOVER if is_hovering else "transparent")

    def select_category(self, cat_id: str) -> None:
        self.active_category = cat_id
        for cid, (frame, ind_bar, title_lbl) in self._cat_buttons.items():
            if cid == cat_id:
                frame.configure(fg_color=COLOR_CONTAINER_ACTIVE)
                ind_bar.configure(fg_color=COLOR_PRIMARY)
                title_lbl.configure(text_color=COLOR_TEXT_PRIMARY)
            else:
                frame.configure(fg_color="transparent")
                ind_bar.configure(fg_color="transparent")
                title_lbl.configure(text_color=COLOR_TEXT_SECONDARY)

        # Titel aktualisieren
        for cid, title in self.CATEGORIES:
            if cid == cat_id:
                self.cat_title_lbl.configure(text=title)
                break

        # Panel umschalten
        for cid, panel in self.category_panels.items():
            if cid == cat_id:
                panel.pack(fill=ctk.BOTH, expand=True)
            else:
                panel.pack_forget()

    # ── Panels ───────────────────────────────────────────────────────────────

    def _build_algo_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["algo"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        s_k, l_k = make_slider_setting(
            c_inner, "Threshold-Faktor k",
            "Multiplikator für adaptive Schwelle T_rel = µ + k·σ (k=3.0 entspricht 99.86% Konfidenz)",
            1.0, 5.0, config.DEFAULT_SIGMA_K, 0.1, "",
            command=lambda v: self._on_change()
        )
        self.sliders["sigma_k"] = (s_k, l_k)

        s_th, l_th = make_slider_setting(
            c_inner, "Morphologischer Top-Hat Kernel (%)",
            "Größe der morphologischen Öffnung relativ zu min(B, H) zur Extraktion lokaler Hitzekontraste",
            0.01, 0.20, config.DEFAULT_TOPHAT_FACTOR, 0.005, "",
            command=lambda v: self._on_change(),
            is_percent=True
        )
        self.sliders["tophat_factor"] = (s_th, l_th)

        s_ma, l_ma = make_slider_setting(
            c_inner, "Minimale Hotspot-Fläche (%)",
            "Unterdrückt isolierte thermische Rauschpixel unterhalb dieser relativen Fläche",
            0.0001, 0.005, config.DEFAULT_MIN_AREA_FACTOR, 0.0001, "",
            command=lambda v: self._on_change(),
            is_percent=True
        )
        self.sliders["min_area_factor"] = (s_ma, l_ma)

        s_mc, l_mc = make_slider_setting(
            c_inner, "Minimale Circularity (Formfaktor 4π·A/U²)",
            "Filtert längliche Randartefakte, Schatten und Reflexionen",
            0.01, 0.60, config.DEFAULT_MIN_CIRCULARITY, 0.01, "",
            command=lambda v: self._on_change()
        )
        self.sliders["min_circularity"] = (s_mc, l_mc)

        s_er, l_er = make_slider_setting(
            c_inner, "Distanz-Erosionsfaktor",
            "Entfernt Übergangsartefakte an den anatomischen Außenkanten des Gewebes",
            0.01, 0.25, config.DEFAULT_DIST_EROSION_FACTOR, 0.005, "",
            command=lambda v: self._on_change(),
            is_percent=True
        )
        self.sliders["dist_erosion_factor"] = (s_er, l_er)

        s_hkl, l_hkl = make_slider_setting(
            c_inner, "Hysterese-Schwelle k_low (Perifokale Ausdehnung)",
            "Schwacher Schwellenwert für das Seeded-Region-Growing entlang perifokaler Gradienten",
            0.5, 3.0, getattr(config, "DEFAULT_HYSTERESIS_K_LOW", 1.8), 0.1, "",
            command=lambda v: self._on_change()
        )
        self.sliders["hysteresis_k_low"] = (s_hkl, l_hkl)

        # Switches
        sw_mad = ctk.CTkSwitch(
            c_inner,
            text="Robustes MAD-Thresholding (Median Absolute Deviation statt Standardabweichung σ)",
            command=self._on_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        if config.DEFAULT_USE_MAD:
            sw_mad.select()
        sw_mad.pack(fill=ctk.X, pady=(8, 2))
        self.switches["use_mad"] = sw_mad

        sw_hyst = ctk.CTkSwitch(
            c_inner,
            text="Adaptive Hysterese (Zwei-Schwellenwert-Region-Growing für erhöhte Sensitivität)",
            command=self._on_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        if getattr(config, "DEFAULT_ENABLE_HYSTERESIS", True):
            sw_hyst.select()
        sw_hyst.pack(fill=ctk.X, pady=(4, 2))
        self.switches["enable_hysteresis"] = sw_hyst

    def _build_podology_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["podology"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        s_asym, l_asym = make_slider_setting(
            c_inner, "Armstrong Asymmetrie-Grenzwert ΔT (°C)",
            "Klinischer Goldstandard nach Armstrong et al. (1997). Werte über dieser Differenz gelten als pathologisch.",
            0.5, 5.0, config.ASYMMETRY_THRESHOLD_C, 0.1, "°C",
            command=lambda v: self._on_change()
        )
        self.sliders["asym_thresh"] = (s_asym, l_asym)

        s_cut, l_cut = make_slider_setting(
            c_inner, "Anatomischer Knöchel-Cutoff Y (%)",
            "Schneidet thermische Einflüsse von Unterschenkeln und Knöcheln oberhalb dieser Höhe ab",
            0.40, 0.90, config.ANATOMICAL_LOWER_CUTOFF_Y, 0.05, "",
            command=lambda v: self._on_change(),
            is_percent=True
        )
        self.sliders["cutoff_y"] = (s_cut, l_cut)

        sw_asym = ctk.CTkSwitch(
            c_inner,
            text="Kontralaterale Seitenvergleichs-Analyse aktivieren (Links vs. Rechts)",
            command=self._on_change,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        if config.DEFAULT_ENABLE_ASYMMETRY:
            sw_asym.select()
        sw_asym.pack(fill=ctk.X, pady=(8, 2))
        self.switches["enable_asymmetry"] = sw_asym

    def _build_radiometry_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["radio"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        ctk.CTkLabel(c_inner, text="Stefan-Boltzmann Strahlungsmodell & Sensor-Kalibrierung", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(0, 8))

        # Emissivität
        ctk.CTkLabel(c_inner, text="Haut-Emissivitätsgrad (ε):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        e_em = ctk.CTkEntry(c_inner, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), fg_color=COLOR_BG_CARD, border_color=COLOR_OUTLINE, height=32)
        e_em.insert(0, str(config.SKIN_EMISSIVITY))
        e_em.pack(fill=ctk.X, pady=(2, 8))
        self.entries["emissivity"] = e_em

        # Reflektierte Temperatur
        ctk.CTkLabel(c_inner, text="Reflektierte Umgebungstemperatur (°C):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        e_refl = ctk.CTkEntry(c_inner, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=12), fg_color=COLOR_BG_CARD, border_color=COLOR_OUTLINE, height=32)
        e_refl.insert(0, str(config.REFLECTED_TEMP_C))
        e_refl.pack(fill=ctk.X, pady=(2, 8))
        self.entries["reflected_temp"] = e_refl

        s_off, l_off = make_slider_setting(
            c_inner, "Kalibrierungs-Nullpunktverschiebung",
            "Manuelle Temperatur-Offsetkorrektur bei Sensordrift",
            -20.0, 20.0, 0.0, 0.5, "°C",
            command=lambda v: self._on_change()
        )
        self.sliders["temp_offset"] = (s_off, l_off)

    def _build_visual_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["visual"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        s_al, l_al = make_slider_setting(
            c_inner, "Overlay Alpha-Deckkraft (%)",
            "Transparenz der roten Hotspot-Markierung über dem Wärmebild",
            0.1, 1.0, 0.5, 0.05, "",
            command=lambda v: self._on_change(),
            is_percent=True
        )
        self.sliders["alpha"] = (s_al, l_al)

        s_lw, l_lw = make_slider_setting(
            c_inner, "Bounding-Box Linienstärke",
            "Linienstärke in Pixeln für diagnostische Rechtecke",
            1.0, 6.0, 2.0, 1.0, "px",
            command=lambda v: self._on_change()
        )
        self.sliders["line_width"] = (s_lw, l_lw)

    def _build_hardware_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["hardware"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        ctk.CTkLabel(c_inner, text="Ausführungs-Engine:", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", pady=(0, 4))
        be_menu = ctk.CTkOptionMenu(
            c_inner,
            values=["Automatisch (Schnellstes)", "Erzwinge Rust-CPU-Core", "Erzwinge PyTorch-GPU", "Erzwinge Python-Fallback"],
            command=self._on_backend_select,
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            fg_color=COLOR_BG_CARD,
            button_color=COLOR_PRIMARY,
            button_hover_color=COLOR_PRIMARY_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=32
        )
        be_menu.pack(fill=ctk.X, pady=(0, 10))
        self.dropdowns["backend"] = be_menu

        ctk.CTkLabel(c_inner, text="Echtzeit-Debounce Verzögerung (ms):", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        s_deb, l_deb = make_slider_setting(
            c_inner, "Neuberechnungs-Verzögerung",
            "Zeit in Millisekunden vor Ausführung nach Slider-Bewegung",
            50, 600, 200, 25, "ms",
            command=lambda v: None
        )
        self.sliders["debounce_ms"] = (s_deb, l_deb)

    def _build_privacy_panel(self) -> None:
        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["privacy"] = panel

        card = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card.pack(fill=ctk.X, pady=4)
        c_inner = ctk.CTkFrame(card, fg_color="transparent")
        c_inner.pack(fill=ctk.X, padx=16, pady=12)

        ctk.CTkLabel(c_inner, text="Datenschutz & DSGVO-Pseudonymisierung", font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(anchor="w", pady=(0, 8))

        sw_dsgvo = ctk.CTkSwitch(
            c_inner,
            text="Automatische SHA-256 Pseudonymisierung bei Berichtsexport (ANON-XXXX)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        sw_dsgvo.select()
        sw_dsgvo.pack(fill=ctk.X, pady=4)
        self.switches["dsgvo_anon"] = sw_dsgvo

        sw_audit = ctk.CTkSwitch(
            c_inner,
            text="Klinischen Audit-Trail in CSV protokollieren (ignite_audit_trail.csv)",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
            progress_color=COLOR_PRIMARY
        )
        sw_audit.select()
        sw_audit.pack(fill=ctk.X, pady=4)
        self.switches["audit_log"] = sw_audit

    def _build_updates_panel(self) -> None:
        import webbrowser
        from gui.services.update_service import is_frozen_app
        from gui.widgets.dialogs import UpdateModal

        panel = ctk.CTkFrame(self.scroll_body, fg_color="transparent")
        self.category_panels["updates"] = panel

        # Karte 1: Versions- & Installationsstatus
        card1 = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card1.pack(fill=ctk.X, pady=4)
        c1_inner = ctk.CTkFrame(card1, fg_color="transparent")
        c1_inner.pack(fill=ctk.X, padx=16, pady=14)

        ctk.CTkLabel(
            c1_inner,
            text="Software-Version & Status",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 8))

        # Statuszeilen
        frozen = is_frozen_app()
        status_mode = "Installierte Desktop-Workstation (.exe)" if frozen else "Entwickler-Modus (Quellcode / venv)"
        ver_str = getattr(config, "APP_VERSION", "3.3.0")
        repo_str = getattr(config, "GITHUB_REPO", "noackjona-hash/JonaNoackIgnite")

        for label_t, val_t in [
            ("Installierte Version:", f"v{ver_str}"),
            ("Betriebsmodus:", status_mode),
            ("GitHub Repository:", repo_str),
        ]:
            row = ctk.CTkFrame(c1_inner, fg_color="transparent")
            row.pack(fill=ctk.X, pady=2)
            ctk.CTkLabel(row, text=label_t, font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"), text_color=COLOR_TEXT_PRIMARY).pack(side=tk.LEFT)
            ctk.CTkLabel(row, text=val_t, font=ctk.CTkFont(family=FONT_FAMILY_MONO, size=11), text_color=COLOR_TEXT_MUTED).pack(side=tk.RIGHT)

        # Update Check Button
        ctk.CTkButton(
            c1_inner,
            text="🔄 Jetzt nach Software-Updates suchen",
            command=lambda: UpdateModal(self.winfo_toplevel(), on_notify=self.on_notify),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            fg_color=COLOR_PRIMARY,
            hover_color=COLOR_PRIMARY_HOVER,
            text_color="#FFFFFF",
            corner_radius=RADIUS_BUTTON,
            height=34
        ).pack(fill=ctk.X, pady=(12, 0))

        # Karte 2: Automatische Update-Prüfung
        card2 = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card2.pack(fill=ctk.X, pady=6)
        c2_inner = ctk.CTkFrame(card2, fg_color="transparent")
        c2_inner.pack(fill=ctk.X, padx=16, pady=14)

        ctk.CTkLabel(
            c2_inner,
            text="Automatische Prüfung beim Start",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        ).pack(anchor="w", pady=(0, 4))

        sw_auto_update = ctk.CTkSwitch(
            c2_inner,
            text="Beim Programmstart automatisch im Hintergrund nach neuen Versionen suchen",
            font=ctk.CTkFont(family=FONT_FAMILY, size=11, weight="bold"),
            progress_color=COLOR_PRIMARY,
            command=self._on_change
        )
        if getattr(config, "AUTO_CHECK_UPDATES", True):
            sw_auto_update.select()
        else:
            sw_auto_update.deselect()
        sw_auto_update.pack(fill=ctk.X, pady=(4, 6))
        self.switches["auto_check_updates"] = sw_auto_update

        ctk.CTkLabel(
            c2_inner,
            text="Sobald auf GitHub ein neues Release veröffentlicht wird, blendet IGNITE eine Benachrichtigung ein.",
            font=ctk.CTkFont(family=FONT_FAMILY, size=10),
            text_color=COLOR_TEXT_MUTED
        ).pack(anchor="w")

        # Karte 3: Releases & Changelog Link
        card3 = make_material_card(panel, corner_radius=RADIUS_CARD, fg_color=COLOR_BG_CARD_VARIANT)
        card3.pack(fill=ctk.X, pady=4)
        c3_inner = ctk.CTkFrame(card3, fg_color="transparent")
        c3_inner.pack(fill=ctk.X, padx=16, pady=12)

        ctk.CTkButton(
            c3_inner,
            text="🌐 Alle Releases & Versionshistorie auf GitHub anzeigen",
            command=lambda: webbrowser.open(f"https://github.com/{repo_str}/releases"),
            font=ctk.CTkFont(family=FONT_FAMILY, size=11),
            fg_color=COLOR_BG_CARD,
            hover_color=COLOR_BG_CARD_HOVER,
            border_width=1,
            border_color=COLOR_OUTLINE,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=RADIUS_BUTTON,
            height=32
        ).pack(fill=ctk.X)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _apply_preset(self, choice: str) -> None:
        p = self.PRESETS.get(choice)
        if not p:
            return

        for k in ["sigma_k", "tophat_factor", "min_area_factor", "min_circularity", "dist_erosion_factor", "asym_thresh", "cutoff_y", "alpha"]:
            if k in p and k in self.sliders:
                slider, label = self.sliders[k]
                slider.set(p[k])
                if k in ("tophat_factor", "min_area_factor", "dist_erosion_factor", "cutoff_y", "alpha"):
                    label.configure(text=f"{p[k]*100:.1f} %")
                else:
                    label.configure(text=f"{p[k]:.1f}".rstrip('0').rstrip('.'))

        if p.get("use_mad", False):
            self.switches["use_mad"].select()
        else:
            self.switches["use_mad"].deselect()

        self.on_notify(f"Preset '{choice}' angewendet.", "info")
        self.on_param_changed()

    def _reset_defaults(self) -> None:
        self._apply_preset("Standard (Jugend forscht 2026)")

    def _on_change(self) -> None:
        self.on_param_changed()

    def _on_backend_select(self, choice: str) -> None:
        mapping = {
            "Automatisch (Schnellstes)": "auto",
            "Erzwinge Rust-CPU-Core": "rust",
            "Erzwinge PyTorch-GPU": "gpu",
            "Erzwinge Python-Fallback": "python"
        }
        val = mapping.get(choice, "auto")
        image_processing.FORCED_BACKEND = val
        self.on_backend_changed(val)
        self.on_notify(f"Backend umgestellt auf: {choice}", "info")

    def get_params(self) -> dict[str, Any]:
        """Liest alle Parameter aus."""
        try:
            em = float(self.entries["emissivity"].get().replace(",", "."))
        except Exception:
            em = config.SKIN_EMISSIVITY

        return {
            "sigma_k": float(self.sliders["sigma_k"][0].get()),
            "tophat_factor": float(self.sliders["tophat_factor"][0].get()),
            "min_area_factor": float(self.sliders["min_area_factor"][0].get()),
            "min_circularity": float(self.sliders["min_circularity"][0].get()),
            "dist_erosion_factor": float(self.sliders["dist_erosion_factor"][0].get()),
            "temp_offset": float(self.sliders.get("temp_offset", (None,))[0].get() if "temp_offset" in self.sliders else 0.0),
            "use_mad": self.switches["use_mad"].get() == 1 if "use_mad" in self.switches else False,
            "enable_hysteresis": self.switches["enable_hysteresis"].get() == 1 if "enable_hysteresis" in self.switches else True,
            "hysteresis_k_low": float(self.sliders["hysteresis_k_low"][0].get()) if "hysteresis_k_low" in self.sliders else config.DEFAULT_HYSTERESIS_K_LOW,
            "enable_asymmetry": self.switches["enable_asymmetry"].get() == 1 if "enable_asymmetry" in self.switches else True,
            "emissivity": em,
            "otsu_min": config.DEFAULT_OTSU_MIN,
            "otsu_max": config.DEFAULT_OTSU_MAX,
            "asym_thresh": float(self.sliders.get("asym_thresh", (None,))[0].get() if "asym_thresh" in self.sliders else 2.2),
            "cutoff_y": float(self.sliders.get("cutoff_y", (None,))[0].get() if "cutoff_y" in self.sliders else 0.65),
            "alpha": float(self.sliders.get("alpha", (None,))[0].get() if "alpha" in self.sliders else 0.5),
        }
