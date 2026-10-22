param(
    [string]$AppVersion = "0.4.1",
    [string]$InnoCompilerPath,
    [string]$OutputSuffix,
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

if ($AppVersion -notmatch '^\d+\.\d+(\.\d+){0,2}$') {
    Write-Error "Versao invalida: $AppVersion. Use o formato 1.2, 1.2.3 ou 1.2.3.4."
    exit 1
}
if ($OutputSuffix -and $OutputSuffix -notmatch '^[a-z0-9][a-z0-9-]{0,20}$') {
    Write-Error "Sufixo de instalador invalido: $OutputSuffix."
    exit 1
}

$outputStem = "GlobalVoice-Setup-$AppVersion"
if ($OutputSuffix) {
    $outputStem += "-$OutputSuffix"
}
elseif ($Fast) {
    $outputStem += "-dev"
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

& (Join-Path $scriptDir "prepare-vb-cable.ps1")

Push-Location $projectDir
try {
    $versionParts = @($AppVersion.Split('.')) + @('0', '0', '0', '0')
    $fileVersion = $versionParts[0..3] -join '.'
    $compilerArguments = @(
        "--define=AppVersion=$AppVersion",
        "--define=AppFileVersion=$fileVersion"
    )
    if ($Fast) {
        $compilerArguments += "--no-compression"
    }
    if ($OutputSuffix -or $Fast) {
        $compilerArguments += "--output-filename=$outputStem"
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

$installerFileName = "$outputStem.exe"
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
