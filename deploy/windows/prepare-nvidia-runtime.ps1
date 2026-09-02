param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$profilePath = Join-Path $scriptDir "runtime-profiles\nvidia-cuda12.json"
$profile = Get-Content -LiteralPath $profilePath -Raw | ConvertFrom-Json
$downloadDir = Join-Path $projectDir ".build\downloads"
$wheelPath = Join-Path $downloadDir $profile.source.filename
$resolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    Join-Path $projectDir "dist\runtime-profiles\$($profile.profileId)"
}
elseif ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
}
else {
    Join-Path $projectDir $OutputPath
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
if (-not (Test-Path -LiteralPath $wheelPath -PathType Leaf)) {
    Write-Output "Baixando $($profile.source.package) $($profile.source.version)..."
    Invoke-WebRequest -Uri $profile.source.url -OutFile $wheelPath
}

$wheelHash = Get-Sha256 $wheelPath
if ($wheelHash -ne $profile.source.sha256) {
    Write-Error "SHA-256 invalido para $wheelPath. Remova o arquivo e tente novamente."
    exit 1
}

New-Item -ItemType Directory -Force -Path $resolvedOutputPath | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($wheelPath)
try {
    foreach ($expectedFile in $profile.files) {
        $entry = $archive.GetEntry($expectedFile.archivePath)
        if ($null -eq $entry) {
            Write-Error "Arquivo nao encontrado no pacote oficial: $($expectedFile.archivePath)"
            exit 1
        }

        $destination = Join-Path $resolvedOutputPath $expectedFile.name
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile(
            $entry,
            $destination,
            $true
        )

        $item = Get-Item -LiteralPath $destination
        $hash = Get-Sha256 $destination
        if ($item.Length -ne $expectedFile.size -or $hash -ne $expectedFile.sha256) {
            Write-Error "Perfil NVIDIA invalido apos extrair $($expectedFile.name)."
            exit 1
        }
    }
}
finally {
    $archive.Dispose()
}

Copy-Item -LiteralPath $profilePath -Destination (
    Join-Path $resolvedOutputPath "profile.json"
) -Force

$runtimeBytes = (
    Get-ChildItem -LiteralPath $resolvedOutputPath -File |
        Measure-Object -Property Length -Sum
).Sum

Write-Output "NVIDIA_RUNTIME_OK=$resolvedOutputPath"
Write-Output "NVIDIA_RUNTIME_SIZE_MB=$([Math]::Round($runtimeBytes / 1MB, 2))"
Write-Output "SOURCE_SHA256=$wheelHash"
