param(
    [switch]$InstallRuntimeDependencies,
    [switch]$DiagnosticConsole,
    [string]$RuntimePythonPath,
    [Alias("CudaRuntimePath")]
    [string]$NvidiaRuntimePath
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$defaultPythonPath = Join-Path $projectDir ".venv\Scripts\python.exe"
$pythonPath = if ([string]::IsNullOrWhiteSpace($RuntimePythonPath)) {
    $defaultPythonPath
}
elseif ([System.IO.Path]::IsPathRooted($RuntimePythonPath)) {
    $RuntimePythonPath
}
else {
    Join-Path $projectDir $RuntimePythonPath
}
$specPath = Join-Path $scriptDir "globalvoice.spec"
$workPath = Join-Path $projectDir ".build\pyinstaller"
$buildVenvPath = Join-Path $projectDir ".build\venv"
$buildPythonPath = Join-Path $buildVenvPath "Scripts\python.exe"
$distPath = Join-Path $projectDir "dist"
$executablePath = Join-Path $distPath "GlobalVoice\GlobalVoice.exe"
$previousPythonPath = $env:PYTHONPATH
$previousDiagnosticConsole = $env:GLOBALVOICE_DIAGNOSTIC_CONSOLE
$previousRuntimePackages = $env:GLOBALVOICE_RUNTIME_SITE_PACKAGES
$previousPath = $env:PATH

if (-not (Test-Path $pythonPath)) {
    Write-Error "Python de runtime nao encontrado em $pythonPath"
    exit 1
}

$resolvedNvidiaRuntimePath = $null
if (-not [string]::IsNullOrWhiteSpace($NvidiaRuntimePath)) {
    $runtimePathCandidate = if ([System.IO.Path]::IsPathRooted($NvidiaRuntimePath)) {
        $NvidiaRuntimePath
    }
    else {
        Join-Path $projectDir $NvidiaRuntimePath
    }
    $resolvedNvidiaRuntimePath = (Resolve-Path $runtimePathCandidate).Path
    foreach ($fileName in @(
        "cublasLt64_12.dll",
        "cublas64_12.dll",
        "NVIDIA-CUDA-LICENSE.txt",
        "profile.json"
    )) {
        $filePath = Join-Path $resolvedNvidiaRuntimePath $fileName
        if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
            Write-Error "Arquivo do perfil NVIDIA nao encontrado: $filePath"
            exit 1
        }
    }
}

Push-Location $projectDir
try {
    if ($InstallRuntimeDependencies) {
        & $pythonPath -m pip install -r "requirements\runtime-windows.lock"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    if (-not (Test-Path $buildPythonPath)) {
        & $pythonPath -m venv $buildVenvPath
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    & $buildPythonPath -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $buildPythonPath -m pip install `
            --disable-pip-version-check `
            --no-deps `
            -r "deploy\windows\requirements-build.txt"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $basePythonPath = (& $pythonPath -c "import sys; print(sys.base_prefix)").Trim()
    $runtimePackagesPath = (
        & $pythonPath -c "import site; print(site.getsitepackages()[-1])"
    ).Trim()
    $controlledPath = @(
        (Join-Path $buildVenvPath "Scripts"),
        (Join-Path $projectDir ".venv\Scripts"),
        $basePythonPath,
        (Join-Path $basePythonPath "DLLs"),
        (Join-Path $env:WINDIR "System32"),
        $env:WINDIR
    ) -join ";"

    $env:PYTHONPATH = "$projectDir;$runtimePackagesPath"
    $env:GLOBALVOICE_DIAGNOSTIC_CONSOLE = if ($DiagnosticConsole) { "1" } else { "0" }
    $env:GLOBALVOICE_RUNTIME_SITE_PACKAGES = $runtimePackagesPath
    $env:PATH = $controlledPath
    & $buildPythonPath -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $distPath `
        --workpath $workPath `
        $specPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    if (-not (Test-Path $executablePath)) {
        Write-Error "Build concluida sem encontrar $executablePath"
        exit 1
    }

    $baseBytes = (
        Get-ChildItem (Split-Path -Parent $executablePath) -File -Recurse |
            Measure-Object -Property Length -Sum
    ).Sum

    $nvidiaRuntimeBytes = 0
    if ($resolvedNvidiaRuntimePath) {
        $runtimeTarget = Join-Path (
            Split-Path -Parent $executablePath
        ) "_internal\runtime\nvidia\cuda12"
        New-Item -ItemType Directory -Force -Path $runtimeTarget | Out-Null
        foreach ($fileName in @(
            "cublasLt64_12.dll",
            "cublas64_12.dll",
            "NVIDIA-CUDA-LICENSE.txt",
            "profile.json"
        )) {
            Copy-Item -LiteralPath (
                Join-Path $resolvedNvidiaRuntimePath $fileName
            ) -Destination $runtimeTarget -Force
        }
        $nvidiaRuntimeBytes = (
            Get-ChildItem -LiteralPath $runtimeTarget -File |
                Measure-Object -Property Length -Sum
        ).Sum
    }

    $bundleBytes = (
        Get-ChildItem (Split-Path -Parent $executablePath) -File -Recurse |
            Measure-Object -Property Length -Sum
    ).Sum
    $bundleSizeMb = [Math]::Round($bundleBytes / 1MB, 2)

    Write-Output "BUILD_OK=$executablePath"
    Write-Output "BASE_SIZE_MB=$([Math]::Round($baseBytes / 1MB, 2))"
    Write-Output "NVIDIA_RUNTIME_SIZE_MB=$([Math]::Round($nvidiaRuntimeBytes / 1MB, 2))"
    Write-Output "BUNDLE_SIZE_MB=$bundleSizeMb"
    Write-Output "RUNTIME_PROFILE=$(if ($resolvedNvidiaRuntimePath) { 'nvidia-cuda12' } else { 'base' })"
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:GLOBALVOICE_DIAGNOSTIC_CONSOLE = $previousDiagnosticConsole
    $env:GLOBALVOICE_RUNTIME_SITE_PACKAGES = $previousRuntimePackages
    $env:PATH = $previousPath
    Pop-Location
}
