Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Set-ProjectPathEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $Value = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $RelativePath))
    [System.Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

Set-ProjectPathEnvironment -Name "NWM_PROJECT_ROOT" -RelativePath "."
Set-ProjectPathEnvironment -Name "UV_PROJECT_ENVIRONMENT" -RelativePath ".venv"
Set-ProjectPathEnvironment -Name "UV_CACHE_DIR" -RelativePath ".cache\uv"
Set-ProjectPathEnvironment -Name "PIP_CACHE_DIR" -RelativePath ".cache\pip"
Set-ProjectPathEnvironment -Name "HF_HOME" -RelativePath ".cache\huggingface"
Set-ProjectPathEnvironment -Name "HF_HUB_CACHE" -RelativePath ".cache\huggingface\hub"
Set-ProjectPathEnvironment -Name "HF_DATASETS_CACHE" -RelativePath ".cache\huggingface\datasets"
Set-ProjectPathEnvironment -Name "TORCH_HOME" -RelativePath ".cache\torch"
Set-ProjectPathEnvironment -Name "XDG_CACHE_HOME" -RelativePath ".cache"
Set-ProjectPathEnvironment -Name "WANDB_DIR" -RelativePath "runs\wandb"
Set-ProjectPathEnvironment -Name "WANDB_CACHE_DIR" -RelativePath ".cache\wandb"
Set-ProjectPathEnvironment -Name "WANDB_CONFIG_DIR" -RelativePath ".cache\wandb-config"
Set-ProjectPathEnvironment -Name "TEMP" -RelativePath ".tmp"
Set-ProjectPathEnvironment -Name "TMP" -RelativePath ".tmp"

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:PYTHONNOUSERSITE = "1"
$env:WANDB_MODE = "offline"
$env:HF_HUB_DISABLE_TELEMETRY = "1"
$env:TOKENIZERS_PARALLELISM = "false"

