param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BenchmarkArguments
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent (Split-Path -Parent $scriptDir)
$pythonPath = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonPath)) {
    Write-Error "Python da venv nao encontrado em $pythonPath"
    exit 1
}

$exitCode = 0
Push-Location $projectDir
try {
    & $pythonPath -m experiments.asr_baseline.run_baseline @BenchmarkArguments
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $exitCode

