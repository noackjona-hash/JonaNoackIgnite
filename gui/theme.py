# -*- coding: utf-8 -*-
"""gui/theme.py – Ultra-Modern Obsidian & Cyber Indigo Theme Tokens for IGNITE Suite.

Provides color tokens, typography defaults, card aesthetics, glow indicators,
and badge styling definitions for CustomTkinter.
"""

# ─── COLOR TOKENS (LIGHT / DARK TUPLES FOR CUSTOMTKINTER) ─────────────────────
COLOR_BG_MAIN = ("#F1F5F9", "#07090E")          # Pure Slate-100 / Obsidian Dark #07090E
COLOR_BG_SIDEBAR = ("#E2E8F0", "#0B0E17")       # Deep Sidebar Slate-200 / Dark Slate #0B0E17
COLOR_BG_CARD = ("#FFFFFF", "#0F1420")          # Card White / Cyber Dark Card #0F1420
COLOR_BG_CARD_HOVER = ("#F8FAFC", "#161D2E")    # Card Hover Light / Cyber Dark Hover #161D2E
COLOR_BORDER_CARD = ("#CBD5E1", "#1E2638")      # Sub-border Light / Deep Slate Border #1E2638
COLOR_BORDER_FOCUS = ("#6366F1", "#818CF8")     # Indigo Accent Border Focus

COLOR_TEXT_PRIMARY = ("#0F172A", "#F8FAFC")     # Deep Slate-900 / Pure White #F8FAFC
COLOR_TEXT_SECONDARY = ("#334155", "#94A3B8")   # Slate-700 / Muted Slate-400
COLOR_TEXT_MUTED = ("#64748B", "#64748B")       # Muted Slate-500
COLOR_TEXT_ACCENT = ("#4F46E5", "#A5B4FC")      # Bright Accent Text

COLOR_BG_INPUT = ("#F8FAFC", "#0A0D15")         # Input Background
COLOR_BORDER_INPUT = ("#CBD5E1", "#1E293B")     # Input Border

# ─── ACCENT & STATUS COLORS ───────────────────────────────────────────────────
COLOR_PRIMARY_ACCENT = "#6366F1"                # Electric Indigo-500
COLOR_HOVER_ACCENT = "#4F46E5"                  # Indigo-600
COLOR_VIOLET = "#8B5CF6"                        # Electric Violet-500
COLOR_CYAN = "#06B6D4"                          # Cyber Cyan-500
COLOR_SUCCESS = "#10B981"                       # Emerald-500
COLOR_WARNING = "#F59E0B"                       # Amber-500
COLOR_DANGER = "#EF4444"                        # Neon Red-500

# ─── TYPOGRAPHY TOKENS ────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# ─── BADGE & PILL COLOR MAP ───────────────────────────────────────────────────
BADGE_STYLES = {
    "RUST": {"bg": "#064E3B", "fg": "#34D399", "border": "#059669", "label": "⚡ RUST CORE (CPU+RAYON)"},
    "GPU": {"bg": "#1E1B4B", "fg": "#A5B4FC", "border": "#6366F1", "label": "🚀 GPU ACCELERATED (CUDA)"},
    "PYTHON": {"bg": "#451A03", "fg": "#FDBA74", "border": "#D97706", "label": "🐍 PYTHON FALLBACK"},
}
