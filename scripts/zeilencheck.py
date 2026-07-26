import subprocess
import sys

def get_tracked_and_untracked_files():
    """Holt alle nicht-ignorierten Dateien direkt von Git in einem Rutsch."""
    try:
        # 1. Alle getrackten Dateien
        cmd_tracked = ["git", "ls-files"]
        res_tracked = subprocess.run(cmd_tracked, capture_output=True, text=True, check=True)
        files_tracked = set(res_tracked.stdout.splitlines())

        # 2. Alle ungetrackten, aber NICHT ignorierten Dateien
        cmd_untracked = ["git", "ls-files", "--others", "--exclude-standard"]
        res_untracked = subprocess.run(cmd_untracked, capture_output=True, text=True, check=True)
        files_untracked = set(res_untracked.stdout.splitlines())

        # Zusammenführen
        all_files = sorted(list(files_tracked | files_untracked))
        return all_files
    except subprocess.CalledProcessError:
        print("Fehler: Das aktuelle Verzeichnis ist kein Git-Repository oder Git meldet einen Fehler.")
        sys.exit(1)
    except FileNotFoundError:
        print("Fehler: Git ist auf diesem System nicht installiert.")
        sys.exit(1)

def count_lines_in_file(file_path):
    """Zählt die Zeilen einer Datei (ignoriert Binärdateien)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def main():
    print("Suche Dateien via Git...")
    files = get_tracked_and_untracked_files()
    
    # Skript selbst ausnehmen, falls vorhanden
    files = [f for f in files if f != "count_lines.py"]

    total_files = len(files)
    if total_files == 0:
        print("Keine relevanten Dateien gefunden.")
        return

    print(f"{total_files} relevante Dateien gefunden. Starte Zählung...\n")

    total_lines = 0

    for idx, file_path in enumerate(files, start=1):
        lines = count_lines_in_file(file_path)
        total_lines += lines

        # Statuszeile im Terminal live überschreiben (\r)
        percent = (idx / total_files) * 100
        sys.stdout.write(f"\r[{percent:5.1f}%] Verarbeitet: {idx}/{total_files} Dateien | Zeilen: {total_lines:,} ({file_path[:40]:<40})")
        sys.stdout.flush()

    # Nach Abschluss eine neue Zeile drucken
    print("\n\n─── Fertig! ───")
    print(f"Gesamte Dateien:    {total_files}")
    print(f"Gesamte Codezeilen: {total_lines:,}")

if __name__ == "__main__":
    main()