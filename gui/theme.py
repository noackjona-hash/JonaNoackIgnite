# -*- coding: utf-8 -*-
"""gui/theme.py – High-Contrast Clinical & Precision Medical Workstation Theme for IGNITE.

Professional, ergonomic design system designed for clinical diagnostic workflows:
- High-contrast slate/zinc surfaces for fatigue-free diagnostic inspection
- Strict functional color discipline (color reserved solely for thermal & pathology data)
- Disciplined, compact corner radii (6-8px) and crisp 1px borders
- Clear, readable typography scale for measurements and metadata
"""

# ── Legacy / Test Compatibility ───────────────────────────────────────────────
GOOGLE_BLUE             = "#1A73E8"
GOOGLE_BLUE_HOVER       = "#1557B0"
GOOGLE_BLUE_ACTIVE      = "#0B57D0"
GOOGLE_BLUE_LIGHT       = "#D3E3FD"

# ── Clinical & High-Contrast Workstation Surfaces ─────────────────────────────
# Canvas background (Light: Crisp Slate-50, Dark: Deep Obsidian-950)
COLOR_BG_APP            = ("#F8FAFC", "#090D14")

# Sidebar navigation background
COLOR_BG_NAV            = ("#F1F5F9", "#0D121B")

# Workstation Cards & Viewport Panels
COLOR_BG_CARD           = ("#FFFFFF", "#131923")
COLOR_BG_CARD_VARIANT   = ("#F1F5F9", "#1A2230")
COLOR_BG_CARD_HOVER     = ("#E2E8F0", "#222D3E")

# Input fields, text entries & chips
COLOR_BG_INPUT          = ("#E2E8F0", "#1E2737")
COLOR_BG_INPUT_HOVER    = ("#CBD5E1", "#283449")

# Active selection containers
COLOR_CONTAINER_ACTIVE  = ("#E2E8F0", "#243042")
COLOR_CONTAINER_BLUE    = ("#E0F2FE", "#0C365C")  # Diagnostic Info container
COLOR_CONTAINER_GREEN   = ("#DCFCE7", "#064E2B")  # Diagnostic Normal container
COLOR_CONTAINER_RED     = ("#FEE2E2", "#5A1313")  # Diagnostic Pathological container
COLOR_CONTAINER_YELLOW  = ("#FEF3C7", "#4D3600")  # Diagnostic Caution container

# ── Outlines & Crisp Structural Dividers ──────────────────────────────────────
COLOR_OUTLINE           = ("#CBD5E1", "#243044")
COLOR_OUTLINE_VARIANT   = ("#E2E8F0", "#1A2332")
COLOR_OUTLINE_FOCUS     = ("#0284C7", "#38BDF8")

# ── Clinical Typography Colors ────────────────────────────────────────────────
COLOR_TEXT_PRIMARY      = ("#0F172A", "#F8FAFC")
COLOR_TEXT_SECONDARY    = ("#334155", "#CBD5E1")
COLOR_TEXT_MUTED        = ("#64748B", "#94A3B8")
COLOR_TEXT_ON_PRIMARY   = "#FFFFFF"
COLOR_TEXT_ACCENT       = ("#0284C7", "#38BDF8")

# ── Primary Actions & Semantic Highlights ─────────────────────────────────────
# High-contrast action styling
COLOR_PRIMARY           = "#0284C7"          # Clinical Cyan / Cobalt Blue
COLOR_PRIMARY_HOVER     = "#0369A1"
COLOR_SUCCESS           = "#16A34A"          # Clinical Normal (Emerald)
COLOR_WARNING           = ("#D97706", "#F59E0B")  # Clinical Borderline (Amber)
COLOR_DANGER            = "#DC2626"          # Clinical Pathological (Red-600)

# ── Typography Scale ──────────────────────────────────────────────────────────
FONT_FAMILY             = "Segoe UI"
FONT_FAMILY_MONO        = "Consolas"

# ── Corner Radii (Compact, Professional Desktop Standard) ────────────────────
RADIUS_CARD             = 8
RADIUS_BUTTON           = 6
RADIUS_BADGE            = 4

# ── Hardware Backend Status (Technical, No Emojis) ───────────────────────────
BACKEND_STYLES = {
    "GPU": {
        "bg": ("#DCFCE7", "#064E2B"),
        "fg": ("#166534", "#86EFAC"),
        "border": ("#86EFAC", "#16A34A"),
        "label": "CUDA GPU Core (Aktiv)",
        "dot": "#16A34A"
    },
    "RUST": {
        "bg": ("#E0F2FE", "#0C365C"),
        "fg": ("#075985", "#7DD3FC"),
        "border": ("#7DD3FC", "#0284C7"),
        "label": "Rust Native Core (Aktiv)",
        "dot": "#0284C7"
    },
    "PYTHON": {
        "bg": ("#F1F5F9", "#1A2230"),
        "fg": ("#475569", "#94A3B8"),
        "border": ("#CBD5E1", "#334155"),
        "label": "CPU Fallback (Python)",
        "dot": "#94A3B8"
    }
}
