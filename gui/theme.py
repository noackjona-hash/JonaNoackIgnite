# -*- coding: utf-8 -*-
"""gui/theme.py – Material Design 3 (Google Style) Theme Tokens for IGNITE.

Provides a clean, cohesive Material You / Google aesthetic for desktop medical imaging.
All tuple tokens are in (light_mode_color, dark_mode_color) format for CustomTkinter.
"""

# ── Google Brand Colors (Google 4-Colors) ────────────────────────────────────
GOOGLE_BLUE             = "#1A73E8"
GOOGLE_BLUE_HOVER       = "#1557B0"
GOOGLE_BLUE_ACTIVE      = "#174EA6"
GOOGLE_BLUE_LIGHT       = "#8AB4F8"

GOOGLE_RED              = "#EA4335"
GOOGLE_RED_HOVER        = "#D93025"
GOOGLE_RED_LIGHT        = "#F28B82"

GOOGLE_GREEN            = "#34A853"
GOOGLE_GREEN_HOVER      = "#1E8E3E"
GOOGLE_GREEN_LIGHT      = "#81C995"

GOOGLE_YELLOW           = "#FBBC04"
GOOGLE_YELLOW_HOVER     = "#F9AB00"
GOOGLE_YELLOW_LIGHT     = "#FDD663"

GOOGLE_PURPLE           = "#9334E6"
GOOGLE_CYAN             = "#12B5CB"

# ── Material Surfaces & Backgrounds ──────────────────────────────────────────
# Base app background (Google Canvas)
COLOR_BG_APP            = ("#F8F9FA", "#1F1F1F")

# Navigation sidebar / rail
COLOR_BG_NAV            = ("#FFFFFF", "#28292A")

# Cards & elevated containers
COLOR_BG_CARD           = ("#FFFFFF", "#2D2F31")
COLOR_BG_CARD_VARIANT   = ("#F1F3F4", "#35363A")
COLOR_BG_CARD_HOVER     = ("#F8F9FA", "#3C4043")

# Input fields, chips, text entries
COLOR_BG_INPUT          = ("#F1F3F4", "#303134")
COLOR_BG_INPUT_HOVER    = ("#E8EAED", "#3C4043")

# Primary tonal containers (Google Tonal Palettes)
COLOR_CONTAINER_BLUE    = ("#E8F0FE", "#1E3A5F")
COLOR_CONTAINER_GREEN   = ("#E6F4EA", "#144A29")
COLOR_CONTAINER_RED     = ("#FCE8E6", "#4A1B1A")
COLOR_CONTAINER_YELLOW  = ("#FEF7E0", "#4A3B12")

# ── Outlines & Dividers ───────────────────────────────────────────────────────
COLOR_OUTLINE           = ("#DADCE0", "#3C4043")
COLOR_OUTLINE_VARIANT   = ("#E8EAED", "#35363A")
COLOR_OUTLINE_FOCUS     = ("#1A73E8", "#8AB4F8")

# ── Text Colors ───────────────────────────────────────────────────────────────
COLOR_TEXT_PRIMARY      = ("#202124", "#E8EAED")
COLOR_TEXT_SECONDARY    = ("#5F6368", "#9AA0A6")
COLOR_TEXT_MUTED        = ("#70757A", "#80868B")
COLOR_TEXT_ON_PRIMARY   = "#FFFFFF"
COLOR_TEXT_ACCENT       = ("#1A73E8", "#8AB4F8")

# ── Action & Semantic Highlights ─────────────────────────────────────────────
COLOR_PRIMARY           = GOOGLE_BLUE
COLOR_PRIMARY_HOVER     = GOOGLE_BLUE_HOVER
COLOR_SUCCESS           = GOOGLE_GREEN
COLOR_WARNING           = ("#E37400", "#FBBC04")
COLOR_DANGER            = GOOGLE_RED

# ── Typography ────────────────────────────────────────────────────────────────
# Google uses Roboto / Segoe UI / Arial with spacious line heights
FONT_FAMILY             = "Segoe UI"
FONT_FAMILY_MONO        = "Consolas"

# ── Backend Badges ────────────────────────────────────────────────────────────
BACKEND_STYLES = {
    "GPU": {
        "bg": ("#E8F0FE", "#174EA6"),
        "fg": ("#1A73E8", "#D2E3FC"),
        "border": ("#D2E3FC", "#1A73E8"),
        "label": "GPU CUDA",
        "dot": "#1A73E8"
    },
    "RUST": {
        "bg": ("#FEF7E0", "#593600"),
        "fg": ("#B06000", "#FEEFC3"),
        "border": ("#FEEFC3", "#FBBC04"),
        "label": "RUST CORE",
        "dot": "#FBBC04"
    },
    "PYTHON": {
        "bg": ("#F1F3F4", "#303134"),
        "fg": ("#5F6368", "#BDC1C6"),
        "border": ("#DADCE0", "#5F6368"),
        "label": "PYTHON CPU",
        "dot": "#5F6368"
    }
}
