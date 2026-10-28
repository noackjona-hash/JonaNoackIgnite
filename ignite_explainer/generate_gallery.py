# -*- coding: utf-8 -*-
"""generate_gallery.py — Erzeugt eine interaktive Präsentations-Galerie aller 42 Stufen.

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Generiert eine eigenständige, offline-fähige HTML-Präsentationsseite in exports/index.html,
die alle 42 Berechnungsschritte mit Bildern, Formeln und klinischen Erklärungen darstellt.
"""

import os
import json
from typing import List, Dict, Any, Optional
try:
    from core.context import PipelineContext
except ImportError:
    from .core.context import PipelineContext



def generate_html_gallery(ctx: PipelineContext, output_dir: str = "exports", bench_data: Dict[str, Any] = None):
    """Baut eine moderne PACS-Galerie (HTML5/CSS3) für die Präsentation aller 42 Stufen."""
    html_path = os.path.join(output_dir, "index.html")
    
    total_time_ms = sum(s.duration_ms for s in ctx.step_results)
    
    # Farben für Triage-Karten
    triage_color = "#16A34A" if ctx.overall_triage_level == "BENIGN" else ("#F59E0B" if ctx.overall_triage_level == "MODERATE" else "#DC2626")

    cards_html = ""
    for s in ctx.step_results:
        # Metadaten-Pills
        metric_pills = ""
        for k, v in s.metrics.items():
            metric_pills += f'<span class="metric-pill"><strong>{k}:</strong> {v}</span>'
            
        phase_class = f"phase-{s.phase_number}"
        
        cards_html += f"""
        <div class="step-card {phase_class}" data-phase="{s.phase_number}">
            <div class="card-header">
                <span class="step-badge">STUFE {s.step_number:02d} / 42</span>
                <span class="phase-badge">{s.phase_name.split(':')[0]}</span>
                <span class="timing-badge">⚡ {s.duration_ms:.2f} ms</span>
            </div>
            <h3 class="step-title">{s.name}</h3>
            
            <div class="image-container">
                <img src="{s.image_filename}" alt="{s.name}" loading="lazy" onclick="openLightbox('{s.image_filename}', '{s.name}')">
            </div>
            
            <div class="card-body">
                <div class="formula-box">
                    <code>{s.formula}</code>
                </div>
                <p class="description">{s.description}</p>
                <div class="metrics-grid">
                    {metric_pills}
                </div>
            </div>
        </div>
        """

    # Benchmark-Box
    bench_html = ""
    if bench_data:
        bench_html = f"""
        <div class="benchmark-banner">
            <div class="bench-col">
                <span class="bench-label">Naiver Python-Loop</span>
                <span class="bench-val red">{bench_data.get('python_loop_ms', 0):.1f} ms</span>
            </div>
            <div class="bench-arrow">➔</div>
            <div class="bench-col">
                <span class="bench-label">NumPy Vektorisierung</span>
                <span class="bench-val yellow">{bench_data.get('numpy_ms', 0):.2f} ms</span>
            </div>
            <div class="bench-arrow">➔</div>
            <div class="bench-col highlight">
                <span class="bench-label">x86_64 SIMD Assembler (AVX2/SSE2)</span>
                <span class="bench-val green">{bench_data.get('assembler_simd_ms', 0):.3f} ms</span>
            </div>
            <div class="bench-col badge-col">
                <span class="speedup-badge">🚀 {bench_data.get('speedup_vs_python', 0):,.0f}× schneller</span>
            </div>
        </div>
        """

    full_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IGNITE v5.0 — 42-Stufige Diagnostik-Pipeline (Jugend forscht 2026)</title>
    <style>
        :root {{
            --bg-dark: #07090E;
            --surface: #0F172A;
            --surface-card: #131D31;
            --border: #1E293B;
            --text-main: #F8FAFC;
            --text-muted: #94A3B8;
            --cyan: #0284C7;
            --cyan-light: #38BDF8;
            --green: #16A34A;
            --yellow: #F59E0B;
            --red: #DC2626;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg-dark);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            padding: 24px;
        }}
        .header {{
            max-width: 1400px;
            margin: 0 auto 32px auto;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }}
        .header h1 {{
            font-size: 28px;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .header h1 span {{ color: var(--cyan-light); }}
        .header p {{ color: var(--text-muted); font-size: 15px; margin-top: 8px; }}
        
        .triage-banner {{
            display: inline-flex;
            align-items: center;
            gap: 12px;
            margin-top: 20px;
            padding: 10px 20px;
            background: {triage_color}22;
            border: 1px solid {triage_color};
            border-radius: 12px;
            font-weight: bold;
            font-size: 16px;
            color: {triage_color};
        }}
        
        .benchmark-banner {{
            margin-top: 24px;
            padding: 18px 24px;
            background: #0B1120;
            border: 1px solid #1E293B;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .bench-col {{ display: flex; flex-direction: column; }}
        .bench-col.highlight {{ background: #0369A122; padding: 6px 14px; border-radius: 8px; border: 1px solid #0284C7; }}
        .bench-label {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: bold; }}
        .bench-val {{ font-size: 18px; font-weight: bold; font-family: monospace; }}
        .bench-val.red {{ color: var(--red); }}
        .bench-val.yellow {{ color: var(--yellow); }}
        .bench-val.green {{ color: #4ADE80; }}
        .bench-arrow {{ color: var(--text-muted); font-size: 20px; }}
        .speedup-badge {{ background: #0284C7; color: #FFF; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 14px; }}
        
        /* Filterleiste */
        .filter-bar {{
            max-width: 1400px;
            margin: 0 auto 24px auto;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 8px;
        }}
        .filter-btn {{
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--text-muted);
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: var(--cyan);
            color: #FFFFFF;
            border-color: var(--cyan-light);
        }}
        
        /* Grid */
        .pipeline-grid {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 24px;
        }}
        
        /* Karten */
        .step-card {{
            background: var(--surface-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .step-card:hover {{
            transform: translateY(-4px);
            border-color: var(--cyan-light);
        }}
        .card-header {{
            padding: 14px 18px 8px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}
        .step-badge {{ font-size: 11px; font-weight: bold; color: var(--cyan-light); background: #0284C722; padding: 4px 8px; border-radius: 6px; }}
        .phase-badge {{ font-size: 11px; font-weight: bold; color: var(--text-muted); }}
        .timing-badge {{ font-size: 11px; color: #4ADE80; font-family: monospace; }}
        
        .step-title {{
            font-size: 16px;
            font-weight: bold;
            padding: 0 18px 12px 18px;
            color: var(--text-main);
        }}
        
        .image-container {{
            background: #000;
            width: 100%;
            height: 250px;
            overflow: hidden;
            position: relative;
            cursor: zoom-in;
        }}
        .image-container img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }}
        .image-container:hover img {{
            transform: scale(1.03);
        }}
        
        .card-body {{
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            flex: 1;
        }}
        
        .formula-box {{
            background: #0B1120;
            border-left: 3px solid var(--cyan-light);
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            overflow-x: auto;
            color: #E2E8F0;
        }}
        .description {{
            font-size: 13px;
            color: var(--text-muted);
            line-height: 1.45;
        }}
        .metrics-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: auto;
            padding-top: 8px;
            border-top: 1px solid #1E293B;
        }}
        .metric-pill {{
            background: #1E293B;
            color: #CBD5E1;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
        }}
        
        /* Lightbox */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 9999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }}
        .lightbox img {{
            max-width: 90%;
            max-height: 80%;
            border-radius: 8px;
            box-shadow: 0 0 30px rgba(0,0,0,0.8);
        }}
        .lightbox-title {{
            color: #FFF;
            font-size: 18px;
            margin-top: 16px;
            font-weight: bold;
        }}
    </style>
</head>
<body>

    <header class="header">
        <h1><span>IGNITE v5.0</span> — Vollständige 42-Stufen Diagnostik-Pipeline</h1>
        <p><strong>Jugend forscht 2026</strong> • Fachgebiet Arbeitswelt / Informatik • Autor: <strong>Jona Noack</strong></p>
        <p>Deterministische, berührungslose Früherkennung diabetischer Fußulzera (DFS) & Gewebeentzündungen mittels LWIR-Thermografie.</p>
        
        <div class="triage-banner">
            <span>Diagnostische End-Triage:</span>
            <strong>{ctx.triage_headline}</strong>
            <span>(Gesamtdauer aller 42 Stufen: {total_time_ms:.1f} ms)</span>
        </div>
        
        {bench_html}
    </header>

    <div class="filter-bar">
        <button class="filter-btn active" onclick="filterPhase('all')">Alle 42 Stufen</button>
        <button class="filter-btn" onclick="filterPhase('1')">Phase I: Sensor (1–6)</button>
        <button class="filter-btn" onclick="filterPhase('2')">Phase II: Segmentierung (7–12)</button>
        <button class="filter-btn" onclick="filterPhase('3')">Phase III: 3D-Kompensation (13–18)</button>
        <button class="filter-btn" onclick="filterPhase('4')">Phase IV: Morphologie & SIMD (19–24)</button>
        <button class="filter-btn" onclick="filterPhase('5')">Phase V: Statistik & MAD (25–30)</button>
        <button class="filter-btn" onclick="filterPhase('6')">Phase VI: Geometrie & Frangi (31–36)</button>
        <button class="filter-btn" onclick="filterPhase('7')">Phase VII: Triage & Armstrong (37–42)</button>
    </div>

    <main class="pipeline-grid" id="pipelineGrid">
        {cards_html}
    </main>

    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <img id="lightboxImg" src="">
        <div class="lightbox-title" id="lightboxTitle"></div>
    </div>

    <script>
        function filterPhase(phase) {{
            const buttons = document.querySelectorAll('.filter-btn');
            buttons.forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            const cards = document.querySelectorAll('.step-card');
            cards.forEach(card => {{
                if (phase === 'all' || card.getAttribute('data-phase') === phase) {{
                    card.style.display = 'flex';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }}

        function openLightbox(src, title) {{
            document.getElementById('lightboxImg').src = src;
            document.getElementById('lightboxTitle').innerText = title;
            document.getElementById('lightbox').style.display = 'flex';
        }}

        function closeLightbox() {{
            document.getElementById('lightbox').style.display = 'none';
        }}
    </script>
</body>
</html>
"""
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
    return html_path
