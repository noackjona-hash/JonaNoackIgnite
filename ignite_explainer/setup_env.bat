@echo off
setlocal enabledelayedexpansion

echo ===============================================================================
echo   IGNITE Medical Imaging Suite - Virtual Environment Setup (Python)
echo   Jugend forscht 2026 - Explainer Pipeline
echo ===============================================================================

set "PYTHON_EXE="

:: 1. Suche nach Python 3.10 / 3.11 / 3.12 / 3.14
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
) else if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
)

:: 2. Fallback: PATH
if "%PYTHON_EXE%"=="" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        python -c "import sys" >nul 2>nul
        if %errorlevel% equ 0 set "PYTHON_EXE=python"
    )
)

if "%PYTHON_EXE%"=="" (
    echo [FEHLER] Kein funktionierender Python-Interpreter gefunden!
    echo Bitte installiere Python 3.10+ oder fuge es zu PATH hinzu.
    pause
    exit /b 1
)

echo [OK] Verwende Python: "%PYTHON_EXE%"
cd /d "%~dp0"

:: 3. Erstelle virtuelles Environment .venv
if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Erstelle isolierte virtuelle Umgebung in .venv ...
    "%PYTHON_EXE%" -m venv .venv
    if %errorlevel% neq 0 (
        echo [FEHLER] Erstellung des virtuellen Environments fehlgeschlagen!
        pause
        exit /b 1
    )
    echo [OK] Virtuelle Umgebung erfolgreich angelegt.
) else (
    echo [INFO] Virtuelle Umgebung .venv existiert bereits.
)

:: 4. Installiere Abhangigkeiten
echo [INFO] Installiere/Aktualisiere Abhangigkeiten aus requirements.txt ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo.
    echo ===============================================================================
    echo   SETUP ERFOLGREICH ABGESCHLOSSEN!
    echo   Starte die Pipeline mit:  run_pipeline.bat
    echo ===============================================================================
) else (
    echo [WARNUNG] Einige Pakete konnten nicht installiert werden. Bitte Logs prufen.
)

pause
