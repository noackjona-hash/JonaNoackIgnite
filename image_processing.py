"""image_processing.py – Python-Wrapper für den Ignite-Rust-Core.

Dieses Modul dient als schlanke Vermittlungsschicht zwischen dem Tkinter-Frontend
(`gui.py`) und dem nativen Rust-Erweiterungsmodul `ignite_core`.

Architektur:
    GUI → image_processing.py (Python-Wrapper) → ignite_core.pyd (Rust-Core)

Fallback-Strategie:
    Falls `ignite_core` nicht importierbar ist (z.B. Build noch nicht ausgeführt),
    wird automatisch auf die ursprüngliche Python-Implementierung zurückgegriffen.
    Eine Warnung in der Konsole informiert den Nutzer über den aktiven Pfad.

Hinweis zum Ladepfad (Umlaut-Workaround):
    `load_thermal_image()` nutzt `np.fromfile()` statt `cv2.imread()`, um
    Windows-Dateipfade mit Umlauten (ä, ö, ü, ß) korrekt zu unterstützen.
    cv2.imread() schlägt bei nicht-ASCII-Pfaden auf Windows fehl.
"""

import warnings
import cv2
import numpy as np

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

# 3. Aktives Backend auf der Konsole ausgeben (nur das primär genutzte)
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
        "  Führe '.\\ build_setup.ps1' aus, um das Rust-Modul zu bauen.\n"
        "  Nutze Python-Fallback-Pipeline (geringere Erkennungsrate).",
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


# ─────────────────────────────────────────────────────────────────────────────
# FUNKTION 1: Wärmebild laden (unverändert, Umlaut-Workaround)
# ─────────────────────────────────────────────────────────────────────────────

def load_thermal_image(filepath: str) -> np.ndarray:
    """Lädt ein Wärmebild als Graustufen-Matrix.

    Nutzt `np.fromfile()` + `cv2.imdecode()` statt `cv2.imread()`, um
    Windows-Dateipfade mit Sonderzeichen (Umlaute, Leerzeichen) korrekt
    zu unterstützen. `cv2.imread()` schlägt bei nicht-ASCII-Pfaden fehl.

    Args:
        filepath: Absoluter oder relativer Dateipfad zum Wärmebild.
                  Unterstützt PNG, JPG, BMP, TIFF und weitere OpenCV-Formate.

    Returns:
        NumPy-Array der Form (H, W), dtype=uint8, Graustufen (0–255).
        Jeder Pixelwert repräsentiert die relative Temperatur im Bild.

    Raises:
        FileNotFoundError: Wenn das Bild nicht geladen oder dekodiert werden kann.
    """
    try:
        # np.fromfile liest rohe Bytes, umgeht os.fsencode()-Probleme mit Umlauten
        file_bytes = np.fromfile(filepath, dtype=np.uint8)

        # cv2.IMREAD_GRAYSCALE: Direkte Graustufen-Dekodierung ohne Farbkonversion
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
# FUNKTION 2: Haupt-Pipeline (Rust-Core oder Python-Fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_body_mask_cpu(img: np.ndarray) -> np.ndarray:
    """Extrahiert die Body-Mask auf der CPU mit identischen Schwellenwerten wie Rust."""
    # Otsu-Binarisierung mit adaptivem Fallback
    otsu_thresh, _ = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = max(35, min(50, otsu_thresh / 2))
    _, mask = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY)
    
    # Distanztransformation
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    max_dist = dist.max()
    if max_dist < 1e-10:
        return np.zeros_like(mask)
        
    # Adaptive Erosion via 5 %
    eroded_mask = (dist >= 0.05 * max_dist).astype(np.uint8) * 255
    return eroded_mask


def _pytorch_gpu_pipeline(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """GPU-beschleunigte Pipeline unter Verwendung von PyTorch CUDA."""
    mask_cpu = _extract_body_mask_cpu(img)
    if np.sum(mask_cpu == 255) == 0:
        raise ValueError("Body-Mask ist leer – kein Körper im Bild erkannt.")
        
    device = torch.device('cuda')
    img_t = torch.from_numpy(img).to(device).float()
    mask_t = torch.from_numpy(mask_cpu).to(device)
    
    # Top-Hat auf der GPU (mittels max_pool2d)
    w = img.shape[1]
    kernel_large = (w * 5 // 100) | 1
    pad = kernel_large // 2
    
    img_4d = img_t.unsqueeze(0).unsqueeze(0)
    
    # Erode: -max_pool2d(-img)
    eroded = -F.max_pool2d(-img_4d, kernel_size=kernel_large, stride=1, padding=pad)
    # Dilate: max_pool2d(eroded)
    dilated = F.max_pool2d(eroded, kernel_size=kernel_large, stride=1, padding=pad)
    # Top-Hat: original - dilated
    tophat_t = (img_4d - dilated).squeeze(0).squeeze(0)
    
    # Maskierung des Top-Hat-Differenzbildes
    diff_t = torch.where(mask_t > 0, tophat_t, torch.zeros_like(tophat_t))
    
    # Statistischer Schwellenwert µ + 3σ + Absolutwert-Filter auf der GPU
    body_pixels = diff_t[mask_t > 0]
    mu_diff = body_pixels.mean()
    sigma_diff = body_pixels.std()
    T_rel = mu_diff + 3.0 * sigma_diff
    
    orig_body_pixels = img_t[mask_t > 0]
    mu_orig = orig_body_pixels.mean()
    
    binary_raw_t = (diff_t > T_rel) & (img_t > mu_orig)
    binary_raw_np = (binary_raw_t.cpu().numpy() * 255).astype(np.uint8)
    
    # Geometrischer Rauschfilter auf der CPU (Connected Components)
    total_body_area = np.sum(mask_cpu == 255)
    min_area = max(10, 0.0005 * total_body_area)
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_raw_np)
    final_mask = np.zeros_like(binary_raw_np)
    
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
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
        if circularity >= 0.01:
            cv2.drawContours(final_mask, [cnt], -1, 255, thickness=cv2.FILLED)
            
    # Visualisierung des Differenzbildes (Min-Max-Normalisierung)
    diff_np = diff_t.cpu().numpy()
    min_val = diff_np.min()
    max_val = diff_np.max()
    diff_range = max_val - min_val
    if diff_range < 1e-10:
        diff_vis = np.zeros_like(diff_np, dtype=np.uint8)
    else:
        diff_vis = ((diff_np - min_val) * 255.0 / diff_range).astype(np.uint8)
        
    return diff_vis, final_mask


def run_rust_pipeline(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Führt die vollständige Bildverarbeitungs-Pipeline aus.
    
    Nutzt vorzugsweise die PyTorch-CUDA GPU-Pipeline. Falls diese fehlschlägt oder
    nicht verfügbar ist, wird das Rust-Core-Modul geladen. Als Letztes greift
    der reine Python-CPU-Fallback.
    """
    if _GPU_AVAILABLE:
        try:
            return _pytorch_gpu_pipeline(img)
        except Exception as e:
            warnings.warn(
                f"[image_processing] GPU-Pipeline fehlgeschlagen! Weiche auf Rust-CPU aus. Details: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

    if _RUST_BACKEND_AVAILABLE and _ignite_core is not None:
        # ── Rust-Pfad ────────────────────────────────────────────────────────
        img_contiguous = np.ascontiguousarray(img, dtype=np.uint8)
        diff_img, hotspot_mask = _ignite_core.process_thermal_pipeline(img_contiguous)
        return diff_img, hotspot_mask

    else:
        # ── Python-Fallback-Pfad ─────────────────────────────────────────────
        return _python_fallback_pipeline(img)


def _python_fallback_pipeline(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Python-Fallback-Pipeline für den Fall, dass der Rust-Core nicht verfügbar ist.

    Implementiert eine vereinfachte Version der Pipeline mit fixen Parametern.
    Dieser Pfad wird ausschließlich als Notfall-Fallback genutzt und hat eine
    niedrigere Erkennungsrate als der Rust-Core.

    Args:
        img: Graustufen-Eingabebild, (H, W), uint8.

    Returns:
        Tuple (diff_img, hotspot_mask) – analog zu `run_rust_pipeline`.
    """
    warnings.warn(
        "[image_processing] Python-Fallback aktiv! Erkennungsrate suboptimal.",
        RuntimeWarning,
        stacklevel=3,
    )

    # Schritt 1: Body-Mask via Otsu
    _, mask = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.erode(mask, kernel, iterations=2)

    # Schritt 2: Gauß-basiertes Differenzbild (ersetzt durch Top-Hat im Rust-Core)
    local_baseline = cv2.GaussianBlur(img, (61, 61), 0)
    diff_img = cv2.subtract(img, local_baseline)
    diff_img = cv2.bitwise_and(diff_img, diff_img, mask=mask)

    # Schritt 3: Fixer Schwellenwert (ersetzt durch µ+2σ im Rust-Core)
    _, hotspots = cv2.threshold(diff_img, 18, 255, cv2.THRESH_BINARY)
    kernel_s = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(hotspots, cv2.MORPH_OPEN, kernel_s)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_s)

    # Schritt 4: Kontur-Mindestfläche (fixer Wert, kein Circularity-Filter)
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    final_mask = np.zeros_like(cleaned)
    for cnt in contours:
        if cv2.contourArea(cnt) >= 150:
            cv2.drawContours(final_mask, [cnt], -1, 255, thickness=cv2.FILLED)

    diff_vis = cv2.normalize(diff_img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return diff_vis, final_mask


# ─────────────────────────────────────────────────────────────────────────────
# FUNKTION 3: Visuelles Overlay (unverändert, reine Visualisierung)
# ─────────────────────────────────────────────────────────────────────────────

def create_hotspot_overlay(original_img: np.ndarray, hotspots_mask: np.ndarray) -> np.ndarray:
    """Erstellt ein visuelles Overlay: Originalbild mit leuchtend roten Hotspots.

    Diese Funktion ist reine Visualisierung und benötigt keine Rust-Beschleunigung,
    da sie einmalig pro Bild ausgeführt wird.

    Args:
        original_img:  Graustufen-Originalbild, shape (H, W), dtype=uint8.
        hotspots_mask: Binäre Hotspot-Maske (0 oder 255), shape (H, W), dtype=uint8.
                       Output von `run_rust_pipeline()`.

    Returns:
        BGR-Farbbild mit rotem Overlay auf Hotspot-Regionen, shape (H, W, 3), dtype=uint8.
        OpenCV-Konvention: BGR-Kanalreihenfolge.
    """
    # Graustufen → BGR für addWeighted-Kompatibilität
    color_img = cv2.cvtColor(original_img, cv2.COLOR_GRAY2BGR)

    # Neon-Rotes Overlay-Bild (BGR: B=85, G=0, R=255 für #FF0055)
    red_img = np.zeros_like(color_img)
    red_img[:] = [85, 0, 255]

    # 70 % Rot + 30 % Original für sichtbare, aber nicht überdeckende Markierung
    blended = cv2.addWeighted(color_img, 0.3, red_img, 0.7, 0)

    # Overlay nur auf Hotspot-Pixel anwenden, Rest behält Originalfarbe
    final_img = np.where(
        hotspots_mask[:, :, None] == 255, blended, color_img
    ).astype(np.uint8)

    return final_img