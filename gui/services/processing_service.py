"""processing_service.py – Hintergrund-Verarbeitungsdienst für die Thermal-Pipeline."""

import threading
import numpy as np
import image_processing

class ThermalProcessingService:
    """Service-Klasse zum Ausführen der Bildverarbeitungs-Pipeline in eigenen Threads."""

    @staticmethod
    def process_async(
        img: np.ndarray,
        sigma_k: float,
        tophat_factor: float,
        min_area_factor: float,
        min_circularity: float,
        otsu_min: int,
        otsu_max: int,
        dist_erosion_factor: float,
        use_mad: bool,
        on_complete_callback,
        on_error_callback
    ):
        """Führt die Thermal-Pipeline im Hintergrund-Thread aus."""

        def _worker():
            try:
                diff_vis, final_mask = image_processing.run_rust_pipeline(
                    img,
                    sigma_k=sigma_k,
                    tophat_factor=tophat_factor,
                    min_area_factor=min_area_factor,
                    min_circularity=min_circularity,
                    otsu_min=otsu_min,
                    otsu_max=otsu_max,
                    dist_erosion_factor=dist_erosion_factor,
                    use_mad=use_mad
                )
                on_complete_callback(diff_vis, final_mask)
            except Exception as e:
                on_error_callback(e)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread
