# -*- coding: utf-8 -*-
"""gui/services/processing_service.py – Asynchronous Thermal Pipeline Engine."""

from __future__ import annotations
import threading
import logging
from typing import Callable, Any, Optional
import numpy as np
import cv2

import config
import image_processing
from utils import pixel_to_celsius, apply_radiometric_emissivity_correction


class ThermalProcessingService:
    """Thread-sicherer Dienst zur Ausführung der Bildverarbeitungs- und Diagnose-Pipeline."""

    _current_job_id: int = 0
    _lock = threading.Lock()

    @classmethod
    def process_async(
        cls,
        image_path: str,
        params: dict[str, Any],
        t_min_c: float,
        t_max_c: float,
        analysis_mode: str,
        colormap_name: str,
        emissivity: float,
        on_progress: Optional[Callable[[float, str], None]],
        on_success: Callable[[dict[str, Any]], None],
        on_error: Callable[[Exception], None],
    ) -> int:
        """Startet die Berechnung in einem Hintergrund-Thread mit Job-ID-Tracking."""
        with cls._lock:
            cls._current_job_id += 1
            job_id = cls._current_job_id

        def _worker():
            try:
                if on_progress:
                    on_progress(0.15, "Lade Wärmebild...")

                # 1. Bild laden
                raw_img = image_processing.load_thermal_image(image_path)

                with cls._lock:
                    if job_id != cls._current_job_id:
                        return

                if on_progress:
                    on_progress(0.35, "Kalibriere Temperatur-Offset...")

                # 2. Kalibrierungs-Offset anwenden
                to = params.get("temp_offset", 0.0)
                range_c = max(1.0, t_max_c - t_min_c)
                raw_offset = int(round(to * 255.0 / range_c))
                calibrated_img = np.clip(raw_img.astype(np.int16) + raw_offset, 0, 255).astype(np.uint8)

                with cls._lock:
                    if job_id != cls._current_job_id:
                        return

                if on_progress:
                    backend_name = image_processing.get_active_backend()
                    on_progress(0.60, f"Berechne Hotspots ({backend_name})...")

                # 3. Rust / GPU / Python Pipeline ausführen
                diff_vis, hotspot_mask = image_processing.run_rust_pipeline(
                    calibrated_img,
                    sigma_k=params.get("sigma_k", config.DEFAULT_SIGMA_K),
                    tophat_factor=params.get("tophat_factor", config.DEFAULT_TOPHAT_FACTOR),
                    min_area_factor=params.get("min_area_factor", config.DEFAULT_MIN_AREA_FACTOR),
                    min_circularity=params.get("min_circularity", config.DEFAULT_MIN_CIRCULARITY),
                    otsu_min=int(params.get("otsu_min", config.DEFAULT_OTSU_MIN)),
                    otsu_max=int(params.get("otsu_max", config.DEFAULT_OTSU_MAX)),
                    dist_erosion_factor=params.get("dist_erosion_factor", config.DEFAULT_DIST_EROSION_FACTOR),
                    use_mad=bool(params.get("use_mad", config.DEFAULT_USE_MAD))
                )

                with cls._lock:
                    if job_id != cls._current_job_id:
                        return

                if on_progress:
                    on_progress(0.85, "Analysiere Symmetrie & Zonen...")

                body_mask_vis = (diff_vis > 0).astype(np.uint8) * 255

                # 4. Asymmetrie-Analyse
                asym_results = image_processing.compute_contralateral_asymmetry(
                    calibrated_img, body_mask_vis, t_min_c, t_max_c, config.ASYMMETRY_THRESHOLD_C
                )

                # 5. Zonen & Hotspot-Objekte
                zonal_stats = cls._compute_zonal_stats(calibrated_img, body_mask_vis)
                general_hotspots = cls._compute_general_hotspots(calibrated_img, hotspot_mask)

                # 6. Diagnostisches Overlay erzeugen
                overlay_bgr = cls._render_overlay(
                    calibrated_img, body_mask_vis, hotspot_mask,
                    colormap_name=colormap_name,
                    analysis_mode=analysis_mode,
                    zonal_stats=zonal_stats,
                    general_hotspots=general_hotspots,
                    asym_results=asym_results,
                    t_min_c=t_min_c,
                    t_max_c=t_max_c
                )
                overlay_rgb = cv2.cvtColor(overlay_bgr, cv2.COLOR_BGR2RGB)

                # 7. Pixel-Statistiken über Gewebe
                body_pixels = calibrated_img[body_mask_vis > 0]
                if len(body_pixels) > 0:
                    mean_val = float(np.mean(body_pixels))
                    std_val = float(np.std(body_pixels))
                    max_val = float(np.max(body_pixels))
                    min_val = float(np.min(body_pixels))
                else:
                    mean_val, std_val, max_val, min_val = 0.0, 0.0, 0.0, 0.0

                hotspot_pixels = int(np.sum(hotspot_mask == 255))
                hotspot_ratio = (hotspot_pixels / len(body_pixels)) * 100.0 if len(body_pixels) > 0 else 0.0

                result = {
                    "job_id": job_id,
                    "image_path": image_path,
                    "raw_original": raw_img,
                    "calibrated_original": calibrated_img,
                    "body_mask": body_mask_vis,
                    "heat_diff": diff_vis,
                    "hotspot_mask": hotspot_mask,
                    "overlay_rgb": overlay_rgb,
                    "overlay_bgr": overlay_bgr,
                    "asym_results": asym_results,
                    "zonal_stats": zonal_stats,
                    "general_hotspots": general_hotspots,
                    "body_pixel_count": len(body_pixels),
                    "hotspot_pixel_count": hotspot_pixels,
                    "hotspot_ratio": hotspot_ratio,
                    "mean_pixel": mean_val,
                    "std_pixel": std_val,
                    "max_pixel": max_val,
                    "min_pixel": min_val,
                    "t_min_c": t_min_c,
                    "t_max_c": t_max_c,
                    "emissivity": emissivity,
                    "backend": image_processing.get_active_backend(),
                    "analysis_mode": analysis_mode,
                    "params": params
                }

                with cls._lock:
                    if job_id == cls._current_job_id:
                        on_success(result)

            except Exception as e:
                logging.error(f"[ProcessingService] Fehler in Pipeline-Job #{job_id}: {e}", exc_info=True)
                with cls._lock:
                    if job_id == cls._current_job_id:
                        on_error(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return job_id

    @staticmethod
    def _compute_zonal_stats(img: np.ndarray, body_mask: np.ndarray) -> dict[str, Any]:
        """Berechnet das klinische 3-Zonen-Modell für linken und rechten Fuß."""
        h, w = img.shape[:2]
        mid_x = w // 2

        stats = {
            "left": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False, "bbox": None},
            "right": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False, "bbox": None}
        }

        # Linker Fuß
        ly, lx = np.where(body_mask[:, :mid_x] > 0)
        if len(ly) > 0:
            min_y, max_y = int(ly.min()), int(ly.max())
            min_x, max_x = int(lx.min()), int(lx.max())
            h_zone = max(1, (max_y - min_y) // 3)

            z1 = (body_mask[min_y:min_y + h_zone, :mid_x] > 0)
            z2 = (body_mask[min_y + h_zone:min_y + 2 * h_zone, :mid_x] > 0)
            z3 = (body_mask[min_y + 2 * h_zone:max_y, :mid_x] > 0)

            p1 = img[min_y:min_y + h_zone, :mid_x][z1]
            p2 = img[min_y + h_zone:min_y + 2 * h_zone, :mid_x][z2]
            p3 = img[min_y + 2 * h_zone:max_y, :mid_x][z3]

            stats["left"]["fore"] = float(np.mean(p1)) if len(p1) > 0 else 0.0
            stats["left"]["mid"] = float(np.mean(p2)) if len(p2) > 0 else 0.0
            stats["left"]["heel"] = float(np.mean(p3)) if len(p3) > 0 else 0.0
            stats["left"]["exists"] = True
            stats["left"]["bbox"] = (min_x, min_y, max_x - min_x, max_y - min_y)

        # Rechter Fuß
        ry, rx = np.where(body_mask[:, mid_x:] > 0)
        if len(ry) > 0:
            min_y, max_y = int(ry.min()), int(ry.max())
            min_x, max_x = int(rx.min()) + mid_x, int(rx.max()) + mid_x
            h_zone = max(1, (max_y - min_y) // 3)

            z1 = (body_mask[min_y:min_y + h_zone, mid_x:] > 0)
            z2 = (body_mask[min_y + h_zone:min_y + 2 * h_zone, mid_x:] > 0)
            z3 = (body_mask[min_y + 2 * h_zone:max_y, mid_x:] > 0)

            p1 = img[min_y:min_y + h_zone, mid_x:][z1]
            p2 = img[min_y + h_zone:min_y + 2 * h_zone, mid_x:][z2]
            p3 = img[min_y + 2 * h_zone:max_y, mid_x:][z3]

            stats["right"]["fore"] = float(np.mean(p1)) if len(p1) > 0 else 0.0
            stats["right"]["mid"] = float(np.mean(p2)) if len(p2) > 0 else 0.0
            stats["right"]["heel"] = float(np.mean(p3)) if len(p3) > 0 else 0.0
            stats["right"]["exists"] = True
            stats["right"]["bbox"] = (min_x, min_y, max_x - min_x, max_y - min_y)

        return stats

    @staticmethod
    def _compute_general_hotspots(img: np.ndarray, hotspot_mask: np.ndarray) -> list[dict[str, Any]]:
        """Findet alle zusammenhängenden Hotspot-Regionen mit Metriken."""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(hotspot_mask)
        hotspots = []
        for i in range(1, num_labels):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            w = int(stats[i, cv2.CC_STAT_WIDTH])
            h = int(stats[i, cv2.CC_STAT_HEIGHT])
            area = int(stats[i, cv2.CC_STAT_AREA])

            mask_i = (labels == i)
            pixels = img[mask_i]
            mean_val = float(np.mean(pixels)) if len(pixels) > 0 else 0.0
            max_val = float(np.max(pixels)) if len(pixels) > 0 else 0.0

            hotspots.append({
                "index": i,
                "area": area,
                "mean_raw": mean_val,
                "max_raw": max_val,
                "bbox": (x, y, w, h),
                "center": (float(centroids[i][0]), float(centroids[i][1]))
            })

        hotspots.sort(key=lambda item: item["area"], reverse=True)
        for idx, item in enumerate(hotspots, start=1):
            item["index"] = idx
        return hotspots

    @staticmethod
    def _render_overlay(
        img: np.ndarray,
        body_mask: np.ndarray,
        hotspot_mask: np.ndarray,
        colormap_name: str,
        analysis_mode: str,
        zonal_stats: dict[str, Any],
        general_hotspots: list[dict[str, Any]],
        asym_results: dict[str, Any],
        t_min_c: float,
        t_max_c: float
    ) -> np.ndarray:
        """Rendert ein klares medizinisches Visualisierungs-Overlay."""
        # Colormap anwenden
        if colormap_name in ("Google Turbo", "Turbo", "Regenbogen (Jet)", "Jet"):
            base = cv2.applyColorMap(img, cv2.COLORMAP_TURBO if hasattr(cv2, "COLORMAP_TURBO") else cv2.COLORMAP_JET)
        elif colormap_name in ("Inferno", "Thermisch"):
            base = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
        elif colormap_name in ("Heiß (Hot)", "Hot"):
            base = cv2.applyColorMap(img, cv2.COLORMAP_HOT)
        else:
            base = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # Hotspot Neon-Rot Overlay (30% Base + 70% Rot)
        red_layer = np.zeros_like(base)
        red_layer[:] = [40, 40, 245]  # BGR
        blended = cv2.addWeighted(base, 0.35, red_layer, 0.65, 0)
        annotated = np.where(hotspot_mask[:, :, None] == 255, blended, base).astype(np.uint8)

        h, w = img.shape[:2]

        if analysis_mode == "Podologische Symmetrieanalyse":
            mid_x = w // 2
            # Symmetrie-Mittelachse
            cv2.line(annotated, (mid_x, 0), (mid_x, h), (200, 200, 200), 1, cv2.LINE_AA)

            # Zonen-Bounding Boxes zeichnen
            for side, color_box in [("left", (0, 220, 100)), ("right", (0, 220, 100))]:
                side_info = zonal_stats.get(side, {})
                if side_info.get("exists") and side_info.get("bbox"):
                    bx, by, bw, bh = side_info["bbox"]
                    cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), color_box, 1)

                    # Zonenlinien (3 Zonen)
                    hz = bh // 3
                    cv2.line(annotated, (bx, by + hz), (bx + bw, by + hz), (255, 180, 0), 1, cv2.LINE_AA)
                    cv2.line(annotated, (bx, by + 2 * hz), (bx + bw, by + 2 * hz), (255, 180, 0), 1, cv2.LINE_AA)

            # Asymmetrie-Banner oben
            if asym_results.get("status"):
                delta_t = asym_results.get("delta_t_c", 0.0)
                is_asym = asym_results.get("is_asymmetric", False)
                banner_color = (30, 30, 210) if is_asym else (25, 140, 45)
                cv2.rectangle(annotated, (0, 0), (w, 28), banner_color, -1)

                label = f"SYMMETRIE: Delta-T = {delta_t:.1f} C  ({'PATHOLOGISCH >2.2 C' if is_asym else 'NORMAL PHYSIOLOGISCH'})"
                cv2.putText(annotated, label, (12, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        else:
            # Allgemeine Hotspots einrahmen
            for hs in general_hotspots:
                bx, by, bw, bh = hs["bbox"]
                idx = hs["index"]
                cv2.rectangle(annotated, (bx, by), (bx + bw, by + bh), (255, 165, 0), 1)
                cv2.putText(annotated, f"H#{idx}", (bx, max(12, by - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 165, 0), 1, cv2.LINE_AA)

        return annotated
