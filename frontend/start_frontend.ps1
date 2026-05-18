param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$entryPoint = Join-Path $scriptDir "src\main.py"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Python da venv nao encontrado em $pythonPath"
    exit 1
}

if (-not (Test-Path $entryPoint)) {
    Write-Error "Entry point do frontend nao encontrado em $entryPoint"
    exit 1
}

Push-Location $repoRoot
try {
    & $pythonPath $entryPoint
}
finally {
    Pop-Location
}
