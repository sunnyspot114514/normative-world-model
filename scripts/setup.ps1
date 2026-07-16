Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$Directories = @(
    ".cache\uv",
    ".cache\pip",
    ".cache\huggingface\hub",
    ".cache\huggingface\datasets",
    ".cache\torch",
    ".cache\wandb",
    ".cache\wandb-config",
    ".tmp",
    "data\raw",
    "data\generated",
    "models",
    "runs\wandb",
    "artifacts"
)

foreach ($RelativePath in $Directories) {
    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $RelativePath) | Out-Null
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    & py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -m compileall -q (Join-Path $ProjectRoot "src")
& $VenvPython -m unittest discover -s (Join-Path $ProjectRoot "tests") -v
& $VenvPython -m normative_world_model check-isolation

Write-Host "Project environment is ready at $ProjectRoot\.venv"
Write-Host "Enter it with: . .\scripts\enter.ps1"

