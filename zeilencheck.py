import os
import subprocess

def is_ignored(path):
    """Prüft via Git, ob ein Pfad durch .gitignore ignoriert wird."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            capture_output=True
        )
        # Returncode 0 bedeutet: Pfad wird ignoriert
        return result.returncode == 0
    except FileNotFoundError:
        print("Fehler: Git ist auf diesem System nicht installiert oder nicht im PATH.")
        exit(1)

def count_lines_in_file(file_path):
    """Zählt die Zeilen einer einzelnen Datei (ignoriert Binärdateien)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def main():
    # Prüfen, ob wir uns in einem Git-Repo befinden
    if not os.path.exists(".git"):
        print("Hinweis: Kein .git-Ordner im aktuellen Verzeichnis gefunden. Git-Ignore funktioniert möglicherweise nicht wie erwartet.")

    total_lines = 0
    total_files = 0

    for root, dirs, files in os.walk("."):
        # Entferne ignorierte Ordner direkt aus 'dirs', damit os.walk nicht hineingeht
        dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d))]

        for file in files:
            file_path = os.path.join(root, file)
            
            # Überspringe das Skript selbst und ignorierte Dateien
            if file == "count_lines.py" or is_ignored(file_path):
                continue

            lines = count_lines_in_file(file_path)
            total_lines += lines
            total_files += 1

    print(f"─── Ergebnis ───")
    print(f"Verarbeitete Dateien: {total_files}")
    print(f"Gesamte Codezeilen:   {total_lines}")

if __name__ == "__main__":
    main()