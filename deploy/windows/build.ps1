param(
    [switch]$InstallRuntimeDependencies,
    [switch]$DiagnosticConsole
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$pythonPath = Join-Path $projectDir ".venv\Scripts\python.exe"
$specPath = Join-Path $scriptDir "globalvoice.spec"
$workPath = Join-Path $projectDir ".build\pyinstaller"
$buildVenvPath = Join-Path $projectDir ".build\venv"
$buildPythonPath = Join-Path $buildVenvPath "Scripts\python.exe"
$runtimePackagesPath = Join-Path $projectDir ".venv\Lib\site-packages"
$distPath = Join-Path $projectDir "dist"
$executablePath = Join-Path $distPath "GlobalVoice\GlobalVoice.exe"
$previousPythonPath = $env:PYTHONPATH
$previousDiagnosticConsole = $env:GLOBALVOICE_DIAGNOSTIC_CONSOLE
$previousPath = $env:PATH

if (-not (Test-Path $pythonPath)) {
    Write-Error "Python da venv nao encontrado em $pythonPath"
    exit 1
}

Push-Location $projectDir
try {
    if ($InstallRuntimeDependencies) {
        & $pythonPath -m pip install -r "backend\requirements.txt"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        & $pythonPath -m pip install -r "frontend\requirements.txt"
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

    $bundleBytes = (
        Get-ChildItem (Split-Path -Parent $executablePath) -File -Recurse |
            Measure-Object -Property Length -Sum
    ).Sum
    $bundleSizeMb = [Math]::Round($bundleBytes / 1MB, 2)

    Write-Output "BUILD_OK=$executablePath"
    Write-Output "BUNDLE_SIZE_MB=$bundleSizeMb"
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    $env:GLOBALVOICE_DIAGNOSTIC_CONSOLE = $previousDiagnosticConsole
    $env:PATH = $previousPath
    Pop-Location
}
