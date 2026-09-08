param(
    [string]$AppVersion = "0.1.0",
    [string]$InnoCompilerPath,
    [switch]$Fast
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$installerScript = Join-Path $scriptDir "installer\GlobalVoice.iss"
$defaultCompiler = Join-Path $projectDir ".build\inno-setup-7.1.0\ISCC.exe"
$compiler = if ([string]::IsNullOrWhiteSpace($InnoCompilerPath)) {
    $defaultCompiler
}
elseif ([System.IO.Path]::IsPathRooted($InnoCompilerPath)) {
    $InnoCompilerPath
}
else {
    Join-Path $projectDir $InnoCompilerPath
}

if ($AppVersion -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') {
    Write-Error "Versao invalida: $AppVersion. Use o formato 1.2.3 ou 1.2.3.4."
    exit 1
}

$requiredFiles = @(
    (Join-Path $projectDir "dist\GlobalVoice\GlobalVoice.exe"),
    (Join-Path $projectDir "dist\runtime-profiles\nvidia-cuda12\cublas64_12.dll"),
    (Join-Path $projectDir "dist\runtime-profiles\nvidia-cuda12\cublasLt64_12.dll"),
    (Join-Path $projectDir "dist\runtime-profiles\nvidia-cuda12\NVIDIA-CUDA-LICENSE.txt"),
    (Join-Path $projectDir "dist\runtime-profiles\nvidia-cuda12\profile.json")
)
foreach ($requiredFile in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        Write-Error "Arquivo necessario para o instalador nao encontrado: $requiredFile"
        exit 1
    }
}

if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    Write-Error "Compilador do Inno Setup nao encontrado em $compiler"
    exit 1
}

Push-Location $projectDir
try {
    $compilerArguments = @(
        "--define=AppVersion=$AppVersion"
    )
    if ($Fast) {
        $compilerArguments += "--no-compression"
        $compilerArguments += "--output-filename=GlobalVoice-Setup-$AppVersion-dev"
    }
    $compilerArguments += $installerScript

    & $compiler $compilerArguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

$installerFileName = if ($Fast) {
    "GlobalVoice-Setup-$AppVersion-dev.exe"
}
else {
    "GlobalVoice-Setup-$AppVersion.exe"
}
$installerPath = Join-Path $projectDir "dist\installer\$installerFileName"
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    Write-Error "Compilacao concluida sem encontrar $installerPath"
    exit 1
}

$installer = Get-Item -LiteralPath $installerPath
$hash = Get-FileHash -LiteralPath $installerPath -Algorithm SHA256
$checksumPath = "$installerPath.sha256"
$checksumLine = "$($hash.Hash.ToLowerInvariant())  $($installer.Name)"
[System.IO.File]::WriteAllText($checksumPath, "$checksumLine`n")
Write-Output "INSTALLER_OK=$installerPath"
Write-Output "INSTALLER_SIZE_MB=$([Math]::Round($installer.Length / 1MB, 2))"
Write-Output "INSTALLER_SHA256=$($hash.Hash)"
Write-Output "CHECKSUM_OK=$checksumPath"
