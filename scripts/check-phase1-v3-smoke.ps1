Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$DataDir = Join-Path $ProjectRoot "data\generated\phase1_v3_smoke"
$ArtifactDir = Join-Path $ProjectRoot "artifacts\phase1_v3_smoke"
$ManifestPath = Join-Path $ArtifactDir "provenance_manifest.json"
$ReportPath = Join-Path $ArtifactDir "phase1_exit_report.json"
$IndependentPath = Join-Path $ArtifactDir "independent_internal_audit.json"
$ReadableSamplePath = Join-Path $ArtifactDir "deterministic_review_sample.json"

if (-not (Test-Path -LiteralPath $ManifestPath) -or -not (Test-Path -LiteralPath $ReportPath)) {
    throw "V3 smoke manifest or report is missing"
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$Report = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
foreach ($Section in @("files", "inputs")) {
    foreach ($Property in $Manifest.$Section.PSObject.Properties) {
        $Path = Join-Path $ProjectRoot $Property.Name
        if (-not (Test-Path -LiteralPath $Path)) {
            throw "Missing $Section path: $($Property.Name)"
        }
        $Actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne [string]$Property.Value) {
            throw "Hash mismatch: $($Property.Name)"
        }
    }
}

if ($Report.status -ne "PASS" -or $Report.run_kind -ne "v3_internal_smoke") {
    throw "V3 smoke exit report is not a PASS"
}
if ([int]$Report.generator_revision -ne 1) {
    throw "Expected V3 generator revision 1"
}
if ([int]$Report.total_discovery_families -ne 600) {
    throw "V3 smoke corpus does not contain 600 families"
}
if ([int]$Report.temporary_fixture_family_count -ne 0) {
    throw "V3 smoke corpus contains temporary fixtures"
}
if ($Report.confirmation.status -ne "RESERVED_NOT_GENERATED") {
    throw "V3 confirmation population was unexpectedly generated"
}
if ($Report.internal_review.authorizes_retained_generation -ne $false) {
    throw "Internal review incorrectly authorizes retained generation"
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python (Join-Path $PSScriptRoot "independent-smoke-audit.py") `
    --data-dir "data/generated/phase1_v3_smoke" `
    --artifact-dir "artifacts/phase1_v3_smoke" `
    --expected-run-kind "v3_internal_smoke" `
    --expected-families-per-environment 300 `
    --output "artifacts/phase1_v3_smoke/independent_internal_audit.json"
if ($LASTEXITCODE -ne 0) {
    throw "Independent V3 smoke audit failed"
}

$Independent = Get-Content -LiteralPath $IndependentPath -Raw | ConvertFrom-Json
if ($Independent.status -ne "PASS") {
    throw "Independent V3 smoke report is not PASS"
}
if ($Independent.governance.authorizes_retained_generation -ne $false) {
    throw "Independent internal audit incorrectly authorizes retention"
}

& $Python (Join-Path $PSScriptRoot "select-internal-review-sample.py") `
    --data-dir "data/generated/phase1_v3_smoke" `
    --output "artifacts/phase1_v3_smoke/deterministic_review_sample.json"
if ($LASTEXITCODE -ne 0) {
    throw "Deterministic readable-review sample selection failed"
}
$ReadableSample = Get-Content -LiteralPath $ReadableSamplePath -Raw | ConvertFrom-Json
if ([int]$ReadableSample.grammar_warning_row_count -ne 0) {
    throw "Readable-review sample contains a known grammar warning"
}
if ([int]$ReadableSample.actor_twin_physical_unchanged_count -ne 0) {
    throw "Readable-review sample contains an unchanged actor intervention"
}

if (Test-Path -LiteralPath (Join-Path $ArtifactDir "EXTERNAL_AUDIT_ACCEPTED.json")) {
    throw "V3 smoke contains an external acceptance record during internal review"
}
if (Test-Path -LiteralPath (Join-Path $ProjectRoot "data\generated\phase1_discovery_v3")) {
    throw "V3 retained corpus exists before external acceptance"
}

Write-Output "V3 native and independent audits passed; deterministic readable sample is fixed; retention remains blocked."
