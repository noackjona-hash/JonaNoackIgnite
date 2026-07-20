import os
import csv
import logging
import config

AUDIT_LOG_HEADER = [
    "Zeitstempel", "Patienten-ID", "Analysemodus", "Bilddatei",
    "sigma_k", "tophat_factor", "T_min_C", "T_max_C",
    "Hotspot_Pixel", "Max_Temp_C", "Symmetrie_Delta", "Operator"
]

def write_audit_entry(entry: dict) -> None:
    """Schreibt einen Eintrag in den klinischen Audit-Trail (CSV).

    Erstellt die Datei mit Header, falls noch nicht vorhanden.
    Appended jeweils eine neue Zeile.

    Args:
        entry: Dictionary mit den Audit-Feldern.
    """
    file_exists = os.path.exists(config.AUDIT_TRAIL_PATH)
    try:
        with open(config.AUDIT_TRAIL_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=AUDIT_LOG_HEADER)
            if not file_exists:
                writer.writeheader()
            writer.writerow(entry)
    except Exception as e:
        logging.error(f"[AUDIT] Fehler beim Schreiben des Audit-Trails: {e}", exc_info=True)
