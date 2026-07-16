Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

& $VenvPython -m compileall -q (Join-Path $ProjectRoot "src")
if ($LASTEXITCODE -ne 0) { throw "compileall failed with exit code $LASTEXITCODE" }
& $VenvPython -m unittest discover -s (Join-Path $ProjectRoot "tests") -v
if ($LASTEXITCODE -ne 0) { throw "unit tests failed with exit code $LASTEXITCODE" }
& $VenvPython -m normative_world_model check-isolation
if ($LASTEXITCODE -ne 0) { throw "isolation audit failed with exit code $LASTEXITCODE" }
