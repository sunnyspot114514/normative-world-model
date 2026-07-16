param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "project-env.ps1")

$ResolvedDestination = [System.IO.Path]::GetFullPath($Destination)
if ($ResolvedDestination.StartsWith($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Backup destination must be outside the project root"
}
if (Test-Path -LiteralPath $ResolvedDestination) {
    throw "Backup destination already exists; refusing to overwrite it"
}

$EvidencePaths = @(
    "data\generated\phase1_v3_smoke",
    "artifacts\phase1_v3_smoke",
    "data\generated\phase1_discovery_v3",
    "artifacts\phase1_v3"
)

New-Item -ItemType Directory -Path $ResolvedDestination | Out-Null
$Manifest = [ordered]@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    project_root = $ProjectRoot
    note = "Redundant evidence copy. Move or synchronize this directory off-machine."
    verified_source_copy_match = $true
    files = [ordered]@{}
}

foreach ($Relative in $EvidencePaths) {
    $Source = Join-Path $ProjectRoot $Relative
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Missing evidence path: $Relative"
    }
    $Target = Join-Path $ResolvedDestination $Relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Recurse
    Get-ChildItem -LiteralPath $Source -Recurse -File |
        ForEach-Object {
            $RepositoryRelative = $_.FullName.Substring(
                $ProjectRoot.Length
            ).TrimStart("\", "/").Replace("\", "/")
            $CopiedFile = Join-Path $ResolvedDestination $RepositoryRelative
            if (-not (Test-Path -LiteralPath $CopiedFile)) {
                throw "Backup copy is missing: $RepositoryRelative"
            }
            $SourceHash = (
                Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            $CopiedHash = (
                Get-FileHash -LiteralPath $CopiedFile -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            if ($SourceHash -ne $CopiedHash) {
                throw "Backup hash mismatch: $RepositoryRelative"
            }
            $Manifest.files[$RepositoryRelative] = [ordered]@{
                bytes = $_.Length
                sha256 = $CopiedHash
                source_copy_match = $true
            }
        }
}

$SecretPath = Join-Path $ProjectRoot ".tmp\confirmation_v3_secret.json"
if (-not (Test-Path -LiteralPath $SecretPath)) {
    throw "Missing confirmation nonce"
}
$SecretJson = Get-Content -LiteralPath $SecretPath -Raw
$ProtectedSecret = ConvertFrom-SecureString (
    ConvertTo-SecureString $SecretJson -AsPlainText -Force
)
$ProtectedSecretPath = Join-Path $ResolvedDestination "confirmation_v3_secret.dpapi"
Set-Content -LiteralPath $ProtectedSecretPath -Value $ProtectedSecret -Encoding utf8
$Manifest.nonce_backup = [ordered]@{
    path = "confirmation_v3_secret.dpapi"
    protection = "Windows DPAPI; restore requires the same Windows user profile"
    plaintext_sha256 = (
        Get-FileHash -LiteralPath $SecretPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
}
$Manifest.files["confirmation_v3_secret.dpapi"] = [ordered]@{
    bytes = (Get-Item -LiteralPath $ProtectedSecretPath).Length
    sha256 = (
        Get-FileHash -LiteralPath $ProtectedSecretPath -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    source_copy_match = $null
}

$ManifestPath = Join-Path $ResolvedDestination "BACKUP_MANIFEST.json"
$Manifest | ConvertTo-Json -Depth 6 |
    Set-Content -LiteralPath $ManifestPath -Encoding utf8
Write-Output "Evidence backup created at $ResolvedDestination"
Write-Output "Copy this directory off-machine before confirmation is generated."
