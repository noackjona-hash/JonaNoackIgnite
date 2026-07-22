"""image_processing.py – Python-Wrapper für den Ignite-Rust-Core.

Dieses Modul dient als schlanke Vermittlungsschicht zwischen dem Tkinter-Frontend
(`gui.py`) und dem nativen Rust-Erweiterungsmodul `ignite_core` sowie dem GPU-Backend.
"""

import warnings
import cv2
import numpy as np
import config as _config

# ─────────────────────────────────────────────────────────────────────────────
# GPU- & Rust-Core-Erkennung mit Fallback-Mechanismus
# ─────────────────────────────────────────────────────────────────────────────
_RUST_BACKEND_AVAILABLE = False
_ignite_core = None
_GPU_AVAILABLE = False

# 1. GPU-Verfügbarkeit via PyTorch CUDA prüfen
try:
    import torch
    import torch.nn.functional as F
    if torch.cuda.is_available():
        _GPU_AVAILABLE = True
except ImportError:
    pass

# 2. Rust-Core importieren
try:
    import ignite_core as _ignite_core
    _RUST_BACKEND_AVAILABLE = True
except ImportError:
    pass

# 3. Aktives Backend auf der Konsole ausgeben
if _GPU_AVAILABLE:
    print(f"[image_processing] GPU-Beschleunigung aktiv: {torch.cuda.get_device_name(0)}")
elif _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
    print(
        f"[image_processing] Rust-Backend aktiv: {_ignite_core.__backend__} "
        f"(v{_ignite_core.__version__})"
    )
else:
    warnings.warn(
        "[image_processing] WARNUNG: Weder GPU-Beschleunigung noch Rust-Backend aktiv!\n"
        "  Nutze Python-Fallback-Pipeline.",
        RuntimeWarning,
        stacklevel=2,
    )

def get_active_backend() -> str:
    """Gibt den Namen des aktuell genutzten Berechnungs-Backends zurück."""
    if _GPU_AVAILABLE:
        return f"GPU (CUDA, {torch.cuda.get_device_name(0)})"
    elif _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
        return getattr(_ignite_core, "__backend__", "CPU+rayon (Rust-native)")
    else:
        return "Python-Fallback"

def compute_odd_kernel(dimension: int, factor: float) -> int:
    """Berechnet eine ungerade Kernelgröße als Prozentsatz der minimalen Bilddimension min(W, H), analog zu Rust."""
    raw = int(dimension * factor)
    odd = max(1, raw | 1)
    return max(3, odd)

# ─────────────────────────────────────────────────────────────────────────────
# FUNKTION 1: Wärmebild laden
# ─────────────────────────────────────────────────────────────────────────────
def load_thermal_image(filepath: str) -> np.ndarray:
    """Lädt ein Wärmebild als Graustufen-Matrix mit Umlaut-Workaround."""
    try:
        file_bytes = np.fromfile(filepath, dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError(
                "Bilddaten konnten nicht dekodiert werden. "
                "Format nicht unterstützt oder Datei beschädigt."
            )
        return img
    except Exception as e:
        raise FileNotFoundError(
            f"Bild konnte nicht geladen werden: {filepath}\nDetails: {e}"
        ) from e

# ─────────────────────────────────────────────────────────────────────────────
# FUNKTION 2: Hilfsfunktion für Body-Mask auf der CPU
# ─────────────────────────────────────────────────────────────────────────────
def _extract_body_mask_cpu(
    img: np.ndarray,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> np.ndarray:
    """Extrahiert die Body-Mask auf der CPU mit identischen Schwellenwerten wie Rust."""
    min_val, max_val, _, _ = cv2.minMaxLoc(img)
    dynamic_range = max_val - min_val
    if dynamic_range < 30:
        threshold = max(otsu_min, min(otsu_max, min_val + 0.3 * dynamic_range))
    else:
        otsu_thresh, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        threshold = max(otsu_min, min(otsu_max, otsu_thresh / 2))
        
    _, mask = cv2.threshold(img, int(threshold), 255, cv2.THRESH_BINARY)
    
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    max_dist = dist.max()
    if max_dist < 1e-10:
        return np.zeros_like(mask)
        
    eroded_mask = (dist >= dist_erosion_factor * max_dist).astype(np.uint8) * 255
    return eroded_mask

def _filter_geometric_noise(
    binary_raw: np.ndarray,
    mask: np.ndarray,
    min_area_factor: float,
    min_circularity: float
) -> np.ndarray:
    """Filtert Rauschen und anatomische Artefakte basierend auf Geometrie und Distanztransformation."""
    total_body_area = np.sum(mask == 255)
    min_area = max(10, min_area_factor * total_body_area)
    
    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    min_dist_from_border = max(
        _config.MIN_DIST_FROM_BORDER_ABS,
        binary_raw.shape[1] * _config.MIN_DIST_FROM_BORDER_FACTOR
    )

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_raw)
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
# FUNKTION 3: GPU/PyTorch-Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def _pytorch_gpu_pipeline(
    img: np.ndarray,
    sigma_k: float = _config.DEFAULT_SIGMA_K,
    tophat_factor: float = _config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = _config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = _config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> tuple[np.ndarray, np.ndarray]:
    """GPU-beschleunigte Pipeline unter Verwendung von PyTorch CUDA."""
    mask_cpu = _extract_body_mask_cpu(img, otsu_min, otsu_max, dist_erosion_factor)
    if np.sum(mask_cpu == 255) == 0:
        raise ValueError("Body-Mask ist leer – kein Körper im Bild erkannt.")
        
    device = torch.device('cuda')
    img_t = torch.from_numpy(img).to(device).float()
    mask_t = torch.from_numpy(mask_cpu).to(device)
    
    dim = min(img.shape[0], img.shape[1])
    kernel_large = compute_odd_kernel(dim, tophat_factor)
    pad = kernel_large // 2
    
    with torch.no_grad():
        img_4d = img_t.unsqueeze(0).unsqueeze(0)
        
        # Erode / Dilate
        eroded = -F.max_pool2d(-img_4d, kernel_size=kernel_large, stride=1, padding=pad)
        dilated = F.max_pool2d(eroded, kernel_size=kernel_large, stride=1, padding=pad)
        tophat_t = (img_4d - dilated).squeeze(0).squeeze(0)
        
        diff_t = torch.where(mask_t > 0, tophat_t, torch.zeros_like(tophat_t))
        
        body_pixels = diff_t[mask_t > 0]
        mu_diff = body_pixels.mean()
        sigma_diff = body_pixels.std()
        T_rel = mu_diff + sigma_k * sigma_diff
        
        orig_body_pixels = img_t[mask_t > 0]
        mu_orig = orig_body_pixels.mean()
        
        binary_raw_t = (diff_t > T_rel) & (img_t > mu_orig)
        binary_raw_np = (binary_raw_t.cpu().numpy() * 255).astype(np.uint8)
    
    # Geometrischer Rauschfilter
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

# ─────────────────────────────────────────────────────────────────────────────
# FUNKTION 4: Python-Fallback-Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def _python_fallback_pipeline(
    img: np.ndarray,
    sigma_k: float = _config.DEFAULT_SIGMA_K,
    tophat_factor: float = _config.DEFAULT_TOPHAT_FACTOR,
    min_area_factor: float = _config.DEFAULT_MIN_AREA_FACTOR,
    min_circularity: float = _config.DEFAULT_MIN_CIRCULARITY,
    otsu_min: int = _config.DEFAULT_OTSU_MIN,
    otsu_max: int = _config.DEFAULT_OTSU_MAX,
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> tuple[np.ndarray, np.ndarray]:
    """Python-Fallback-Pipeline mit identischen mathematischen Schritten wie Rust."""
    warnings.warn(
        "[image_processing] Python-Fallback aktiv! Performance beeinträchtigt.",
        RuntimeWarning,
        stacklevel=3,
    )
    
    # 1. Body mask
    mask = _extract_body_mask_cpu(img, otsu_min, otsu_max, dist_erosion_factor)
    total_body_area = np.sum(mask == 255)
    if total_body_area == 0:
        raise ValueError("Body-Mask ist leer – kein Körper im Bild erkannt.")
        
    # 2. Top-Hat
    dim = min(img.shape[0], img.shape[1])
    kernel_large = compute_odd_kernel(dim, tophat_factor)
    kernel_se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_large, kernel_large))
    opened = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel_se)
    tophat = cv2.subtract(img, opened)
    diff_img = cv2.bitwise_and(tophat, tophat, mask=mask)
    
    # 3. Stats threshold
    body_pixels = diff_img[mask > 0]
    mu_diff = np.mean(body_pixels)
    sigma_diff = np.std(body_pixels)
    T_rel = mu_diff + sigma_k * sigma_diff
    
    orig_body_pixels = img[mask > 0]
    mu_orig = np.mean(orig_body_pixels)
    
    binary_raw = ((diff_img > T_rel) & (img > mu_orig)).astype(np.uint8) * 255
    
    # Geometrischer Rauschfilter
    final_mask = _filter_geometric_noise(binary_raw, mask, min_area_factor, min_circularity)
            
    diff_vis = cv2.normalize(diff_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return diff_vis, final_mask

# ─────────────────────────────────────────────────────────────────────────────
# MAIN WRAPPER API
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
    dist_erosion_factor: float = _config.DEFAULT_DIST_EROSION_FACTOR
) -> tuple[np.ndarray, np.ndarray]:
    """Führt die vollständige Bildverarbeitungs-Pipeline aus."""
    global FORCED_BACKEND

    if FORCED_BACKEND == "gpu":
        if _GPU_AVAILABLE:
            return _pytorch_gpu_pipeline(
                img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor
            )
        else:
            raise RuntimeError("GPU-Backend (CUDA) ist nicht verfügbar!")

    elif FORCED_BACKEND == "rust":
        if _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
            img_contiguous = np.ascontiguousarray(img, dtype=np.uint8)
            return _ignite_core.process_thermal_pipeline(
                img_contiguous, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor
            )
        else:
            raise RuntimeError("Natives Rust-Core-Modul ist nicht verfügbar!")

    elif FORCED_BACKEND == "python":
        return _python_fallback_pipeline(
            img, sigma_k, tophat_factor, min_area_factor, min_circularity,
            otsu_min, otsu_max, dist_erosion_factor
        )

    else:  # auto
        if _GPU_AVAILABLE:
            try:
                return _pytorch_gpu_pipeline(
                    img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                    otsu_min, otsu_max, dist_erosion_factor
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
                otsu_min, otsu_max, dist_erosion_factor
            )
        else:
            return _python_fallback_pipeline(
                img, sigma_k, tophat_factor, min_area_factor, min_circularity,
                otsu_min, otsu_max, dist_erosion_factor
            )

# ─────────────────────────────────────────────────────────────────────────────
# VISUAL OVERLAY
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

    # B=85, G=0, R=255 für Neon-Rot
    red_img = np.zeros_like(color_img)
    red_img[:] = [85, 0, 255]

    blended = cv2.addWeighted(color_img, 0.3, red_img, 0.7, 0)
    final_img = np.where(
        hotspots_mask[:, :, None] == 255, blended, color_img
    ).astype(np.uint8)

    return final_img