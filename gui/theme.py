# -*- coding: utf-8 -*-
"""gui/theme.py – Standard Light Theme Tokens for IGNITE Suite.

Schlichtes, helles Standard-Desktop-Design (Windows-Look). Stellt Farb-Tokens,
Typografie-Defaults, Karten-Stil und Badge-Definitionen fuer CustomTkinter bereit.
Farb-Tokens nutzen das CustomTkinter-Format ``(light, dark)``; die Light-Werte
bilden den Standard-Look, die Dark-Werte sind ein schlichtes neutrales Grau.
"""

# --- COLOR TOKENS (LIGHT / DARK TUPLES FOR CUSTOMTKINTER) --------------------
COLOR_BG_MAIN = ("#F0F0F0", "#2B2B2B")          # Standard-Fenstergrau
COLOR_BG_SIDEBAR = ("#E8E8E8", "#252525")       # Seitenleiste etwas dunkler
COLOR_BG_CARD = ("#FFFFFF", "#333333")          # Karten-/Panel-Hintergrund
COLOR_BG_CARD_HOVER = ("#F0F0F0", "#3A3A3A")    # Karte Hover
COLOR_BORDER_CARD = ("#D0D0D0", "#454545")      # Neutraler Rahmen
COLOR_BORDER_FOCUS = ("#0067C0", "#4CC2FF")     # Fokus-Rahmen (Standard-Blau)

COLOR_TEXT_PRIMARY = ("#1A1A1A", "#FFFFFF")     # Haupttext
COLOR_TEXT_SECONDARY = ("#444444", "#CCCCCC")   # Sekundaertext
COLOR_TEXT_MUTED = ("#767676", "#999999")       # Gedaempfter Text
COLOR_TEXT_ACCENT = ("#0067C0", "#4CC2FF")      # Akzent-Text

COLOR_BG_INPUT = ("#FFFFFF", "#2D2D2D")         # Eingabefeld-Hintergrund
COLOR_BORDER_INPUT = ("#B0B0B0", "#555555")     # Eingabefeld-Rahmen

# --- ACCENT & STATUS COLORS --------------------------------------------------
COLOR_PRIMARY_ACCENT = "#0067C0"                # Standard-Blau (Windows)
COLOR_HOVER_ACCENT = "#005BA1"                  # Blau (Hover)
COLOR_VIOLET = "#0067C0"                         # auf Standard-Blau vereinheitlicht
COLOR_CYAN = "#0067C0"                            # auf Standard-Blau vereinheitlicht
COLOR_SUCCESS = "#107C10"                        # Standard-Gruen
COLOR_WARNING = "#C77700"                        # Standard-Orange
COLOR_DANGER = "#C42B1C"                         # Standard-Rot

# --- TYPOGRAPHY TOKENS -------------------------------------------------------
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# --- BADGE & PILL COLOR MAP (schlichte, neutrale Pills ohne Emojis) ----------
BADGE_STYLES = {
    "RUST": {"bg": "#E8E8E8", "fg": "#333333", "border": "#C0C0C0", "label": "RUST CORE"},
    "GPU": {"bg": "#E8E8E8", "fg": "#333333", "border": "#C0C0C0", "label": "GPU"},
    "PYTHON": {"bg": "#E8E8E8", "fg": "#333333", "border": "#C0C0C0", "label": "PYTHON"},
}
