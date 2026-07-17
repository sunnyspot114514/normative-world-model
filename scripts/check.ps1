Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Missing .venv. Run .\scripts\setup.ps1 first."
}

function Invoke-CheckedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Description,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    # Windows PowerShell 5.1 turns ordinary native stderr into a terminating
    # NativeCommandError when ErrorActionPreference is Stop. unittest writes
    # its normal progress and summary to stderr, so capture both streams while
    # relying on the process exit code for pass/fail.
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

$V3Manifest = Join-Path $ProjectRoot "artifacts\phase1_v3_smoke\provenance_manifest.json"
if (Test-Path -LiteralPath $V3Manifest) {
    $V3Acceptance = Join-Path $ProjectRoot "artifacts\phase1_v3_smoke\EXTERNAL_AUDIT_ACCEPTED.json"
    if (Test-Path -LiteralPath $V3Acceptance) {
        & $VenvPython (Join-Path $PSScriptRoot "check-phase1-v3-post-acceptance.py")
    }
    else {
        & (Join-Path $PSScriptRoot "check-phase1-v3-smoke.ps1")
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Phase-1 V3 lifecycle audit failed with exit code $LASTEXITCODE"
    }
}

$Phase3Result = Join-Path $ProjectRoot "artifacts\phase3_retained_schema_gate\schema_gate_result.json"
if (Test-Path -LiteralPath $Phase3Result) {
    Invoke-CheckedPython -Description "Phase-3 schema-gate result audit" -Arguments @(
        (Join-Path $PSScriptRoot "verify-phase3-retained-schema-gate-result.py")
    )
}

$AntiCollapseResult = Join-Path $ProjectRoot "artifacts\phase3_anti_collapse_smoke\result.json"
if (Test-Path -LiteralPath $AntiCollapseResult) {
    Invoke-CheckedPython -Description "Phase-3 anti-collapse smoke result audit" -Arguments @(
        (Join-Path $PSScriptRoot "verify-phase3-anti-collapse-smoke-result.py")
    )
}

$AntiCollapseV2Result = Join-Path $ProjectRoot "artifacts\phase3_anti_collapse_smoke_v2\result.json"
if (Test-Path -LiteralPath $AntiCollapseV2Result) {
    Invoke-CheckedPython -Description "Phase-3 anti-collapse smoke v2 result audit" -Arguments @(
        (Join-Path $PSScriptRoot "verify-phase3-anti-collapse-smoke-v2-result.py")
    )
}
