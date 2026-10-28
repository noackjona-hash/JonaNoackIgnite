# ==============================================================================
# IGNITE Medical Imaging Suite v12.3.4.81 — Automated Installer Build Script
# Pure Go Native Architecture: AVX2 Rechenkern + Win32 PACS Workstation
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Building IGNITE Medical Imaging Suite v12.3.4.81 (Pure Go Suite)" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

# 1. Clean and initialize release directory
$PublishDir = "$RootDir\release\publish"
if (Test-Path $PublishDir) {
    Remove-Item -Path $PublishDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PublishDir -Force | Out-Null

# 2. Build Go AVX2 Core Engine
Write-Host "`n[1/4] Compiling Go AVX2 Core Engine..." -ForegroundColor Yellow
Set-Location "$RootDir\core"
go build -ldflags="-s -w" -o ignite-core.exe ./cmd/ignite-core
if ($LASTEXITCODE -ne 0) { throw "Go core build failed!" }

# 3. Build Go Native Desktop Workstation (Walk GUI with C++ Flair)
Write-Host "`n[2/4] Compiling Go Native Walk Medical Workstation..." -ForegroundColor Yellow
Set-Location "$RootDir\desktop"
go build -ldflags="-H windowsgui -s -w" -o Ignite.exe .
if ($LASTEXITCODE -ne 0) { throw "Go desktop build failed!" }

# 4. Copy bundled dependencies into publish folder
Write-Host "`n[3/4] Bundling Go binaries, Lua rules and manifest..." -ForegroundColor Yellow
Copy-Item -Path "$RootDir\desktop\Ignite.exe" -Destination "$PublishDir\Ignite.exe" -Force
if (Test-Path "$RootDir\desktop\Ignite.exe.manifest") {
    Copy-Item -Path "$RootDir\desktop\Ignite.exe.manifest" -Destination "$PublishDir\Ignite.exe.manifest" -Force
}
Copy-Item -Path "$RootDir\core\ignite-core.exe" -Destination "$PublishDir\ignite-core.exe" -Force
Copy-Item -Path "$RootDir\rules" -Destination "$PublishDir\rules" -Recurse -Force
if (Test-Path "$RootDir\desktop\ignite_medical.db") {
    Copy-Item -Path "$RootDir\desktop\ignite_medical.db" -Destination "$PublishDir\ignite_medical.db" -Force
}

# 5. Compile Installer with Inno Setup
Write-Host "`n[4/4] Compiling Setup Installer with Inno Setup..." -ForegroundColor Yellow
$IsccCandidates = @(
    "C:\Users\jonan\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    throw "Inno Setup Compiler (ISCC.exe) not found!"
}

& $Iscc "$RootDir\installer\setup.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed!" }

Write-Host "`n==================================================================" -ForegroundColor Green
Write-Host " Installer created successfully in dist/:" -ForegroundColor Green
Get-Item "$RootDir\dist\IGNITE_Medical_Suite_v12.3.4.81_Setup.exe" | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host "==================================================================" -ForegroundColor Green
