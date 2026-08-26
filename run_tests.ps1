param()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $scriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Python da venv nao encontrado em $pythonPath"
    exit 1
}

$exitCode = 0
Push-Location $scriptDir
try {
    & $pythonPath -m unittest discover -s tests -t . -v
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode
