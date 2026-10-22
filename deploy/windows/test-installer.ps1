param(
    [string]$InstallerPath = "dist\installer\GlobalVoice-Setup-0.4.1.exe",
    [string]$InstallPath,
    [ValidateSet("base", "nvidia")]
    [string]$RuntimeProfile = "base",
    [switch]$IncludeVBCable
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$resolvedInstallerPath = if ([System.IO.Path]::IsPathRooted($InstallerPath)) {
    [System.IO.Path]::GetFullPath($InstallerPath)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $projectDir $InstallerPath))
}
$requestedInstallPath = if ([string]::IsNullOrWhiteSpace($InstallPath)) {
    ".build\installer-smoke\$RuntimeProfile"
}
else {
    $InstallPath
}
$resolvedInstallPath = if ([System.IO.Path]::IsPathRooted($requestedInstallPath)) {
    [System.IO.Path]::GetFullPath($requestedInstallPath)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path $projectDir $requestedInstallPath))
}
$smokeRoot = [System.IO.Path]::GetFullPath((Join-Path $projectDir ".build\installer-smoke"))
$smokePrefix = $smokeRoot.TrimEnd('\') + '\'
if (-not $resolvedInstallPath.StartsWith(
    $smokePrefix, [System.StringComparison]::OrdinalIgnoreCase
)) {
    Write-Error "O destino do teste deve permanecer dentro de $smokeRoot."
    exit 1
}
if (-not (Test-Path -LiteralPath $resolvedInstallerPath -PathType Leaf)) {
    Write-Error "Instalador nao encontrado em $resolvedInstallerPath."
    exit 1
}
if (Test-Path -LiteralPath $resolvedInstallPath) {
    Write-Error "O destino do teste ja existe: $resolvedInstallPath. Desinstale a execucao anterior."
    exit 1
}
if ($IncludeVBCable) {
    $cableEnum = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\VBAudioVACMME\Enum' -Name Count -ErrorAction SilentlyContinue
    if ($null -eq $cableEnum -or [int]$cableEnum.Count -le 0) {
        Write-Error 'Este teste exige VB-CABLE já instalado; não instalará o driver no PC de desenvolvimento.'
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path $smokeRoot | Out-Null
$installLog = Join-Path $smokeRoot "install-$RuntimeProfile.log"
$uninstallLog = Join-Path $smokeRoot "uninstall-$RuntimeProfile.log"
$components = if ($RuntimeProfile -eq 'nvidia') { 'base,nvidia' } else { 'base' }
if ($IncludeVBCable) { $components += ',cable' }
$setupArguments = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/SP-",
    "/CURRENTUSER",
    "/DIR=`"$resolvedInstallPath`"",
    "/TYPE=custom",
    "/COMPONENTS=$components",
    "/TASKS=",
    "/PAIRS=none",
    "/LOG=`"$installLog`""
)
$application = $null
$heldManifestPath = $null

try {
    $setup = Start-Process `
        -FilePath $resolvedInstallerPath `
        -ArgumentList $setupArguments `
        -Wait `
        -PassThru `
        -WindowStyle Hidden
    if ($setup.ExitCode -ne 0) {
        throw "A instalacao terminou com codigo $($setup.ExitCode)."
    }

    $applicationPath = Join-Path $resolvedInstallPath "GlobalVoice.exe"
    $uninstallerPath = Join-Path $resolvedInstallPath "unins000.exe"
    if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
        throw "Executavel instalado nao encontrado em $applicationPath."
    }
    if (-not (Test-Path -LiteralPath $uninstallerPath -PathType Leaf)) {
        throw "Desinstalador nao encontrado em $uninstallerPath."
    }
    $installationIniPath = Join-Path $resolvedInstallPath 'installation.ini'
    $installationIni = Get-Content -LiteralPath $installationIniPath -Raw
    if ($installationIni -notmatch '(?m)^Base=pt-br\r?$' -or
        $installationIni -notmatch '(?m)^InstallId=\d{14}\r?$') {
        throw 'O manifesto nao registra o idioma principal ou a nova instalacao.'
    }

    $installerVersion = [regex]::Match(
        [System.IO.Path]::GetFileName($resolvedInstallerPath),
        '^GlobalVoice-Setup-(\d+\.\d+(?:\.\d+){0,2})(?:-[a-z0-9-]+)?\.exe$'
    )
    if (-not $installerVersion.Success) {
        throw "Nome de instalador sem versao reconhecida: $resolvedInstallerPath"
    }
    $installedIconPath = Join-Path $resolvedInstallPath "GlobalVoice-$($installerVersion.Groups[1].Value).ico"
    $sourceIconPath = Join-Path $projectDir "frontend\assets\newicon.ico"
    if (-not (Test-Path -LiteralPath $installedIconPath -PathType Leaf)) {
        throw "Icone da aplicacao nao encontrado em $installedIconPath."
    }
    if ((Get-FileHash -LiteralPath $installedIconPath -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $sourceIconPath -Algorithm SHA256).Hash) {
        throw "O icone instalado nao corresponde ao novo icone da aplicacao."
    }

    $cudaRuntimePath = Join-Path $resolvedInstallPath "_internal\runtime\nvidia\cuda12"
    $cudaFiles = @(
        Get-ChildItem -LiteralPath $cudaRuntimePath -File -ErrorAction SilentlyContinue
    )
    if ($RuntimeProfile -eq "base" -and $cudaFiles.Count -gt 0) {
        throw "O teste somente CPU instalou arquivos opcionais de cuBLAS."
    }
    if ($RuntimeProfile -eq "nvidia") {
        foreach ($fileName in ("cublas64_12.dll", "cublasLt64_12.dll")) {
            if (-not (Test-Path -LiteralPath (Join-Path $cudaRuntimePath $fileName))) {
                throw "O perfil NVIDIA nao instalou $fileName."
            }
        }
    }

    # Evita que o teste da copia temporaria substitua os idiomas do perfil real.
    $heldManifestPath = "$installationIniPath.smoke-hold"
    Move-Item -LiteralPath $installationIniPath -Destination $heldManifestPath
    $application = Start-Process `
        -FilePath $applicationPath `
        -PassThru `
        -WindowStyle Hidden
    if (-not $application.WaitForExit(8000)) {
        $application.Refresh()
    }
    if ($application.HasExited) {
        throw "O aplicativo instalado encerrou durante a verificacao de inicializacao."
    }

    Write-Output "INSTALL_SMOKE_OK=$applicationPath"
    Write-Output "RUNTIME_PROFILE_OK=$RuntimeProfile"
    if ($IncludeVBCable) {
        if ($installationIni -match 'RestartRequestedAt') {
            throw 'O instalador solicitou reinício mesmo com VB-CABLE preexistente.'
        }
        Write-Output 'PREEXISTING_VB_CABLE_OK=true'
    }
}
finally {
    if ($null -ne $application -and -not $application.HasExited) {
        Stop-Process -Id $application.Id -Force
        $application.WaitForExit()
    }
    if ($heldManifestPath -and (Test-Path -LiteralPath $heldManifestPath -PathType Leaf)) {
        Move-Item -LiteralPath $heldManifestPath -Destination $installationIniPath
    }

    $uninstallerPath = Join-Path $resolvedInstallPath "unins000.exe"
    if (Test-Path -LiteralPath $uninstallerPath -PathType Leaf) {
        $uninstallArguments = @(
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/LOG=`"$uninstallLog`""
        )
        $uninstall = Start-Process `
            -FilePath $uninstallerPath `
            -ArgumentList $uninstallArguments `
            -Wait `
            -PassThru `
            -WindowStyle Hidden
        if ($uninstall.ExitCode -ne 0) {
            Write-Error "A desinstalacao terminou com codigo $($uninstall.ExitCode)."
        }
    }
}

if (Test-Path -LiteralPath $resolvedInstallPath) {
    Write-Error "A desinstalacao nao removeu $resolvedInstallPath."
    exit 1
}

Write-Output "UNINSTALL_SMOKE_OK=true"
