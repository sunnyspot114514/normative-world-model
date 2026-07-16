Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$ActivateScript = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path -LiteralPath $ActivateScript)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

. $ActivateScript
Set-Location -LiteralPath $ProjectRoot
Write-Host "Activated isolated environment: $ProjectRoot\.venv"

