@echo off
setlocal enabledelayedexpansion
title IGNITE Medical Suite · Standalone Showcase Launcher

echo ======================================================
echo  IGNITE Medical Suite v5.0.0 · Standalone Showcase
echo  Jugend forscht 2026 · Fachgebiet Arbeitswelt
echo ======================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE="

:: 1. Suche nach Python im PATH oder typischen Windows-Installationspfaden
where python >nul 2>nul
if %errorlevel% equ 0 (
    :: Pruefe ob es der echte Python ist oder nur der Windows Store Alias
    python --version >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    )
)

if "!PYTHON_EXE!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 (
        py --version >nul 2>nul
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=py"
        )
    )
)

if "!PYTHON_EXE!"=="" (
    for /d %%P in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%P\python.exe" (
            set "PYTHON_EXE=%%P\python.exe"
        )
    )
)

if "!PYTHON_EXE!"=="" (
    for /d %%P in ("C:\Python*") do (
        if exist "%%P\python.exe" (
            set "PYTHON_EXE=%%P\python.exe"
        )
    )
)

:: 2. Ausfuehrung
if not "!PYTHON_EXE!"=="" (
    echo [OK] Python Runtime gefunden: !PYTHON_EXE!
    echo Starte interaktiven Showcase Server...
    echo.
    "!PYTHON_EXE!" "%SCRIPT_DIR%standalone_demo.py" %*
) else (
    echo [HINWEIS] Kein Python auf diesem Rechner installiert.
    echo Starte Standalone Offline HTML-Showcase im Browser...
    echo.
    start "" "%SCRIPT_DIR%docs\STANDALONE_DEMO_OFFLINE.html"
)

if "%~1"=="" pause
