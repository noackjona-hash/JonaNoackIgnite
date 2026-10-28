@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtuelle Umgebung nicht gefunden. Starte automatisches Setup ...
    call setup_env.bat
    if not exist ".venv\Scripts\python.exe" (
        echo [FEHLER] Setup konnte nicht abgeschlossen werden.
        pause
        exit /b 1
    )
)

echo [START] Fuhre IGNITE 42-Stufen Explainer Pipeline aus ...
".venv\Scripts\python.exe" main.py %*

if %errorlevel% neq 0 (
    echo [FEHLER] Pipeline mit Fehlercode %errorlevel% beendet.
) else (
    echo.
    echo [FERTIG] Alle Stufen wurden erfolgreich exportiert!
    echo Offne den Ergebnisordner: exports\
)
pause
