Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $CommandArguments
    )

    & python @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: python $($CommandArguments -join ' ')"
    }
}

Invoke-Python -CommandArguments @("scripts/check_python.py")
Invoke-Python -CommandArguments @("scripts/render_manifests.py", "--check")
Invoke-Python -CommandArguments @("scripts/validate_repository.py", "--strict")
Invoke-Python -CommandArguments @("-m", "unittest", "discover", "-s", "tests", "-v")
Invoke-Python -CommandArguments @("-m", "compileall", "-q", "scripts", "tests")
Invoke-Python -CommandArguments @("scripts/evidence_gate.py", "examples/completion-evidence.pass.json", "--contract", "examples/task-contract.static-validation.json")

foreach ($fixture in @("examples/completion-evidence.fail.json", "examples/completion-evidence.partial.json")) {
    $output = & python scripts/evidence_gate.py $fixture 2>&1
    $status = $LASTEXITCODE
    if ($status -eq 0) {
        throw "Non-complete evidence fixture was accepted: $fixture"
    }
    if ($status -ne 1) {
        $output | Write-Error
        throw "Evidence gate failed unexpectedly with exit code $status`: $fixture"
    }
    Write-Output "negative evidence fixture rejected: PASS ($fixture)"
}

Invoke-Python -CommandArguments @("scripts/score_eval_runs.py", "evals/fixtures/sample-runs.jsonl", "--allow-synthetic")
Write-Output "bootstrap: PASS"
