Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "Python 3.11 or newer is required."
}

& $Python.Source scripts/bootstrap.py
if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap failed with exit code $LASTEXITCODE."
}
