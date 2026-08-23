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
                    on_progress(0.30, "Kalibriere Temperatur-Offset...")

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
                    on_progress(0.55, f"Berechne Multi-Skalen Hotspots ({backend_name})...")

                # 3. Multi-Scale Hotspot Pipeline ausführen
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
                    on_progress(0.75, "Analysiere PCA-Ausrichtung & thermische Gradienten...")

                body_mask_vis = (diff_vis > 0).astype(np.uint8) * 255

                # 4. Thermischer Gradientenfluss & Laplace-Divergenz
                gradient_results = image_processing.compute_thermal_gradients_and_divergence(
                    calibrated_img, body_mask_vis
                )

                # 5. Kontralaterale Asymmetrie-Analyse inklusive PCA-Ausrichtung
                asym_results = image_processing.compute_contralateral_asymmetry(
                    calibrated_img, body_mask_vis, t_min_c, t_max_c, config.ASYMMETRY_THRESHOLD_C
                )
                pca_results = asym_results.get("pca")

                # 6. Zonen-Statistiken (PCA-unterstützt) & Hotspot-Objekte
                zonal_stats = cls._compute_zonal_stats(calibrated_img, body_mask_vis, pca_results)
                general_hotspots = cls._compute_general_hotspots(calibrated_img, hotspot_mask)

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

                # 8. Evidenzbasierter Thermal Severity Index (TSI)
                delta_t = asym_results.get("delta_t_c", 0.0)
                tsi_results = image_processing.compute_thermal_severity_index(
                    delta_t_c=delta_t,
                    hotspot_pixel_count=hotspot_pixels,
                    body_pixel_count=len(body_pixels),
                    max_gradient=gradient_results.get("max_gradient", 0.0),
                    std_pixel=std_val
                )

                # 9. Bilaterale Kontralaterale Registrierungs- & Subtraktionskarte
                bilateral_map_results = image_processing.compute_bilateral_asymmetry_map(
                    calibrated_img, body_mask_vis, t_min_c, t_max_c
                )

                # 10. Pennes Bioheat Wärmeflussdichte-Vektorfeld
                bioheat_results = image_processing.compute_pennes_bioheat_flux(
                    calibrated_img, body_mask_vis, t_min_c, t_max_c
                )

                # 11. Frangi Vesselness Filter (Gefäß- & Venenstruktur-Erkennung)
                frangi_vesselness = image_processing.compute_frangi_vesselness_filter(
                    calibrated_img, body_mask_vis
                )

                # 12. Adaptive Doppel-Schwellenwert-Hysterese
                hysteresis_mask = image_processing.apply_hysteresis_thresholding(
                    diff_vis, body_mask_vis,
                    k_high=params.get("hysteresis_k_high", config.DEFAULT_HYSTERESIS_K_HIGH),
                    k_low=params.get("hysteresis_k_low", config.DEFAULT_HYSTERESIS_K_LOW),
                    use_mad=bool(params.get("use_mad", config.DEFAULT_USE_MAD))
                )

                # 13. Diagnostisches Overlay erzeugen
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

                result = {
                    "job_id": job_id,
                    "image_path": image_path,
                    "raw_original": raw_img,
                    "calibrated_original": calibrated_img,
                    "body_mask": body_mask_vis,
                    "heat_diff": diff_vis,
                    "hotspot_mask": hotspot_mask,
                    "hysteresis_mask": hysteresis_mask,
                    "frangi_vesselness": frangi_vesselness,
                    "bilateral_map_results": bilateral_map_results,
                    "bioheat_results": bioheat_results,
                    "overlay_rgb": overlay_rgb,
                    "overlay_bgr": overlay_bgr,
                    "asym_results": asym_results,
                    "zonal_stats": zonal_stats,
                    "general_hotspots": general_hotspots,
                    "gradient_results": gradient_results,
                    "pca_results": pca_results,
                    "tsi_results": tsi_results,
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
    def _compute_zonal_stats(img: np.ndarray, body_mask: np.ndarray, pca_results: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Berechnet das klinische 3-Zonen-Modell mit bevorzugter PCA-Hauptachsenorientierung."""
        if pca_results and pca_results.get("left", {}).get("exists") and pca_results.get("right", {}).get("exists"):
            l_info = pca_results["left"]
            r_info = pca_results["right"]
            return {
                "left": {
                    "fore": l_info["fore_c"],
                    "mid": l_info["mid_c"],
                    "heel": l_info["heel_c"],
                    "exists": True,
                    "bbox": l_info.get("bbox"),
                    "angle_deg": l_info.get("angle_deg", 0.0)
                },
                "right": {
                    "fore": r_info["fore_c"],
                    "mid": r_info["mid_c"],
                    "heel": r_info["heel_c"],
                    "exists": True,
                    "bbox": r_info.get("bbox"),
                    "angle_deg": r_info.get("angle_deg", 0.0)
                }
            }

        # Fallback Bounding-Box
        h, w = img.shape[:2]
        mid_x = w // 2

        stats = {
            "left": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False, "bbox": None, "angle_deg": 0.0},
            "right": {"fore": 0.0, "mid": 0.0, "heel": 0.0, "exists": False, "bbox": None, "angle_deg": 0.0}
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
                "id": i,
                "bbox": (x, y, w, h),
                "area_px": area,
                "mean_intensity": mean_val,
                "max_intensity": max_val,
                "center": (int(centroids[i][0]), int(centroids[i][1]))
            })
        return hotspots

    @classmethod
    def _render_overlay(
        cls,
        calibrated_img: np.ndarray,
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
        """Erzeugt das diagnostische Overlay mit Bounding-Boxen und Annotationen."""
        # Colormap anwenden
        from gui.utils_ui import apply_colormap_to_image
        base_rgb = apply_colormap_to_image(calibrated_img, colormap_name)
        base_bgr = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2BGR)

        # Rote Hotspots einblenden
        red_layer = np.zeros_like(base_bgr)
        red_layer[:] = [0, 0, 255]
        blended = cv2.addWeighted(base_bgr, 0.4, red_layer, 0.6, 0)
        overlay = np.where(hotspot_mask[:, :, None] == 255, blended, base_bgr).astype(np.uint8)

        # Hotspot Bounding-Boxen
        for hs in general_hotspots:
            x, y, w, h = hs["bbox"]
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), 1)

        # Podologie-Zonen markieren falls im Podologie-Modus
        if analysis_mode == "Podologische Symmetrieanalyse":
            for side in ["left", "right"]:
                info = zonal_stats.get(side, {})
                if info.get("exists") and info.get("bbox"):
                    bx, by, bw, bh = info["bbox"]
                    cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (255, 200, 0), 1)
                    h3 = bh // 3
                    cv2.line(overlay, (bx, by + h3), (bx + bw, by + h3), (255, 200, 0), 1)
                    cv2.line(overlay, (bx, by + 2 * h3), (bx + bw, by + 2 * h3), (255, 200, 0), 1)

        return overlay
