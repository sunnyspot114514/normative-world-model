Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

& $VenvPython -m normative_world_model check-phase1
if ($LASTEXITCODE -ne 0) { throw "Phase-1 artifact verification failed" }
