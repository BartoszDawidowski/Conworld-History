# Build worldsim-platec on Windows (Milestone 3).
# Requires: Visual Studio Build Tools with "Desktop development with C++",
# Python 3.12, and optionally uv.
#
# Usage (from repo root, Developer PowerShell for VS):
#   .\vendor\pyplatec\scripts\build_windows.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location (Join-Path $Root "vendor\pyplatec")

Write-Host "Building worldsim-platec (extended PyPlatec)..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv pip install -e .
} else {
    py -3.12 -m pip install -e .
}

py -3.12 -c "import platec; assert hasattr(platec, 'get_agemap'); print('OK', platec.__file__)"
Write-Host "Windows build smoke check passed."
