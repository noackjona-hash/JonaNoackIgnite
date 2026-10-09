[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = $null

# Bevorzuge installierte Python 3.10 / 3.14 Interpreter im Benutzerverzeichnis
$candidates = @(
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    "$env:LOCALAPPDATA\Python\bin\python.exe"
)

foreach ($cand in $candidates) {
    if (Test-Path $cand) {
        $pythonExe = $cand
        break
    }
}

if (-not $pythonExe) {
    if (Get-Command "python" -ErrorAction SilentlyContinue) {
        $pythonExe = "python"
    }
}

if (-not $pythonExe) {
    Write-Error "[FEHLER] Kein funktionierender Python-Interpreter gefunden."
    exit 1
}

& $pythonExe "$scriptDir\cli.py" @ArgsList
