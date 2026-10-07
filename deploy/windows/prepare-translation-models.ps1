param(
    [string]$RuntimePythonPath
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Resolve-Path (Join-Path $scriptDir "..\..")
$pythonPath = if ([string]::IsNullOrWhiteSpace($RuntimePythonPath)) {
    Join-Path $projectDir ".venv\Scripts\python.exe"
}
elseif ([System.IO.Path]::IsPathRooted($RuntimePythonPath)) {
    $RuntimePythonPath
}
else {
    Join-Path $projectDir $RuntimePythonPath
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Error "Python de runtime não encontrado em $pythonPath"
    exit 1
}

Push-Location $projectDir
try {
    & $pythonPath "deploy\windows\prepare-translation-models.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
