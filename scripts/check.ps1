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

$Phase5SyntheticClientPlanV10 = Join-Path $ProjectRoot ".cache\phase5_synthetic_client_plan\v10-b2887ba90d81-b752a05215d7.json"
if (Test-Path -LiteralPath $Phase5SyntheticClientPlanV10) {
    Invoke-CheckedPython -Description "Phase-5 synthetic client plan V10 audit" -Arguments @(
        "-c",
        "from normative_world_model.phase5_synthetic_client_plan import verify_phase5_synthetic_client_plan as v; print(v())"
    )
}

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

$DiversityGatewayV3Result = Join-Path $ProjectRoot "artifacts\phase3_diversity_gateway_v3\result.json"
if (Test-Path -LiteralPath $DiversityGatewayV3Result) {
    Invoke-CheckedPython -Description "Phase-3 diversity-gateway V3 result audit" -Arguments @(
        "-c",
        "from pathlib import Path; from normative_world_model.gateway_v3_result_lock import verify_phase3_diversity_gateway_v3_result as v; f=v(Path.cwd()); print({'status':'PASS' if not f else 'FAIL','failures':f}); raise SystemExit(bool(f))"
    )
}

$RepresentationGatewayV4Result = Join-Path $ProjectRoot "artifacts\phase3_representation_gateway_v4\result.json"
if (Test-Path -LiteralPath $RepresentationGatewayV4Result) {
    Invoke-CheckedPython -Description "Phase-3 representation-gateway V4 result audit" -Arguments @(
        (Join-Path $PSScriptRoot "verify-phase3-representation-gateway-v4-result.py")
    )
}
