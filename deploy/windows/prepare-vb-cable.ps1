$ErrorActionPreference = "Stop"
$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$archive = Join-Path $projectDir ".build\VBCABLE_Driver_Pack45.zip"
$download = "$archive.download"
$destination = Join-Path $projectDir ".build\VBCABLE_Driver_Pack45"
$expectedHash = "B950E39F01AF1D04EA623C8F6D8EB9B6EA5C477C637295FABF20631C85116BFB"
$officialUrl = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip"

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $archive) | Out-Null
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    Invoke-WebRequest -Uri $officialUrl -OutFile $download
    $downloadHash = (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash
    if ($downloadHash -ne $expectedHash) {
        Remove-Item -LiteralPath $download -Force
        throw "O pacote oficial do VB-CABLE mudou: SHA-256 inesperado."
    }
    Move-Item -LiteralPath $download -Destination $archive
}

$archiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($archiveHash -ne $expectedHash) {
    throw "SHA-256 inválido para $archive"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
try {
    $expectedFiles = @($zip.Entries | Where-Object { -not [string]::IsNullOrEmpty($_.Name) } |
        ForEach-Object { $_.FullName })
    foreach ($name in $expectedFiles) {
        if ([System.IO.Path]::GetFileName($name) -ne $name) {
            throw "Caminho inesperado no pacote do VB-CABLE: $name"
        }
    }
}
finally {
    $zip.Dispose()
}

Expand-Archive -LiteralPath $archive -DestinationPath $destination -Force
$actualFiles = @(Get-ChildItem -LiteralPath $destination -File -Recurse |
    ForEach-Object { $_.FullName.Substring($destination.Length + 1) })
$unexpected = @($actualFiles | Where-Object { $_ -notin $expectedFiles })
if ($unexpected.Count -gt 0) {
    throw "Arquivos inesperados na pasta verificada do VB-CABLE: $($unexpected -join ', ')"
}
$setup = Join-Path $destination "VBCABLE_Setup_x64.exe"
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
    throw "Instalador x64 do VB-CABLE ausente."
}
$signature = Get-AuthenticodeSignature -LiteralPath $setup
if ($signature.Status -ne "Valid") {
    throw "Assinatura do instalador VB-CABLE inválida: $($signature.Status)"
}
Write-Output "VB_CABLE_OK=$setup"
Write-Output "VB_CABLE_SHA256=$archiveHash"
