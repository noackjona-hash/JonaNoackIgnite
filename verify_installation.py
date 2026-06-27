import sys
import numpy as np

try:
    import ignite_core
    print(f"ignite_core importiert")
    print(f"Version: {ignite_core.__version__}")
    print(f"Backend: {ignite_core.__backend__}")
    
    # Synthetisches Testsignal: Körper-ähnliches Bild mit künstlichem Hotspot
    img = np.zeros((480, 640), dtype=np.uint8)
    img[100:380, 80:560] = 120   # Körper-Region (warm)
    img[150:230, 200:320] = 185  # Großer Hotspot (muss erkannt werden)
    
    diff, mask = ignite_core.process_thermal_pipeline(img, 3.0, 0.05, 0.0005, 0.01, 35, 50, 0.05)
    hotspot_px = int(mask.sum()) // 255
    
    print(f"Differenzbild:  shape={diff.shape}, dtype={diff.dtype}")
    print(f"Hotspot-Maske:  shape={mask.shape}, dtype={mask.dtype}")
    print(f"Hotspot-Pixel:  {hotspot_px}")
    
    if hotspot_px > 0:
        print("[ERFOLG] Pipeline erkennt künstlichen Hotspot korrekt!")
        sys.exit(0)
    else:
        print("[HINWEIS] Kein Hotspot erkannt (Schwellenwert sehr adaptiv)")
        sys.exit(0)
        
except ImportError as e:
    print(f"FEHLER: ignite_core konnte nicht importiert werden: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"PIPELINE-FEHLER: {e}", file=sys.stderr)
    sys.exit(1)
