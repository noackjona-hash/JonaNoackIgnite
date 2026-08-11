# -*- coding: utf-8 -*-
"""gui/theme.py – Design-Tokens für IGNITE Medical Imaging Suite.

Alle CTk-Farbtokens: (light_value, dark_value).
"""

# ── Oberflächen ───────────────────────────────────────────────────────────────
COLOR_BG_MAIN       = ("#F0F2F5", "#1E1E1E")   # Fenster-Hintergrund
COLOR_BG_SIDEBAR    = ("#E8EAED", "#252525")   # Sidebar
COLOR_BG_CARD       = ("#FFFFFF", "#2D2D2D")   # Cards & Panels
COLOR_BG_CARD_HOVER = ("#F5F5F5", "#363636")   # Card Hover
COLOR_BG_INPUT      = ("#F5F5F5", "#3A3A3A")   # Eingabefelder

# ── Rahmen ────────────────────────────────────────────────────────────────────
COLOR_BORDER_CARD  = ("#D8D8D8", "#484848")
COLOR_BORDER_FOCUS = ("#0067C0", "#4CC2FF")
COLOR_BORDER_INPUT = ("#C0C0C0", "#555555")

# ── Text ──────────────────────────────────────────────────────────────────────
COLOR_TEXT_PRIMARY   = ("#1A1A1A", "#F0F0F0")
COLOR_TEXT_SECONDARY = ("#444444", "#CCCCCC")
COLOR_TEXT_MUTED     = ("#767676", "#909090")
COLOR_TEXT_ACCENT    = ("#0067C0", "#4CC2FF")

# ── Aktionsfarben ─────────────────────────────────────────────────────────────
COLOR_PRIMARY_ACCENT = "#0067C0"
COLOR_HOVER_ACCENT   = "#005BA1"
COLOR_PRESSED_ACCENT = "#004888"
COLOR_VIOLET         = "#0067C0"   # Alias
COLOR_CYAN           = "#0067C0"   # Alias

# ── Statusfarben ──────────────────────────────────────────────────────────────
COLOR_SUCCESS = "#107C10"
COLOR_WARNING = "#C77700"
COLOR_DANGER  = "#C42B1C"

# ── Typografie ────────────────────────────────────────────────────────────────
FONT_FAMILY      = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# ── Backend-Badges ────────────────────────────────────────────────────────────
BADGE_STYLES = {
    "RUST":   {"bg": "#FFF4E6", "fg": "#8B3A00", "border": "#FFD0A0", "label": "RUST CORE"},
    "GPU":    {"bg": "#EBF4FF", "fg": "#004E99", "border": "#A0C8F0", "label": "GPU  CUDA"},
    "PYTHON": {"bg": "#F0F0F0", "fg": "#4A4A4A", "border": "#C8C8C8", "label": "PYTHON"},
}
