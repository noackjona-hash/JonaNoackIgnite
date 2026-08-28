# -*- coding: utf-8 -*-
"""image_processing.py – High-Performance Multi-Modal Thermal Analysis Pipeline for IGNITE.

Enthält die vollständige Signal- und Bildverarbeitungs-Pipeline:
1. Multi-Otsu & Adaptive Distanz-Gewebesegmentierung
2. Multi-Scale Morphological Top-Hat (MTH) zur Hotspot-Extraktion
3. Thermische Gradientenfluss- & 2D-Laplace-Divergenzanalyse
4. PCA-gestützte anatomische Fußausrichtung (Principal Component Alignment)
5. Evidenzbasierter Thermal Severity Index (TSI) & IWGDF-Risikoklassifikation
"""

from typing import Tuple, Optional, Any, Dict
import os
import warnings
import cv2
import numpy as np
import logging
import config as _config

# ─────────────────────────────────────────────────────────────────────────────
# Lazy GPU- & Rust-Core-Erkennung mit Fallback-Mechanismus
# ─────────────────────────────────────────────────────────────────────────────
_RUST_BACKEND_AVAILABLE = False
_ignite_core: Optional[object] = None
_GPU_AVAILABLE = False
_GPU_INITIALIZED = False
_TORCH = None

# Rust-Core importieren
try:
    import ignite_core as _ignite_core
    _RUST_BACKEND_AVAILABLE = True
except ImportError:
    pass

def _init_gpu() -> bool:
    """Initialisiert GPU lazily, wird nur aufgerufen wenn GPU tatsächlich benötigt wird."""
    global _GPU_AVAILABLE, _GPU_INITIALIZED, _TORCH
    
    if _GPU_INITIALIZED:
        return _GPU_AVAILABLE
    
    _GPU_INITIALIZED = True
    
    try:
        import importlib
        torch = importlib.import_module("torch")
        _TORCH = torch
        if torch.cuda.is_available():
            try:
                major, minor = torch.cuda.get_device_capability(0)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    _dummy = torch.zeros(1, device="cuda")
                _GPU_AVAILABLE = True
                logging.info(f"GPU-Beschleunigung verfügbar: {torch.cuda.get_device_name(0)} (CC {major}.{minor})")
            except Exception as inner_e:
                logging.debug(f"CUDA-Device inkompatibel oder nicht nutzbar: {inner_e}")
                _GPU_AVAILABLE = False
    except Exception as e:
        logging.debug(f"GPU-Initialisierung fehlgeschlagen: {e}")
        _GPU_AVAILABLE = False
    
    return _GPU_AVAILABLE

if _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
    logging.info(
        f"Rust-Backend verfügbar: {getattr(_ignite_core, '__backend__', 'CPU+rayon (Rust-native)')} "
        f"(v{getattr(_ignite_core, '__version__', 'unknown')})"
    )
else:
    logging.warning(
        "WARNUNG: Rust-Backend nicht verfügbar! "
        "Nutze Python-Fallback-Pipeline (langsamer)."
    )

def get_active_backend() -> str:
    """Gibt den Namen des aktuell genutzten Berechnungs-Backends zurück."""
    if _init_gpu() and _GPU_AVAILABLE:
        return f"GPU (CUDA, {_TORCH.cuda.get_device_name(0)})"
    elif _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
        return getattr(_ignite_core, "__backend__", "CPU+rayon (Rust-native)")
    else:
        return "Python-Fallback"

def compute_odd_kernel(dimension: int, factor: float) -> int:
    """Berechnet eine ungerade Kernelgröße als Prozentsatz der minimalen Bilddimension min(W, H)."""
    raw = int(dimension * factor)
    odd = max(1, raw | 1)
    return max(3, odd)

# ─────────────────────────────────────────────────────────────────────────────
# 1. BILD LADEN (8-BIT, 16-BIT RADIOMETRISCH, TIFF, RJPG, NPY)
# ─────────────────────────────────────────────────────────────────────────────
def _extract_flir_radiometric_raw(filepath: str) -> Optional[np.ndarray]:
    """
    Sucht in einer JPEG-Datei nach eingebetteten FLIR-Radiometriedaten im APP1-Segment.
    Gibt die 16-Bit Roh-Temperaturmatrix zurück oder None, wenn keine Daten vorhanden sind.
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()

        flir_tag = b"FLIR\x00"
        idx = 0
        while True:
            idx = data.find(b"\xff\xe1", idx)
            if idx == -1 or idx + 4 >= len(data):
                break
            length = int.from_bytes(data[idx+2:idx+4], "big")
            segment = data[idx+4:idx+2+length]
            if segment.startswith(flir_tag):
                raw_png_idx = segment.find(b"\x89PNG\r\n\x1a\n")
                if raw_png_idx != -1:
                    png_bytes = segment[raw_png_idx:]
                    raw_arr = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                    if raw_arr is not None:
                        return raw_arr
            idx += 2 + length
    except Exception as e:
        logging.debug(f"FLIR APP1 Parsing übersprungen: {e}")
    return None


def _normalize_loaded_matrix(
    img: np.ndarray,
    t_min: float = _config.DEFAULT_TEMP_MIN,
    t_max: float = _config.DEFAULT_TEMP_MAX
) -> np.ndarray:
    """Konvertiert beliebige Bildmatrizen (16-Bit, Float, Multi-Kanal) in ein 8-Bit Graustufenbild."""
    # Mehrkanalige Bilder (z.B. RGB/BGR/RGBA)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = img[:, :, :3]
        if img.shape[2] == 3:
            if np.array_equal(img[:, :, 0], img[:, :, 1]) and np.array_equal(img[:, :, 1], img[:, :, 2]):
                img = img[:, :, 0]
            else:
                # Perzeptive Graustufenkonvertierung (ITU-R BT.601)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.dtype == np.uint8 else (
                    0.299 * img[:, :, 2] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 0]
                ).astype(img.dtype)

    # 16-Bit, 32-Bit Float oder Integer-Daten kalibrieren
    if img.dtype == np.uint16 or np.issubdtype(img.dtype, np.floating) or img.dtype == np.int32:
        from utils import convert_16bit_radiometric_to_8bit
        return convert_16bit_radiometric_to_8bit(img, t_min=t_min, t_max=t_max)

    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)

    return img


def load_thermal_image(
    filepath: str,
    t_min: float = _config.DEFAULT_TEMP_MIN,
    t_max: float = _config.DEFAULT_TEMP_MAX
) -> np.ndarray:
    """
    Lädt ein Wärmebild als kalibriertes 8-Bit Graustufen-Matrix.

    Unterstützt:
    - 8-Bit Standardformate (JPEG, PNG, BMP)
    - 16-Bit RAW / TIFF (z. B. radiometrische FLIR/Optris/Hikmicro Daten, mK, Centikelvin, 0.1°C)
    - 32-Bit Float-TIFF (direkte Temperatur-Messwerte in °C)
    - NumPy Arrays (.npy) mit Rohdaten
    - FLIR Radiometrische JPEGs (RJPG) mit eingebettetem APP1-Thermal-Stream
    - Mehrkanalige RGB/BGR-Wärmebilder (automatische Konvertierung zu kalibrierten Graustufen)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Bilddatei nicht gefunden: {filepath}")

    # 1. NumPy .npy Datei
    if filepath.lower().endswith(".npy"):
        try:
            arr = np.load(filepath)
            return _normalize_loaded_matrix(arr, t_min, t_max)
        except Exception as e:
            raise ValueError(f".npy Datei konnte nicht geladen werden: {e}") from e

    # 2. FLIR Radiometrisches JPEG
    if filepath.lower().endswith((".jpg", ".jpeg", ".rjpg")):
        flir_raw = _extract_flir_radiometric_raw(filepath)
        if flir_raw is not None:
            return _normalize_loaded_matrix(flir_raw, t_min, t_max)

    # 3. OpenCV mit IMREAD_UNCHANGED (um 16-Bit / Float / Unkomprimiert ohne Quantisierungsverlust zu erhalten)
    img = None
    try:
        file_bytes = np.fromfile(filepath, dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
    except Exception as e:
        logging.debug(f"cv2.imdecode fehlgeschlagen für {filepath}: {e}")

    # 4. Fallback zu Pillow (Multi-Page TIFF, 16-Bit TIFFs, seltene Farbräume)
    if img is None:
        try:
            from PIL import Image
            with Image.open(filepath) as pil_img:
                img = np.array(pil_img)
        except Exception as e:
            raise FileNotFoundError(
                f"Bild konnte weder mit OpenCV noch mit Pillow geladen werden: {filepath}\nDetails: {e}"
            ) from e

    if img is None or img.size == 0:
        raise ValueError(
            "Bilddaten konnten nicht dekodiert werden. Format nicht unterstützt oder Datei beschädigt."
        )

    return _normalize_loaded_matrix(img, t_min, t_max)

# ─────────────────────────────────────────────────────────────────────────────
# 2. ADAPTIVE GEWEBESEGMENTIERUNG (MULTI-OTSU)
# ─────────────────────────────────────────────────────────────────────────────
def extract_body_mask_multi_otsu(
    img: np.ndarray,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> np.ndarray:
    """
    Segmentiert biologisches Gewebe durch 3-Klassen adaptive Schwellenwertanalyse
    (Kalter Hintergrund vs. lauwarme Auflage vs. warmes Gewebe) mit Distanzerosion.
    """
    min_val, max_val, _, _ = cv2.minMaxLoc(img)
    dynamic_range = max_val - min_val

    # WICHTIG: Diese Konstanten muessen exakt mit dem Rust-Kern (src/lib.rs,
    # extract_body_mask) uebereinstimmen, sonst divergieren die Backends.
    # Rust rechnet mit u8-Integerdivision (otsu_thresh / 2), daher hier // 2.
    if dynamic_range < 30:
        threshold = max(otsu_min, min(otsu_max, min_val + 0.3 * dynamic_range))
    else:
        otsu_thresh, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        threshold = max(otsu_min, min(otsu_max, int(otsu_thresh) // 2))

    _, raw_mask = cv2.threshold(img, int(threshold), 255, cv2.THRESH_BINARY)

    # Morphologisches Closing zum Schließen kleiner Poren.
    # Rechteckiges Element, um dem Rust-Kern zu entsprechen: dessen separable
    # Lemire-Morphologie kann kein elliptisches Strukturelement abbilden.
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    cleaned_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_CLOSE, close_kernel)

    # Distanztransformation zur Elimination von Kantenübergangs-Artefakten
    dist = cv2.distanceTransform(cleaned_mask, cv2.DIST_L2, 3)
    max_dist = dist.max()
    if max_dist < 1e-10:
        return np.zeros_like(img, dtype=np.uint8)

    eroded_mask = (dist >= dist_erosion_factor * max_dist).astype(np.uint8) * 255
    return eroded_mask

def _extract_body_mask_cpu(
    img: np.ndarray,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> np.ndarray:
    """Abwärtskompatible Hilfsfunktion für Body-Mask."""
    return extract_body_mask_multi_otsu(img, otsu_min, otsu_max, dist_erosion_factor)

# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-SCALE MORPHOLOGICAL TOP-HAT (MTH)
# ─────────────────────────────────────────────────────────────────────────────
def compute_multiscale_tophat(
    img: np.ndarray,
    factors: tuple[float, ...] = _config.DEFAULT_MULTISCALE_FACTORS,
    mask: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Berechnet die Multi-Skalen Top-Hat Transformation über mehrere morphologische Skalen.
    MTH(I) = max_k (I - (I o S_k))
    Erfasst gleichzeitig punktförmige Mikronekrosen (kleiner Kernel) und flächige Entzündungen (großer Kernel).
    """
    dim = min(img.shape[0], img.shape[1])
    diff_stack = []

    for factor in factors:
        k_size = compute_odd_kernel(dim, factor)
        kernel_se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
        opened = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel_se)
        tophat = cv2.subtract(img, opened)
        if mask is not None:
            tophat = cv2.bitwise_and(tophat, tophat, mask=mask)
        diff_stack.append(tophat)

    if len(diff_stack) == 1:
        return diff_stack[0]

    # Maximum-Intensitäts-Projektion über alle Skalen
    mth = np.maximum.reduce(diff_stack)
    return mth

# ─────────────────────────────────────────────────────────────────────────────
# 4. THERMISCHER GRADIENTENFLUSS & 2D-LAPLACE-DIVERGENZ
# ─────────────────────────────────────────────────────────────────────────────
def compute_thermal_gradients_and_divergence(
    img: np.ndarray,
    mask: Optional[np.ndarray] = None
) -> dict[str, Any]:
    """
    Berechnet das thermische Gradientenvektorfeld (||grad T||) und die thermische 2D-Divergenz (Laplace-Operator).
    Echte pathologische Entzündungsherde erzeugen steile Ränder und eine signifikante negative Divergenz.
    """
    img_f = img.astype(np.float32)

    grad_x = cv2.Sobel(img_f, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(img_f, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    laplacian = cv2.Laplacian(img_f, cv2.CV_32F, ksize=3)

    if mask is not None and np.sum(mask > 0) > 0:
        valid = mask > 0
        mean_grad = float(np.mean(grad_mag[valid]))
        max_grad = float(np.max(grad_mag[valid]))
        mean_laplacian = float(np.mean(laplacian[valid]))
        min_laplacian = float(np.min(laplacian[valid]))
    else:
        mean_grad = float(np.mean(grad_mag))
        max_grad = float(np.max(grad_mag))
        mean_laplacian = float(np.mean(laplacian))
        min_laplacian = float(np.min(laplacian))

    return {
        "grad_magnitude": grad_mag,
        "laplacian": laplacian,
        "mean_gradient": round(mean_grad, 2),
        "max_gradient": round(max_grad, 2),
        "mean_laplacian": round(mean_laplacian, 2),
        "min_laplacian": round(min_laplacian, 2)
    }

# ─────────────────────────────────────────────────────────────────────────────
# 5. PCA-GESTÜTZTE ANATOMISCHE FUSSAUSRICHTUNG (ROTATIONSINVARIANZ)
# ─────────────────────────────────────────────────────────────────────────────
def compute_pca_foot_alignment_and_zones(
    img: np.ndarray,
    body_mask: np.ndarray,
    temp_min_c: float = _config.DEFAULT_TEMP_MIN,
    temp_max_c: float = _config.DEFAULT_TEMP_MAX
) -> dict[str, Any]:
    """
    Segmentiert linken und rechten Fuß, ermittelt per Hauptkomponentenanalyse (PCA / Trägheitsmomente)
    den Rotationswinkel jedes Fußes und segmentiert Vorfuß, Mittelfuß und Ferse rotationsinvariant entlang
    der anatomischen Längsachse.
    """
    h, w = img.shape[:2]
    mid_x = w // 2

    temp_range = max(1.0, temp_max_c - temp_min_c)

    def _analyze_single_foot(mask_side: np.ndarray, x_offset: int = 0) -> dict[str, Any]:
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_side)
        if num_labels <= 1:
            return {"exists": False, "angle_deg": 0.0, "fore_c": 0.0, "mid_c": 0.0, "heel_c": 0.0, "bbox": None}

        # Größte Komponente als Fuß wählen
        largest_idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        foot_mask = (labels == largest_idx)
        ys, xs = np.where(foot_mask)

        if len(ys) < 30:
            return {"exists": False, "angle_deg": 0.0, "fore_c": 0.0, "mid_c": 0.0, "heel_c": 0.0, "bbox": None}

        # Bounding-Box
        bx = int(stats[largest_idx, cv2.CC_STAT_LEFT]) + x_offset
        by = int(stats[largest_idx, cv2.CC_STAT_TOP])
        bw = int(stats[largest_idx, cv2.CC_STAT_WIDTH])
        bh = int(stats[largest_idx, cv2.CC_STAT_HEIGHT])

        # PCA über Raumkoordinaten
        cx = float(np.mean(xs))
        cy = float(np.mean(ys))

        # Zentrierte Kovarianzmatrix
        dx = xs - cx
        dy = ys - cy
        cov = np.cov(np.vstack((dx, dy)))

        try:
            evals, evecs = np.linalg.eigh(cov)
            # Hauptvektor der größten Varianz
            main_vec = evecs[:, -1]
            angle_rad = np.arctan2(main_vec[1], main_vec[0])
            angle_deg = float(np.degrees(angle_rad))
            # Normalisiere Winkel auf vertikale Ausrichtung (-90° bis +90°)
            if angle_deg < -90:
                angle_deg += 180
            elif angle_deg > 90:
                angle_deg -= 180
        except Exception:
            angle_deg = 0.0
            main_vec = np.array([0.0, 1.0])

        # Projektion der Pixel entlang der Hauptachse
        proj = dx * main_vec[0] + dy * main_vec[1]
        p_min, p_max = float(proj.min()), float(proj.max())
        p_range = max(1e-5, p_max - p_min)

        # 3 anatomische Zonen entlang der longitudinalen Hauptachse:
        # Vorfuß (Metatarsus/Zehen, 0-40%), Mittelfuß (Gewölbe, 40-70%), Ferse (Calcaneus, 70-100%)
        norm_proj = (proj - p_min) / p_range
        # Wenn Hauptvektor nach oben zeigt, invertieren wir für anatomische Konsistenz
        if main_vec[1] < 0:
            norm_proj = 1.0 - norm_proj

        z_fore = norm_proj <= 0.40
        z_mid = (norm_proj > 0.40) & (norm_proj <= 0.70)
        z_heel = norm_proj > 0.70

        # Cavanagh & Rodgers Plantar Arch Index (AI = Area_Midfoot / Area_Total)
        n_fore = int(np.sum(z_fore))
        n_mid = int(np.sum(z_mid))
        n_heel = int(np.sum(z_heel))
        n_tot = max(1, n_fore + n_mid + n_heel)
        arch_index = float(n_mid / n_tot)

        if arch_index < 0.21:
            arch_type = "Pes Cavus (Hohlfuß)"
            arch_code = "cavus"
        elif arch_index <= 0.26:
            arch_type = "Normales Längsgewölbe"
            arch_code = "normal"
        else:
            arch_type = "Pes Planus (Senk-/Plattfuß / Charcot-Verdacht)"
            arch_code = "planus"

        # Pixelwerte an den entsprechenden Koordinaten
        actual_xs = xs + x_offset
        pixels_all = img[ys, actual_xs]

        p_fore = pixels_all[z_fore]
        p_mid = pixels_all[z_mid]
        p_heel = pixels_all[z_heel]

        def _to_c(px_arr):
            if len(px_arr) == 0:
                return 0.0
            return float(temp_min_c + (np.mean(px_arr) / 255.0) * temp_range)

        return {
            "exists": True,
            "angle_deg": round(angle_deg, 1),
            "fore_c": round(_to_c(p_fore), 2),
            "mid_c": round(_to_c(p_mid), 2),
            "heel_c": round(_to_c(p_heel), 2),
            "arch_index": round(arch_index, 3),
            "arch_type": arch_type,
            "arch_code": arch_code,
            "zone_counts": {"fore": n_fore, "mid": n_mid, "heel": n_heel},
            "bbox": (bx, by, bw, bh)
        }

    left_mask = (body_mask[:, :mid_x] > 0).astype(np.uint8) * 255
    right_mask = (body_mask[:, mid_x:] > 0).astype(np.uint8) * 255

    left_res = _analyze_single_foot(left_mask, x_offset=0)
    right_res = _analyze_single_foot(right_mask, x_offset=mid_x)

    d_fore = abs(left_res["fore_c"] - right_res["fore_c"]) if left_res["exists"] and right_res["exists"] else 0.0
    d_mid = abs(left_res["mid_c"] - right_res["mid_c"]) if left_res["exists"] and right_res["exists"] else 0.0
    d_heel = abs(left_res["heel_c"] - right_res["heel_c"]) if left_res["exists"] and right_res["exists"] else 0.0

    return {
        "left": left_res,
        "right": right_res,
        "delta_fore_c": round(d_fore, 2),
        "delta_mid_c": round(d_mid, 2),
        "delta_heel_c": round(d_heel, 2),
        "pca_aligned": True
    }

# ─────────────────────────────────────────────────────────────────────────────
# 6. THERMAL SEVERITY INDEX (TSI) & IWGDF-RISIKOKLASSIFIKATION
# ─────────────────────────────────────────────────────────────────────────────
def compute_thermal_severity_index(
    delta_t_c: float,
    hotspot_pixel_count: int,
    body_pixel_count: int,
    max_gradient: float,
    std_pixel: float
) -> dict[str, Any]:
    """
    Berechnet den standardisierten IGNITE Thermal Severity Index (TSI, 0.0 - 10.0)
    und die klinische IWGDF-Risikostufe.
    """
    # 1. Delta-T Term normiert auf Armstrong Goldstandard (2.2 °C = 1.0)
    term_delta_t = min(3.0, delta_t_c / 2.2)

    # 2. Flächenanteil-Term (Hotspot-Ratio normiert)
    area_ratio = (hotspot_pixel_count / max(1, body_pixel_count)) * 100.0
    term_area = min(3.0, area_ratio / 1.5)

    # 3. Gradienten-Schärfeterm
    sigma_norm = max(1.0, std_pixel)
    term_grad = min(3.0, max_gradient / (2.0 * sigma_norm))

    # Gewichteter Gesamtscore (0.0 - 10.0)
    raw_score = (
        _config.TSI_WEIGHT_DELTA_T * term_delta_t +
        _config.TSI_WEIGHT_AREA * term_area +
        _config.TSI_WEIGHT_GRADIENT * term_grad
    ) * (10.0 / 3.0)
    tsi_score = round(max(0.0, min(10.0, float(raw_score))), 1)

    # IWGDF Risikostufe
    if tsi_score <= 2.0 and delta_t_c <= 1.5 and hotspot_pixel_count < 50:
        tier = 0
        tier_name = "Stufe 0: Physiologischer Normalbefund"
        tier_desc = "Keine thermischen Auffälligkeiten. Routinekontrolle."
        color = "#16A34A"
    elif tsi_score <= 4.5 and delta_t_c <= 2.2:
        tier = 1
        tier_name = "Stufe 1: Geringe Asymmetrie / Beobachtung"
        tier_desc = "Subklinische thermische Differenz. Engmaschiges Monitoring empfohlen."
        color = "#D97706"
    elif tsi_score <= 7.5:
        tier = 2
        tier_name = "Stufe 2: Signifikanter Entzündungsherd"
        tier_desc = "Manifeste Hyperthermie (ΔT > 2.2 °C). Diagnostische Abklärung indiziert."
        color = "#EA580C"
    else:
        tier = 3
        tier_name = "Stufe 3: Akutes Ulkus- / Infektionsrisiko"
        tier_desc = "Schwere thermische Asymmetrie mit ausgeprägtem Fokus. Dringende Intervention."
        color = "#DC2626"

    return {
        "score": tsi_score,
        "tier": tier,
        "tier_name": tier_name,
        "tier_desc": tier_desc,
        "color": color,
        "term_delta_t": round(term_delta_t, 2),
        "term_area": round(term_area, 2),
        "term_grad": round(term_grad, 2),
    }

# ─────────────────────────────────────────────────────────────────────────────
# 7. BILATERALE KONTRALATERALE REGISTRIERUNG & ASYMMETRIE-MAPPING
# ─────────────────────────────────────────────────────────────────────────────
def compute_bilateral_asymmetry_map(
    img: np.ndarray,
    body_mask: np.ndarray,
    temp_min_c: float = _config.DEFAULT_TEMP_MIN,
    temp_max_c: float = _config.DEFAULT_TEMP_MAX
) -> dict[str, Any]:
    """
    Registriert linken und gespiegelten rechten Fuß anatomisch und berechnet das räumliche
    ΔT(x,y) Asymmetrie-Differenzbild nach Armstrong / Ring & Ammer Goldstandard.
    """
    h, w = img.shape[:2]
    mid_x = w // 2
    temp_range = max(1.0, temp_max_c - temp_min_c)

    left_mask = (body_mask[:, :mid_x] > 0).astype(np.uint8) * 255
    right_mask = (body_mask[:, mid_x:] > 0).astype(np.uint8) * 255

    num_l, _, stats_l, _ = cv2.connectedComponentsWithStats(left_mask)
    num_r, _, stats_r, _ = cv2.connectedComponentsWithStats(right_mask)

    if num_l <= 1 or num_r <= 1:
        return {
            "valid": False,
            "asymmetry_map": np.zeros((h, w), dtype=np.float32),
            "max_delta_t": 0.0,
            "mean_delta_t": 0.0,
            "high_risk_area_px": 0,
            "hotspot_coord": None
        }

    l_idx = 1 + int(np.argmax(stats_l[1:, cv2.CC_STAT_AREA]))
    r_idx = 1 + int(np.argmax(stats_r[1:, cv2.CC_STAT_AREA]))

    lx, ly, lw, lh = int(stats_l[l_idx, cv2.CC_STAT_LEFT]), int(stats_l[l_idx, cv2.CC_STAT_TOP]), int(stats_l[l_idx, cv2.CC_STAT_WIDTH]), int(stats_l[l_idx, cv2.CC_STAT_HEIGHT])
    rx, ry, rw, rh = int(stats_r[r_idx, cv2.CC_STAT_LEFT]) + mid_x, int(stats_r[r_idx, cv2.CC_STAT_TOP]), int(stats_r[r_idx, cv2.CC_STAT_WIDTH]), int(stats_r[r_idx, cv2.CC_STAT_HEIGHT])

    crop_l = temp_min_c + (img[ly:ly+lh, lx:lx+lw].astype(np.float32) / 255.0) * temp_range
    mask_l = (body_mask[ly:ly+lh, lx:lx+lw] > 0)

    crop_r = temp_min_c + (img[ry:ry+rh, rx:rx+rw].astype(np.float32) / 255.0) * temp_range
    mask_r = (body_mask[ry:ry+rh, rx:rx+rw] > 0)

    crop_r_mirrored = cv2.flip(crop_r, 1)
    mask_r_mirrored = cv2.flip(mask_r.astype(np.uint8), 1) > 0

    target_h, target_w = max(lh, rh), max(lw, rw)
    norm_l = cv2.resize(crop_l, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    norm_mask_l = cv2.resize(mask_l.astype(np.uint8), (target_w, target_h), interpolation=cv2.INTER_NEAREST) > 0

    norm_r = cv2.resize(crop_r_mirrored, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
    norm_mask_r = cv2.resize(mask_r_mirrored.astype(np.uint8), (target_w, target_h), interpolation=cv2.INTER_NEAREST) > 0

    valid_overlap = norm_mask_l & norm_mask_r
    delta_t_map = np.abs(norm_l - norm_r) * valid_overlap.astype(np.float32)

    max_delta = float(np.max(delta_t_map)) if np.any(valid_overlap) else 0.0
    mean_delta = float(np.mean(delta_t_map[valid_overlap])) if np.any(valid_overlap) else 0.0
    high_risk_px = int(np.sum((delta_t_map >= _config.ASYMMETRY_THRESHOLD_C) & valid_overlap))

    if max_delta > 0:
        max_y, max_x = np.unravel_index(np.argmax(delta_t_map), delta_t_map.shape)
        hotspot_pt = (int(max_x), int(max_y))
    else:
        hotspot_pt = None

    return {
        "valid": True,
        "asymmetry_map": delta_t_map,
        "max_delta_t": round(max_delta, 2),
        "mean_delta_t": round(mean_delta, 2),
        "high_risk_area_px": high_risk_px,
        "hotspot_coord": hotspot_pt,
        "norm_dimensions": (target_w, target_h)
    }

# ─────────────────────────────────────────────────────────────────────────────
# 8. ADAPTIVE DOPPEL-SCHWELLENWERT-HYSTERESE
# ─────────────────────────────────────────────────────────────────────────────
def apply_hysteresis_thresholding(
    diff_img: np.ndarray,
    mask: np.ndarray,
    k_high: float = _config.DEFAULT_HYSTERESIS_K_HIGH,
    k_low: float = _config.DEFAULT_HYSTERESIS_K_LOW,
    use_mad: bool = False
) -> np.ndarray:
    """
    Adaptive Hysterese-Segmentierung mit morphologischer Geodäten-Rekonstruktion.
    Starke Schwellenwerte erfassen gesicherte Entzündungskerne, schwache Schwellenwerte
    integrieren angrenzende perifokale Hyperämiezellen ohne Sensorrauschen.
    """
    if mask is None or np.sum(mask > 0) == 0:
        return np.zeros_like(diff_img, dtype=np.uint8)

    valid_pixels = diff_img[mask > 0]
    if len(valid_pixels) == 0:
        return np.zeros_like(diff_img, dtype=np.uint8)

    if use_mad:
        med = float(np.median(valid_pixels))
        mad = float(np.median(np.abs(valid_pixels - med)))
        sigma = max(1e-5, 1.4826 * mad)
        thresh_high = med + k_high * sigma
        thresh_low = med + k_low * sigma
    else:
        mean_v = float(np.mean(valid_pixels))
        sigma = max(1e-5, float(np.std(valid_pixels)))
        thresh_high = mean_v + k_high * sigma
        thresh_low = mean_v + k_low * sigma

    strong_mask = ((diff_img >= thresh_high) & (mask > 0)).astype(np.uint8) * 255
    weak_mask = ((diff_img >= thresh_low) & (mask > 0)).astype(np.uint8) * 255

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(weak_mask)
    final_hysteresis = np.zeros_like(diff_img, dtype=np.uint8)

    for i in range(1, num_labels):
        comp = (labels == i)
        if np.any(strong_mask[comp] > 0):
            final_hysteresis[comp] = 255

    return final_hysteresis

# ─────────────────────────────────────────────────────────────────────────────
# 9. PENNES BIOHEAT WÄRMEFLUSSDICHTE & ENTZÜNDUNGSQUELLENDICHTE
# ─────────────────────────────────────────────────────────────────────────────
def compute_pennes_bioheat_flux(
    img: np.ndarray,
    mask: Optional[np.ndarray] = None,
    temp_min_c: float = _config.DEFAULT_TEMP_MIN,
    temp_max_c: float = _config.DEFAULT_TEMP_MAX,
    k_tissue: float = _config.TISSUE_THERMAL_CONDUCTIVITY
) -> dict[str, Any]:
    """
    Berechnet die thermische Wärmeflussdichte q = -k * grad(T) und die
    metabolische Wärmequellendichte Q = -div(q) = k * Lap(T) nach der Pennes-Bioheat-Gleichung.
    Nutzt den schnellen Rust-Core falls verfügbar, sonst NumPy/OpenCV.
    """
    if _RUST_BACKEND_AVAILABLE and _ignite_core is not None and hasattr(_ignite_core, "compute_pennes_bioheat"):
        try:
            arr_c = np.ascontiguousarray(img, dtype=np.uint8)
            mask_c = np.ascontiguousarray(mask, dtype=np.uint8) if mask is not None else None
            flux_mag, q_source, mean_flux, max_flux, mean_source, max_source = _ignite_core.compute_pennes_bioheat(
                arr_c, mask_c, temp_min_c, temp_max_c, k_tissue
            )
            return {
                "flux_magnitude": np.array(flux_mag, copy=False),
                "heat_source_density": np.array(q_source, copy=False),
                "mean_flux_mw_cm2": round(mean_flux, 2),
                "max_flux_mw_cm2": round(max_flux, 2),
                "mean_heat_source": round(mean_source, 2),
                "max_heat_source": round(max_source, 2)
            }
        except Exception:
            pass

    temp_range = max(1.0, temp_max_c - temp_min_c)
    temp_c = temp_min_c + (img.astype(np.float32) / 255.0) * temp_range

    dx_m = 0.001
    grad_x = cv2.Sobel(temp_c, cv2.CV_32F, 1, 0, ksize=3) / (8.0 * dx_m)
    grad_y = cv2.Sobel(temp_c, cv2.CV_32F, 0, 1, ksize=3) / (8.0 * dx_m)

    flux_x = -k_tissue * grad_x * 0.1
    flux_y = -k_tissue * grad_y * 0.1
    flux_mag = np.sqrt(flux_x**2 + flux_y**2)

    laplacian = cv2.Laplacian(temp_c, cv2.CV_32F, ksize=3) / (dx_m**2)
    q_source = (k_tissue * laplacian) * 1e-4

    if mask is not None and np.sum(mask > 0) > 0:
        valid = mask > 0
        mean_flux = float(np.mean(flux_mag[valid]))
        max_flux = float(np.max(flux_mag[valid]))
        mean_source = float(np.mean(q_source[valid]))
        max_source = float(np.max(q_source[valid]))
    else:
        mean_flux = float(np.mean(flux_mag))
        max_flux = float(np.max(flux_mag))
        mean_source = float(np.mean(q_source))
        max_source = float(np.max(q_source))

    return {
        "flux_magnitude": flux_mag,
        "heat_source_density": q_source,
        "mean_flux_mw_cm2": round(mean_flux, 2),
        "max_flux_mw_cm2": round(max_flux, 2),
        "mean_heat_source": round(mean_source, 2),
        "max_heat_source": round(max_source, 2)
    }

# ─────────────────────────────────────────────────────────────────────────────
# 10. FRANGI-HESSIAN GEFÄSS- & LINEARITÄTSFILTER
# ─────────────────────────────────────────────────────────────────────────────
def compute_frangi_vesselness_filter(
    img: np.ndarray,
    mask: Optional[np.ndarray] = None,
    sigmas: tuple[float, ...] = _config.FRANGI_SCALE_RANGE,
    beta: float = _config.FRANGI_BETA,
    c: float = _config.FRANGI_C
) -> np.ndarray:
    """
    Frangi Vesselness Filter basierend auf Eigenwerten der Hesse-Matrix.
    Identifiziert tubuläre oberflächliche Venenstrukturen zur Vermeidung von False Positives.
    """
    img_f = img.astype(np.float32)
    max_vesselness = np.zeros_like(img_f)

    for sigma in sigmas:
        ksize = int(2 * np.ceil(2 * sigma) + 1)
        smoothed = cv2.GaussianBlur(img_f, (ksize, ksize), sigma)

        hxx = cv2.Sobel(smoothed, cv2.CV_32F, 2, 0, ksize=3)
        hyy = cv2.Sobel(smoothed, cv2.CV_32F, 0, 2, ksize=3)
        hxy = cv2.Sobel(smoothed, cv2.CV_32F, 1, 1, ksize=3)

        hxx *= (sigma ** 2)
        hyy *= (sigma ** 2)
        hxy *= (sigma ** 2)

        tmp = np.sqrt(np.maximum(0.0, (hxx - hyy)**2 + 4 * hxy**2))
        lambda1 = 0.5 * (hxx + hyy - tmp)
        lambda2 = 0.5 * (hxx + hyy + tmp)

        swap = np.abs(lambda1) > np.abs(lambda2)
        l1 = np.where(swap, lambda2, lambda1)
        l2 = np.where(swap, lambda1, lambda2)

        rb = np.abs(l1) / (np.abs(l2) + 1e-6)
        s = np.sqrt(l1**2 + l2**2)

        vesselness = np.exp(- (rb**2) / (2 * (beta**2))) * (1.0 - np.exp(- (s**2) / (2 * (c**2))))
        vesselness[l2 >= 0] = 0.0

        max_vesselness = np.maximum(max_vesselness, vesselness)

    if mask is not None:
        max_vesselness[mask == 0] = 0.0

    v_min, v_max = max_vesselness.min(), max_vesselness.max()
    if v_max - v_min > 1e-6:
        v_norm = ((max_vesselness - v_min) / (v_max - v_min) * 255.0).astype(np.uint8)
    else:
        v_norm = np.zeros_like(img, dtype=np.uint8)

    return v_norm

# ─────────────────────────────────────────────────────────────────────────────
# 11. GEOMETRISCHER RAUSCHFILTER
# ─────────────────────────────────────────────────────────────────────────────
def _filter_geometric_noise(
    binary_raw: np.ndarray,
    mask: np.ndarray,
    min_area_factor: float,
    min_circularity: float
) -> np.ndarray:
    """Filtert Rauschen und anatomische Randartefakte basierend auf Geometrie und Distanztransformation."""
    total_body_area = np.sum(mask == 255)
    min_area = max(10, min_area_factor * total_body_area)

    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    min_dist_from_border = max(
        _config.MIN_DIST_FROM_BORDER_ABS,
        binary_raw.shape[1] * _config.MIN_DIST_FROM_BORDER_FACTOR
    )

    # 4-Konnektivitaet, um exakt dem Rust-Kern (connected_components in src/lib.rs)
    # zu entsprechen. OpenCV verwendet sonst standardmaessig 8-Konnektivitaet,
    # was zu abweichenden Komponentenzerlegungen und damit zu Backend-Divergenz fuehrt.
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_raw, connectivity=4)
    final_mask = np.zeros_like(binary_raw)

    border_margin = _config.BORDER_MARGIN_PX
    h_img, w_img = binary_raw.shape[:2]

    for i in range(1, num_labels):
        centroid_y = centroids[i][1]
        if centroid_y > h_img * _config.ANATOMICAL_LOWER_CUTOFF_Y:
            continue

        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue

        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w_box = stats[i, cv2.CC_STAT_WIDTH]
        h_box = stats[i, cv2.CC_STAT_HEIGHT]

        if x <= border_margin or y <= border_margin or (x + w_box) >= (w_img - border_margin) or (y + h_box) >= (h_img - border_margin):
            continue

        component_mask = (labels == i)
        max_dist = float(np.max(dist_map[component_mask])) if np.sum(component_mask) > 0 else 0.0
        if max_dist < min_dist_from_border:
            continue

        contours, _ = cv2.findContours(
            (labels == i).astype(np.uint8) * 255,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            continue
        cnt = contours[0]
        perimeter = cv2.arcLength(cnt, True)
        if perimeter < 1.0:
            continue
        circularity = (4.0 * np.pi * area) / (perimeter * perimeter)
        if circularity >= min_circularity:
            cv2.drawContours(final_mask, [cnt], -1, 255, thickness=cv2.FILLED)

    return final_mask

# ─────────────────────────────────────────────────────────────────────────────
# 8. PIPELINE-IMPLEMENTIERUNGEN (GPU / PYTHON / RUST)
# ─────────────────────────────────────────────────────────────────────────────
def _pytorch_gpu_pipeline(
    img: np.ndarray,
    sigma_k: float = _config.DEFAULT_SIGMA_K,
    tophat_factor: float = _config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = _config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = _config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR,
    use_mad: bool = _config.DEFAULT_USE_MAD
) -> tuple[np.ndarray, np.ndarray]:
    """GPU-beschleunigte Pipeline unter Verwendung von PyTorch CUDA."""
    mask_cpu = extract_body_mask_multi_otsu(img, otsu_min, otsu_max, dist_erosion_factor)
    if np.sum(mask_cpu == 255) == 0:
        raise ValueError("Body-Mask ist leer – kein Körper im Bild erkannt.")

    device = _TORCH.device('cuda')
    img_t = _TORCH.from_numpy(img).to(device).float()
    mask_t = _TORCH.from_numpy(mask_cpu).to(device)

    dim = min(img.shape[0], img.shape[1])
    kernel_large = compute_odd_kernel(dim, tophat_factor)
    pad = kernel_large // 2

    import importlib
    F = importlib.import_module("torch.nn.functional")
    with _TORCH.no_grad():
        img_4d = img_t.unsqueeze(0).unsqueeze(0)

        # Multi-Skalen Erode / Dilate
        eroded = -F.max_pool2d(-img_4d, kernel_size=kernel_large, stride=1, padding=pad)
        dilated = F.max_pool2d(eroded, kernel_size=kernel_large, stride=1, padding=pad)
        tophat_t = (img_4d - dilated).squeeze(0).squeeze(0)

        diff_t = _TORCH.where(mask_t > 0, tophat_t, _TORCH.zeros_like(tophat_t))

        body_pixels = diff_t[mask_t > 0]
        orig_body_pixels = img_t[mask_t > 0]

        if use_mad:
            median_diff = body_pixels.median()
            mad_diff = (body_pixels - median_diff).abs().median()
            sigma_diff = 1.4826 * mad_diff
            T_rel = median_diff + sigma_k * sigma_diff
            mu_orig = orig_body_pixels.median()
        else:
            mu_diff = body_pixels.mean()
            sigma_diff = body_pixels.std()
            T_rel = mu_diff + sigma_k * sigma_diff
            mu_orig = orig_body_pixels.mean()

        binary_raw_t = (diff_t > T_rel) & (img_t > mu_orig)
        binary_raw_np = (binary_raw_t.cpu().numpy() * 255).astype(np.uint8)

    final_mask = _filter_geometric_noise(binary_raw_np, mask_cpu, min_area_factor, min_circularity)

    diff_np = diff_t.cpu().numpy()
    min_val = diff_np.min()
    max_val = diff_np.max()
    diff_range = max_val - min_val
    if diff_range < 1e-10:
        diff_vis = np.zeros_like(diff_np, dtype=np.uint8)
    else:
        diff_vis = ((diff_np - min_val) * 255.0 / diff_range).astype(np.uint8)

    return diff_vis, final_mask

def _python_fallback_pipeline(
    img: np.ndarray,
    sigma_k: float = _config.DEFAULT_SIGMA_K,
    tophat_factor: float = _config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = _config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = _config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR,
    use_mad: bool = _config.DEFAULT_USE_MAD,
    multiscale: bool = False,
    pre_blur: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Python-Fallback der Hotspot-Pipeline.

    Diese Funktion ist die Referenz-Reimplementierung des Rust-Kerns und muss
    dessen Verhalten so genau wie moeglich nachbilden. Deshalb sind
    ``multiscale`` und ``pre_blur`` standardmaessig deaktiviert: der Rust-Kern
    rechnet einskalig und ohne Vorglaettung (siehe process_thermal_pipeline in
    src/lib.rs). Werden sie aktiviert, weicht das Ergebnis bewusst vom Rust-Kern
    ab und ist nicht mehr paritaetsfaehig.

    Hinweis zur verbleibenden Restabweichung: Der Rust-Kern nutzt eine separable
    Lemire-Morphologie mit *rechteckigem* Strukturelement (O(K) statt O(K^2)),
    OpenCV hier ebenfalls MORPH_RECT. Die Distanztransformation verwendet
    dagegen unterschiedliche Approximationen (Chamfer 3/4 in Rust,
    cv2.DIST_L2/3x3 hier), weshalb exakte Bit-Paritaet nicht erreichbar ist.
    """
    warnings.warn(
        "[image_processing] Python-Fallback aktiv! Performance beeinträchtigt.",
        RuntimeWarning,
        stacklevel=3,
    )

    # 0. Vorglaettung nur auf ausdruecklichen Wunsch (Rust-Kern glaettet nicht)
    img_blurred = cv2.blur(img, (3, 3)) if pre_blur else img

    # 1. Body mask via Multi-Otsu
    mask = extract_body_mask_multi_otsu(img_blurred, otsu_min, otsu_max, dist_erosion_factor)
    total_body_area = np.sum(mask == 255)
    if total_body_area == 0:
        raise ValueError("Body-Mask ist leer – kein Körper im Bild erkannt.")

    # 2. Top-Hat – einskalig (Rust-aequivalent) oder multiskalig (abweichend)
    if multiscale:
        diff_img = compute_multiscale_tophat(
            img_blurred,
            factors=(tophat_factor * 0.5, tophat_factor, tophat_factor * 2.0),
            mask=mask
        )
    else:
        dim = min(img_blurred.shape[0], img_blurred.shape[1])
        k_size = compute_odd_kernel(dim, tophat_factor)
        kernel_se = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
        opened = cv2.morphologyEx(img_blurred, cv2.MORPH_OPEN, kernel_se)
        tophat = cv2.subtract(img_blurred, opened)
        diff_img = cv2.bitwise_and(tophat, tophat, mask=mask)

    # 3. Statistik-Thresholding
    body_pixels = diff_img[mask > 0]
    orig_body_pixels = img_blurred[mask > 0]

    if use_mad:
        median_diff = float(np.median(body_pixels))
        mad_diff = float(np.median(np.abs(body_pixels - median_diff)))
        sigma_diff = 1.4826 * mad_diff
        T_rel = median_diff + sigma_k * sigma_diff
        mu_orig = float(np.median(orig_body_pixels))
    else:
        mu_diff = float(np.mean(body_pixels))
        sigma_diff = float(np.std(body_pixels))
        T_rel = mu_diff + sigma_k * sigma_diff
        mu_orig = float(np.mean(orig_body_pixels))

    binary_raw = ((diff_img > T_rel) & (img_blurred > mu_orig)).astype(np.uint8) * 255

    # 4. Geometrischer Rauschfilter
    final_mask = _filter_geometric_noise(binary_raw, mask, min_area_factor, min_circularity)

    diff_vis = cv2.normalize(diff_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return diff_vis, final_mask

# ─────────────────────────────────────────────────────────────────────────────
# 9. MAIN WRAPPER API
# ─────────────────────────────────────────────────────────────────────────────
FORCED_BACKEND = "auto"

def run_rust_pipeline(
    img: np.ndarray,
    sigma_k: float = _config.DEFAULT_SIGMA_K,
    tophat_factor: float = _config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = _config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = _config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR,
    use_mad: bool = _config.DEFAULT_USE_MAD
) -> tuple[np.ndarray, np.ndarray]:
    """Führt die vollständige Bildverarbeitungs-Pipeline aus."""
    global FORCED_BACKEND

    if FORCED_BACKEND == "gpu":
        if _GPU_AVAILABLE:
            return _pytorch_gpu_pipeline(
                img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor, use_mad
            )
        else:
            raise RuntimeError("GPU-Backend (CUDA) ist nicht verfügbar!")

    elif FORCED_BACKEND == "rust":
        if _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
            img_contiguous = np.ascontiguousarray(img, dtype=np.uint8)
            return _ignite_core.process_thermal_pipeline(
                img_contiguous, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor, use_mad
            )
        else:
            raise RuntimeError("Natives Rust-Core-Modul ist nicht verfügbar!")

    elif FORCED_BACKEND == "python":
        return _python_fallback_pipeline(
            img, sigma_k, tophat_factor, min_area_factor, min_circularity,
            otsu_min, otsu_max, dist_erosion_factor, use_mad
        )

    else:  # auto
        if _GPU_AVAILABLE:
            try:
                return _pytorch_gpu_pipeline(
                    img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                    otsu_min, otsu_max, dist_erosion_factor, use_mad
                )
            except Exception as e:
                warnings.warn(
                    f"[image_processing] GPU-Pipeline failed! Falling back to Rust CPU. Details: {e}",
                    RuntimeWarning,
                    stacklevel=2,
                )

        if _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
            img_contiguous = np.ascontiguousarray(img, dtype=np.uint8)
            return _ignite_core.process_thermal_pipeline(
                img_contiguous, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor, use_mad
            )
        else:
            return _python_fallback_pipeline(
                img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor, use_mad
            )

# ─────────────────────────────────────────────────────────────────────────────
# 10. VISUELLES OVERLAY
# ─────────────────────────────────────────────────────────────────────────────
def create_hotspot_overlay(original_img: np.ndarray, hotspots_mask: np.ndarray, colormap_name: str = "Graustufen") -> np.ndarray:
    """Erstellt ein visuelles Overlay: Originalbild mit gewähltem Colormap und roten Hotspots."""
    if colormap_name == "Regenbogen (Jet)":
        color_img = cv2.applyColorMap(original_img, cv2.COLORMAP_JET)
    elif colormap_name == "Inferno":
        color_img = cv2.applyColorMap(original_img, cv2.COLORMAP_INFERNO)
    elif colormap_name == "Heiß (Hot)":
        color_img = cv2.applyColorMap(original_img, cv2.COLORMAP_HOT)
    else:  # Graustufen
        color_img = cv2.cvtColor(original_img, cv2.COLOR_GRAY2BGR)

    red_img = np.zeros_like(color_img)
    red_img[:] = [85, 0, 255]

    blended = cv2.addWeighted(color_img, 0.3, red_img, 0.7, 0)
    final_img = np.where(
        hotspots_mask[:, :, None] == 255, blended, color_img
    ).astype(np.uint8)

    return final_img

# ─────────────────────────────────────────────────────────────────────────────
# 11. KONTRALATERALE ASYMMETRIE-ANALYSE MIT PCA
# ─────────────────────────────────────────────────────────────────────────────
def compute_contralateral_asymmetry(
    img: np.ndarray,
    body_mask: np.ndarray,
    temp_min_c: float = _config.DEFAULT_TEMP_MIN,
    temp_max_c: float = _config.DEFAULT_TEMP_MAX,
    threshold_c: float = _config.ASYMMETRY_THRESHOLD_C
) -> dict:
    """
    Berechnet die kontralaterale Temperatur-Asymmetrie zwischen linker und rechter Körperhälfte
    inklusive PCA-basierter Fußwinkel-Erkennung.
    """
    if img is None or body_mask is None or np.sum(body_mask == 255) == 0:
        return {
            "left_mean_c": 0.0,
            "right_mean_c": 0.0,
            "delta_t_c": 0.0,
            "is_asymmetric": False,
            "status": "Keine Gewebe-Maske",
            "pca": None
        }

    h, w = img.shape[:2]
    mid_x = w // 2

    left_mask = body_mask[:, :mid_x] > 0
    right_mask = body_mask[:, mid_x:] > 0

    left_px = img[:, :mid_x][left_mask]
    right_px = img[:, mid_x:][right_mask]

    if len(left_px) == 0 or len(right_px) == 0:
        return {
            "left_mean_c": 0.0,
            "right_mean_c": 0.0,
            "delta_t_c": 0.0,
            "is_asymmetric": False,
            "status": "Nur einseitiges Gewebe",
            "pca": None
        }

    mu_left_raw = float(np.mean(left_px))
    mu_right_raw = float(np.mean(right_px))

    temp_range = max(1.0, temp_max_c - temp_min_c)
    left_temp_c = temp_min_c + (mu_left_raw / 255.0) * temp_range
    right_temp_c = temp_min_c + (mu_right_raw / 255.0) * temp_range
    delta_t_c = abs(left_temp_c - right_temp_c)
    is_asymmetric = delta_t_c > threshold_c

    pca_info = compute_pca_foot_alignment_and_zones(img, body_mask, temp_min_c, temp_max_c)

    return {
        "left_mean_c": round(left_temp_c, 2),
        "right_mean_c": round(right_temp_c, 2),
        "delta_t_c": round(delta_t_c, 2),
        "is_asymmetric": is_asymmetric,
        "status": "Pathologische Asymmetrie (⚠️ > 2.2°C)" if is_asymmetric else "Physiologisch Symmetrisch (✓)",
        "pca": pca_info
    }