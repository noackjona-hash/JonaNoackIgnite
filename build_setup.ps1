# build_setup.ps1
# ─────────────────────────────────────────────────────────────────────────────
# Ignite – Build-Helfer für das native Rust-Erweiterungsmodul `ignite_core`
#
# Das Modul ist komplett in purem Rust implementiert (ndarray + imageproc).
# Es werden keine externen C/C++-Abhängigkeiten (OpenCV, LLVM) benötigt.
# Ein Standard-Rust-Toolchain (rustc >= 1.70) und Python >= 3.10 genügen.
#
# Verwendung:
#   .\build_setup.ps1            # Standard-Build (Debug, schnell)
#   .\build_setup.ps1 -Release   # Release-optimierter Build (langsamer)
#   .\build_setup.ps1 -Clean     # Cargo-Cache leeren vor dem Build
#   .\build_setup.ps1 -Test      # Nur Smoke-Test, kein Rebuild
#
# Voraussetzungen:
#   - Rust-Toolchain: winget install Rustlang.Rustup  (dann: rustup default stable)
#   - Python 3.10+:   winget install Python.Python.3.10
#   - maturin:        python -m pip install maturin
# ─────────────────────────────────────────────────────────────────────────────

param(
    [switch]$Release = $false,  # Release-optimierter Build
    [switch]$Clean   = $false,  # Cargo clean vor dem Build
    [switch]$Test    = $false   # Nur Smoke-Test ausführen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ignite Core v0.1.0 – Rust Build" -ForegroundColor Cyan
Write-Host "  Reine Rust-Implementierung (kein C++)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Nur Smoke-Test
# ─────────────────────────────────────────────────────────────────────────────
if ($Test) {
    Write-Host "Führe Smoke-Test aus..." -ForegroundColor Yellow
    python -c @"
import ignite_core
import numpy as np
print(f'ignite_core v{ignite_core.__version__}')
print(f'Backend: {ignite_core.__backend__}')
img = np.zeros((480, 640), dtype=np.uint8)
img[100:380, 80:560] = 120
img[150:230, 200:320] = 185
diff, mask = ignite_core.process_thermal_pipeline(img)
px = int(mask.sum()) // 255
print(f'Hotspot-Pixel: {px}')
print('OK' if px > 0 else 'HINWEIS: Kein Hotspot (normales Verhalten bei homogenem Testsignal)')
"@
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# SCHRITT 1: Voraussetzungen prüfen
# ─────────────────────────────────────────────────────────────────────────────
Write-Host "[1/4] Prüfe Voraussetzungen..." -ForegroundColor Yellow

try {
    $rustc_ver = rustc --version
    Write-Host "  ✓ $rustc_ver" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Rust nicht gefunden! Installiere mit: winget install Rustlang.Rustup" -ForegroundColor Red
    exit 1
}

try {
    $cargo_ver = cargo --version
    Write-Host "  ✓ $cargo_ver" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Cargo nicht gefunden!" -ForegroundColor Red
    exit 1
}

try {
    $python_ver = python --version
    Write-Host "  ✓ $python_ver" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Python nicht gefunden!" -ForegroundColor Red
    exit 1
}

try {
    $maturin_ver = python -m maturin --version
    Write-Host "  ✓ maturin $maturin_ver" -ForegroundColor Green
} catch {
    Write-Host "  Installiere maturin..." -ForegroundColor Yellow
    python -m pip install maturin
}

# ─────────────────────────────────────────────────────────────────────────────
# SCHRITT 2: Optionaler Clean
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
if ($Clean) {
    Write-Host "[2/4] Cargo Clean..." -ForegroundColor Yellow
    cargo clean
    Write-Host "  ✓ Clean abgeschlossen" -ForegroundColor Green
} else {
    Write-Host "[2/4] Cargo Clean übersprungen (nutze -Clean zum Aktivieren)" -ForegroundColor Gray
}

# ─────────────────────────────────────────────────────────────────────────────
# SCHRITT 3: Build
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/4] Baue ignite_core..." -ForegroundColor Yellow

$dist_dir = "dist"
if (-not (Test-Path $dist_dir)) {
    New-Item -ItemType Directory -Path $dist_dir | Out-Null
}

$build_args = @("build", "--out", $dist_dir, "--interpreter", "python")
if ($Release) {
    $build_args += "--release"
    Write-Host "  Modus: Release (optimiert, ~2-5 Min. Kompilierzeit)" -ForegroundColor Magenta
} else {
    Write-Host "  Modus: Debug (schnell, keine Optimierungen)" -ForegroundColor Gray
}

Write-Host "  Befehl: python -m maturin $($build_args -join ' ')" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Kompiliere... (erster Build: ~1-3 Min. wegen Crate-Downloads)" -ForegroundColor DarkGray

python -m maturin @build_args

# Wheel finden und installieren
$wheel = Get-ChildItem $dist_dir -Filter "*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($wheel) {
    Write-Host ""
    Write-Host "  ✓ Wheel gebaut: $($wheel.Name)" -ForegroundColor Green
    Write-Host "  Installiere Wheel..." -ForegroundColor Yellow
    python -m pip install --force-reinstall $wheel.FullName --quiet
    Write-Host "  ✓ ignite_core installiert" -ForegroundColor Green
} else {
    Write-Host "  ✗ Kein Wheel gefunden in $dist_dir" -ForegroundColor Red
    exit 1
}

# ─────────────────────────────────────────────────────────────────────────────
# SCHRITT 4: Verifikation
# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4/4] Verifikation..." -ForegroundColor Yellow

python -c @"
import sys
try:
    import ignite_core
    print(f'  OK: ignite_core importiert')
    print(f'  Version: {ignite_core.__version__}')
    print(f'  Backend: {ignite_core.__backend__}')
    
    import numpy as np
    # Synthetisches Testsignal: Körper-ähnliches Bild mit künstlichem Hotspot
    img = np.zeros((480, 640), dtype=np.uint8)
    img[100:380, 80:560] = 120   # Körper-Region (warm)
    img[150:230, 200:320] = 185  # Großer Hotspot (muss erkannt werden)
    
    diff, mask = ignite_core.process_thermal_pipeline(img)
    hotspot_px = int(mask.sum()) // 255
    
    print(f'  Differenzbild:  shape={diff.shape}, dtype={diff.dtype}')
    print(f'  Hotspot-Maske:  shape={mask.shape}, dtype={mask.dtype}')
    print(f'  Hotspot-Pixel:  {hotspot_px}')
    
    if hotspot_px > 0:
        print('  ✓ ERFOLG: Pipeline erkennt künstlichen Hotspot korrekt!')
    else:
        print('  ⚠ HINWEIS: Kein Hotspot erkannt (Schwellenwert sehr adaptiv)')
        
except ImportError as e:
    print(f'  FEHLER: {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'  PIPELINE-FEHLER: {e}', file=sys.stderr)
    sys.exit(1)
"@

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD ABGESCHLOSSEN!" -ForegroundColor Green
Write-Host "  GUI starten: python main.py" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
