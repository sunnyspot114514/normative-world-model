Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$ArtifactDir = Join-Path $ProjectRoot "artifacts\phase1_revision2_smoke"
$ManifestPath = Join-Path $ArtifactDir "provenance_manifest.json"
$ReportPath = Join-Path $ArtifactDir "phase1_exit_report.json"
if (-not (Test-Path -LiteralPath $ManifestPath) -or -not (Test-Path -LiteralPath $ReportPath)) {
    throw "Revision-2 smoke manifest or report is missing"
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
if ($Report.status -ne "PASS" -or $Report.run_kind -ne "revision2_smoke") {
    throw "Smoke exit report is not a revision2_smoke PASS"
}
if ([int]$Report.total_discovery_families -ne 600) {
    throw "Smoke corpus does not contain 600 families"
}
if ([int]$Report.temporary_fixture_family_count -ne 0) {
    throw "Smoke corpus contains temporary fixtures"
}
if ($Report.confirmation.status -ne "RESERVED_NOT_GENERATED") {
    throw "Confirmation population was unexpectedly generated"
}
Write-Output "Revision-2 smoke artifacts and provenance hashes passed."

