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

import config
from audit_log import write_audit_entry
from utils import pixel_to_celsius, pseudonymize_patient


class ExportService:
    """Service-Klasse zum Generieren von HTML-Klinikberichten und Protokollen."""

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
        patient_name: str = "Unbekannt",
        patient_dob: str = "",
        operator: str = "Jugend forscht 2026",
        notes: str = "",
        output_filepath: Optional[str] = None
    ) -> str:
        """Erzeugt einen eigenständigen, modernen Google Material Design HTML-Befundbericht."""
        image_path = analysis_result.get("image_path", "Unbekannt")
        base_name = os.path.splitext(os.path.basename(image_path))[0]

        if not output_filepath:
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            output_filepath = os.path.join(config.OUTPUT_DIR, f"report_{base_name}.html")

        # Pseudonymisierung prüfen
        is_anon = patient_name.startswith("ANON-")
        if not is_anon and patient_name.strip() and patient_name != "Unbekannt":
            display_patient_id = pseudonymize_patient(patient_name, patient_dob)
            is_anon = True
        else:
            display_patient_id = patient_name

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

        # Base64-Bilder einbetten
        b64_orig = cls._cv_to_base64(analysis_result.get("calibrated_original", np.zeros((10, 10), dtype=np.uint8)))
        b64_mask = cls._cv_to_base64(analysis_result.get("body_mask", np.zeros((10, 10), dtype=np.uint8)))
        b64_diff = cls._cv_to_base64(analysis_result.get("heat_diff", np.zeros((10, 10), dtype=np.uint8)))
        b64_overlay = cls._cv_to_base64(analysis_result.get("overlay_rgb", np.zeros((10, 10, 3), dtype=np.uint8)), is_rgb=True)

        # Status & Badges
        if analysis_mode == "Podologische Symmetrieanalyse":
            if is_asymmetric:
                status_text = "Pathologische Asymmetrie (ΔT > 2.2 °C)"
                status_color = "#EA4335"
                status_bg = "#FCE8E6"
            else:
                status_text = "Physiologisch symmetrisch (Normalbefund)"
                status_color = "#34A853"
                status_bg = "#E6F4EA"
        else:
            if hotspot_px >= 150:
                status_text = "Klinisch auffällige Hyperthermie-Hotspots"
                status_color = "#EA4335"
                status_bg = "#FCE8E6"
            elif hotspot_px > 0:
                status_text = "Geringfügige thermische Abweichung"
                status_color = "#E37400"
                status_bg = "#FEF7E0"
            else:
                status_text = "Unauffällig / Keine Entzündungsherde"
                status_color = "#34A853"
                status_bg = "#E6F4EA"

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
            <div class="card" style="margin-top: 24px;">
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
                            <td><strong style="color: {'#EA4335' if d_fore_c > 2.2 else '#202124'};">{d_fore_c:.2f} °C</strong></td>
                            <td><span class="chip {'chip-danger' if d_fore_c > 2.2 else 'chip-success'}">{'Asymmetrie' if d_fore_c > 2.2 else 'Symmetrisch'}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Mittelfuß (Längsgewölbe)</strong></td>
                            <td>{l_mid_c:.1f} °C</td>
                            <td>{r_mid_c:.1f} °C</td>
                            <td><strong style="color: {'#EA4335' if d_mid_c > 2.2 else '#202124'};">{d_mid_c:.2f} °C</strong></td>
                            <td><span class="chip {'chip-danger' if d_mid_c > 2.2 else 'chip-success'}">{'Asymmetrie' if d_mid_c > 2.2 else 'Symmetrisch'}</span></td>
                        </tr>
                        <tr>
                            <td><strong>Ferse (Rückfuß)</strong></td>
                            <td>{l_heel_c:.1f} °C</td>
                            <td>{r_heel_c:.1f} °C</td>
                            <td><strong style="color: {'#EA4335' if d_heel_c > 2.2 else '#202124'};">{d_heel_c:.2f} °C</strong></td>
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
            --google-blue: #1A73E8;
            --google-red: #EA4335;
            --google-green: #34A853;
            --google-yellow: #FBBC04;
            --bg-app: #F8F9FA;
            --surface: #FFFFFF;
            --outline: #DADCE0;
            --text-main: #202124;
            --text-secondary: #5F6368;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
        body {{ background-color: var(--bg-app); color: var(--text-main); padding: 32px 16px; line-height: 1.5; }}
        .container {{ max-width: 980px; margin: 0 auto; }}
        
        /* Header */
        .app-header {{
            background: var(--surface);
            border: 1px solid var(--outline);
            border-radius: 16px;
            padding: 24px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(60,64,67,0.08);
        }}
        .brand-title {{ font-size: 22px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 8px; }}
        .brand-dot {{ width: 10px; height: 10px; border-radius: 50%; background-color: var(--google-blue); display: inline-block; }}
        .brand-sub {{ font-size: 13px; color: var(--text-secondary); margin-top: 2px; }}
        
        /* Cards */
        .card {{
            background: var(--surface);
            border: 1px solid var(--outline);
            border-radius: 16px;
            padding: 24px 28px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(60,64,67,0.08);
        }}
        .card-title {{
            font-size: 15px;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* Grids */
        .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
        .meta-item {{ background: #F8F9FA; padding: 12px 16px; border-radius: 10px; border: 1px solid #E8EAED; }}
        .meta-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-secondary); font-weight: 600; }}
        .meta-val {{ font-size: 14px; font-weight: 600; color: var(--text-main); margin-top: 4px; }}
        
        /* Chips */
        .chip {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }}
        .chip-success {{ background: #E6F4EA; color: #137333; }}
        .chip-danger {{ background: #FCE8E6; color: #C5221F; }}
        .chip-warning {{ background: #FEF7E0; color: #B06000; }}
        .chip-blue {{ background: #E8F0FE; color: #174EA6; }}
        
        /* Image Grid */
        .img-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-top: 12px; }}
        .img-card {{ background: #F8F9FA; border: 1px solid #E8EAED; border-radius: 12px; padding: 12px; text-align: center; }}
        .img-card img {{ width: 100%; height: auto; border-radius: 8px; display: block; }}
        .img-caption {{ font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-top: 8px; }}
        
        /* Table */
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px 16px; text-align: left; font-size: 13px; border-bottom: 1px solid var(--outline); }}
        th {{ background-color: #F8F9FA; font-weight: 600; color: var(--text-secondary); font-size: 11px; text-transform: uppercase; }}
        tr:last-child td {{ border-bottom: none; }}
        
        /* Footer */
        .footer {{ text-align: center; font-size: 11px; color: var(--text-secondary); padding: 24px 0 10px; }}
        
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
                <div style="font-size: 12px; color: var(--text-secondary); margin-top: 6px;">{now_str}</div>
            </div>
        </div>

        <!-- Stammdaten Card -->
        <div class="card">
            <div class="card-title">Untersuchungs- & Patientendaten</div>
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Patienten-ID</div>
                    <div class="meta-val">{display_patient_id}</div>
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
            <div style="background: {status_bg}; border: 1px solid {status_color}30; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 11px; text-transform: uppercase; font-weight: 700; color: {status_color};">Globales Fazit</div>
                    <div style="font-size: 16px; font-weight: 700; color: {status_color}; margin-top: 2px;">{status_text}</div>
                </div>
                <span class="chip" style="background: {status_color}; color: #FFF; font-size: 12px; padding: 6px 14px;">
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
                "Patienten-ID": display_patient_id,
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
                <td><strong style="color: {'#EA4335' if hotspot_px > 0 else '#34A853'};">{hotspot_px:,} px</strong></td>
                <td>{delta_t:.2f} °C</td>
                <td><span class="chip {badge_class}">{status_text}</span></td>
                <td><a href="{report_name}" style="color: #1A73E8; text-decoration: none; font-weight: 600;">Bericht öffnen &rarr;</a></td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>IGNITE Stapelverarbeitungs-Übersicht</title>
    <style>
        body {{ font-family: 'Segoe UI', Roboto, sans-serif; background: #F8F9FA; color: #202124; padding: 40px 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: #FFF; border: 1px solid #DADCE0; border-radius: 16px; padding: 32px; box-shadow: 0 1px 3px rgba(60,64,67,0.08); }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E8EAED; padding-bottom: 20px; margin-bottom: 24px; }}
        .title {{ font-size: 24px; font-weight: 700; color: #202124; }}
        .sub {{ font-size: 13px; color: #5F6368; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid #DADCE0; font-size: 13px; }}
        th {{ background: #F8F9FA; color: #5F6368; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
        .chip {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }}
        .chip-success {{ background: #E6F4EA; color: #137333; }}
        .chip-danger {{ background: #FCE8E6; color: #C5221F; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="title">IGNITE Serienuntersuchungs-Bericht</div>
                <div class="sub">{len(results_list)} Wärmebilder erfolgreich automatisiert analysiert</div>
            </div>
            <div style="font-size: 12px; color: #5F6368;">Erstellt: <strong>{now_str}</strong></div>
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
