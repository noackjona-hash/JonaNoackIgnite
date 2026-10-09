"""
generate_pipeline_film.py
Generiert einen hochwertigen Erklärfilm (Full HD 1080p @ 30 FPS, H.264 + AAC)
über alle Stufen der IGNITE-Bildverarbeitungs-Pipeline mit Hintergrundmusik
aus presentation/The_Geometry_of_Discovery.mp3.
"""

import os
import sys
import math
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------
# KONFIGURATION & PFADE
# -------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESENTATION_DIR = os.path.join(ROOT_DIR, "presentation")
AUDIO_FILE = os.path.join(PRESENTATION_DIR, "The_Geometry_of_Discovery.mp3")
OUTPUT_VIDEO = os.path.join(PRESENTATION_DIR, "IGNITE_Erklaerfilm_Pipeline_v5.mp4")

FFMPEG_BIN = r"C:\Users\jonan\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

W, H = 1920, 1080
FPS = 30
TOTAL_DURATION = 75.0  # Sekunden
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

# Schriftarten
FONT_TITLE_LARGE = ImageFont.truetype("C:/Windows/Fonts/seguibl.ttf", 44)
FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 34)
FONT_SUBTITLE = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 22)
FONT_STAGE_BADGE = ImageFont.truetype("C:/Windows/Fonts/seguibl.ttf", 19)
FONT_BODY = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 19)
FONT_BODY_BOLD = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 21)
FONT_MONO = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 15)
FONT_MONO_BOLD = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 17)

# Farbpalette (Obsidian Medical Theme)
COLOR_BG = (7, 9, 14)
COLOR_PANEL_BG = (14, 19, 30)
COLOR_PANEL_BORDER = (37, 99, 235)
COLOR_CYAN = (0, 240, 255)
COLOR_BLUE = (37, 99, 235)
COLOR_RED_ALERT = (255, 42, 85)
COLOR_GREEN_OK = (0, 230, 118)
COLOR_YELLOW = (255, 214, 0)
COLOR_TEXT_MAIN = (241, 245, 249)
COLOR_TEXT_MUTED = (148, 163, 184)
COLOR_GRID = (16, 22, 34)

# -------------------------------------------------------------
# ASSET-CACHE LADEN
# -------------------------------------------------------------
print("[1/4] Lade Pipeline-Bildassets in den Arbeitsspeicher...")

def load_img(rel_path, target_size=(1080, 810)):
    full_path = os.path.join(ROOT_DIR, rel_path)
    if os.path.exists(full_path):
        img = Image.open(full_path).convert("RGB")
        return img.resize(target_size, Image.Resampling.LANCZOS)
    return Image.new("RGB", target_size, (20, 25, 35))

img_cache = {
    "stage0": load_img("images/pap_stage0_raw_thermal.png"),
    "stage1": load_img("images/pap_stage1_body_mask.png"),
    "stage2_depth": load_img("images/pap_stage2_3d_depth_map.png"),
    "stage3_corr": load_img("images/pap_stage3_corrected_thermal.png"),
    "stage4_tophat": load_img("images/pap_stage4_tophat_diff.png"),
    "stage5_hotspot": load_img("images/pap_stage5_hotspot_mask.png"),
    "stage6_veins": load_img("images/pap_stage6_vascular_tree.png"),
    "stage7_overlay": load_img("images/pap_stage7_final_diagnosis_overlay.png"),
    "skizze_tophat": load_img("images/skizze_tophat_prinzip.png", (480, 270)),
    "skizze_mad": load_img("images/skizze_gauss_vs_mad.png", (480, 270)),
    "skizze_asym": load_img("images/skizze_asymmetrie_analyse.png", (480, 270)),
}

# -------------------------------------------------------------
# SZENEN-DEFINITIONEN
# -------------------------------------------------------------
SCENES = [
    {
        "id": "intro",
        "start": 0.0, "end": 7.0,
        "badge": "JUGEND FORSCHT 2026",
        "title": "IGNITE MEDICAL IMAGING SUITE",
        "subtitle": "Automatisierte Infrarot-Thermografie zur Entzündungs-Früherkennung",
        "type": "title_card"
    },
    {
        "id": "stage0",
        "start": 7.0, "end": 14.0,
        "badge": "STUFE 0: AUSGANGSLAGE",
        "title": "DAS KLINISCHE DILEMMA",
        "subtitle": "Kühle distale Zehe vs. warme physiologische Fußsohle",
        "img_key": "stage0",
        "callouts": [
            {
                "target": (451, 389), "box_w": 420, "box_h": 62,
                "box_pos": (490, 270),
                "title": "AKUTE PHLEGMONE (ZEH)",
                "sub": "Kühle Peripherie (24-28 °C), aber akuter Entzündungs-Peak!",
                "color": COLOR_RED_ALERT
            },
            {
                "target": (705, 655), "box_w": 420, "box_h": 62,
                "box_pos": (60, 680),
                "title": "PHYSIOLOGISCHE WÄRME (SOHLE)",
                "sub": "Plantarsohle (~34 °C) überstrahlt naive globale Schwellen!",
                "color": COLOR_YELLOW
            }
        ],
        "points": [
            ("Herausforderung:", "Klassische globale Schwellenwerte versagen"),
            ("Fehlerrisiko:", "Sohle wird fälschlich als 'Hotspot' markiert"),
            ("Gefahr:", "Echte Zehen- und Fingerentzündungen werden übersehen"),
            ("IGNITE-Lösung:", "7-stufige biophysikalische Bildverarbeitungs-Pipeline")
        ]
    },
    {
        "id": "stage1",
        "start": 14.0, "end": 22.0,
        "badge": "STUFE 1 / 7",
        "title": "ADAPTIVE GEWEBESEGMENTIERUNG",
        "subtitle": "Multi-Otsu Binarisierung, Akren-Erhaltung & Randschutz",
        "img_key": "stage1",
        "points": [
            ("Verfahren:", "Multi-Otsu Intra-Klassen-Minimierung"),
            ("Artefakt-Filter:", "4-Wege BFS entfernt Raum- & Betttuchrauschen (< 2%)"),
            ("Innovation:", "Chamfer-L2 Distanzerosion auf 0,5% (1-2 px) minimiert"),
            ("Akren-Erhaltung:", "Schmale Zehen- und Fingerkuppen bleiben 100% intakt"),
            ("Hardware:", "Parallele Goroutinen auf allen CPU-Kernen (19.6 ms)")
        ]
    },
    {
        "id": "stage2",
        "start": 22.0, "end": 30.0,
        "badge": "STUFE 2 / 7",
        "title": "3D-OBERFLÄCHE & WINKELKORREKTUR",
        "subtitle": "Physikalisch kalibrierte Lambertian-LWIR-Kompensation",
        "img_key": "stage2_depth",
        "inset_key": "stage3_corr",
        "points": [
            ("3D-Modell:", "Shape-from-Silhouette Höhenfeld Z(x,y) & Normalen"),
            ("Physik:", "Fresnel- & Lambert-Emissivitätsabfall bei Schrägwinkeln"),
            ("Problem früher:", "Unkalibriertes Modell erzeugte +3.5 K Kunst-Hitze"),
            ("Kalibrierung:", "Gedeckelt auf k_theta <= 1.2 K (max 12 Einheiten)"),
            ("Klinischer Nutzen:", "Gleicht Randabfall aus, ohne die Sohle aufzublähen")
        ]
    },
    {
        "id": "stage3",
        "start": 30.0, "end": 38.0,
        "badge": "STUFE 3 / 7",
        "title": "MULTI-SCALE TOP-HAT FILTERUNG",
        "subtitle": "AVX2 SIMD Hardware-Inner-Loop für 1D-Lemire Operatoren",
        "img_key": "stage4_tophat",
        "inset_key": "skizze_tophat",
        "points": [
            ("Mathematik:", "TopHat(I) = I - Opening_K(I) = I - ((I (-) K) (+) K)"),
            ("Wirkung:", "Subtrahiert glatte Verläufe, isoliert Hitzespitzen"),
            ("Assembler-Core:", "x86_64 Plan9 AVX2 (VPMINUB, VPMAXUB, VPSUBUSB)"),
            ("Durchsatz:", "32 Pixel GLEICHZEITIG pro CPU-Taktzyklus"),
            ("Latenz:", "1.4 ms (@160x120) / 37.8 ms (@1440x1080) in Go!")
        ]
    },
    {
        "id": "stage4",
        "start": 38.0, "end": 46.0,
        "badge": "STUFE 4 / 7",
        "title": "STATISTISCHES OUTLIER-THRESHOLDING",
        "subtitle": "Robustes MAD-Verfahren mit biologischer Gewebeschwelle",
        "img_key": "stage5_hotspot",
        "inset_key": "skizze_mad",
        "points": [
            ("Bimodales Problem:", "Kalte Zehen verzerren arithmetischen Mittelwert"),
            ("MAD-Lösung:", "Median Absolute Deviation: T_mad = Median + k * 1.48 * MAD"),
            ("Vitalitätsschwelle:", "TissueFloor = min(max(Median * 0.55, 45), 80)"),
            ("Schutz:", "Kühle Extremitäten (24-30 °C) werden NICHT verworfen"),
            ("Hardware:", "Vektorisierter SIMD thresholdMaskAVX2 Kernel")
        ]
    },
    {
        "id": "stage5",
        "start": 46.0, "end": 54.0,
        "badge": "STUFE 5 / 7",
        "title": "VASKULÄRE VEIN-KARTIERUNG",
        "subtitle": "Multiskaliger Frangi-Vesselness Filter auf 2D-Hesse-Matrix",
        "img_key": "stage6_veins",
        "points": [
            ("Hesse-Matrix:", "H = [[I_xx, I_xy], [I_xy, I_yy]] über 3 Skalen"),
            ("Differenzierung:", "Blobness R_B trennt runde Entzündungen von Venen"),
            ("SIMD-FMA:", "8 Float32-Werte parallel mit VMULPS & VADDPS"),
            ("Sicherheit:", "Verhindert Fehldiagnosen durch oberflächliche Blutgefäße"),
            ("Mehrwert:", "Dient Pflegepersonal zugleich als digitaler Venenfinder")
        ]
    },
    {
        "id": "stage6",
        "start": 54.0, "end": 62.0,
        "badge": "STUFE 6 / 7",
        "title": "BIOPHYSIKALISCHE DTBC-KLASSIFIKATION",
        "subtitle": "Entzündung vs. Druckstelle & Armstrong-Seitenvergleich",
        "img_key": "stage7_overlay",
        "inset_key": "skizze_asym",
        "points": [
            ("DTBC-Biophysik:", "Entzündungs-Halo (Delta_T_halo >= 0.5 K) vs. Keratin"),
            ("Laplace-Flux:", "Laplace T << 0 detektiert metabolische Wärmequelle"),
            ("Armstrong-Kriterium:", "Bilateraler Spiegelvergleich: Delta_T >= 2.2 K"),
            ("Lua-Regelengine:", "Regeln in rules/ ohne Neukompilierung editierbar"),
            ("Diagnose:", "Phlegmone vs. Druckstelle vs. pAVK-Gradient dT/dy")
        ]
    },
    {
        "id": "stage7",
        "start": 62.0, "end": 70.0,
        "badge": "STUFE 7 / 7",
        "title": "KLINISCHES SEVERITY-RANKING",
        "subtitle": "Zielgenaue Priorisierung des Zehenherdes als Fund #1",
        "img_key": "stage7_overlay",
        "callouts": [
            {
                "target": (451, 389), "box_w": 440, "box_h": 62,
                "box_pos": (490, 270),
                "title": "HERD #1 [KRITISCH]",
                "sub": "Großzehe rechts • Score: 9.8 • ΔT = +5.2 K (Armstrong Stufe 3)",
                "color": COLOR_RED_ALERT
            }
        ],
        "points": [
            ("Triage-Formel:", "Priority = Score_Lua * 100 + Delta_T_focal"),
            ("Volltreffer:", "Akuter Herd auf dem Zeh erhält höchste Priorität"),
            ("Eliminiert:", "Diffuse physiologische Sohlenwärme sicher de-priorisiert"),
            ("Visualisierung:", "Obsidian Medical Workstation mit Vorhang-Wipe & 2.5D"),
            ("Gesamtlaufzeit:", "169.5 ms End-to-End @ 1440x1080 (0.0 ms CPU Rendering)")
        ]
    },
    {
        "id": "outro",
        "start": 70.0, "end": 75.0,
        "badge": "FAZIT & HIGHLIGHTS",
        "title": "IGNITE: DIAGNOSTIK DER NÄCHSTEN GENERATION",
        "subtitle": "Deterministisch • DSGVO-konform • Echtzeitfähig",
        "type": "summary_card"
    }
]

# -------------------------------------------------------------
# FRAME-RENDERING ENGINE
# -------------------------------------------------------------
def render_frame(frame_idx):
    t = frame_idx / FPS
    active_scene = SCENES[-1]
    for s in SCENES:
        if s["start"] <= t < s["end"]:
            active_scene = s
            break

    frame = Image.new("RGB", (W, H), COLOR_BG)
    draw = ImageDraw.Draw(frame)

    # Grid
    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=COLOR_GRID, width=1)
    for x in range(0, W, 60):
        draw.line([(x, 0), (x, H)], fill=COLOR_GRID, width=1)

    # Top Header Bar
    draw.rectangle([(0, 0), (W, 72)], fill=(11, 16, 26))
    draw.line([(0, 72), (W, 72)], fill=COLOR_CYAN, width=2)

    # Pulse Dot
    pulse_radius = 5 + int(2 * math.sin(t * 6))
    draw.ellipse([(38 - pulse_radius, 36 - pulse_radius), (38 + pulse_radius, 36 + pulse_radius)], fill=COLOR_CYAN)
    draw.text((54, 18), "IGNITE MEDICAL WORKSTATION v5.0", font=FONT_TITLE, fill=COLOR_CYAN)

    header_meta = f"STAGE PIPELINE WALKTHROUGH  •  {t:.1f}s / {TOTAL_DURATION:.0f}s"
    draw.text((W - 540, 26), header_meta, font=FONT_SUBTITLE, fill=COLOR_TEXT_MUTED)

    # Bottom Progress Bar & Stepper
    draw.rectangle([(0, H - 64), (W, H)], fill=(11, 16, 26))
    draw.line([(0, H - 64), (W, H - 64)], fill=COLOR_BLUE, width=2)

    # Animated Progress Line
    prog_pct = min(1.0, t / TOTAL_DURATION)
    draw.line([(0, H - 64), (int(W * prog_pct), H - 64)], fill=COLOR_CYAN, width=4)

    # Stepper Text (kompakt ohne Überlappung)
    stepper_text = "PIPELINE: [0. ROHBILD] > [1. OTSU] > [2. 3D] > [3. TOP-HAT] > [4. MAD] > [5. FRANGI] > [6. DTBC] > [7. RANKING]"
    draw.text((40, H - 46), stepper_text, font=FONT_MONO, fill=COLOR_TEXT_MUTED)

    hud_stat = "AVX2 SIMD: 1.4 ms  |  DSGVO: 100% LOKAL"
    draw.text((W - 440, H - 46), hud_stat, font=FONT_MONO_BOLD, fill=COLOR_CYAN)

    scene_type = active_scene.get("type", "stage")

    if scene_type == "title_card":
        p_w, p_h = 1300, 680
        p_x0, p_y0 = (W - p_w) // 2, 160
        draw.rounded_rectangle([(p_x0, p_y0), (p_x0 + p_w, p_y0 + p_h)], radius=20, fill=COLOR_PANEL_BG, outline=COLOR_CYAN, width=3)

        # Dynamischer Badge
        badge_text = active_scene["badge"]
        bbox = FONT_STAGE_BADGE.getbbox(badge_text)
        badge_w = (bbox[2] - bbox[0]) + 30
        draw.rounded_rectangle([(p_x0 + 60, p_y0 + 55), (p_x0 + 60 + badge_w, p_y0 + 98)], radius=8, fill=COLOR_CYAN)
        draw.text((p_x0 + 75, p_y0 + 64), badge_text, font=FONT_STAGE_BADGE, fill=COLOR_BG)

        draw.text((p_x0 + 60, p_y0 + 135), active_scene["title"], font=FONT_TITLE_LARGE, fill=(255, 255, 255))
        draw.text((p_x0 + 60, p_y0 + 205), active_scene["subtitle"], font=FONT_TITLE, fill=COLOR_CYAN)

        draw.line([(p_x0 + 60, p_y0 + 275), (p_x0 + p_w - 60, p_y0 + 275)], fill=COLOR_PANEL_BORDER, width=2)

        feature_boxes = [
            ("HOCHAUFLOESEND & DETERMINISTISCH", "Keine Black-Box Halluzinationen - 100% mathematische Nachvollziehbarkeit"),
            ("HARDWARE-INNER-LOOP IN AVX2", "6 dedizierte Assembler-Kernels in Go Plan9 - 1,4 ms Latenz voellig C-compilerfrei"),
            ("UNIVERSELLE AKREN-ERHALTUNG", "0,5% Chamfer-Erosion + Randschutz bewahren Zehen & Finger vor dem Wegschneiden"),
            ("KLINISCHE SEVERITY-TRIAGE", "Physiologische Sohlenwaerme de-priorisiert - akute Herde zielgenau als #1 markiert")
        ]

        f_y = p_y0 + 310
        for f_title, f_desc in feature_boxes:
            draw.text((p_x0 + 60, f_y + 2), f_title, font=FONT_BODY_BOLD, fill=COLOR_CYAN)
            draw.text((p_x0 + 60, f_y + 32), f_desc, font=FONT_BODY, fill=COLOR_TEXT_MAIN)
            f_y += 78

    elif scene_type == "summary_card":
        p_w, p_h = 1300, 680
        p_x0, p_y0 = (W - p_w) // 2, 160
        draw.rounded_rectangle([(p_x0, p_y0), (p_x0 + p_w, p_y0 + p_h)], radius=20, fill=COLOR_PANEL_BG, outline=COLOR_GREEN_OK, width=3)

        badge_text = active_scene["badge"]
        bbox = FONT_STAGE_BADGE.getbbox(badge_text)
        badge_w = (bbox[2] - bbox[0]) + 30
        draw.rounded_rectangle([(p_x0 + 60, p_y0 + 55), (p_x0 + 60 + badge_w, p_y0 + 98)], radius=8, fill=COLOR_GREEN_OK)
        draw.text((p_x0 + 75, p_y0 + 64), badge_text, font=FONT_STAGE_BADGE, fill=COLOR_BG)

        draw.text((p_x0 + 60, p_y0 + 135), active_scene["title"], font=FONT_TITLE_LARGE, fill=(255, 255, 255))
        draw.text((p_x0 + 60, p_y0 + 205), active_scene["subtitle"], font=FONT_TITLE, fill=COLOR_GREEN_OK)

        draw.line([(p_x0 + 60, p_y0 + 275), (p_x0 + p_w - 60, p_y0 + 275)], fill=COLOR_PANEL_BORDER, width=2)

        summary_stats = [
            ("Erkennungsgenauigkeit:", "100% Recall auf akut entzuendeter Grosszehe (bild 1)"),
            ("Fehlalarm-Unterdrueckung:", "0 Falsch-Positive auf physiologischer Fusssohle"),
            ("Universelle Eignung:", "Anatomie-agnostisch fuer Fuesse, Haende, Knie, Ruecken"),
            ("Technologie-Stack:", "Go 1.27 Core - Plan9 AVX2 - C# .NET 10 WPF - Lua Rules"),
            ("Wettbewerb:", "Stiftung Jugend forscht e. V. 2026 - Autor: Jona Noack")
        ]

        s_y = p_y0 + 310
        for s_lbl, s_val in summary_stats:
            draw.text((p_x0 + 60, s_y), s_lbl, font=FONT_BODY_BOLD, fill=COLOR_CYAN)
            draw.text((p_x0 + 380, s_y), s_val, font=FONT_BODY, fill=COLOR_TEXT_MAIN)
            s_y += 66

    else:
        # Standard Stage View
        img_key = active_scene.get("img_key", "stage0")
        stage_img = img_cache.get(img_key)
        if stage_img:
            s_w, s_h = 1080, 810
            frame.paste(stage_img, (50, 115))
            draw.rectangle([(48, 113), (50 + s_w + 2, 115 + s_h + 2)], outline=COLOR_CYAN, width=2)

            # Inset Schema
            inset_key = active_scene.get("inset_key")
            if inset_key and inset_key in img_cache:
                inset_img = img_cache[inset_key]
                in_w, in_h = 360, 202
                resized_inset = inset_img.resize((in_w, in_h), Image.Resampling.LANCZOS)
                in_x, in_y = 50 + s_w - in_w - 20, 115 + s_h - in_h - 20
                frame.paste(resized_inset, (in_x, in_y))
                draw.rectangle([(in_x - 2, in_y - 2), (in_x + in_w + 2, in_y + in_h + 2)], outline=COLOR_YELLOW, width=2)
                draw.rectangle([(in_x, in_y), (in_x + 130, in_y + 28)], fill=(11, 16, 26))
                draw.text((in_x + 8, in_y + 4), "MATHE-SCHEMA", font=FONT_MONO, fill=COLOR_YELLOW)

            # Exakte Callout-Retikel & Fadenkreuze
            if "callouts" in active_scene:
                for c in active_scene["callouts"]:
                    tx, ty = c["target"]
                    bx, by = c["box_pos"]
                    bw, bh = c["box_w"], c["box_h"]
                    col = c["color"]

                    # Ziel-Fadenkreuz
                    rad = 22 + int(3 * math.sin(t * 8))
                    draw.ellipse([(tx - rad, ty - rad), (tx + rad, ty + rad)], outline=col, width=2)
                    draw.line([(tx - rad - 8, ty), (tx + rad + 8, ty)], fill=col, width=2)
                    draw.line([(tx, ty - rad - 8), (tx, ty + rad + 8)], fill=col, width=2)

                    # Leader Line zum Info-Kasten
                    target_anchor = (bx if bx > tx else bx + bw, by + bh // 2)
                    draw.line([(tx, ty), target_anchor], fill=col, width=2)

                    # Info Kasten
                    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=8, fill=(11, 16, 26), outline=col, width=2)
                    draw.text((bx + 12, by + 8), c["title"], font=FONT_STAGE_BADGE, fill=col)
                    draw.text((bx + 12, by + 34), c["sub"], font=FONT_MONO, fill=COLOR_TEXT_MAIN)

        # Infokarte rechts
        card_x0, card_y0 = 1170, 115
        card_x1, card_y1 = 1870, 925
        draw.rounded_rectangle([(card_x0, card_y0), (card_x1, card_y1)], radius=16, fill=COLOR_PANEL_BG, outline=COLOR_PANEL_BORDER, width=2)

        # Dynamischer Badge
        badge_text = active_scene["badge"]
        bbox = FONT_STAGE_BADGE.getbbox(badge_text)
        badge_w = (bbox[2] - bbox[0]) + 30
        draw.rounded_rectangle([(card_x0 + 30, card_y0 + 30), (card_x0 + 30 + badge_w, card_y0 + 72)], radius=8, fill=COLOR_CYAN)
        draw.text((card_x0 + 45, card_y0 + 38), badge_text, font=FONT_STAGE_BADGE, fill=COLOR_BG)

        draw.text((card_x0 + 30, card_y0 + 90), active_scene["title"], font=FONT_TITLE, fill=(255, 255, 255))
        draw.text((card_x0 + 30, card_y0 + 135), active_scene["subtitle"], font=FONT_SUBTITLE, fill=COLOR_CYAN)

        draw.line([(card_x0 + 30, card_y0 + 180), (card_x1 - 30, card_y0 + 180)], fill=COLOR_PANEL_BORDER, width=1)

        # Feature Points
        pts = active_scene.get("points", [])
        cur_y = card_y0 + 205
        for p_lbl, p_val in pts:
            draw.text((card_x0 + 30, cur_y), p_lbl, font=FONT_BODY_BOLD, fill=COLOR_CYAN)
            draw.text((card_x0 + 30, cur_y + 28), p_val, font=FONT_BODY, fill=COLOR_TEXT_MAIN)
            cur_y += 72

    return np.array(frame)[:, :, ::-1]

# -------------------------------------------------------------
# FFMPEG PIPELINE & ENCODING
# -------------------------------------------------------------
def main():
    print(f"[2/4] Initialisiere Video-Encoder ({TOTAL_FRAMES} Frames, {FPS} FPS, Dauer: {TOTAL_DURATION}s)...")
    
    audio_fade_filter = f"afade=t=in:ss=0:d=1.5,afade=t=out:st={TOTAL_DURATION - 3.0}:d=3.0"

    ffmpeg_cmd = [
        FFMPEG_BIN,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "bgr24",
        "-r", str(FPS),
        "-i", "-",
        "-ss", "0",
        "-t", str(TOTAL_DURATION),
        "-i", AUDIO_FILE,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-af", audio_fade_filter,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]

    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

    print("[3/4] Generiere und streame Frames direkt an FFmpeg...")
    for idx in range(TOTAL_FRAMES):
        bgr_frame = render_frame(idx)
        proc.stdin.write(bgr_frame.tobytes())
        if (idx + 1) % 150 == 0 or idx == TOTAL_FRAMES - 1:
            pct = (idx + 1) / TOTAL_FRAMES * 100
            t_cur = (idx + 1) / FPS
            sys.stdout.write(f"\r  > Fortschritt: {idx + 1}/{TOTAL_FRAMES} Frames ({pct:.1f}%) | Film-Zeit: {t_cur:.1f}s")
            sys.stdout.flush()

    print("\n[4/4] Schliesse Videodatenstrom und finalisiere MP4...")
    proc.stdin.close()
    proc.wait()

    if proc.returncode == 0 and os.path.exists(OUTPUT_VIDEO):
        size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
        print(f"\n[OK] ERFOLGREICH! Erklaerfilm erstellt:\n     Pfad: {os.path.abspath(OUTPUT_VIDEO)}\n     Dateigroesse: {size_mb:.2f} MB")
    else:
        print(f"\n[!] Fehler beim Enkodieren! Returncode: {proc.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    main()
