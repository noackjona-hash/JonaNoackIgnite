# ==============================================================================
# IGNITE Medical Imaging Suite v5.0.0 — Automated Installer Build Script
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Building IGNITE Medical Imaging Suite v5.0.0 Release & Installer" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan

$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

# 1. Build Go AVX2 Core
Write-Host "`n[1/4] Compiling Go AVX2 Core Engine..." -ForegroundColor Yellow
Set-Location "$RootDir\core"
go build -o ignite-core.exe ./cmd/ignite-core
if ($LASTEXITCODE -ne 0) { throw "Go build failed!" }

# 2. Publish .NET 10 Desktop Application
Write-Host "`n[2/4] Publishing .NET 10 WPF Desktop Application..." -ForegroundColor Yellow
Set-Location $RootDir
dotnet publish desktop/Ignite.Desktop.csproj -c Release -r win-x64 --self-contained false -o release/publish
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed!" }

# 3. Copy bundled dependencies into publish folder
Write-Host "`n[3/4] Bundling Go core and Lua rules..." -ForegroundColor Yellow
Copy-Item -Path "$RootDir\core\ignite-core.exe" -Destination "$RootDir\release\publish\ignite-core.exe" -Force
Copy-Item -Path "$RootDir\rules" -Destination "$RootDir\release\publish\rules" -Recurse -Force

# 4. Compile Installer with Inno Setup
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
Get-Item "$RootDir\dist\IGNITE_Medical_Suite_v5.0.0_Setup.exe" | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
Write-Host "==================================================================" -ForegroundColor Green
