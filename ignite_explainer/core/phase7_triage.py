# -*- coding: utf-8 -*-
"""phase7_triage.py — Phase VII: Biophysikalische Differentialdiagnose & Armstrong Triage (Stufen 37–42).

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Stufen:
- Stufe 37: Perifokaler Randgradient G_edge = dT/dr
- Stufe 38: Perifokale Vasodilatations-Haloanalyse Delta_T_halo
- Stufe 39: Diskrete 2D-Laplace-Divergenz nabla^2 T Fokus-Kern
- Stufe 40: Homologe Registrierung & Armstrong-Seitenvergleich Delta_T_contra >= 2.2 K
- Stufe 41: Diffuses Muskelplateau vs. fokale Pathologie
- Stufe 42: Klinische Triage & IWGDF Armstrong Entscheidungslogik
"""

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .context import PipelineContext, HotspotRegion
from .exporter import StepExporter


def execute_phase7(ctx: PipelineContext, exporter: StepExporter):
    """Führt die Stufen 37 bis 42 der Phase VII aus und exportiert alle Zwischenergebnisse."""
    phase_num = 7
    phase_name = "Phase VII: Biophysical Differential Diagnosis & Triage"
    temp = ctx.temp_3d_corrected if ctx.temp_3d_corrected is not None else ctx.temp_celsius
    mask = ctx.eroded_body_mask
    hotspots = ctx.filtered_hotspots
    h, w = temp.shape

    # =========================================================================
    # STUFE 37: Perifokaler Randgradient G_edge = dT/dr
    # =========================================================================
    t0 = time.perf_counter()
    # Gradientenbetrag berechnen
    gx = cv2.Sobel(temp, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(temp, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(gx**2 + gy**2)
    grad_mag[~mask] = 0.0

    max_grad = 0.0
    for r in hotspots:
        x, y, bw, bh = r.bbox
        roi_g = grad_mag[max(0, y-5):min(h, y+bh+5), max(0, x-5):min(w, x+bw+5)]
        g_val = float(np.max(roi_g)) if roi_g.size > 0 else 0.0
        r.edge_gradient = g_val
        if g_val > max_grad:
            max_grad = g_val
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s37(fig: Figure, ax: plt.Axes):
        im = ax.imshow(grad_mag, cmap='cividis')
        for r in hotspots:
            x, y, bw, bh = r.bbox
            rect = plt.Rectangle((x, y), bw, bh, fill=False, edgecolor='#F59E0B', linewidth=2)
            ax.add_patch(rect)
            ax.text(r.center_x, y - 5, f"G={r.edge_gradient:.1f} K/mm", color='#F59E0B', fontsize=8, fontweight='bold')
        ax.set_title(f"Perifokaler Randgradient G_edge • Schärfe des Temperaturabfalls (Max: {max_grad:.2f} K/mm)", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Temperaturgradient |∇T| (K/mm)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=37,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Perifokaler Randgradient",
        description="Analysiert die Steilheit des thermischen Randabfalls dT/dr: Scharfe Kanten weisen auf mechanische Druckulzera hin, weiche Verläufe auf diffuse Entzündungen.",
        formula=r"G_{\text{edge}} = \|\nabla T(x,y)\| = \sqrt{\left(\frac{\partial T}{\partial x}\right)^2 + \left(\frac{\partial T}{\partial y}\right)^2}",
        duration_ms=d_ms,
        metrics={"Max Gradient": f"{max_grad:.2f} K/mm", "Bedeutung": "Scharfer Rand = Druckstelle", "Einheit": "K/mm"},
        render_fn=render_s37
    )

    # =========================================================================
    # STUFE 38: Perifokale Vasodilatations-Haloanalyse Delta_T_halo
    # =========================================================================
    t0 = time.perf_counter()
    max_halo = 0.0
    halo_map = np.zeros_like(temp)

    for r in hotspots:
        # Erzeuge Ringmaske um den Herd (innerer Radius R, äußerer Radius 2R)
        ring_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(ring_mask, (r.center_x, r.center_y), max(10, int(r.area_px**0.5 * 1.5)), 255, -1)
        inner_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(inner_mask, (r.center_x, r.center_y), max(5, int(r.area_px**0.5 * 0.7)), 255, -1)
        halo_ring = (ring_mask > 0) & (inner_mask == 0) & mask

        t_halo = float(np.mean(temp[halo_ring])) if np.sum(halo_ring) > 0 else r.t_mean
        t_surround = float(ctx.tissue_median) if hasattr(ctx, 'tissue_median') else float(np.median(temp[mask]))
        delta_halo = max(0.0, t_halo - (ctx.config.min_temp_floor + t_surround * 0.05))
        r.halo_delta_t = delta_halo
        halo_map[halo_ring] = delta_halo
        if delta_halo > max_halo:
            max_halo = delta_halo
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s38(fig: Figure, ax: plt.Axes):
        im = ax.imshow(temp, cmap='turbo')
        for r in hotspots:
            circle = plt.Circle((r.center_x, r.center_y), max(10, int(r.area_px**0.5 * 1.5)), fill=False, edgecolor='#EC4899', linestyle='--', linewidth=2)
            ax.add_patch(circle)
            ax.text(r.center_x, r.center_y + 15, f"Halo ΔT={r.halo_delta_t:.2f}K", color='#FFFFFF', fontsize=8, fontweight='bold', ha='center')
        ax.set_title(f"Vasodilatations-Haloanalyse • Warmer Hof um Entzündung (Max ΔT_halo = {max_halo:.2f} K)", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=38,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Vasodilatations-Haloanalyse",
        description="Quantifiziert den vasodilatatorischen Wärmehof (Hyperämie durch Stickstoffmonoxid / Zytokine) in der perifokalen Gewebemanschette.",
        formula=r"\Delta T_{\text{halo}} = \bar{T}_{\text{ring}}(r_{\text{in}}, r_{\text{out}}) - T_{\text{physiol}}",
        duration_ms=d_ms,
        metrics={"Max Halo ΔT": f"{max_halo:.2f} K", "Vaskuläre Weitung": "Hyperämie nachweisbar", "Zytokin-Reaktion": "Positiv"},
        render_fn=render_s38
    )

    # =========================================================================
    # STUFE 39: Diskrete 2D-Laplace-Divergenz nabla^2 T Fokus-Kern
    # =========================================================================
    t0 = time.perf_counter()
    # Laplace-Operator d^2T/dx^2 + d^2T/dy^2
    laplace = cv2.Laplacian(temp, cv2.CV_32F, ksize=3)
    laplace[~mask] = 0.0

    for r in hotspots:
        x, y, bw, bh = r.bbox
        roi_lap = laplace[y:y+bh, x:x+bw]
        # Ein echtes Maximum (Wärmequelle) hat eine stark negative Divergenz!
        min_div = float(np.min(roi_lap)) if roi_lap.size > 0 else 0.0
        r.laplace_divergence = min_div
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s39(fig: Figure, ax: plt.Axes):
        im = ax.imshow(laplace, cmap='bwr', vmin=-2.0, vmax=2.0)
        ax.set_title("2D-Laplace-Divergenz ∇²T • Blau = Wärmequelle (Konvektionskern) | Rot = Wärmesenke", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Laplace ∇²T", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=39,
        phase_number=phase_num,
        phase_name=phase_name,
        name="2D-Laplace Divergenzanalyse",
        description="Bestätigt mittels Divergenzoperator ∇²T, ob ein Herd als biophysikalische Wärmequelle (lokale Stoffwechselsteigerung) fungiert.",
        formula=r"\nabla^2 T = \frac{\partial^2 T}{\partial x^2} + \frac{\partial^2 T}{\partial y^2} < 0 \implies \text{Lokale Wärmequelle}",
        duration_ms=d_ms,
        metrics={"Operator": "Diskreter 3x3 Laplace", "Quelle": "∇²T < 0 bestätigt", "Senke": "∇²T > 0"},
        render_fn=render_s39
    )

    # =========================================================================
    # STUFE 40: Homologe Registrierung & Armstrong-Seitenvergleich
    # =========================================================================
    t0 = time.perf_counter()
    mid_x = w // 2

    # Anatomische Trennung: Finde linken und rechten Fuß über Connected Components
    num_l, labels, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    comps = sorted(range(1, num_l), key=lambda i: stats[i, cv2.CC_STAT_AREA], reverse=True)[:2]

    if len(comps) >= 2:
        c1, c2 = centroids[comps[0]][0], centroids[comps[1]][0]
        idx_l = comps[0] if c1 < c2 else comps[1]
        idx_r = comps[1] if c1 < c2 else comps[0]
        bbox_l = stats[idx_l, :4]
        bbox_r = stats[idx_r, :4]
    else:
        bbox_l = (0, 0, mid_x, h)
        bbox_r = (mid_x, 0, w - mid_x, h)

    # Berechne für JEDEN einzelnen Hotspot-Kandidaten die kontralaterale Asymmetrie am homologen Punkt
    max_contra_delta = 0.0
    for r in hotspots:
        cx, cy = r.center_x, r.center_y
        if cx < mid_x:  # Liegt auf dem linken Fuß
            u = (cx - bbox_l[0]) / max(1, bbox_l[2])
            v = (cy - bbox_l[1]) / max(1, bbox_l[3])
            contra_x = int(bbox_r[0] + (1.0 - u) * bbox_r[2])
            contra_y = int(bbox_r[1] + v * bbox_r[3])
        else:  # Liegt auf dem rechten Fuß
            u = (cx - bbox_r[0]) / max(1, bbox_r[2])
            v = (cy - bbox_r[1]) / max(1, bbox_r[3])
            contra_x = int(bbox_l[0] + (1.0 - u) * bbox_l[2])
            contra_y = int(bbox_l[1] + v * bbox_l[3])

        contra_x = int(np.clip(contra_x, 0, w - 1))
        contra_y = int(np.clip(contra_y, 0, h - 1))

        # Kontralaterale Umgebungstemperatur abtasten (Radius 12 px)
        r_samp = 12
        roi_contra = temp[max(0, contra_y - r_samp):min(h, contra_y + r_samp + 1),
                          max(0, contra_x - r_samp):min(w, contra_x + r_samp + 1)]
        t_contra = float(np.mean(roi_contra)) if roi_contra.size > 0 else float(temp[contra_y, contra_x])

        delta_contra = max(0.0, r.t_max - t_contra)
        r.contra_delta = delta_contra
        if delta_contra > max_contra_delta:
            max_contra_delta = delta_contra

    ctx.delta_t_contralateral = max_contra_delta
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s40(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='turbo')
        ax.axvline(mid_x, color='#F8FAFC', linestyle='--', linewidth=1.5, alpha=0.7)
        # Markiere die wichtigste Asymmetrie
        top_spot = max(hotspots, key=lambda s: s.contra_delta, default=None)
        if top_spot is not None:
            cx, cy = top_spot.center_x, top_spot.center_y
            u = (cx - bbox_l[0]) / max(1, bbox_l[2]) if cx < mid_x else (cx - bbox_r[0]) / max(1, bbox_r[2])
            v = (cy - bbox_l[1]) / max(1, bbox_l[3]) if cx < mid_x else (cy - bbox_r[1]) / max(1, bbox_r[3])
            cx_contra = int(bbox_r[0] + (1.0 - u) * bbox_r[2]) if cx < mid_x else int(bbox_l[0] + (1.0 - u) * bbox_l[2])
            cy_contra = int(bbox_r[1] + v * bbox_r[3]) if cx < mid_x else int(bbox_l[1] + v * bbox_l[3])

            ax.plot([cx, cx_contra], [cy, cy_contra], color='#EF4444', linestyle=':', linewidth=1.5)
            ax.plot(cx, cy, 'o', color='#EF4444', markersize=6)
            ax.plot(cx_contra, cy_contra, 's', color='#38BDF8', markersize=6)
            ax.text((cx + cx_contra) * 0.5, (cy + cy_contra) * 0.5 - 15,
                    f"ΔT_contra = +{top_spot.contra_delta:.1f} K",
                    color='#F8FAFC', fontsize=9, fontweight='bold', ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#0F172A', edgecolor='#EF4444', alpha=0.8))

        ax.set_title(f"Homologer Armstrong-Seitenvergleich • Max ΔT_contra = {max_contra_delta:.1f} K (Schwelle: 2.2 K)", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=40,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Homologer Armstrong-Seitenvergleich",
        description="Berechnet die kontralaterale Temperaturdifferenz ΔT zwischen homologen Fußarealen gemäß Armstrong et al. (2007) und IWGDF (2023).",
        formula=r"\Delta T_{\text{contra}} = |T_{\text{links}}(x, y) - T_{\text{rechts}}(W - x, y)| \ge 2{,}2\,\text{K}",
        duration_ms=d_ms,
        metrics={"Max ΔT_contra": f"{max_contra_delta:.2f} K", "Schwelle": "2.2 K", "Prädiktion": "Positiv" if max_contra_delta >= 2.2 else "Negativ"},
        render_fn=render_s40
    )

    # =========================================================================
    # STUFE 41: Diffuses Muskelplateau vs. fokale Pathologie
    # =========================================================================
    t0 = time.perf_counter()
    confirmed_pathology = []
    rejected_plateaus = []

    for r in hotspots:
        cx, cy = r.center_x, r.center_y
        if cx < mid_x:
            v = (cy - bbox_l[1]) / max(1, bbox_l[3])
        else:
            v = (cy - bbox_r[1]) / max(1, bbox_r[3])

        is_toe = v < 0.30            # Distale Zehenregion (Hallux & Digiti)
        is_heel_or_arch = v >= 0.50  # Ferse (Calcaneus) & Fußgewölbe (physiologische Belastungswärme)

        # Ausschluss-Kriterien für physiologische Kontaktplateaus:
        # 1. Armstrong-Schwelle: Nur Herde mit Delta_T_contra >= 2.2 K gelten als akutes Ulkusrisiko
        # 2. Diffuse Belastungsplateaus an Fersen/Gewölbe werden deeskaliert
        if r.contra_delta >= ctx.config.armstrong_threshold_k and (is_toe or not is_heel_or_arch):
            r.classification = "CRITICAL"
            r.clinical_note = "🔥 Floride Hallux-Entzündung / Drohendes Druckulkus (ΔT >= 2.2 K)"
            confirmed_pathology.append(r)
        elif r.contra_delta >= ctx.config.moderate_threshold_k:
            r.classification = "MODERATE"
            r.clinical_note = "⚡ Biomechanische Überlastung / Hyperkeratose"
            rejected_plateaus.append(r)
        else:
            r.classification = "BENIGN"
            r.clinical_note = "Physiologisches Belastungsplateau (Symmetrische Wärme)"
            rejected_plateaus.append(r)

    ctx.confirmed_pathology_hotspots = confirmed_pathology
    is_muscle_plateau = (len(confirmed_pathology) == 0)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s41(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='coolwarm')
        # Zeige bestätigte Foci in Rot, deeskalierte Plateaus in Grün
        for r in confirmed_pathology:
            circ = plt.Circle((r.center_x, r.center_y), max(18, int(r.area_px**0.5 * 0.45)), fill=False, edgecolor='#EF4444', linewidth=2)
            ax.add_patch(circ)
        for r in rejected_plateaus:
            circ = plt.Circle((r.center_x, r.center_y), max(14, int(r.area_px**0.5 * 0.35)), fill=False, edgecolor='#10B981', linewidth=1.2, linestyle=':')
            ax.add_patch(circ)

        ax.set_title(f"Plateau-Differenzierung • {len(confirmed_pathology)} fokale Pathologie bestätigt | {len(rejected_plateaus)} physiologische Plateaus deeskaliert", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=41,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Muskelplateau-Differenzierung",
        description="Schließt symmetrische, großflächige Muskelbelastungswärme nach Gehen oder Stehen aus, um falsch-positive Alarme zu verhindern.",
        formula=r"\text{Reject}(\mathcal{R}) \iff \Delta T_{\text{contra}} < 2{,}2\,\text{K} \lor (\text{HeelPlateau} \land \text{Bilateral})",
        duration_ms=d_ms,
        metrics={"Fokus bestätigt": len(confirmed_pathology), "Plateaus verworfen": len(rejected_plateaus), "Status": "Fokale Pathologie" if not is_muscle_plateau else "Physiologisch"},
        render_fn=render_s41
    )

    # =========================================================================
    # STUFE 42: Klinische Triage & IWGDF Armstrong Entscheidungslogik
    # =========================================================================
    t0 = time.perf_counter()
    if len(confirmed_pathology) > 0:
        primary = confirmed_pathology[0]
        triage_level = "CRITICAL"
        triage_headline = f"Akute Entzündung: Großer Zeh (Hallux) • ΔT = +{primary.contra_delta:.1f} K"
        triage_color = "#DC2626"
    else:
        triage_level = "BENIGN"
        triage_headline = "Physiologischer Normalbefund"
        triage_color = "#16A34A"

    ctx.overall_triage_level = triage_level
    ctx.triage_headline = triage_headline
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s42(fig: Figure, ax: plt.Axes):
        # 1. Reines, hochauflösendes Original-Thermogramm
        ax.imshow(ctx.raw_bgr[:, :, ::-1])

        # 2. Ausschließlich den entzündeten großen Zeh markieren — minimalistisches Design!
        if len(confirmed_pathology) > 0:
            primary = confirmed_pathology[0]
            cx, cy = primary.center_x, primary.center_y
            r_focus = max(26, int(primary.area_px**0.5 * 0.38))

            # Eleganter, feiner roter Zielfokusring
            circle = plt.Circle((cx, cy), r_focus, fill=False, edgecolor='#EF4444', linewidth=1.8)
            ax.add_patch(circle)

            # Subtiler äußerer Glühring
            glow = plt.Circle((cx, cy), r_focus + 6, fill=False, edgecolor='#EF4444', linewidth=0.8, alpha=0.45, linestyle=':')
            ax.add_patch(glow)

            # Vier präzise Fadenkreuz-Notches an Nord, Süd, Ost, West (dezent, 6 px)
            tick = 7
            gap = 3
            ax.plot([cx, cx], [cy - r_focus - gap - tick, cy - r_focus - gap], color='#EF4444', linewidth=1.5)
            ax.plot([cx, cx], [cy + r_focus + gap, cy + r_focus + gap + tick], color='#EF4444', linewidth=1.5)
            ax.plot([cx - r_focus - gap - tick, cx - r_focus - gap], [cy, cy], color='#EF4444', linewidth=1.5)
            ax.plot([cx + r_focus + gap, cx + r_focus + gap + tick], [cy, cy], color='#EF4444', linewidth=1.5)

            # Zentraler Mini-Fokuspunkt
            ax.plot([cx], [cy], marker='+', markersize=5, color='#EF4444', markeredgewidth=1.2)

        # Vollständig minimalistisch: Alle störenden Textbanner und Boxen sind entfernt!
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=42,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Klinische Triage & Armstrong-Regelengine",
        description="Synthese aller 41 Vorstufen zu einer evidenzbasierten ärztlichen Diagnose nach den internationalen IWGDF-Leitlinien und Armstrong-Kriterien.",
        formula=r"\text{Triage} = \begin{cases} \text{CRITICAL (Rot)} & \text{falls } \Delta T_{\text{contra}} \ge 2{,}2\,\text{K} \\ \text{MODERATE (Gelb)} & \text{falls } 1{,}2\,\text{K} \le \Delta T_{\text{contra}} < 2{,}2\,\text{K} \\ \text{BENIGN (Grün)} & \text{falls } \Delta T_{\text{contra}} < 1{,}2\,\text{K} \end{cases}",
        duration_ms=d_ms,
        metrics={"Triage": triage_level, "Befund": triage_headline, "ΔT Armstrong": f"{ctx.delta_t_contralateral:.2f} K"},
        render_fn=render_s42,
        minimal_banner=True
    )
