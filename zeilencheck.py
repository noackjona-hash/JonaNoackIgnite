import subprocess
import sys
import os

# Dateiendungen oder Dateien, die KEIN handgeschriebener Quellcode sind und das Ergebnis verfälschen
EXCLUDE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf", 
    ".zip", ".tar", ".gz", ".7z", ".mp3", ".mp4", ".wav", ".ttf", ".woff", ".woff2",
    ".lock", ".exe", ".iss", ".spec", ".whl", ".bin", ".dat", ".log"
}

EXCLUDE_EXACT_FILES = {
    "Cargo.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "benchmark_results.json"
}

EXCLUDE_DIRS = {
    "test-data", "target", "dist", "build", "ignite_steps_output", "test_venv", ".pytest_cache"
}

def get_repo_root():
    """Ermittelt das Hauptverzeichnis des Git-Repositories."""
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        print("Fehler: Aktueller Ordner ist kein Git-Repository.")
        sys.exit(1)

def get_all_code_files(repo_root):
    """Holt ALLE getrackten und ungetrackten (aber nicht ignorierten) Dateien ab Repo-Root."""
    try:
        cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=repo_root)
        
        all_files = res.stdout.splitlines()
        
        valid_files = []
        for f in all_files:
            file_name = os.path.basename(f)
            ext = os.path.splitext(f)[1].lower()
            parts = f.replace("\\", "/").split("/")

            # Verzeichnisse, Skript selbst, Lockfiles und Binär-Assets überspringen
            if any(d in EXCLUDE_DIRS for d in parts[:-1]):
                continue

            if file_name == "zeilencheck.py" or file_name in EXCLUDE_EXACT_FILES or ext in EXCLUDE_EXTENSIONS:
                continue
                
            valid_files.append(f)

        return sorted(valid_files)
    except Exception as e:
        print(f"Fehler beim Abrufen der Git-Dateien: {e}")
        sys.exit(1)

def count_lines_in_file(full_path):
    """Zählt Zeilen und prüft auf Textdatei."""
    try:
        # Liest Datei als Text; schlägt bei reinen Binärdateien meist fehl
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def main():
    repo_root = get_repo_root()
    print(f"Repository-Root: {repo_root}")
    print("Suche Dateien via Git...")
    
    files = get_all_code_files(repo_root)
    total_files = len(files)

    if total_files == 0:
        print("Keine relevanten Code-Dateien gefunden.")
        return

    print(f"{total_files} relevante Code-Dateien gefunden. Starte Zählung...\n")

    total_lines = 0

    for idx, rel_path in enumerate(files, start=1):
        full_path = os.path.join(repo_root, rel_path)
        lines = count_lines_in_file(full_path)
        total_lines += lines

        percent = (idx / total_files) * 100
        display_name = rel_path if len(rel_path) <= 40 else "..." + rel_path[-37:]
        sys.stdout.write(f"\r[{percent:5.1f}%] {idx}/{total_files} | Zeilen: {total_lines:,} ({display_name:<40})")
        sys.stdout.flush()

    print("\n\n─── Fertig! ───")
    print(f"Gefundene Code-Dateien: {total_files}")
    print(f"Gesamte Codezeilen:     {total_lines:,}")

if __name__ == "__main__":
    main()