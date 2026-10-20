# ==============================================================================
# build_all_platforms.ps1 — Universal Multi-OS Package Generator fuer IGNITE v5.0
# ==============================================================================

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $RootDir) { $RootDir = (Get-Location).Path }
$DistDir = Join-Path $RootDir "dist"
$CoreDir = Join-Path $RootDir "core"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " IGNITE Medical Suite v5.0.0 -- Multi-Platform Release Builder" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

# 1. Verzeichnisse anlegen
$platforms = @("windows", "linux-amd64", "linux-arm64", "android", "macos")
foreach ($p in $platforms) {
    $pDir = Join-Path $DistDir $p
    if (-not (Test-Path $pDir)) {
        New-Item -ItemType Directory -Path $pDir -Force | Out-Null
    }
}

# 2. Go Core Binaries kompilieren
Write-Host "`n[1/4] Kompiliere Go-Core fuer alle Plattformen..." -ForegroundColor Yellow
Set-Location $CoreDir

# Windows amd64 (AVX2)
Write-Host "  * Windows x86_64 (AVX2)..." -ForegroundColor Gray
$env:GOOS = "windows"; $env:GOARCH = "amd64"; $env:CGO_ENABLED = "0"
go build -ldflags="-s -w" -o (Join-Path $DistDir "windows\ignite-core.exe") ./cmd/ignite-core
Copy-Item (Join-Path $DistDir "windows\ignite-core.exe") (Join-Path $CoreDir "ignite-core.exe") -Force

# Linux amd64 (AVX2 fuer Fedora, Ubuntu, Arch)
Write-Host "  * Linux x86_64 (Fedora/Ubuntu AVX2)..." -ForegroundColor Gray
$env:GOOS = "linux"; $env:GOARCH = "amd64"; $env:CGO_ENABLED = "0"
go build -ldflags="-s -w" -o (Join-Path $DistDir "linux-amd64\ignite-core") ./cmd/ignite-core

# Linux arm64 (Scalar Fallback fuer Fedora aarch64, Raspberry Pi, Android)
Write-Host "  * Linux ARM64 (Fedora aarch64, Raspberry Pi, Android)..." -ForegroundColor Gray
$env:GOOS = "linux"; $env:GOARCH = "arm64"; $env:CGO_ENABLED = "0"
go build -ldflags="-s -w" -o (Join-Path $DistDir "linux-arm64\ignite-core") ./cmd/ignite-core
Copy-Item (Join-Path $DistDir "linux-arm64\ignite-core") (Join-Path $DistDir "android\ignite-core-android-arm64") -Force

# macOS darwin-arm64 & darwin-amd64
Write-Host "  * macOS (Apple Silicon arm64 & Intel amd64)..." -ForegroundColor Gray
$env:GOOS = "darwin"; $env:GOARCH = "arm64"; $env:CGO_ENABLED = "0"
go build -ldflags="-s -w" -o (Join-Path $DistDir "macos\ignite-core-darwin-arm64") ./cmd/ignite-core
$env:GOOS = "darwin"; $env:GOARCH = "amd64"; $env:CGO_ENABLED = "0"
go build -ldflags="-s -w" -o (Join-Path $DistDir "macos\ignite-core-darwin-amd64") ./cmd/ignite-core

Set-Location $RootDir

# 3. Gemeinsame Assets verteilen
Write-Host "`n[2/4] Buendle Standalone-Showcases, Lua-Regeln und Testdaten..." -ForegroundColor Yellow
foreach ($p in $platforms) {
    $pDir = Join-Path $DistDir $p
    
    Copy-Item (Join-Path $RootDir "standalone_demo.py") (Join-Path $pDir "standalone_demo.py") -Force
    Copy-Item (Join-Path $RootDir "docs\STANDALONE_DEMO_OFFLINE.html") (Join-Path $pDir "STANDALONE_DEMO_OFFLINE.html") -Force
    
    $rulesDir = Join-Path $pDir "rules"
    if (-not (Test-Path $rulesDir)) { New-Item -ItemType Directory $rulesDir -Force | Out-Null }
    Copy-Item (Join-Path $RootDir "rules\*") $rulesDir -Recurse -Force
    
    $testDir = Join-Path $pDir "test-data"
    if (-not (Test-Path $testDir)) { New-Item -ItemType Directory $testDir -Force | Out-Null }
    Copy-Item (Join-Path $RootDir "test-data\bild (1).jpeg") $testDir -Force
    Copy-Item (Join-Path $RootDir "test-data\bild (2).jpeg") $testDir -Force
    Copy-Item (Join-Path $RootDir "test-data\bild (3).jpeg") $testDir -Force
}

# 4. Plattform-spezifische Launcher kopieren
Write-Host "`n[3/4] Erzeuge Starter und Anleitungen..." -ForegroundColor Yellow
Copy-Item (Join-Path $RootDir "run_demo.bat") (Join-Path $DistDir "windows\run_demo.bat") -Force
Copy-Item (Join-Path $RootDir "run_demo.sh") (Join-Path $DistDir "linux-amd64\run_demo.sh") -Force
Copy-Item (Join-Path $RootDir "run_demo.sh") (Join-Path $DistDir "linux-arm64\run_demo.sh") -Force
Copy-Item (Join-Path $RootDir "run_demo.sh") (Join-Path $DistDir "android\run_demo.sh") -Force
Copy-Item (Join-Path $RootDir "run_demo.sh") (Join-Path $DistDir "macos\run_demo.sh") -Force

if (Test-Path (Join-Path $RootDir "desktop-go\ignite-workstation-go.exe")) {
    Copy-Item (Join-Path $RootDir "desktop-go\ignite-workstation-go.exe") (Join-Path $DistDir "windows\ignite-workstation-go.exe") -Force
}

# 5. Zusammenfassung & Ergebnis-Tabelle
Write-Host "`n[4/4] Pruefe fertige Releases in dist/..." -ForegroundColor Yellow
Write-Host "`n==================================================================" -ForegroundColor Green
Write-Host " ALL PLATFORM BUILDS COMPLETED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green

foreach ($p in $platforms) {
    $pDir = Join-Path $DistDir $p
    Write-Host "`n[+] Plattform: $p ($pDir)" -ForegroundColor Cyan
    Get-ChildItem -Path $pDir | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
}

Write-Host "==================================================================" -ForegroundColor Green
