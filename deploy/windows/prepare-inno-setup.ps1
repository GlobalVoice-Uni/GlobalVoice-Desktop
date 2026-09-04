param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$version = "7.1.0"
$fileName = "innosetup-$version-x64.exe"
$downloadUrl = "https://github.com/jrsoftware/issrc/releases/download/is-7_1_0/$fileName"
$expectedSha256 = "0362A383ED217D4C4239B5933866DD96D3EB2102737DA92F80F6057A4B40DF2F"
$downloadDir = Join-Path $projectDir ".build\downloads"
$installerPath = Join-Path $downloadDir $fileName
$resolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    Join-Path $projectDir ".build\inno-setup-$version"
}
elseif ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
}
else {
    Join-Path $projectDir $OutputPath
}
$compilerPath = Join-Path $resolvedOutputPath "ISCC.exe"

if (Test-Path -LiteralPath $compilerPath -PathType Leaf) {
    Write-Output "INNO_SETUP_OK=$compilerPath"
    exit 0
}

New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    Write-Output "Baixando Inno Setup $version x64..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath
}

$actualSha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash
if ($actualSha256 -ne $expectedSha256) {
    Write-Error "SHA-256 invalido para $installerPath. Remova o arquivo e tente novamente."
    exit 1
}

$signature = Get-AuthenticodeSignature -FilePath $installerPath
if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notmatch "CN=Pyrsys B\.V\.") {
    Write-Error "Assinatura Authenticode invalida ou editor inesperado em $installerPath."
    exit 1
}

$arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + $resolvedOutputPath + '"'
$process = Start-Process `
    -FilePath $installerPath `
    -ArgumentList $arguments `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
if ($process.ExitCode -ne 0) {
    Write-Error "A instalacao local do Inno Setup terminou com codigo $($process.ExitCode)."
    exit $process.ExitCode
}

if (-not (Test-Path -LiteralPath $compilerPath -PathType Leaf)) {
    Write-Error "Inno Setup instalado sem encontrar o compilador em $compilerPath."
    exit 1
}

Write-Output "INNO_SETUP_OK=$compilerPath"
Write-Output "INNO_SETUP_SHA256=$actualSha256"
