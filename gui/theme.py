# -*- coding: utf-8 -*-
"""gui/theme.py – Design-Tokens für IGNITE Medical Imaging Suite.

Klare visuelle Hierarchie durch 4 Oberflächenebenen:
  BG_BASE   → Fenster-Hintergrund (tiefste Ebene)
  BG_RAISED → Sidebar, Panels  (eine Ebene höher)
  BG_CARD   → Cards, Kacheln   (zwei Ebenen höher)
  BG_INPUT  → Eingabefelder    (auf Card-Ebene, leicht abgesetzt)

Alle Farb-Tokens verwenden CustomTkinter-Format ``(light_value, dark_value)``.
"""

# ── Oberflächen-Hierarchie (4 Ebenen) ────────────────────────────────────────
COLOR_BG_MAIN     = ("#F2F2F7", "#1C1C1E")   # Ebene 0 – Fenster-Hintergrund
COLOR_BG_SIDEBAR  = ("#E5E5EA", "#252528")   # Ebene 1 – Seitenleiste
COLOR_BG_CARD     = ("#FFFFFF", "#2C2C2E")   # Ebene 2 – Cards & Panels
COLOR_BG_CARD_HOVER = ("#F0F0F5", "#38383A") # Ebene 2 – Card Hover-State
COLOR_BG_INPUT    = ("#F2F2F7", "#3A3A3C")   # Ebene 3 – Eingabefelder

# ── Rahmen & Trennlinien ──────────────────────────────────────────────────────
COLOR_BORDER_CARD  = ("#D1D1D6", "#48484A")  # Standard-Rahmen
COLOR_BORDER_INPUT = ("#C7C7CC", "#545458")  # Eingabefeld-Rahmen
COLOR_BORDER_FOCUS = ("#007AFF", "#0A84FF")  # Fokus-Rahmen (iOS-Blau)

# ── Typografie ────────────────────────────────────────────────────────────────
COLOR_TEXT_PRIMARY   = ("#000000", "#FFFFFF")  # Haupttext – max. Kontrast
COLOR_TEXT_SECONDARY = ("#3C3C43", "#EBEBF5")  # Sekundärtext ~60 % Opazität
COLOR_TEXT_MUTED     = ("#8E8E93", "#8E8E93")  # Hinweise, Labels
COLOR_TEXT_ACCENT    = ("#007AFF", "#0A84FF")  # Blauer Akzent-Text

# ── Aktionsfarben (Primär-Akzent) ─────────────────────────────────────────────
COLOR_PRIMARY_ACCENT = "#007AFF"   # iOS-Systemblau – klar, vertraut
COLOR_HOVER_ACCENT   = "#0062CC"   # Hover: dunkleres Blau
COLOR_PRESSED_ACCENT = "#004999"   # Active/Pressed
COLOR_VIOLET         = "#007AFF"   # Alias (rückwärtskompatibel)
COLOR_CYAN           = "#007AFF"   # Alias (rückwärtskompatibel)

# ── Statusfarben ─────────────────────────────────────────────────────────────
COLOR_SUCCESS = "#34C759"   # iOS-Grün
COLOR_WARNING = "#FF9500"   # iOS-Orange
COLOR_DANGER  = "#FF3B30"   # iOS-Rot

# ── Typografie-Tokens ─────────────────────────────────────────────────────────
FONT_FAMILY      = "Segoe UI"   # Windows; Fallback auf System-Font
FONT_FAMILY_MONO = "Consolas"   # Monospace für Metriken

# ── Backend-Badges ────────────────────────────────────────────────────────────
# Schlichte, neutrale Pills ohne Emojis – professionelles Erscheinungsbild
BADGE_STYLES = {
    "RUST":   {"bg": "#FFF4E6", "fg": "#C05000", "border": "#FFD0A0", "label": "RUST CORE"},
    "GPU":    {"bg": "#E8F4FD", "fg": "#005B9F", "border": "#A0C8F0", "label": "GPU  CUDA"},
    "PYTHON": {"bg": "#F0F4F8", "fg": "#4A5568", "border": "#C0CCDA", "label": "PYTHON"},
}

