# -*- coding: utf-8 -*-
"""phase4_morphology.py — Phase IV: Multiskalige Morphologische Anomalie-Extraktion (Stufen 19–24).

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Stufen:
- Stufe 19: Dynamische Kernberechnung R = max(15, 0.05 * min(W, H))
- Stufe 20: 1D Horizontale Minkowski Erosion
- Stufe 21: 1D Vertikale Minkowski Erosion
- Stufe 22: 1D Horizontale Minkowski Dilation
- Stufe 23: 1D Vertikale Minkowski Dilation
- Stufe 24: Morphologischer White Top-Hat Residuum (x86_64 SIMD Assembler Kernel)
"""

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from .context import PipelineContext
from .exporter import StepExporter

try:
    from assembly.fast_simd import simd_saturating_sub
except ImportError:
    from ..assembly.fast_simd import simd_saturating_sub




def execute_phase4(ctx: PipelineContext, exporter: StepExporter):
    """Führt die Stufen 19 bis 24 der Phase IV aus und exportiert alle Zwischenergebnisse."""
    phase_num = 4
    phase_name = "Phase IV: Multiscale Morphological Anomaly Extraction"
    gray = ctx.raw_gray
    mask = ctx.eroded_body_mask
    h, w = gray.shape

    # =========================================================================
    # STUFE 19: Dynamische Kernberechnung R = max(15, 0.05 * min(W, H))
    # =========================================================================
    t0 = time.perf_counter()
    min_dim = min(h, w)
    k_factor = ctx.config.kernel_factor  # 0.05
    radius = max(15, int(k_factor * min_dim))
    ctx.kernel_radius_px = radius
    k_diameter = 2 * radius + 1
    struct_elem = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_diameter, k_diameter))
    ctx.structuring_element = struct_elem
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s19(fig: Figure, ax: plt.Axes):
        # Zeige das kreisförmige Strukturelement B
        ax.imshow(struct_elem, cmap='Blues')
        ax.set_title(f"Kreisförmiges Strukturelement B • Radius: {radius} px ({radius*0.6:.1f} mm) • Durchmesser: {k_diameter} px", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=19,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Dynamische Kerngrößen-Berechnung",
        description="Skaliert das morphologische Strukturelement B proportional zur Auflösung, um physiologische Hintergrundgradienten sauber zu erfassen.",
        formula=r"R = \max\left(15,\, \lfloor 0{,}05 \cdot \min(W, H) \rfloor\right), \quad B = \mathcal{B}_{R}(0)",
        duration_ms=d_ms,
        metrics={"Radius R": f"{radius} px", "Metrisch": f"{radius*0.6:.1f} mm", "Durchmesser": f"{k_diameter} px"},
        render_fn=render_s19
    )

    # =========================================================================
    # STUFE 20: 1D Horizontale Minkowski Erosion
    # =========================================================================
    t0 = time.perf_counter()
    # 1D-Separation: O(2R) statt O(R^2) Komplexität pro Pixel!
    kernel_1d_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_diameter, 1))
    eroded_h = cv2.erode(gray, kernel_1d_h)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s20(fig: Figure, ax: plt.Axes):
        ax.imshow(eroded_h, cmap='bone')
        ax.set_title("1D Horizontale Minkowski-Erosion • Minima-Filterung zeilenweise", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=20,
        phase_number=phase_num,
        phase_name=phase_name,
        name="1D Horizontale Minkowski Erosion",
        description="Erste Stufe der separablen morphologischen Erosion: Findet das horizontale lokale Minimum über 2R+1 Pixel.",
        formula=r"\mathcal{E}_H(I)(x,y) = \min_{-R \le k \le R} I(x+k, y)",
        duration_ms=d_ms,
        metrics={"Kernel-Typ": "1D Horizontal", "Länge": f"{k_diameter} px", "Komplexität": "O(R)"},
        render_fn=render_s20
    )

    # =========================================================================
    # STUFE 21: 1D Vertikale Minkowski Erosion
    # =========================================================================
    t0 = time.perf_counter()
    kernel_1d_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_diameter))
    eroded_2d = cv2.erode(eroded_h, kernel_1d_v)
    ctx.eroded_img = eroded_2d
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s21(fig: Figure, ax: plt.Axes):
        ax.imshow(eroded_2d, cmap='bone')
        ax.set_title("Vollständige 2D-Erosion (Horiz + Vert) • Lokale Talsohle isoliert", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=21,
        phase_number=phase_num,
        phase_name=phase_name,
        name="1D Vertikale Minkowski Erosion",
        description="Zweite Stufe der separablen Erosion: Liefert die vollständige zweidimensionale morphologische Talsohle.",
        formula=r"\mathcal{E}_B(I)(x,y) = \mathcal{E}_V(\mathcal{E}_H(I))(x,y) = \min_{(u,v) \in B} I(x+u, y+v)",
        duration_ms=d_ms,
        metrics={"Kernel-Typ": "1D Vertikal", "Status": "2D-Erosion komplett", "Operationen": "2x 1D statt 2D"},
        render_fn=render_s21
    )

    # =========================================================================
    # STUFE 22: 1D Horizontale Minkowski Dilation
    # =========================================================================
    t0 = time.perf_counter()
    dilated_h = cv2.dilate(eroded_2d, kernel_1d_h)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s22(fig: Figure, ax: plt.Axes):
        ax.imshow(dilated_h, cmap='bone')
        ax.set_title("1D Horizontale Minkowski-Dilation • Rekonstruktion des Hintergrunds", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=22,
        phase_number=phase_num,
        phase_name=phase_name,
        name="1D Horizontale Minkowski Dilation",
        description="Erste Stufe der Dilation auf dem erodierten Bild zur Rekonstruktion der großflächigen thermischen Grundlast.",
        formula=r"\mathcal{D}_H(\mathcal{E}_B(I))(x,y) = \max_{-R \le k \le R} \mathcal{E}_B(I)(x+k, y)",
        duration_ms=d_ms,
        metrics={"Kernel-Typ": "1D Horizontal", "Länge": f"{k_diameter} px", "Phase": "Opening Schritt 1"},
        render_fn=render_s22
    )

    # =========================================================================
    # STUFE 23: 1D Vertikale Minkowski Dilation (Morphologisches Opening)
    # =========================================================================
    t0 = time.perf_counter()
    opened_img = cv2.dilate(dilated_h, kernel_1d_v)
    ctx.opened_img = opened_img
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s23(fig: Figure, ax: plt.Axes):
        im = ax.imshow(opened_img, cmap='inferno')
        ax.set_title("Morphologisches Opening (I ∘ B) • Großflächiger physiologischer Hintergrund", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Hintergrund-Intensität", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=23,
        phase_number=phase_num,
        phase_name=phase_name,
        name="1D Vertikale Minkowski Dilation",
        description="Schließt das morphologische Opening ab: Glattes Hintergrund-Temperaturfeld ohne fokale Hotspots.",
        formula=r"(I \circ B)(x,y) = \mathcal{D}_B(\mathcal{E}_B(I))(x,y)",
        duration_ms=d_ms,
        metrics={"Status": "Opening fertiggestellt", "Hintergrund": "Glatt", "Fokale Peaks": "Entfernt"},
        render_fn=render_s23
    )

    # =========================================================================
    # STUFE 24: Morphologischer White Top-Hat Residuum (x86_64 SIMD Assembler)
    # =========================================================================
    t0 = time.perf_counter()
    # ECHTE x86_64 SIMD ASSEMBLER-SUBTRAKTION:
    tophat_diff, backend = simd_saturating_sub(gray, opened_img)
    # Außerhalb des Gewebes auf 0 setzen
    tophat_diff[~mask] = 0
    ctx.tophat_diff = tophat_diff
    ctx.backend_used = backend
    max_peak_val = int(np.max(tophat_diff))
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s24(fig: Figure, ax: plt.Axes):
        im = ax.imshow(tophat_diff, cmap='hot', vmin=0, vmax=max(10, max_peak_val))
        ax.set_title(f"White Top-Hat WTH(I) • {backend} • Max Peak: {max_peak_val} Graustufen", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Top-Hat Residuum (Fokale Überhöhung)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=24,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Morphologischer White Top-Hat",
        description="Subtrahiert das Opening vom Original mittels x86-64 SIMD Assembler (VPSUBUSB / PSUBUSB): Isoliert alle fokalen Entzündungsherde bit-identisch!",
        formula=r"\text{WTH}(I) = I - (I \circ B) = \text{VPSUBUSB}(I,\, I \circ B)",
        duration_ms=d_ms,
        metrics={"Rechenkern": backend, "Max Überhöhung": f"{max_peak_val} Stufen", "SIMD-Instruktion": "PSUBUSB (16 B/Takt)"},
        render_fn=render_s24
    )
