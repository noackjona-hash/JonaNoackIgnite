"""export_service.py – Exportdienste für PDF-Berichte und CSV-Protokolle."""

import os
import csv
import logging
import datetime
import config
from audit_log import write_audit_entry

class ExportService:
    """Service-Klasse zum Generieren von klinischen Analyseressourcen (PDF/CSV)."""

    @staticmethod
    def export_audit_log(entries: list, output_path: str = config.AUDIT_TRAIL_PATH):
        """Exportiert das Audit-Protokoll in eine CSV-Datei."""
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "PatientID", "Backend", "HotspotsDetected", "MeanTempC", "MaxTempC"])
                for entry in entries:
                    writer.writerow([
                        entry.get("timestamp", ""),
                        entry.get("patient_id", ""),
                        entry.get("backend", ""),
                        entry.get("hotspots_count", 0),
                        entry.get("mean_temp", 0.0),
                        entry.get("max_temp", 0.0)
                    ])
            return True
        except Exception as e:
            logging.error(f"Fehler beim Exportieren des Audit-Logs: {e}")
            return False

    @staticmethod
    def log_clinical_audit(patient_id: str, backend: str, hotspots_count: int, mean_temp: float, max_temp: float):
        """Fügt einen Eintrag zum persistenten klinischen Audit-Trail hinzu."""
        return write_audit_entry(patient_id, backend, hotspots_count, mean_temp, max_temp)
