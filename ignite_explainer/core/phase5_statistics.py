# -*- coding: utf-8 -*-
"""phase5_statistics.py — Phase V: Statistische Schwellwertbildung & Hampel-MAD (Stufen 25–30).

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Stufen:
- Stufe 25: 256-Bin Histogramm über biologischem Gewebe
- Stufe 26: Exakter O(N) Median über kumulative Histogramm-Summe
- Stufe 27: Hampel-MAD Skalenschätzung (sigma = 1.4826 * MAD)
- Stufe 28: Biologischer Mindesttemperaturboden T_floor
- Stufe 29: Vektorisierter Schwellwertvergleich (tau = Median + k * sigma)
- Stufe 30: Geodätische Dual-Threshold Hysterese-Rekonstruktion
"""

import time
import numpy as np
import cv2
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .context import PipelineContext
from .exporter import StepExporter


def execute_phase5(ctx: PipelineContext, exporter: StepExporter):
    """Führt die Stufen 25 bis 30 der Phase V aus und exportiert alle Zwischenergebnisse."""
    phase_num = 5
    phase_name = "Phase V: Statistical Outlier Profiling & Thresholding"
    tophat = ctx.tophat_diff
    mask = ctx.eroded_body_mask
    temp = ctx.temp_3d_corrected if ctx.temp_3d_corrected is not None else ctx.temp_celsius
    h, w = tophat.shape

    # Nur Pixel innerhalb des Gewebes
    tissue_tophat_vals = tophat[mask]
    tissue_temp_vals = temp[mask]
    n_tissue = len(tissue_tophat_vals)

    # =========================================================================
    # STUFE 25: 256-Bin Histogramm über biologischem Gewebe
    # =========================================================================
    t0 = time.perf_counter()
    hist, bin_edges = np.histogram(tissue_tophat_vals, bins=256, range=(0, 256))
    ctx.tissue_histogram = hist
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s25(fig: Figure, ax: plt.Axes):
        ax.bar(range(60), hist[:60], color='#0284C7', edgecolor='#0369A1', width=0.8)
        ax.set_title(f"256-Bin Gewebe-Histogramm • N = {n_tissue:,} Pixel analysiert", color='#E2E8F0', fontsize=11)
        ax.set_xlabel("Top-Hat Residuum (Intensitätsstufen)", color='#94A3B8', fontsize=10)
        ax.set_ylabel("Häufigkeit", color='#94A3B8', fontsize=10)
        ax.tick_params(colors='#94A3B8')
        ax.grid(True, linestyle=':', alpha=0.3, color='#475569')

    exporter.export_step(
        ctx=ctx,
        step_number=25,
        phase_number=phase_num,
        phase_name=phase_name,
        name="256-Bin Gewebe-Histogramm",
        description="Erfasst die diskrete Verteilung aller Top-Hat Überhöhungen ausschließlich über physiologischem Gewebe (ohne Hintergrundverzerrung).",
        formula=r"h(v) = \sum_{(x,y) \in \mathcal{M}} \delta(\text{WTH}(x,y) - v), \quad v \in [0, 255]",
        duration_ms=d_ms,
        metrics={"Gewebe-Pixel": f"{n_tissue:,}", "Bins": 256, "Max Frequenz": int(np.max(hist))},
        render_fn=render_s25
    )

    # =========================================================================
    # STUFE 26: Exakter O(N) Median über kumulative Histogramm-Summe
    # =========================================================================
    t0 = time.perf_counter()
    cum_hist = np.cumsum(hist)
    half_n = n_tissue / 2.0
    med_val = int(np.searchsorted(cum_hist, half_n))
    ctx.tissue_median = float(med_val)
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s26(fig: Figure, ax: plt.Axes):
        ax.plot(range(60), cum_hist[:60] / n_tissue * 100.0, color='#38BDF8', linewidth=2, label='Kumulative Summe')
        ax.axhline(50.0, color='#F59E0B', linestyle='--', label='50% Quantil (Median)')
        ax.axvline(med_val, color='#10B981', linestyle='-', linewidth=2, label=f'Median = {med_val}')
        ax.set_title(f"Deterministischer O(N) Median = {med_val} • Berechnet via CDF-Inversion", color='#E2E8F0', fontsize=11)
        ax.set_xlabel("Top-Hat Intensität", color='#94A3B8')
        ax.set_ylabel("Kumulativer Anteil (%)", color='#94A3B8')
        ax.legend(facecolor='#1E293B', edgecolor='#475569', labelcolor='#F8FAFC')
        ax.tick_params(colors='#94A3B8')
        ax.grid(True, linestyle=':', alpha=0.3, color='#475569')

    exporter.export_step(
        ctx=ctx,
        step_number=26,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Exakter O(N) Median",
        description="Ermittelt das 50%-Quantil in O(N)-Zeit über die kumulative Verteilungsfunktion — immun gegen einzelne extreme Entzündungsherde.",
        formula=r"\text{Median} = \min \left\{ v \ \middle|\ \sum_{i=0}^v h(i) \ge \frac{N}{2} \right\}",
        duration_ms=d_ms,
        metrics={"Median": med_val, "Laufzeit": f"{d_ms:.3f} ms", "Komplexität": "O(N) deterministisch"},
        render_fn=render_s26
    )

    # =========================================================================
    # STUFE 27: Hampel-MAD Skalenschätzung (sigma = 1.4826 * MAD)
    # =========================================================================
    t0 = time.perf_counter()
    # Absolute Abweichungen zum Median
    abs_dev = np.abs(tissue_tophat_vals.astype(float) - med_val)
    # MAD = Median der absoluten Abweichungen
    mad = float(np.median(abs_dev))
    # Gauß-konsistenter Skalenschätzer sigma = 1.4826 * MAD
    sigma = 1.4826 * mad
    ctx.tissue_mad = mad
    ctx.tissue_sigma = sigma
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s27(fig: Figure, ax: plt.Axes):
        ax.hist(abs_dev, bins=50, range=(0, 50), color='#6366F1', edgecolor='#4338CA', alpha=0.8)
        ax.axvline(mad, color='#F59E0B', linestyle='--', linewidth=2, label=f'MAD = {mad:.2f}')
        ax.axvline(sigma, color='#EC4899', linestyle='-', linewidth=2, label=f'σ̂ = 1.4826·MAD = {sigma:.2f}')
        ax.set_title(f"Hampel-MAD Streuung • MAD: {mad:.2f} • Robuste Standardabweichung σ̂: {sigma:.2f}", color='#E2E8F0', fontsize=11)
        ax.set_xlabel("Absolute Abweichung |x - Median|", color='#94A3B8')
        ax.set_ylabel("Häufigkeit", color='#94A3B8')
        ax.legend(facecolor='#1E293B', edgecolor='#475569', labelcolor='#F8FAFC')
        ax.tick_params(colors='#94A3B8')
        ax.grid(True, linestyle=':', alpha=0.3, color='#475569')

    exporter.export_step(
        ctx=ctx,
        step_number=27,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Hampel-MAD Skalenschätzung",
        description="Berechnet die Median Absolute Deviation (MAD): Verhindert Maskierungsfehler (Swamping & Masking) durch floride Entzündungsareale.",
        formula=r"\text{MAD} = \text{median}(|x_i - \text{Median}|), \quad \hat{\sigma} = 1{,}4826 \cdot \text{MAD}",
        duration_ms=d_ms,
        metrics={"MAD": f"{mad:.2f}", "Sigma σ̂": f"{sigma:.2f}", "Konsistenzfaktor": "1.4826"},
        render_fn=render_s27
    )

    # =========================================================================
    # STUFE 28: Biologischer Mindesttemperaturboden T_floor
    # =========================================================================
    t0 = time.perf_counter()
    # Nur Regionen über dem biologischen Mindesttemperaturboden (20 °C) betrachten
    t_floor = ctx.config.min_temp_floor  # 20.0 °C
    valid_floor_mask = (temp >= t_floor) & mask
    cold_artifacts = int(np.sum(mask & (~valid_floor_mask)))
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s28(fig: Figure, ax: plt.Axes):
        im = ax.imshow(temp, cmap='coolwarm', vmin=15, vmax=35)
        ax.set_title(f"Biologischer Temperaturboden T_floor = {t_floor:.1f} °C • {cold_artifacts} kalte Randpixel ignoriert", color='#E2E8F0', fontsize=11)
        ax.axis('off')
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("Temperatur (°C)", color='#94A3B8', fontsize=10)
        cbar.ax.tick_params(colors='#94A3B8')

    exporter.export_step(
        ctx=ctx,
        step_number=28,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Biologischer Temperaturboden",
        description="Schließt kalte Randzonen und ischämisch abgestorbene Randartefakte unterhalb von 20 °C vor der Schwellwertbildung aus.",
        formula=r"\mathcal{M}_{\text{valid}} = \mathcal{M}_{\text{tissue}} \cap \{ (x,y) \mid T(x,y) \ge T_{\text{floor}} \}, \quad T_{\text{floor}} = 20{,}0\,^\circ\text{C}",
        duration_ms=d_ms,
        metrics={"T_Floor": f"{t_floor:.1f} °C", "Ausgeschlossen": cold_artifacts, "Status": "Validiert"},
        render_fn=render_s28
    )

    # =========================================================================
    # STUFE 29: Vektorisierter Schwellwertvergleich (tau = Median + k * sigma)
    # =========================================================================
    t0 = time.perf_counter()
    k = ctx.config.k_factor  # 3.0
    tau = med_val + k * sigma
    ctx.outlier_threshold_tau = tau

    # Schwellwertmaskierung: Hotspot-Kandidaten (müssen mindestens Gewebemedian erreichen)
    t_median_tissue = float(np.median(tissue_temp_vals)) if len(tissue_temp_vals) > 0 else 30.0
    raw_outliers = (tophat >= tau) & valid_floor_mask & (temp >= t_median_tissue)
    ctx.outlier_mask = raw_outliers
    outlier_count = int(np.sum(raw_outliers))
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s29(fig: Figure, ax: plt.Axes):
        ax.imshow(tophat, cmap='gray')
        # Zeige Outlier in leuchtendem Gelb/Rot
        out_vis = np.zeros((h, w, 4), dtype=np.float32)
        out_vis[raw_outliers] = [1.0, 0.2, 0.0, 0.8]  # Leuchtendes Rotorange
        ax.imshow(out_vis)
        ax.set_title(f"Hampel-Outlier-Schwelle τ = {tau:.1f} (k={k:.1f}) • {outlier_count} Anomaliepixel markiert", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=29,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Vektorisierter Schwellwertvergleich",
        description="Extrahiert statistisch signifikante Hyperthermiepunkte mit k=3.0 (99.7% Konfidenzniveau nach Gauß / Hampel).",
        formula=r"\tau = \text{Median} + k \cdot \hat{\sigma}, \quad \mathcal{A}_{\text{raw}} = \{ (x,y) \mid \text{WTH}(x,y) \ge \tau \}",
        duration_ms=d_ms,
        metrics={"Schwelle τ": f"{tau:.2f}", "k-Faktor": f"{k:.1f}", "Anomaliepixel": outlier_count},
        render_fn=render_s29
    )

    # =========================================================================
    # STUFE 30: Geodätische Dual-Threshold Hysterese-Rekonstruktion
    # =========================================================================
    t0 = time.perf_counter()
    # Dual-Threshold: tau_high = Median + 3.0*sigma, tau_low = Median + 1.5*sigma
    tau_low = med_val + 1.5 * sigma
    low_mask = (tophat >= tau_low) & valid_floor_mask & (temp >= t_median_tissue)

    # Hysterese: Rekonstruiere alle Pixel von tau_low, die mit einem tau_high-Kern verbunden sind
    num_l, labels_l = cv2.connectedComponents(low_mask.astype(np.uint8))
    reconstructed = np.zeros_like(raw_outliers)

    for lab in range(1, num_l):
        comp = (labels_l == lab)
        if np.any(comp & raw_outliers):
            reconstructed[comp] = True

    ctx.outlier_mask = reconstructed
    d_ms = (time.perf_counter() - t0) * 1000.0

    def render_s30(fig: Figure, ax: plt.Axes):
        ax.imshow(temp, cmap='inferno')
        overlay = np.zeros((h, w, 4), dtype=np.float32)
        overlay[reconstructed] = [0.0, 1.0, 0.4, 0.6]  # Grün für Hysterese
        overlay[raw_outliers] = [1.0, 0.0, 0.0, 0.8]   # Rot für starken Kern
        ax.imshow(overlay)
        ax.set_title(f"Hysterese-Rekonstruktion • Rot: Kerne (τ={tau:.1f}) | Grün: Randzonen (τ={tau_low:.1f})", color='#E2E8F0', fontsize=11)
        ax.axis('off')

    exporter.export_step(
        ctx=ctx,
        step_number=30,
        phase_number=phase_num,
        phase_name=phase_name,
        name="Geodätische Hysterese-Rekonstruktion",
        description="Vollständige Konturerfassung durch morphologische Hysterese: Verbindet starke Entzündungskerne mit ihren subklinischen Randzonen.",
        formula=r"\mathcal{A}_{\text{hyst}} = \mathcal{R}_{\mathcal{A}_{\text{low}}}(\mathcal{A}_{\text{high}}), \quad \tau_{\text{low}} = \text{Med} + 1{,}5\hat{\sigma}",
        duration_ms=d_ms,
        metrics={"Tau High": f"{tau:.2f}", "Tau Low": f"{tau_low:.2f}", "Pixel nach Hysterese": int(np.sum(reconstructed))},
        render_fn=render_s30
    )
