# -*- coding: utf-8 -*-
"""phase6_geometry.py — Phase VI: Geometrische Morphologie & Gefäßdifferenzierung (Stufen 31–36).

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Stufen:
- Stufe 31: 4-fach vernetzte BFS-Clusterung der Anomalie-Regionen
- Stufe 32: Flächenfilterung (A >= 0.03% Gewebefläche, Subpixel-Rauschunterdrückung)
- Stufe 33: Zirkularitäts-Filterung (C = 4*pi*A / P^2 >= 0.08)
- Stufe 34: Kollisionsfilter mit dem Bildsensorrand (X, Y >= 15 px)
- Stufe 35: 2D-Hesse-Matrix-Zerlegung (Eigenwerte lambda_1, lambda_2)
- Stufe 36: Multiskalen Frangi-Filterung zur Gefäßunterdrückung
"""

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .context import PipelineContext, HotspotRegion
from .exporter import StepExporter


def execute_phase6(ctx: PipelineContext, exporter: StepExporter):
    """Führt die Stufen 31 bis 36 der Phase VI aus und exportiert alle Zwischenergebnisse."""
    phase_num = 6
    phase_name = "Phase VI: Geometric Morphology & Artifact Rejection"
    outlier_mask = ctx.outlier_mask.astype(np.uint8)
    temp = ctx.temp_3d_corrected if ctx.temp_3d_corrected is not None else ctx.temp_celsius
    h, w = outlier_mask.shape

    # =========================================================================
    # STUFE 31: 4-fach vernetzte BFS-Clusterung der Anomalie-Regionen
    # =========================================================================
    t0 = time.perf_counter()
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(outlier_mask, connectivity=4)
    raw_regions = []

    for i in range(1, num_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        cx, cy = int(centroids[i][0]), int(centroids[i][1])

        # Region-Ausschnitt für Umfangsberechnung
        roi_mask = (labels[y:y+bh, x:x+bw] == i).astype(np.uint8)
        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        perimeter = cv2.arcLength(contours[0], True) if len(contours) > 0 else 1.0
        circ = (4.0 * np.pi * area) / (perimeter**2) if perimeter > 0 else 0.0

        # Temperaturwerte im Herd
        comp_mask = (labels == i)
        t_max = float(np.max(temp[comp_mask]))
        t_mean = float(np.mean(temp[comp_mask]))

        region = HotspotRegion(
            region_id=i,
            center_x=cx,
            center_y=cy,
            bbox=(x, y, bw, bh),
            area_px=area,
            circularity=circ,
            aspect_ratio=float(bw) / max(1, bh),
            t_max=t_max,
            t_mean=t_mean,
            edge_gradient=0.0,
            halo_delta_t=0.0,
            laplace_divergence=0.0
        )
        raw_regions.append(region)

    ctx.raw_hotspot_regions = raw_regions
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s31(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='turbo')
        for r in raw_regions:
            x, y, bw, bh = r.bbox
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor='#F59E0B', linewidth=1.5)
            ax.add_patch(rect)
            ax.text(r.center_x, r.center_y, f"#{r.region_id}", color='#FFFFFF', fontsize=9, fontweight='bold', ha='center', va='center')
        ax.set_title(f"BFS-Clusterung • {len(raw_regions)} Hotspot-Kandidaten lokalisiert", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=31,
        phase_number=phase_num,
        phase_name=phase_name,
        name="BFS-Clusterung der Anomalie-Regionen",
        description="Fasst zusammenhängende Hyperthermie-Pixel mittels 4-Wege BFS in diskrete anatomische Befund-Kandidaten zusammen.",
        formula=r"\mathcal{R}_k = \{ p \mid \text{Labels}(p) = k \}, \quad \text{Centroid} = \frac{1}{|\mathcal{R}_k|} \sum_{p \in \mathcal{R}_k} p",
        duration_ms=d_ms,
        metrics={"Kandidaten": len(raw_regions), "Konnektivität": "4-fach vernetzt", "Status": "Initial erfasst"},
        render_fn=render_s31
    )

    # =========================================================================
    # STUFE 32: Flächenfilterung: Verwerfe Subpixel-Rauschen (< 0.03% Gewebefläche)
    # =========================================================================
    t0 = time.perf_counter()
    min_area_px = max(4, int(ctx.config.min_area_fraction * ctx.tissue_pixel_count))
    area_passed = [r for r in raw_regions if r.area_px >= min_area_px]
    area_rejected = len(raw_regions) - len(area_passed)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s32(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='inferno')
        for r in raw_regions:
            x, y, bw, bh = r.bbox
            color = '#10B981' if r in area_passed else '#EF4444'
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor=color, linewidth=1.5)
            ax.add_patch(rect)
        ax.set_title(f"Flächenfilterung (Min-Fläche = {min_area_px} px) • {len(area_passed)} behalten, {area_rejected} verworfen", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=32,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Flächenfilterung gegen Rauschen",
        description="Filtert mikroskopische Einzelpixel-Artefakte unterhalb von 0.03% der Fußgewebefläche aus.",
        formula=r"\text{Keep}(\mathcal{R}_k) \iff \text{Area}(\mathcal{R}_k) \ge 0{,}0003 \cdot N_{\text{tissue}}",
        duration_ms=d_ms,
        metrics={"Mindestgröße": f"{min_area_px} px", "Beibehalten": len(area_passed), "Rauschpunkte eliminiert": area_rejected},
        render_fn=render_s32
    )

    # =========================================================================
    # STUFE 33: Zirkularitäts-Filterung (C = 4*pi*A / P^2 >= 0.08)
    # =========================================================================
    t0 = time.perf_counter()
    min_circ = ctx.config.min_circularity  # 0.08
    circ_passed = [r for r in area_passed if r.circularity >= min_circ]
    circ_rejected = len(area_passed) - len(circ_passed)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s33(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='inferno')
        for r in area_passed:
            x, y, bw, bh = r.bbox
            color = '#10B981' if r in circ_passed else '#F59E0B'
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor=color, linewidth=1.5)
            ax.add_patch(rect)
            lbl = "Rund" if r in circ_passed else "Linear"
            ax.text(x, max(10, y - 5), f"C={r.circularity:.2f} ({lbl})", color=color, fontsize=8, fontweight='bold')
        ax.set_title(f"Zirkularitätsprüfung (C >= {min_circ}) • Rund: {len(circ_passed)} | Lineare Venen: {circ_rejected}", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=33,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Zirkularitäts-Prüfung",
        description="Unterscheidet kreisförmige pathologische Druckstellen (hohe Zirkularität) von langgestreckten Venen (niedrige Zirkularität).",
        formula=r"C = \frac{4\pi \cdot \text{Area}}{\text{Perimeter}^2} \ge 0{,}08",
        duration_ms=d_ms,
        metrics={"Min Zirkularität": f"{min_circ}", "Kompakt/Rund": len(circ_passed), "Langgestreckt/Vene": circ_rejected},
        render_fn=render_s33
    )

    # =========================================================================
    # STUFE 34: Kollisionsfilter mit dem Bildsensorrand (X, Y >= 15 px)
    # =========================================================================
    t0 = time.perf_counter()
    b_px = ctx.config.border_exclusion_px  # 15
    border_passed = []
    border_rejected = 0

    for r in circ_passed:
        x, y, bw, bh = r.bbox
        if x <= b_px or y <= b_px or (x + bw) >= (w - b_px) or (y + bh) >= (h - b_px):
            border_rejected += 1
        else:
            border_passed.append(r)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s34(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='inferno')
        # Sensorrand-Sicherheitszone zeichnen
        border_rect = plt.Rectangle((b_px, b_px), w - 2*b_px, h - 2*b_px, fill=False, edgecolor='#DC2626', linestyle=':', linewidth=1.5)
        ax.add_patch(border_rect)
        for r in circ_passed:
            x, y, bw, bh = r.bbox
            color = '#10B981' if r in border_passed else '#DC2626'
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor=color, linewidth=1.5)
            ax.add_patch(rect)
        ax.set_title(f"Sensorrand-Ausschluss (Marge = {b_px} px) • {len(border_passed)} sicher im Sensorzentrum", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=34,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Sensorrand-Ausschluss",
        description="Schließt Randartefakte und Vignettierungseffekte an den Kanten des Bolometer-Sensors aus.",
        formula=r"\text{Valid}(\mathcal{R}_k) \iff \text{BBox}(\mathcal{R}_k) \subset [b_{\text{px}},\, W - b_{\text{px}}] \times [b_{\text{px}},\, H - b_{\text{px}}]",
        duration_ms=d_ms,
        metrics={"Randabstand": f"{b_px} px", "Sicher im Zentrum": len(border_passed), "Am Rand verworfen": border_rejected},
        render_fn=render_s34
    )

    # =========================================================================
    # STUFE 35: 2D-Hesse-Matrix-Zerlegung (lambda_1, lambda_2)
    # =========================================================================
    t0 = time.perf_counter()
    # Zweite Ableitungen für Hesse-Matrix
    # Ixx, Ixy, Iyy
    smooth_temp = cv2.GaussianBlur(temp, (5, 5), 1.0)
    ixx = cv2.Sobel(smooth_temp, cv2.CV_32F, 2, 0, ksize=3)
    iyy = cv2.Sobel(smooth_temp, cv2.CV_32F, 0, 2, ksize=3)
    ixy = cv2.Sobel(smooth_temp, cv2.CV_32F, 1, 1, ksize=3)

    # Hesse-Eigenwerte: det(H - lambda*I) = 0
    # lambda = (trace +- sqrt(trace^2 - 4*det)) / 2
    trace = ixx + iyy
    det = (ixx * iyy) - (ixy ** 2)
    disc = np.clip((trace ** 2) - (4.0 * det), 0.0, None)
    sqrt_disc = np.sqrt(disc)

    l1 = (trace - sqrt_disc) / 2.0
    l2 = (trace + sqrt_disc) / 2.0

    # Sortiere so, dass |l1| <= |l2|
    swap = np.abs(l1) > np.abs(l2)
    tmp = l1.copy()
    l1[swap] = l2[swap]
    l2[swap] = tmp[swap]

    ctx.hessian_l1 = l1
    ctx.hessian_l2 = l2
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s35(fig: Figure, ax: plt.Axes):
        im = ax.imshow(l2, cmap='seismic', vmin=-1.0, vmax=1.0)
        ax.set_title("Hesse-Matrix Hauptkrümmung λ₂ • Krümmungstopologie der Thermodynamik", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Krümmungseigenwert λ₂", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=35,
        phase_number=phase_num,
        phase_name=phase_name,
        name="2D-Hesse-Matrix-Zerlegung",
        description="Berechnet die lokalen Krümmungseigenwerte λ₁, λ₂ der Temperaturfunktion zur morphologischen Gefäß- und Herdklassifikation.",
        formula=r"\mathcal{H} = \begin{bmatrix} I_{xx} & I_{xy} \\ I_{xy} & I_{yy} \end{bmatrix}, \quad \det(\mathcal{H} - \lambda \mathcal{I}) = 0",
        duration_ms=d_ms,
        metrics={"Eigenwerte": "λ₁, λ₂ (|λ₁| ≤ |λ₂|)", "Kernel": "Sobel 2. Ordnung", "Glättung": "Gauß σ=1.0"},
        render_fn=render_s35
    )

    # =========================================================================
    # STUFE 36: Multiskalen Frangi-Filterung zur Gefäßunterdrückung
    # =========================================================================
    t0 = time.perf_counter()
    beta = 0.5
    c_param = 1.0

    # R_B = |l1| / |l2|, S = sqrt(l1^2 + l2^2)
    rb = np.abs(l1) / np.clip(np.abs(l2), 1e-5, None)
    s_norm = np.sqrt(l1**2 + l2**2)

    # Frangi Vesselness: V = 0 wenn l2 > 0 (Dunkle Röhre)
    # V = exp(-Rb^2 / 2*beta^2) * (1 - exp(-S^2 / 2*c^2))
    vesselness = np.zeros_like(l2)
    tubular_cond = (l2 < 0)  # Helle röhrenförmige Strukturen (warme Venen)
    vesselness[tubular_cond] = np.exp(-(rb[tubular_cond]**2) / (2.0 * (beta**2))) * (1.0 - np.exp(-(s_norm[tubular_cond]**2) / (2.0 * (c_param**2))))
    vesselness[~ctx.eroded_body_mask] = 0.0
    ctx.frangi_vesselness = vesselness

    # Hotspot-Klassifikation: Enthält die Region signifikante Frangi-Gefäße?
    final_regions = []
    for r in border_passed:
        x, y, bw, bh = r.bbox
        roi_vessel = vesselness[y:y+bh, x:x+bw]
        mean_v = float(np.mean(roi_vessel)) if roi_vessel.size > 0 else 0.0
        if mean_v > 0.4:
            r.is_vascular = True
            r.clinical_note = "Physiologische Fußvene (Vesselness > 0.4)"
        else:
            r.is_vascular = False
            r.clinical_note = "Fokaler Entzündungsherd"
            final_regions.append(r)

    ctx.filtered_hotspots = final_regions
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s36(fig: Figure, ax: plt.Axes):
        im = ax.imshow(vesselness, cmap='magma')
        # Zeichne erkannte Herde ein
        for r in final_regions:
            x, y, bw, bh = r.bbox
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor='#38BDF8', linewidth=2)
            ax.add_patch(rect)
            ax.text(r.center_x, r.center_y, f"HERD #{r.region_id}", color='#FFFFFF', fontsize=9, fontweight='bold', ha='center', va='center')
        ax.set_title(f"Frangi-Vesselness Filter • {len(final_regions)} echte Entzündungsherde isoliert (Venen unterdrückt)", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Vesselness-Wahrscheinlichkeit", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=36,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Multiskalen Frangi-Filterung",
        description="Unterdrückt physiologische Venennetze (Vesselness) zugunsten echter zirkulärer Entzündungsherde unter Druckstellen.",
        formula=r"\mathcal{V}(\sigma) = \begin{cases} 0 & \text{falls } \lambda_2 > 0 \\ \exp\left(-\frac{R_B^2}{2\beta^2}\right) \left(1 - \exp\left(-\frac{S^2}{2c^2}\right)\right) & \text{sonst} \end{cases}",
        duration_ms=d_ms,
        metrics={"Herde bestätigt": len(final_regions), "Beta-Parameter": f"{beta}", "C-Parameter": f"{c_param}"},
        render_fn=render_s36
    )
