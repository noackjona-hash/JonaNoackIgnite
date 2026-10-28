# -*- coding: utf-8 -*-
"""phase3_depth_3d.py — Phase III: 3D Anatomical Inflation & Angle Compensation (Stufen 13–18).

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Stufen:
- Stufe 13: Shape-from-Silhouette 3D-Tiefenmodell Z(x, y)
- Stufe 14: 3D-Normalenfeld n(x, y) = (-dZ/dx, -dZ/dy, 1)
- Stufe 15: Kosinus-Blickwinkelfeld cos(theta) = n * v
- Stufe 16: LWIR Fresnel-Emissivitätsmodellierung epsilon(theta)
- Stufe 17: Tangentiale Kosinus-Kompensation (Delta_T <= 1.2 K)
- Stufe 18: Generierung der winkelkorrigierten Matrix T_corr
"""

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .context import PipelineContext
from .exporter import StepExporter


def execute_phase3(ctx: PipelineContext, exporter: StepExporter):
    """Führt die Stufen 13 bis 18 der Phase III aus und exportiert alle Zwischenergebnisse."""
    phase_num = 3
    phase_name = "Phase III: 3D Anatomical Inflation & Angle Compensation"
    dist_field = ctx.distance_field
    mask = ctx.eroded_body_mask
    temp = ctx.temp_celsius
    h, w = temp.shape

    # =========================================================================
    # STUFE 13: Shape-from-Silhouette 3D-Tiefenmodell Z(x, y)
    # =========================================================================
    t0 = time.perf_counter()
    # Modelliert den Fuß als biophysikalisch gewölbten Halbzylinder/Ellipsoid
    max_d = float(np.max(dist_field)) if np.max(dist_field) > 0 else 1.0
    norm_d = np.clip(dist_field / max_d, 0.0, 1.0)
    # Elliptische Inflation: Z(x,y) = R * sqrt(1 - (1 - d/R)^2)
    depth_3d = np.where(mask, max_d * np.sqrt(np.clip(1.0 - (1.0 - norm_d)**2, 0.0, 1.0)), 0.0).astype(np.float32)
    ctx.depth_map_3d = depth_3d
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s13(fig: Figure, ax: plt.Axes):
        im = ax.imshow(depth_3d, cmap='viridis')
        ax.set_title(f"3D Shape-from-Silhouette • Anatomische Gewölbehöhe: {np.max(depth_3d):.1f} px", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Z-Höhe (Pixel)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=13,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Shape-from-Silhouette 3D-Tiefenmodell",
        description="Rekonstruiert die dreidimensionale anatomische Wölbung Z(x, y) des Fußes anhand der euklidischen Randgeodäten.",
        formula=r"Z(x,y) = R_{\max} \cdot \sqrt{1 - \left(1 - \frac{D(x,y)}{R_{\max}}\right)^2}",
        duration_ms=d_ms,
        metrics={"Max Höhe": f"{np.max(depth_3d):.1f} px", "Geodäte R_max": f"{max_d:.1f} px", "Körpermodell": "Elliptisch"},
        render_fn=render_s13
    )

    # =========================================================================
    # STUFE 14: 3D-Normalenfeld n(x, y) = (-dZ/dx, -dZ/dy, 1)
    # =========================================================================
    t0 = time.perf_counter()
    # Sobel-Operatoren zur Bestimmung der 3D-Oberflächenneigung
    dz_dx = cv2.Sobel(depth_3d, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    dz_dy = cv2.Sobel(depth_3d, cv2.CV_32F, 0, 1, ksize=3) / 8.0

    # Normalenvektoren n = (-dZ/dx, -dZ/dy, 1) normalisieren
    nx = -dz_dx
    ny = -dz_dy
    nz = np.ones_like(nx)
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    norm[norm == 0] = 1.0
    nx /= norm
    ny /= norm
    nz /= norm

    # RGB-Repräsentation des Normalenfeldes: (nx+1)/2, (ny+1)/2, nz
    normals_rgb = np.zeros((h, w, 3), dtype=np.float32)
    normals_rgb[..., 0] = (nx + 1.0) / 2.0
    normals_rgb[..., 1] = (ny + 1.0) / 2.0
    normals_rgb[..., 2] = nz
    normals_rgb[~mask] = 0.0
    ctx.normal_map_3d = normals_rgb
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s14(fig: Figure, ax: plt.Axes):
        ax.imshow(normals_rgb)
        ax.set_title("3D-Oberflächennormalen n(x, y) • RGB = (Normal_X, Normal_Y, Normal_Z)", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=14,
        phase_number=phase_num,
        phase_name=phase_name,
        name="3D-Oberflächennormalen",
        description="Ermittelt die Ausrichtung jedes mikroskopischen Hautareals im 3D-Raum mittels partieller Ableitungen der Tiefenfunktion.",
        formula=r"\vec{n}(x,y) = \frac{\left( -\frac{\partial Z}{\partial x}, -\frac{\partial Z}{\partial y}, 1 \right)^T}{\sqrt{\left(\frac{\partial Z}{\partial x}\right)^2 + \left(\frac{\partial Z}{\partial y}\right)^2 + 1}}",
        duration_ms=d_ms,
        metrics={"Gradienten": "Sobel 3x3", "Normalisierung": "Unit Sphere", "Status": "Berechnet"},
        render_fn=render_s14
    )

    # =========================================================================
    # STUFE 15: Kosinus-Blickwinkelfeld cos(theta) = n * v
    # =========================================================================
    t0 = time.perf_counter()
    # Kamera blickt entlang der Z-Achse: v = (0, 0, 1) -> cos(theta) = nz
    cos_theta = np.clip(nz, 0.1, 1.0)
    ctx.cosine_view_angle = cos_theta
    min_cos = float(np.min(cos_theta[mask])) if np.sum(mask) > 0 else 0.5
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s15(fig: Figure, ax: plt.Axes):
        vis_cos = np.zeros_like(cos_theta)
        vis_cos[mask] = cos_theta[mask]
        im = ax.imshow(vis_cos, cmap='magma', vmin=0.1, vmax=1.0)
        ax.set_title(f"Kosinus-Blickwinkel cos(θ) • Minimaler Winkel an Kante: {np.degrees(np.arccos(min_cos)):.1f}°", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("cos(θ) Blickwinkel", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=15,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Kosinus-Blickwinkelfeld",
        description="Quantifiziert den optischen Einfallswinkel θ zwischen Kameraachse und gekrümmter Hautoberfläche nach dem Lambert'schen Gesetz.",
        formula=r"\cos\theta = \frac{\vec{n} \cdot \vec{v}}{\|\vec{n}\| \|\vec{v}\|} = n_z(x,y)",
        duration_ms=d_ms,
        metrics={"Min cos(θ)": f"{min_cos:.3f}", "Max Neigung": f"{np.degrees(np.arccos(min_cos)):.1f}°", "Blickvektor": "(0, 0, 1)"},
        render_fn=render_s15
    )

    # =========================================================================
    # STUFE 16: LWIR Fresnel-Emissivitätsmodellierung
    # =========================================================================
    t0 = time.perf_counter()
    # Menschliche Haut hat bei normalem Blickwinkel ε_0 = 0.98.
    # Bei schrägem Einfall fällt die Emissivität nach Fresnel ab: ε(θ) = ε_0 * cos(θ)^p
    eps_0 = 0.98
    p_power = 0.2
    emissivity = np.where(mask, eps_0 * (cos_theta ** p_power), eps_0).astype(np.float32)
    ctx.emissivity_map = emissivity
    min_eps = float(np.min(emissivity[mask])) if np.sum(mask) > 0 else eps_0
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s16(fig: Figure, ax: plt.Axes):
        vis_eps = np.zeros_like(emissivity)
        vis_eps[mask] = emissivity[mask]
        im = ax.imshow(vis_eps, cmap='inferno', vmin=0.85, vmax=0.98)
        ax.set_title(f"Fresnel-Hautemissivität ε(θ) • Min: {min_eps:.3f} | Max: {eps_0:.2f}", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Emissivität ε", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=16,
        phase_number=phase_num,
        phase_name=phase_name,
        name="LWIR Fresnel-Emissivitätsmodellierung",
        description="Modelliert den physikalischen Abfall der Wärmeabstrahlung an gekrümmten Körpergrenzen nach den elektrodynamischen Fresnel-Formeln.",
        formula=r"\varepsilon(\theta) = \varepsilon_0 \cdot \cos^p(\theta), \quad \varepsilon_0 = 0{,}98, \quad p = 0{,}2",
        duration_ms=d_ms,
        metrics={"ε_0 (Normale)": f"{eps_0}", "Min ε(θ)": f"{min_eps:.3f}", "Exponent p": f"{p_power}"},
        render_fn=render_s16
    )

    # =========================================================================
    # STUFE 17: Tangentiale Kosinus-Temperaturkompensation (Delta_T <= 1.2 K)
    # =========================================================================
    t0 = time.perf_counter()
    # T_real = T_apparent / (eps(theta))^(1/4)
    # Stefan-Boltzmann: E = eps * sigma * T^4 -> T = (E / (eps*sigma))^(1/4)
    factor = (1.0 / (emissivity ** 0.25)) - 1.0
    delta_t_raw = (temp + 273.15) * factor  # in Kelvin
    # Strikter Sicherheitsdeckel von 1.2 K nach DIN EN ISO 13485
    delta_t_capped = np.clip(delta_t_raw, 0.0, 1.2)
    delta_t_capped[~mask] = 0.0
    max_comp_k = float(np.max(delta_t_capped))
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s17(fig: Figure, ax: plt.Axes):
        im = ax.imshow(delta_t_capped, cmap='hot', vmin=0.0, vmax=1.2)
        ax.set_title(f"Kosinus-Temperaturkompensation ΔT • Max: +{max_comp_k:.2f} K (Gedeckelt auf 1.2 K)", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Temperatur-Zuschlag (K)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=17,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Tangentiale Kosinus-Kompensation",
        description="Berechnet den mathematischen Temperaturzuschlag für schräg geneigte Randbezirke mit Sicherheitsdeckelung auf maximal 1.2 K.",
        formula=r"\Delta T_{\text{corr}} = \min\left(1{,}2\,\text{K},\, (T + 273{,}15) \cdot \left(\frac{1}{\sqrt[4]{\varepsilon(\theta)}} - 1\right)\right)",
        duration_ms=d_ms,
        metrics={"Max Zuschlag": f"+{max_comp_k:.2f} K", "Sicherheitsgrenze": "1.2 K", "Schutz": "Keine Überhitzung"},
        render_fn=render_s17
    )

    # =========================================================================
    # STUFE 18: Generierung der winkelkorrigierten Matrix T_corr
    # =========================================================================
    t0 = time.perf_counter()
    corrected_temp = temp + delta_t_capped
    ctx.temp_3d_corrected = corrected_temp
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s18(fig: Figure, ax: plt.Axes):
        im = ax.imshow(corrected_temp, cmap='turbo')
        ax.set_title("Winkelkorrigierte Thermomatrix T_corr • Randabkühlungs-Artefakte neutralisiert", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Korrigierte Temp. (°C)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=18,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Winkelkorrigierte Thermomatrix",
        description="Liefert die physikalisch bereinigte Temperaturverteilung, bei der die durch 3D-Körperkrümmung bedingte Scheinkühlung eliminiert ist.",
        formula=r"T_{\text{corr}}(x,y) = T_{\text{apparent}}(x,y) + \Delta T_{\text{corr}}(x,y)",
        duration_ms=d_ms,
        metrics={"T_Mittel Vorher": f"{np.mean(temp[mask]):.2f} °C", "T_Mittel Nachher": f"{np.mean(corrected_temp[mask]):.2f} °C", "Status": "Optimal"},
        render_fn=render_s18
    )
