# Build Windows x86-64 worldsim_worker.exe (Milestone 18 — release-blocking).
# Prerequisites: Python 3.12, Visual Studio Build Tools (C++), CMake (for platec).
#
# From repo root (Developer PowerShell for VS):
#   .\packaging\build_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Py = "py -3.12"
} elseif (Test-Path "$Root\worldsim\.venv\Scripts\python.exe") {
    $Py = "$Root\worldsim\.venv\Scripts\python.exe"
} else {
    throw "Python 3.12 not found (install py launcher or worldsim\.venv)"
}

Write-Host "Building vendored platec..."
& "$Root\vendor\pyplatec\scripts\build_windows.ps1"

Write-Host "Installing worldsim + pyinstaller..."
Invoke-Expression "$Py -m pip install -e `"$Root\worldsim`""
Invoke-Expression "$Py -m pip install `"pyinstaller==6.14.2`""

$env:PYTHONPATH = "$Root\worldsim\src;$Root\vendor\pyplatec"
if (Test-Path "$Root\packaging\build") { Remove-Item -Recurse -Force "$Root\packaging\build" }
if (Test-Path "$Root\packaging\dist") { Remove-Item -Recurse -Force "$Root\packaging\dist" }

Write-Host "PyInstaller..."
Invoke-Expression "$Py -m PyInstaller --noconfirm --clean --distpath `"$Root\packaging\dist`" --workpath `"$Root\packaging\build`" `"$Root\packaging\worldsim_worker.spec`""

$Worker = Join-Path $Root "packaging\dist\worldsim_worker\worldsim_worker.exe"
if (-not (Test-Path $Worker)) { throw "missing $Worker" }

Write-Host "Smoke --help"
& $Worker --help | Out-Null
Write-Host "Smoke foundation"
$Out = Join-Path $Root "packaging\dist\smoke_out"
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
& $Worker --seed 1 --output $Out --stage foundation --dry-run
if (-not (Test-Path "$Out\seed_manifest.json")) { throw "smoke failed" }

Write-Host "OK Windows worker → $Worker"
Write-Host "Copy packaging\dist\worldsim_worker\ next to the Godot export (see packaging\README.md)."
