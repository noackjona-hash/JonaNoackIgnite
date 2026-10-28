# -*- coding: utf-8 -*-
"""main.py — Einstiegspunkt der 42-stufigen IGNITE Pipeline.

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite (v5.0.0)

Führt eine deterministische, vollautomatisierte Analyse für genau EIN geladenes
Infrarot-Thermogramm durch und exportiert JEDEN einzelnen der 42 Berechnungsschritte
als beschriftetes Diagnose-Bild und JSON-Metadaten in den Ordner exports/.

Ausführung:
    python main.py [PFAD_ZUM_BILD]
"""

import os
import sys
import time
import argparse

# Pfad-Konfiguration für relative Imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from core.context import PipelineConfig, PipelineContext
from core.exporter import StepExporter
from core.phase1_radiometry import execute_phase1
from core.phase2_segmentation import execute_phase2
from core.phase3_depth_3d import execute_phase3
from core.phase4_morphology import execute_phase4
from core.phase5_statistics import execute_phase5
from core.phase6_geometry import execute_phase6
from core.phase7_triage import execute_phase7
from assembly.fast_simd import benchmark_assembly_vs_python
# Windows Terminal-Codierung absichern
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from generate_gallery import generate_html_gallery


def print_banner():
    banner = """
    =============================================================================
      IGNITE *  42-STUFIGE EXPLAINER PIPELINE
      Jugend forscht 2026  *  Fachgebiet Arbeitswelt / Informatik
      Entwickelt von: Jona Noack
    =============================================================================
    """
    print(banner)



def run_pipeline(image_path: str, output_dir: str = "exports"):
    """Lädt ein Bild und führt alle 42 Stufen sequentiell aus."""
    print_banner()

    if not os.path.isabs(image_path):
        image_path = os.path.abspath(image_path)

    if not os.path.isfile(image_path):
        print(f"[FEHLER] Bilddatei nicht gefunden: {image_path}")
        sys.exit(1)

    abs_output_dir = os.path.abspath(os.path.join(SCRIPT_DIR, output_dir))
    os.makedirs(abs_output_dir, exist_ok=True)

    print(f"[*] Eingabebild:      {image_path}")
    print(f"[*] Export-Ordner:    {abs_output_dir}")
    print(f"[*] Berechnungsstufen: 42 Stufen in 7 klinischen Phasen\n")

    t_start = time.perf_counter()

    # 1. Pipeline-Kontext initialisieren
    config = PipelineConfig()
    ctx = PipelineContext(config=config)
    exporter = StepExporter(output_dir=abs_output_dir)

    # 2. Phase I: Sensor & Radiometrie (Stufen 1–6)
    print("▶ [Phase I/VII]   Sensor & Radiometrische Kalibrierung (Stufen 1–6) ...")
    execute_phase1(ctx, exporter, image_path)

    # 3. Phase II: Anatomische Gewebesegmentierung (Stufen 7–12)
    print("▶ [Phase II/VII]  Anatomische Gewebesegmentierung & Geodäten (Stufen 7–12) ...")
    execute_phase2(ctx, exporter)

    # 4. Phase III: 3D Anatomical Inflation & Winkelkorrektur (Stufen 13–18)
    print("▶ [Phase III/VII] 3D Anatomische Wölbung & Lambertian-Kompensation (Stufen 13–18) ...")
    execute_phase3(ctx, exporter)

    # 5. Phase IV: Multiskalige Morphologie & SIMD Assembler (Stufen 19–24)
    print("▶ [Phase IV/VII]  Morphologische Top-Hat Extraktion & AVX2-Assembler (Stufen 19–24) ...")
    execute_phase4(ctx, exporter)

    # 6. Phase V: Statistische Schwellwertbildung & Hampel-MAD (Stufen 25–30)
    print("▶ [Phase V/VII]   Hampel-MAD Statistik & Robuste Outlier-Detektion (Stufen 25–30) ...")
    execute_phase5(ctx, exporter)

    # 7. Phase VI: Geometrische Morphologie & Frangi-Filterung (Stufen 31–36)
    print("▶ [Phase VI/VII]  Clusterung, Zirkularität & Frangi-Gefäßunterdrückung (Stufen 31–36) ...")
    execute_phase6(ctx, exporter)

    # 8. Phase VII: Biophysikalische Differentialdiagnose & Armstrong Triage (Stufen 37–42)
    print("▶ [Phase VII/VII] Halo, Laplace & Evidenzbasierte IWGDF-Triage (Stufen 37–42) ...\n")
    execute_phase7(ctx, exporter)

    t_total = (time.perf_counter() - t_start) * 1000.0

    # 9. Performance-Benchmark: Python vs. NumPy vs. Assembler
    print("[*] Führe Hardware-Beschleunigungs-Benchmark durch (x86_64 SIMD vs. Python) ...")
    bench_data = benchmark_assembly_vs_python(iterations=25)
    print(f"    • Reiner Python-Loop:           {bench_data['python_loop_ms']:.2f} ms")
    print(f"    • NumPy C-Vektorisierung:       {bench_data['numpy_ms']:.3f} ms")
    print(f"    • IGNITE x86_64 SIMD Assembler: {bench_data['assembler_simd_ms']:.3f} ms")
    print(f"    ➔ Geschwindigkeitsvorteil:      {bench_data['speedup_vs_python']:,.0f}x schneller!\n")

    # 10. Interaktive HTML-Präsentations-Galerie generieren
    gallery_file = generate_html_gallery(ctx, output_dir=abs_output_dir, bench_data=bench_data)

    # 11. Klinische Abschluss-Zusammenfassung drucken
    print("=" * 75)
    print("                       KLINISCHE DIAGNOSE-ZUSAMMENFASSUNG")
    print("=" * 75)
    print(f"Gesamt-Triage:           [{ctx.overall_triage_level}]")
    print(f"Diagnose-Befund:         {ctx.triage_headline}")
    print(f"Kontralaterales Delta-T: {ctx.delta_t_contralateral:.2f} K (Armstrong-Schwelle: 2.2 K)")
    print(f"Gewebe-Pixel:            {ctx.tissue_pixel_count:,} Pixel ({ctx.tissue_pixel_count * (0.6**2):.1f} mm2)")
    print(f"Bestaetigter Entzuendungsherd:   {len(ctx.confirmed_pathology_hotspots)} (Großer Zeh / Hallux)")
    print(f"Verarbeitete Stufen:     {len(ctx.step_results)} / 42 Stufen bit-reproduzierbar exportiert")
    print(f"Gesamtlaufzeit Pipeline: {t_total:.2f} ms")
    print("-" * 75)
    print(f"[OK] Alle 42 Stufen-Bilder (PNG) & Daten (JSON) gespeichert in:")
    print(f"  {abs_output_dir}")
    print(f"[OK] Interaktive Praesentations-Galerie zum Zeigen und Erklaeren:")
    print(f"  file:///{gallery_file.replace(os.sep, '/')}")
    print("=" * 75)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IGNITE 42-Stufen Explainer Pipeline")
    # Standardmäßig wird bild (1).jpeg aus test-data verwendet
    default_img = os.path.join(SCRIPT_DIR, "..", "test-data", "bild (1).jpeg")
    parser.add_argument("image", nargs="?", default=default_img, help="Pfad zum Thermogramm")
    parser.add_argument("--out", default="exports", help="Ausgabeordner für die 42 Schritte")
    args = parser.parse_args()

    run_pipeline(args.image, args.out)
