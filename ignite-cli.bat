@echo off
setlocal

set "PYTHON_EXE="

:: 1. Bevorzuge lokale Python 3.10 / 3.14 Pfade
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
) else if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
)

:: 2. Fallback auf System-PATH
if "%PYTHON_EXE%"=="" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        python -c "import sys" >nul 2>nul
        if %errorlevel% equ 0 set "PYTHON_EXE=python"
    )
)

if "%PYTHON_EXE%"=="" (
    echo [FEHLER] Kein funktionierender Python-Interpreter gefunden.
    echo Bitte installiere Python oder setze PATH korrekt.
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0cli.py" %*
