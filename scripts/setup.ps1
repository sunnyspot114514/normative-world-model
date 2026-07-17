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

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $PreviousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $Output = & $VenvPython @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }
    $Output | ForEach-Object {
        $Text = if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $_.Exception.Message
        }
        else {
            $_.ToString()
        }
        if ($Text) { Write-Host $Text }
    }
    if ($ExitCode -ne 0) {
        throw "$Description failed with exit code $ExitCode"
    }
}

Invoke-CheckedPython -Description "compileall" -Arguments @(
    "-m", "compileall", "-q", (Join-Path $ProjectRoot "src")
)
Invoke-CheckedPython -Description "unit tests" -Arguments @(
    "-m", "unittest", "discover", "-s", (Join-Path $ProjectRoot "tests"), "-v"
)
Invoke-CheckedPython -Description "isolation audit" -Arguments @(
    "-m", "normative_world_model", "check-isolation"
)

Write-Host "Project environment is ready at $ProjectRoot\.venv"
Write-Host "Enter it with: . .\scripts\enter.ps1"
