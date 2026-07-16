Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

$Requirements = Join-Path $ProjectRoot "requirements-model.txt"
$TorchIndex = "https://download.pytorch.org/whl/cu126"

& $VenvPython -m pip install `
    --index-url $TorchIndex `
    "torch==2.9.1+cu126"
if ($LASTEXITCODE -ne 0) {
    throw "PyTorch installation failed with exit code $LASTEXITCODE"
}

$NonTorch = @(
    "transformers==4.57.6",
    "accelerate==1.12.0",
    "peft==0.18.0",
    "safetensors==0.7.0",
    "hf_xet==1.5.1"
)
& $VenvPython -m pip install @NonTorch
if ($LASTEXITCODE -ne 0) {
    throw "Model dependency installation failed with exit code $LASTEXITCODE"
}

& $VenvPython (Join-Path $ProjectRoot "scripts\check-model-environment.py")
if ($LASTEXITCODE -ne 0) {
    throw "Model dependency verification failed with exit code $LASTEXITCODE"
}

Write-Host "Model dependencies match $Requirements"
