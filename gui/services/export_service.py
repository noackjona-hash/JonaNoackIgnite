# -*- coding: utf-8 -*-
"""gui/services/export_service.py – Clinical Report Generation & Audit Logging for IGNITE."""

from __future__ import annotations
import os
import io
import base64
import datetime
import logging
from typing import Any, Optional
import cv2
import numpy as np
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

import config
from audit_log import write_audit_entry
from utils import pixel_to_celsius, pseudonymize_patient


class ExportService:
    """Service-Klasse zum Generieren von klinischen PDF- und HTML-Befundberichten und Protokollen."""

    @staticmethod
    def _cv_to_reportlab_image(img_array: np.ndarray, target_w_mm: float = 88.0, is_rgb: bool = False) -> Optional[RLImage]:
        """Konvertiert eine OpenCV Bildmatrix in ein ReportLab Flowable Image."""
        try:
            if is_rgb:
                bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif len(img_array.shape) == 2:
                bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            else:
                bgr = img_array

            success, buffer = cv2.imencode(".png", bgr)
            if not success:
                return None
            img_io = io.BytesIO(buffer.tobytes())
            h, w = img_array.shape[:2]
            aspect = h / max(1, w)
            w_pt = target_w_mm * mm
            h_pt = w_pt * aspect
            return RLImage(img_io, width=w_pt, height=h_pt)
        except Exception as e:
            logging.debug(f"Fehler bei ReportLab Image Konvertierung: {e}")
            return None

    @staticmethod
    def _cv_to_base64(img_array: np.ndarray, is_rgb: bool = False) -> str:
        """Konvertiert eine Bildmatrix in einen Base64-Data-URI String."""
        try:
            if is_rgb:
                bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif len(img_array.shape) == 2:
                bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            else:
                bgr = img_array

            success, buffer = cv2.imencode(".png", bgr)
            if not success:
                return ""
            encoded = base64.b64encode(buffer).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
        except Exception as e:
            logging.debug(f"Fehler bei Base64-Konvertierung: {e}")
            return ""

    @classmethod
    def generate_html_report(
        cls,
        analysis_result: dict[str, Any],
        record_id: str = "Unbekannt",
        operator: str = "Jugend forscht 2026",
        notes: str = "",
        output_filepath: Optional[str] = None
    ) -> str:
        """Erzeugt einen eigenständigen, modernen High-Contrast HTML-Befundbericht."""
        image_path = analysis_result.get("image_path", "Unbekannt")
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        if not output_filepath:
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            output_filepath = os.path.join(config.OUTPUT_DIR, f"report_{base_name}.html")

        # Sicherstellen, dass die Kennung pseudonymisiert ist
        if record_id and not record_id.startswith("ANON-") and record_id != "Unbekannt":
            display_record_id = pseudonymize_patient(record_id)
        else:
            display_record_id = record_id

        now_str = datetime.datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")
        backend = analysis_result.get("backend", "Python CPU")
        analysis_mode = analysis_result.get("analysis_mode", "Klinische Allgemeinanalyse")

        t_min = analysis_result.get("t_min_c", 20.0)
        t_max = analysis_result.get("t_max_c", 40.0)
        mean_px = analysis_result.get("mean_pixel", 0.0)
        std_px = analysis_result.get("std_pixel", 0.0)
        max_px = analysis_result.get("max_pixel", 0.0)
        hotspot_px = analysis_result.get("hotspot_pixel_count", 0)
        body_px = analysis_result.get("body_pixel_count", 0)
        hotspot_ratio = analysis_result.get("hotspot_ratio", 0.0)

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        max_c = pixel_to_celsius(max_px, t_min, t_max)

        asym = analysis_result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)
        is_asymmetric = asym.get("is_asymmetric", False)

        tsi = analysis_result.get("tsi_results", {})
        tsi_score = tsi.get("score", 0.0)
        tsi_tier_name = tsi.get("tier_name", "Stufe 0: Physiologischer Normalbefund")
        tsi_tier_desc = tsi.get("tier_desc", "Keine Auffälligkeiten.")
        tsi_color = tsi.get("color", "#16A34A")

        grads = analysis_result.get("gradient_results", {})
        max_grad = grads.get("max_gradient", 0.0)

        pca = analysis_result.get("pca_results")
        pca_l_ang = pca.get("left", {}).get("angle_deg", 0.0) if pca else 0.0
        pca_r_ang = pca.get("right", {}).get("angle_deg", 0.0) if pca else 0.0

        # Base64-Bilder einbetten
        b64_orig = cls._cv_to_base64(analysis_result.get("calibrated_original", np.zeros((10, 10), dtype=np.uint8)))
        b64_mask = cls._cv_to_base64(analysis_result.get("body_mask", np.zeros((10, 10), dtype=np.uint8)))
        b64_diff = cls._cv_to_base64(analysis_result.get("heat_diff", np.zeros((10, 10), dtype=np.uint8)))
        b64_overlay = cls._cv_to_base64(analysis_result.get("overlay_rgb", np.zeros((10, 10, 3), dtype=np.uint8)), is_rgb=True)

        # Status & Badges
        if analysis_mode == "Podologische Symmetrieanalyse":
            if is_asymmetric:
                status_text = "Pathologische Asymmetrie (ΔT > 2.2 °C)"
                status_color = "#DC2626"
                status_bg = "#FEF2F2"
            else:
                status_text = "Physiologisch symmetrisch (Normalbefund)"
                status_color = "#16A34A"
                status_bg = "#F0FDF4"
        else:
            if hotspot_px >= 150:
                status_text = "Klinisch auffällige Hyperthermie-Hotspots"
                status_color = "#DC2626"
                status_bg = "#FEF2F2"
            elif hotspot_px > 0:
                status_text = "Geringfügige thermische Abweichung"
                status_color = "#D97706"
                status_bg = "#FFFBEB"
            else:
                status_text = "Unauffällig / Keine Entzündungsherde"
                status_color = "#16A34A"
                status_bg = "#F0FDF4"

        # Zonen-Tabelle HTML
        zonal = analysis_result.get("zonal_stats", {})
        zonal_html = ""
        if zonal.get("left", {}).get("exists") and zonal.get("right", {}).get("exists"):
            l_fore_c = pixel_to_celsius(zonal["left"]["fore"], t_min, t_max)
            r_fore_c = pixel_to_celsius(zonal["right"]["fore"], t_min, t_max)
            d_fore_c = abs(l_fore_c - r_fore_c)

            l_mid_c = pixel_to_celsius(zonal["left"]["mid"], t_min, t_max)
            r_mid_c = pixel_to_celsius(zonal["right"]["mid"], t_min, t_max)
            d_mid_c = abs(l_mid_c - r_mid_c)

            l_heel_c = pixel_to_celsius(zonal["left"]["heel"], t_min, t_max)
            r_heel_c = pixel_to_celsius(zonal["right"]["heel"], t_min, t_max)
            d_heel_c = abs(l_heel_c - r_heel_c)

            zonal_html = f"""
            <div class="card" style="margin-top: 20px;">
                <div class="card-title">Podologischer 3-Zonen-Symmetrievergleich</div>
                <table>
                    <thead>
                        <tr>
                            <th>Anatomische Zone</th>
                            <th>Linker Fuß (L)</th>
                            <th>Rechter Fuß (R)</th>
                            <th>Differenz (ΔT)</th>
                            <th>Bewertung</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><strong>Vorfuß (Ballen / Zehen)</strong></td>
                            <td>{l_fore_c:.1f} °C</td>
                            <td>{r_fore_c:.1f} °C</td>
                            <td><strong style="color: {'#DC2626' if d_fore_c > 2.2 else '#0F172A'};">{d_fore_c:.2f} °C</strong></td>
                            <td><span class="chip {'chip-danger' if d_fore_c > 2.2 else 'chip-success'}">{'Asymmetrie' if d_fore_c > 2.2 else 'Symmetrisch'}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Mittelfuß (Längsgewölbe)</strong></td>
                            <td>{l_mid_c:.1f} °C</td>
                            <td>{r_mid_c:.1f} °C</td>
                            <td><strong style="color: {'#DC2626' if d_mid_c > 2.2 else '#0F172A'};">{d_mid_c:.2f} °C</strong></td>
                            <td><span class="chip {'chip-danger' if d_mid_c > 2.2 else 'chip-success'}">{'Asymmetrie' if d_mid_c > 2.2 else 'Symmetrisch'}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Ferse (Rückfuß)</strong></td>
                            <td>{l_heel_c:.1f} °C</td>
                            <td>{r_heel_c:.1f} °C</td>
                            <td><strong style="color: {'#DC2626' if d_heel_c > 2.2 else '#0F172A'};">{d_heel_c:.2f} °C</strong></td>
                            <td><span class="chip {'chip-danger' if d_heel_c > 2.2 else 'chip-success'}">{'Asymmetrie' if d_heel_c > 2.2 else 'Symmetrisch'}</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>"""

        html_content = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IGNITE Befundbericht – {base_name}</title>
    <style>
        :root {{
            --primary: #0284C7;
            --danger: #DC2626;
            --success: #16A34A;
            --warning: #D97706;
            --bg-app: #F8FAFC;
            --surface: #FFFFFF;
            --surface-variant: #F1F5F9;
            --outline: #E2E8F0;
            --text-main: #0F172A;
            --text-secondary: #475569;
            --text-muted: #64748B;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background-color: var(--bg-app); color: var(--text-main); padding: 32px 16px; line-height: 1.5; }}
        .container {{ max-width: 960px; margin: 0 auto; }}
        
        /* Header */
        .app-header {{
            background: var(--surface);
            border: 1px solid var(--outline);
            border-radius: 8px;
            padding: 20px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .brand-title {{ font-size: 20px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 8px; }}
        .brand-dot {{ width: 8px; height: 8px; border-radius: 4px; background-color: var(--primary); display: inline-block; }}
        .brand-sub {{ font-size: 12px; color: var(--text-muted); margin-top: 2px; }}
        
        /* Cards */
        .card {{
            background: var(--surface);
            border: 1px solid var(--outline);
            border-radius: 8px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* Grids */
        .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
        .meta-item {{ background: var(--surface-variant); padding: 10px 14px; border-radius: 6px; border: 1px solid var(--outline); }}
        .meta-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); font-weight: 600; }}
        .meta-val {{ font-size: 13px; font-weight: 600; color: var(--text-main); margin-top: 2px; }}
        
        /* Chips */
        .chip {{ display: inline-flex; align-items: center; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .chip-success {{ background: #DCFCE7; color: #166534; }}
        .chip-danger {{ background: #FEE2E2; color: #991B1B; }}
        .chip-warning {{ background: #FEF3C7; color: #92400E; }}
        .chip-blue {{ background: #E0F2FE; color: #075985; }}
        
        /* Image Grid */
        .img-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 8px; }}
        .img-card {{ background: var(--surface-variant); border: 1px solid var(--outline); border-radius: 6px; padding: 10px; text-align: center; }}
        .img-card img {{ width: 100%; height: auto; border-radius: 4px; display: block; }}
        .img-caption {{ font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-top: 6px; }}
        
        /* Table */
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
        th, td {{ padding: 10px 14px; text-align: left; font-size: 12px; border-bottom: 1px solid var(--outline); }}
        th {{ background-color: var(--surface-variant); font-weight: 600; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; }}
        tr:last-child td {{ border-bottom: none; }}
        
        /* Footer */
        .footer {{ text-align: center; font-size: 11px; color: var(--text-muted); padding: 20px 0 8px; }}
        
        @media print {{
            body {{ padding: 0; background: #FFF; }}
            .card, .app-header {{ box-shadow: none; border-color: #CCC; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Top App Bar -->
        <div class="app-header">
            <div>
                <div class="brand-title"><span class="brand-dot"></span> IGNITE Medical Imaging Suite</div>
                <div class="brand-sub">Klinischer Thermografie-Befundbericht · Jugend forscht 2026</div>
            </div>
            <div style="text-align: right;">
                <span class="chip chip-blue">{backend}</span>
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">{now_str}</div>
            </div>
        </div>

        <!-- Stammdaten Card -->
        <div class="card">
            <div class="card-title">Untersuchungs- & Datensatzdaten</div>
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Datensatz / Pseudonym-ID</div>
                    <div class="meta-val">{display_record_id}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Dateiname</div>
                    <div class="meta-val">{os.path.basename(image_path)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Untersucher</div>
                    <div class="meta-val">{operator}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Datenschutz-Status</div>
                    <div class="meta-val"><span class="chip chip-success">DSGVO Pseudonymisiert</span></div>
                </div>
            </div>
        </div>

        <!-- Diagnostische Ergebnisse Card -->
        <div class="card">
            <div class="card-title">Quantitative Analyse & Befund</div>
            <div style="background: {status_bg}; border: 1px solid {status_color}40; border-radius: 6px; padding: 14px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: {status_color};">Globales Fazit</div>
                    <div style="font-size: 15px; font-weight: 700; color: {status_color}; margin-top: 2px;">{status_text}</div>
                </div>
                <span class="chip" style="background: {status_color}; color: #FFF; font-size: 11px; padding: 4px 10px;">
                    ΔT = {delta_t:.1f} °C
                </span>
            </div>

            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Mittlere Temperatur (Gewebe)</div>
                    <div class="meta-val">{mean_c:.2f} °C</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Standardabweichung (σ)</div>
                    <div class="meta-val">±{std_c:.2f} °C</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Maximaltemperatur</div>
                    <div class="meta-val">{max_c:.2f} °C</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Hotspot-Fläche</div>
                    <div class="meta-val">{hotspot_px:,} px ({hotspot_ratio:.2f} %)</div>
                </div>
            </div>
        </div>

        <!-- Thermal Severity Index & Risiko-Klassifikation -->
        <div class="card">
            <div class="card-title">Klinischer Thermal Severity Index (TSI) & IWGDF-Risiko</div>
            <div style="display: flex; gap: 16px; align-items: center; background: var(--surface-variant); padding: 14px 18px; border-radius: 6px; border: 1px solid var(--outline);">
                <div style="font-size: 26px; font-weight: 800; font-family: monospace; color: {tsi_color};">
                    {tsi_score:.1f} <span style="font-size: 13px; font-weight: 500; color: var(--text-muted);">/ 10</span>
                </div>
                <div style="flex: 1;">
                    <div style="font-size: 13px; font-weight: 700; color: {tsi_color};">{tsi_tier_name}</div>
                    <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">{tsi_tier_desc}</div>
                </div>
                <div style="text-align: right; font-size: 11px; color: var(--text-muted);">
                    <div>Therm. Gradient: <strong>{max_grad:.1f}</strong></div>
                    <div>PCA-Achsen: <strong>L {pca_l_ang:+.1f}° · R {pca_r_ang:+.1f}°</strong></div>
                </div>
            </div>
        </div>

        {zonal_html}

        <!-- 4-Pipeline Stufen Grid -->
        <div class="card">
            <div class="card-title">Visuelle 4-Stufen-Pipeline</div>
            <div class="img-grid">
                <div class="img-card">
                    <img src="{b64_orig}" alt="1. Original">
                    <div class="img-caption">1. Original-Wärmebild</div>
                </div>
                <div class="img-card">
                    <img src="{b64_mask}" alt="2. Körper-Maske">
                    <div class="img-caption">2. Gewebe-Segmentierung</div>
                </div>
                <div class="img-card">
                    <img src="{b64_diff}" alt="3. Lokale Hitze-Differenz">
                    <div class="img-caption">3. Morphologische Top-Hat Differenz</div>
                </div>
                <div class="img-card">
                    <img src="{b64_overlay}" alt="4. Hotspot-Overlay">
                    <div class="img-caption">4. Entzündungs-Hotspots & Annotation</div>
                </div>
            </div>
        </div>

        <div class="footer">
            IGNITE Medical Imaging Suite · Entwickelt von Jona Noack für Jugend forscht 2026 (Fachgebiet Arbeitswelt).<br>
            <em>Hinweis: Forschungsprototyp – Kein zertifiziertes EU-MDR Medizinprodukt.</em>
        </div>
    </div>
</body>
</html>"""

        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Audit-Log Eintrag schreiben
        try:
            write_audit_entry({
                "Zeitstempel": datetime.datetime.now().isoformat(),
                "Patienten-ID": display_record_id,
                "Analysemodus": analysis_mode,
                "Bilddatei": os.path.basename(image_path),
                "sigma_k": analysis_result.get("params", {}).get("sigma_k", 3.0),
                "tophat_factor": analysis_result.get("params", {}).get("tophat_factor", 0.05),
                "T_min_C": t_min,
                "T_max_C": t_max,
                "Hotspot_Pixel": hotspot_px,
                "Max_Temp_C": round(max_c, 2),
                "Symmetrie_Delta": round(delta_t, 2),
                "Operator": operator
            })
        except Exception as e:
            logging.error(f"Audit log write failed: {e}")

        return output_filepath

    @classmethod
    def generate_batch_summary_html(
        cls,
        results_list: list[dict[str, Any]],
        output_dir: str
    ) -> str:
        """Erzeugt einen Gesamtbericht über alle in einem Batch verarbeiteten Wärmebilder."""
        summary_path = os.path.join(output_dir, "batch_summary_report.html")
        now_str = datetime.datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")

        rows = ""
        for item in results_list:
            fname = os.path.basename(item.get("filepath", ""))
            hotspot_px = item.get("hotspot_count", 0)
            delta_t = item.get("delta_t_c", 0.0)
            status_text = item.get("status_text", "Unauffällig")
            is_warn = item.get("is_warning", False)
            report_name = item.get("report_filename", "")

            badge_class = "chip-danger" if is_warn else "chip-success"
            rows += f"""
            <tr>
                <td><strong>{fname}</strong></td>
                <td><strong style="color: {'#DC2626' if hotspot_px > 0 else '#16A34A'};">{hotspot_px:,} px</strong></td>
                <td>{delta_t:.2f} °C</td>
                <td><span class="chip {badge_class}">{status_text}</span></td>
                <td><a href="{report_name}" style="color: #0284C7; text-decoration: none; font-weight: 600;">Bericht öffnen &rarr;</a></td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE Stapelverarbeitungs-Übersicht</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #F8FAFC; color: #0F172A; padding: 32px 16px; }}
        .container {{ max-width: 960px; margin: 0 auto; background: #FFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 16px; margin-bottom: 20px; }}
        .title {{ font-size: 20px; font-weight: 700; color: #0F172A; }}
        .sub {{ font-size: 12px; color: #64748B; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #E2E8F0; font-size: 12px; }}
        th {{ background: #F1F5F9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        .chip {{ display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .chip-success {{ background: #DCFCE7; color: #166534; }}
        .chip-danger {{ background: #FEE2E2; color: #991B1B; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="title">IGNITE Serienuntersuchungs-Bericht</div>
                <div class="sub">{len(results_list)} Wärmebilder erfolgreich analysiert</div>
            </div>
            <div style="font-size: 12px; color: #64748B;">Erstellt: <strong>{now_str}</strong></div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Wärmebild</th>
                    <th>Hotspots</th>
                    <th>Symmetrie (ΔT)</th>
                    <th>Status</th>
                    <th>Einzelbericht</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(html)

        return summary_path

    @classmethod
    def generate_pdf_report(
        cls,
        analysis_result: dict[str, Any],
        record_id: str = "Unbekannt",
        operator: str = "Jugend forscht 2026",
        notes: str = "",
        output_filepath: Optional[str] = None
    ) -> str:
        """Erzeugt einen druckreifen, hochauflösenden A4-Klinikbefundbericht als PDF mit ReportLab."""
        image_path = analysis_result.get("image_path", "Unbekannt")
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        if not output_filepath or not output_filepath.lower().endswith(".pdf"):
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            output_filepath = os.path.join(config.OUTPUT_DIR, f"report_{base_name}.pdf")

        if record_id and not record_id.startswith("ANON-") and record_id != "Unbekannt":
            display_record_id = pseudonymize_patient(record_id)
        else:
            display_record_id = record_id

        now_str = datetime.datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")
        backend = analysis_result.get("backend", "Python CPU")
        analysis_mode = analysis_result.get("analysis_mode", "Klinische Allgemeinanalyse")

        t_min = analysis_result.get("t_min_c", 20.0)
        t_max = analysis_result.get("t_max_c", 40.0)
        mean_px = analysis_result.get("mean_pixel", 0.0)
        std_px = analysis_result.get("std_pixel", 0.0)
        max_px = analysis_result.get("max_pixel", 0.0)
        min_px = analysis_result.get("min_pixel", 0.0)
        hotspot_px = analysis_result.get("hotspot_pixel_count", 0)
        body_px = analysis_result.get("body_pixel_count", 0)
        hotspot_ratio = analysis_result.get("hotspot_ratio", 0.0)

        mean_c = pixel_to_celsius(mean_px, t_min, t_max)
        std_c = (std_px / 255.0) * (t_max - t_min)
        max_c = pixel_to_celsius(max_px, t_min, t_max)
        min_c = pixel_to_celsius(min_px, t_min, t_max)
        sigma_k = analysis_result.get("params", {}).get("sigma_k", 3.0)
        thresh_c = mean_c + sigma_k * std_c

        asym = analysis_result.get("asym_results", {})
        delta_t = asym.get("delta_t_c", 0.0)
        is_asymmetric = asym.get("is_asymmetric", False)

        tsi = analysis_result.get("tsi_results", {})
        tsi_score = tsi.get("score", 0.0)
        tsi_tier_name = tsi.get("tier_name", "Stufe 0: Physiologischer Normalbefund")
        tsi_tier_desc = tsi.get("tier_desc", "Keine Auffälligkeiten.")
        tsi_color_hex = tsi.get("color", "#16A34A")

        grads = analysis_result.get("gradient_results", {})
        max_grad = grads.get("max_gradient", 0.0)

        pca = analysis_result.get("pca_results")
        pca_l_ang = pca.get("left", {}).get("angle_deg", 0.0) if pca else 0.0
        pca_r_ang = pca.get("right", {}).get("angle_deg", 0.0) if pca else 0.0

        # Status text & colors
        if analysis_mode == "Podologische Symmetrieanalyse":
            if is_asymmetric:
                status_text = "Pathologische Asymmetrie (ΔT > 2.2 °C nach Armstrong)"
                status_color = "#DC2626"
            else:
                status_text = "Physiologisch symmetrisch (Normbefund <= 2.2 °C)"
                status_color = "#16A34A"
        else:
            if hotspot_px >= 150:
                status_text = "Klinisch auffällige Hyperthermie-Hotspots"
                status_color = "#DC2626"
            elif hotspot_px > 0:
                status_text = "Geringfügige thermische Abweichung"
                status_color = "#D97706"
            else:
                status_text = "Unauffällig / Keine Entzündungsherde"
                status_color = "#16A34A"

        # Arch Index Info
        zonal = analysis_result.get("zonal_stats", {})
        ai_l = zonal.get("left", {}).get("arch_index", 0.24)
        ai_r = zonal.get("right", {}).get("arch_index", 0.24)
        type_l = zonal.get("left", {}).get("arch_type", "Normal")
        type_r = zonal.get("right", {}).get("arch_type", "Normal")

        # ReportLab Document Setup
        doc = SimpleDocTemplate(
            output_filepath,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm
        )

        styles = getSampleStyleSheet()
        style_title = ParagraphStyle('RepTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=17, textColor=colors.HexColor('#1A73E8'))
        style_sub = ParagraphStyle('RepSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#64748B'))
        style_card_title = ParagraphStyle('RepCardTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#0F172A'))
        style_cell = ParagraphStyle('RepCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10.5, textColor=colors.HexColor('#334155'))
        style_cell_bold = ParagraphStyle('RepCellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10.5, textColor=colors.HexColor('#0F172A'))
        style_caption = ParagraphStyle('RepCaption', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=TA_CENTER, textColor=colors.HexColor('#475569'))
        style_disclaimer = ParagraphStyle('RepDisc', parent=styles['Normal'], fontName='Helvetica', fontSize=6.8, leading=8.5, textColor=colors.HexColor('#94A3B8'))

        elements = []

        # 1. Header Table
        header_data = [
            [
                Paragraph('<b>IGNITE Medical Imaging Suite</b><br/><font size="7.5" color="#64748B">Klinischer Befundbericht · Thermografische Entzündungsdiagnostik</font>', style_title),
                Paragraph(f'<b>Patient:</b> {display_record_id}<br/><b>Datum:</b> {now_str}<br/><b>Untersucher:</b> {operator}<br/><b>Modus:</b> {analysis_mode}', style_sub)
            ]
        ]
        t_header = Table(header_data, colWidths=[108 * mm, 78 * mm])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(t_header)
        elements.append(Spacer(1, 2 * mm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1A73E8'), spaceAfter=3 * mm))

        # 2. Befund-Zusammenfassung Box
        summary_data = [
            [
                Paragraph(f'<b>DIAGNOSTISCHER GESAMTSTATUS:</b> <font color="{status_color}"><b>{status_text}</b></font>', style_card_title),
                Paragraph(f'<b>TSI-Score:</b> <font color="{tsi_color_hex}"><b>{tsi_score:.1f} / 10</b></font> ({tsi_tier_name})', style_cell)
            ],
            [
                Paragraph(f'<b>Cavanagh & Rodgers Arch Index:</b> L: <b>{ai_l:.3f}</b> ({type_l}) · R: <b>{ai_r:.3f}</b> ({type_r})', style_cell),
                Paragraph(f'<b>Max. Temperatur:</b> {max_c:.1f} °C (Gewebe-Mittelwert µ: {mean_c:.1f} °C ± {std_c:.1f} °C)', style_cell)
            ]
        ]
        t_sum = Table(summary_data, colWidths=[104 * mm, 82 * mm])
        t_sum.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ]))
        elements.append(t_sum)
        elements.append(Spacer(1, 3 * mm))

        # 3. 2x2 Image Grid
        orig_arr = analysis_result.get("calibrated_original", np.zeros((10, 10), dtype=np.uint8))
        mask_arr = analysis_result.get("body_mask", np.zeros((10, 10), dtype=np.uint8))
        diff_arr = analysis_result.get("heat_diff", np.zeros((10, 10), dtype=np.uint8))
        over_arr = analysis_result.get("overlay_rgb", np.zeros((10, 10, 3), dtype=np.uint8))

        rl1 = cls._cv_to_reportlab_image(orig_arr, target_w_mm=86.0, is_rgb=False)
        rl2 = cls._cv_to_reportlab_image(mask_arr, target_w_mm=86.0, is_rgb=False)
        rl3 = cls._cv_to_reportlab_image(diff_arr, target_w_mm=86.0, is_rgb=False)
        rl4 = cls._cv_to_reportlab_image(over_arr, target_w_mm=86.0, is_rgb=True)

        if rl1 and rl2 and rl3 and rl4:
            grid_data = [
                [rl1, rl2],
                [Paragraph('1. Original-Wärmebild (Kalibriert)', style_caption), Paragraph('2. Gewebe-Segmentierung (Körpermaske)', style_caption)],
                [rl3, rl4],
                [Paragraph('3. Morphologische Top-Hat Differenz', style_caption), Paragraph('4. Detektierte Hotspots & Annotation', style_caption)],
            ]
            t_grid = Table(grid_data, colWidths=[93 * mm, 93 * mm])
            t_grid.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            elements.append(t_grid)
            elements.append(Spacer(1, 3 * mm))

        # 4. Parameter & 3-Zonen Tabelle
        l_fore_c = pixel_to_celsius(zonal.get("left", {}).get("fore", mean_px), t_min, t_max)
        r_fore_c = pixel_to_celsius(zonal.get("right", {}).get("fore", mean_px), t_min, t_max)
        d_fore_c = abs(l_fore_c - r_fore_c)

        l_mid_c = pixel_to_celsius(zonal.get("left", {}).get("mid", mean_px), t_min, t_max)
        r_mid_c = pixel_to_celsius(zonal.get("right", {}).get("mid", mean_px), t_min, t_max)
        d_mid_c = abs(l_mid_c - r_mid_c)

        l_heel_c = pixel_to_celsius(zonal.get("left", {}).get("heel", mean_px), t_min, t_max)
        r_heel_c = pixel_to_celsius(zonal.get("right", {}).get("heel", mean_px), t_min, t_max)
        d_heel_c = abs(l_heel_c - r_heel_c)

        fore_warn = f'<font color="#DC2626"><b>Δ {d_fore_c:.1f} °C ⚠️</b></font>' if d_fore_c > 2.2 else f'Δ {d_fore_c:.1f} °C'
        mid_warn = f'<font color="#DC2626"><b>Δ {d_mid_c:.1f} °C ⚠️</b></font>' if d_mid_c > 2.2 else f'Δ {d_mid_c:.1f} °C'
        heel_warn = f'<font color="#DC2626"><b>Δ {d_heel_c:.1f} °C ⚠️</b></font>' if d_heel_c > 2.2 else f'Δ {d_heel_c:.1f} °C'

        param_data = [
            [Paragraph('<b>Messparameter</b>', style_cell_bold), Paragraph('<b>Wert</b>', style_cell_bold), Paragraph('<b>Podologische Zone</b>', style_cell_bold), Paragraph('<b>Links</b>', style_cell_bold), Paragraph('<b>Rechts</b>', style_cell_bold), Paragraph('<b>Differenz ΔT</b>', style_cell_bold)],
            [Paragraph('Gewebe-Mittelwert (µ)', style_cell), Paragraph(f'{mean_c:.1f} °C', style_cell), Paragraph('Vorfuß (Ballen)', style_cell), Paragraph(f'{l_fore_c:.1f} °C', style_cell), Paragraph(f'{r_fore_c:.1f} °C', style_cell), Paragraph(fore_warn, style_cell)],
            [Paragraph('Standardabweichung (σ)', style_cell), Paragraph(f'±{std_c:.2f} °C', style_cell), Paragraph('Mittelfuß (Gewölbe)', style_cell), Paragraph(f'{l_mid_c:.1f} °C', style_cell), Paragraph(f'{r_mid_c:.1f} °C', style_cell), Paragraph(mid_warn, style_cell)],
            [Paragraph('Adaptive Schwelle (µ+k·σ)', style_cell), Paragraph(f'{thresh_c:.1f} °C', style_cell), Paragraph('Ferse (Rückfuß)', style_cell), Paragraph(f'{l_heel_c:.1f} °C', style_cell), Paragraph(f'{r_heel_c:.1f} °C', style_cell), Paragraph(heel_warn, style_cell)],
            [Paragraph('Hotspot-Fläche', style_cell), Paragraph(f'{hotspot_px} px ({hotspot_ratio:.1f} %)', style_cell), Paragraph('Cavanagh Arch Index', style_cell), Paragraph(f'{ai_l:.3f}', style_cell), Paragraph(f'{ai_r:.3f}', style_cell), Paragraph('Asymmetrie-Check', style_cell)],
        ]
        t_params = Table(param_data, colWidths=[38 * mm, 26 * mm, 38 * mm, 28 * mm, 28 * mm, 28 * mm])
        t_params.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ]))
        elements.append(t_params)
        elements.append(Spacer(1, 2 * mm))

        # 5. Klinische Anmerkungen (falls vorhanden)
        if notes and notes.strip():
            notes_data = [[
                Paragraph(f'<b>Klinische Anmerkungen des Untersuchers:</b> {notes.strip()}', style_cell)
            ]]
            t_notes = Table(notes_data, colWidths=[186 * mm])
            t_notes.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFFBEB')),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCD34D')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(t_notes)
            elements.append(Spacer(1, 2 * mm))

        # 6. Fußnote & Disclaimer
        disc = Paragraph(
            'IGNITE Medical Imaging Suite · Entwickelt von Jona Noack für Jugend forscht 2026 (Fachgebiet Arbeitswelt). '
            '<em>Hinweis: Forschungsprototyp – Kein zertifiziertes EU-MDR Medizinprodukt. DSGVO-konforme In-Memory Pseudonymisierung.</em>',
            style_disclaimer
        )
        elements.append(disc)

        doc.build(elements)

        # Audit-Log Eintrag schreiben
        try:
            write_audit_entry({
                "Zeitstempel": datetime.datetime.now().isoformat(),
                "Patienten-ID": display_record_id,
                "Format": "PDF",
                "Analysemodus": analysis_mode,
                "Bilddatei": os.path.basename(image_path),
                "sigma_k": sigma_k,
                "T_min_C": t_min,
                "T_max_C": t_max,
                "Hotspot_Pixel": hotspot_px,
                "Max_Temp_C": round(max_c, 2),
                "Symmetrie_Delta": round(delta_t, 2),
                "Operator": operator
            })
        except Exception as e:
            logging.error(f"Audit log write failed: {e}")

        return output_filepath

    @classmethod
    def generate_batch_summary_pdf(
        cls,
        results_list: list[dict[str, Any]],
        output_dir: str
    ) -> str:
        """Erzeugt einen Gesamtübersichts-Bericht aller Batch-Bilder als druckfertiges PDF."""
        summary_path = os.path.join(output_dir, "batch_summary_report.pdf")
        now_str = datetime.datetime.now().strftime("%d.%m.%Y, %H:%M Uhr")

        doc = SimpleDocTemplate(
            summary_path,
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm
        )

        styles = getSampleStyleSheet()
        style_title = ParagraphStyle('SummTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=17, textColor=colors.HexColor('#1A73E8'))
        style_sub = ParagraphStyle('SummSub', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#64748B'))
        style_cell = ParagraphStyle('SummCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155'))
        style_cell_bold = ParagraphStyle('SummCellB', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0F172A'))

        elements = []

        # Header
        header_data = [
            [
                Paragraph('<b>IGNITE Serienuntersuchungs-Bericht (Batch)</b><br/><font size="8" color="#64748B">Stapelverarbeitung von Infrarot-Thermogrammen</font>', style_title),
                Paragraph(f'<b>Anzahl Aufnahmen:</b> {len(results_list)}<br/><b>Erstellt am:</b> {now_str}', style_sub)
            ]
        ]
        t_header = Table(header_data, colWidths=[110 * mm, 76 * mm])
        elements.append(t_header)
        elements.append(Spacer(1, 2 * mm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1A73E8'), spaceAfter=4 * mm))

        # Batch Table
        table_rows = [
            [
                Paragraph('<b>Bilddatei</b>', style_cell_bold),
                Paragraph('<b>Hotspots (px)</b>', style_cell_bold),
                Paragraph('<b>Symmetrie (ΔT)</b>', style_cell_bold),
                Paragraph('<b>Diagnostischer Status</b>', style_cell_bold)
            ]
        ]

        for item in results_list:
            fname = os.path.basename(item.get("filepath", ""))
            hotspot_px = item.get("hotspot_count", 0)
            delta_t = item.get("delta_t_c", 0.0)
            status_text = item.get("status_text", "Unauffällig")
            is_warn = item.get("is_warning", False)

            col_hotspot = '#DC2626' if hotspot_px > 0 else '#16A34A'
            col_status = '#DC2626' if is_warn else '#16A34A'

            table_rows.append([
                Paragraph(f'<b>{fname}</b>', style_cell),
                Paragraph(f'<font color="{col_hotspot}"><b>{hotspot_px:,} px</b></font>', style_cell),
                Paragraph(f'{delta_t:.2f} °C', style_cell),
                Paragraph(f'<font color="{col_status}"><b>{status_text}</b></font>', style_cell),
            ])

        t_batch = Table(table_rows, colWidths=[70 * mm, 35 * mm, 35 * mm, 46 * mm])
        t_batch.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(t_batch)
        elements.append(Spacer(1, 4 * mm))

        # Disclaimer
        disc = Paragraph(
            'IGNITE Medical Imaging Suite · Entwickelt von Jona Noack für Jugend forscht 2026. '
            '<em>Hinweis: Forschungsprototyp – Kein zertifiziertes EU-MDR Medizinprodukt.</em>',
            style_cell
        )
        elements.append(disc)

        doc.build(elements)
        return summary_path

    @classmethod
    def export_report(
        cls,
        analysis_result: dict[str, Any],
        record_id: str = "Unbekannt",
        operator: str = "Jugend forscht 2026",
        notes: str = "",
        format_choice: str = "PDF (.pdf)",
        output_filepath: Optional[str] = None
    ) -> list[str]:
        """Universeller Export-Handler, der flexibel PDF, HTML oder beide Formate erzeugt."""
        generated_files = []
        fmt = format_choice.lower()

        if "pdf" in fmt or "beide" in fmt:
            pdf_path = cls.generate_pdf_report(
                analysis_result=analysis_result,
                record_id=record_id,
                operator=operator,
                notes=notes,
                output_filepath=output_filepath if (output_filepath and output_filepath.endswith(".pdf")) else None
            )
            generated_files.append(pdf_path)

        if "html" in fmt or "beide" in fmt:
            html_path = cls.generate_html_report(
                analysis_result=analysis_result,
                record_id=record_id,
                operator=operator,
                notes=notes,
                output_filepath=output_filepath if (output_filepath and output_filepath.endswith(".html")) else None
            )
            generated_files.append(html_path)

        return generated_files

