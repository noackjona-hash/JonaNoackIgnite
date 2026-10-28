# -*- coding: utf-8 -*-
"""exporter.py — Bild- und Datenexporteur für alle 42 Stufen.

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Erzeugt für jeden der 42 Pipeline-Schritte:
1. Ein beschriftetes, hochauflösendes Diagnosebild (PNG) mit klinischem Header-Banner,
   Farbskala und visualisierten Algorithmus-Schichten.
2. Eine strukturierte JSON-Metadatendatei mit Zeitmessungen und biophysikalischen Kennzahlen.
"""

import os
import json
import time
from typing import Dict, Any, Optional, Tuple, Callable
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")  # Headless Backend ohne GUI
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from .context import PipelineContext, StepResult


class StepExporter:
    """Verwaltet den Export aller Zwischenergebnisse in den Zielordner."""

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def export_step(
        self,
        ctx: PipelineContext,
        step_number: int,
        phase_number: int,
        phase_name: str,
        name: str,
        description: str,
        formula: str,
        duration_ms: float,
        metrics: Dict[str, Any],
        render_fn: Callable[[Figure, plt.Axes], None],
        minimal_banner: bool = False
    ) -> StepResult:
        """Exportiert einen einzelnen Algorithmus-Schritt als PNG und JSON."""
        prefix = f"step_{step_number:02d}_{self._slugify(name)}"
        img_filename = f"{prefix}.png"
        json_filename = f"{prefix}.json"
        img_path = os.path.join(self.output_dir, img_filename)
        json_path = os.path.join(self.output_dir, json_filename)

        # 1. Bild zeichnen mit Matplotlib
        fig = plt.figure(figsize=(10, 7.5 if minimal_banner else 7.0), dpi=150, facecolor='#0B0F19')

        if minimal_banner:
            # Reines Vollbild-Rendering ohne störenden Header-Banner
            ax_main = fig.add_axes([0.01, 0.01, 0.98, 0.98])
            ax_main.set_facecolor('#0B0F19')
            render_fn(fig, ax_main)
        else:
            # Oberer Banner-Bereich für Titel & Metadaten (GridSpec)
            gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[1.2, 8.8], hspace=0.15)
            
            ax_banner = fig.add_subplot(gs[0])
            ax_banner.set_facecolor('#131B2A')
            ax_banner.axis('off')
            
            # Banner-Inhalt
            header_text = f"IGNITE v5.0 • STUFE {step_number:02d} / 42  |  {phase_name.upper()}"
            ax_banner.text(0.02, 0.70, header_text, color='#38BDF8', fontsize=11, fontweight='bold', va='center')
            ax_banner.text(0.02, 0.28, name, color='#F8FAFC', fontsize=13, fontweight='bold', va='center')
            
            # Wichtigste Kennzahlen rechts im Banner (ohne Überlappung)
            metric_items = [f"{k}: {v}" for k, v in list(metrics.items())[:2]]
            metric_items.append(f"{duration_ms:.2f} ms")
            metric_str = "  |  ".join(metric_items)
            ax_banner.text(0.98, 0.30, metric_str, color='#94A3B8', fontsize=8.5, ha='right', va='center')

            # Haupt-Plot-Achse
            ax_main = fig.add_subplot(gs[1])
            ax_main.set_facecolor('#0B0F19')
            
            # Ausführung des spezifischen Renderings
            render_fn(fig, ax_main)

        # Speichern
        fig.savefig(img_path, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight')
        plt.close(fig)

        # 2. JSON-Metadaten speichern
        meta = {
            "step_number": step_number,
            "phase_number": phase_number,
            "phase_name": phase_name,
            "name": name,
            "description": description,
            "formula": formula,
            "duration_ms": duration_ms,
            "metrics": metrics,
            "image_filename": img_filename
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # 3. StepResult erzeugen und im Kontext registrieren
        res = StepResult(
            step_number=step_number,
            phase_number=phase_number,
            phase_name=phase_name,
            name=name,
            description=description,
            formula=formula,
            duration_ms=duration_ms,
            metrics=metrics,
            image_filename=img_filename,
            json_filename=json_filename
        )
        ctx.step_results.append(res)
        return res

    @staticmethod
    def _slugify(text: str) -> str:
        """Erzeugt einen sauberen Dateinamen-Slug."""
        clean = ""
        for c in text.lower():
            if c.isalnum():
                clean += c
            elif c in [' ', '-', '_']:
                clean += '_'
        return clean.strip('_')[:35]
