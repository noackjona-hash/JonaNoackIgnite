# -*- coding: utf-8 -*-
"""gui/theme.py – Google Material 3 / Material You Fluid Design System for IGNITE.

Implements the modern Google Gemini / Android Material You aesthetic:
- Soft tinted canvas surfaces (#F0F4F9)
- Floating elevated cards (#FFFFFF with corner_radius=24)
- Expressive, comfortable Google Sans typography scale
- Generous touch targets and rounded-full pill buttons
"""

# ── Google Brand Colors ───────────────────────────────────────────────────────
GOOGLE_BLUE             = "#1A73E8"
GOOGLE_BLUE_HOVER       = "#1557B0"
GOOGLE_BLUE_ACTIVE      = "#0B57D0"
GOOGLE_BLUE_LIGHT       = "#D3E3FD"

GOOGLE_RED              = "#EA4335"
GOOGLE_RED_HOVER        = "#D93025"
GOOGLE_RED_LIGHT        = "#F9DEDC"

GOOGLE_GREEN            = "#34A853"
GOOGLE_GREEN_HOVER      = "#1E8E3E"
GOOGLE_GREEN_LIGHT      = "#C4EED0"

GOOGLE_YELLOW           = "#FBBC04"
GOOGLE_YELLOW_HOVER     = "#F9AB00"
GOOGLE_YELLOW_LIGHT     = "#FFE7A5"

GOOGLE_PURPLE           = "#9334E6"
GOOGLE_CYAN             = "#12B5CB"

# ── Modern Material You / Google Fluid Surfaces ──────────────────────────────
# Fluid canvas background (Google Gemini / Workspace soft tone)
COLOR_BG_APP            = ("#F0F4F9", "#131314")

# Seamless sidebar background (matching canvas for floating nav pills)
COLOR_BG_NAV            = ("#F0F4F9", "#131314")

# Floating elevated cards & containers
COLOR_BG_CARD           = ("#FFFFFF", "#1E1F20")
COLOR_BG_CARD_VARIANT   = ("#F8FAFD", "#282A2C")
COLOR_BG_CARD_HOVER     = ("#F0F4F9", "#333538")

# Input fields, chips, text entries
COLOR_BG_INPUT          = ("#E9EEF6", "#282A2C")
COLOR_BG_INPUT_HOVER    = ("#DDE3EA", "#333538")

# Material You Tonal Containers (Active Pills & Badges)
COLOR_CONTAINER_BLUE    = ("#D3E3FD", "#044289")  # Google Blue active container
COLOR_CONTAINER_GREEN   = ("#C4EED0", "#0F5223")  # Google Green active container
COLOR_CONTAINER_RED     = ("#F9DEDC", "#601410")  # Google Red warning container
COLOR_CONTAINER_YELLOW  = ("#FFE7A5", "#4E3E00")  # Google Yellow attention container

# ── Outlines & Subtle Dividers ────────────────────────────────────────────────
COLOR_OUTLINE           = ("#E1E3E1", "#333538")
COLOR_OUTLINE_VARIANT   = ("#EDF0EE", "#282A2C")
COLOR_OUTLINE_FOCUS     = ("#0B57D0", "#A8C7FA")

# ── Text Colors ───────────────────────────────────────────────────────────────
COLOR_TEXT_PRIMARY      = ("#1F1F1F", "#E3E3E3")
COLOR_TEXT_SECONDARY    = ("#444746", "#C4C7C5")
COLOR_TEXT_MUTED        = ("#727775", "#8E918F")
COLOR_TEXT_ON_PRIMARY   = "#FFFFFF"
COLOR_TEXT_ACCENT       = ("#0B57D0", "#A8C7FA")

# ── Action & Semantic Highlights ─────────────────────────────────────────────
COLOR_PRIMARY           = "#0B57D0"          # Google Material 3 Primary Blue
COLOR_PRIMARY_HOVER     = "#0842A0"
COLOR_SUCCESS           = "#1E8E3E"          # Google Success Green
COLOR_WARNING           = ("#B06000", "#F29900")
COLOR_DANGER            = "#D93025"          # Google Danger Red

# ── Typography Scale ──────────────────────────────────────────────────────────
# Expressive Google typography
FONT_FAMILY             = "Segoe UI"
FONT_FAMILY_MONO        = "Consolas"

# ── Backend Badges ────────────────────────────────────────────────────────────
BACKEND_STYLES = {
    "GPU": {
        "bg": ("#D3E3FD", "#044289"),
        "fg": ("#0B57D0", "#D3E3FD"),
        "border": ("#A8C7FA", "#0B57D0"),
        "label": "⚡ GPU CUDA Engine",
        "dot": "#0B57D0"
    },
    "RUST": {
        "bg": ("#FFE7A5", "#4E3E00"),
        "fg": ("#7A4B00", "#FFE7A5"),
        "border": ("#FDD663", "#FBBC04"),
        "label": "⚡ Rust Native Core",
        "dot": "#FBBC04"
    },
    "PYTHON": {
        "bg": ("#E9EEF6", "#282A2C"),
        "fg": ("#444746", "#C4C7C5"),
        "border": ("#E1E3E1", "#444746"),
        "label": "⏱ Python CPU Fallback",
        "dot": "#727775"
    }
}
