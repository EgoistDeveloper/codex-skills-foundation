$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "Python 3 is required."
}

& $Python.Source scripts/validate_repository.py --strict
& $Python.Source -m unittest discover -s tests -v
& $Python.Source -m compileall -q scripts plugins/engineering-foundation/scripts tests

Write-Host "Foundation validation passed."
