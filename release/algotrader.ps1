[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'stop', 'status', 'reconnect', 'upgrade')]
    [string]$Command = 'setup',
    [string]$Directory = '',
    [switch]$Prerelease,
    [switch]$FromBundle
)
$ErrorActionPreference = 'Stop'
if (($Prerelease -or $FromBundle) -and $Command -ne 'upgrade') {
    throw '-Prerelease and -FromBundle require the upgrade command.'
}
if ($Prerelease -and $FromBundle) { throw 'Choose one upgrade option.' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/'
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with Linux containers, then retry.' }
$EngineOS = (& docker info --format '{{.OSType}}')
if ($EngineOS.Trim() -ne 'linux') { throw 'Select Linux containers in Docker Desktop, then retry.' }
$Endpoint = (& docker context inspect --format '{{.Endpoints.docker.Host}}')
if ($env:DOCKER_HOST) { $Endpoint = $env:DOCKER_HOST }
if ($Endpoint -notmatch '^npipe://') { throw 'Use the local Docker Desktop engine for this installation.' }
$ComposeVersion = (& docker compose version --short)
if ($LASTEXITCODE -ne 0) { throw 'Install Docker Compose: https://docs.docker.com/compose/install/' }
if ([version]($ComposeVersion.TrimStart('v').Split('-')[0]) -lt [version]'2.30.0') {
    throw 'Docker Compose 2.30 or newer is required: https://docs.docker.com/compose/install/'
}
$DefaultDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'AlgoTrader'
if (-not $Directory) {
    $Directory = $DefaultDirectory
    if ($Command -eq 'setup' -and -not (Test-Path (Join-Path $Directory 'state/installation.json'))) {
        $Selection = Read-Host "Installation directory [$DefaultDirectory]"
        if ($Selection) { $Directory = $Selection }
    }
}
$Directory = [IO.Path]::GetFullPath($Directory)
$ConfigDirectory = Join-Path $Directory 'config'
$DataDirectory = Join-Path $Directory 'data'
$StateDirectory = Join-Path $Directory 'state'
foreach ($Path in @($ConfigDirectory, $DataDirectory, $StateDirectory)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}
$BundleDirectory = $PSScriptRoot
$Record = Join-Path $StateDirectory 'installation.json'
if ($Command -ne 'setup' -and -not $FromBundle -and (Test-Path -LiteralPath $Record)) {
    $Installed = (Get-Content -LiteralPath $Record -Raw | ConvertFrom-Json).version
    if ($Installed -cmatch '^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$') {
        $AcceptedBundle = Join-Path $DataDirectory "releases/$Installed"
        if (Test-Path -LiteralPath (Join-Path $AcceptedBundle 'installer-image.txt')) {
            $BundleDirectory = $AcceptedBundle
        }
    }
}
$ImagePath = Join-Path $BundleDirectory 'installer-image.txt'
if (-not (Test-Path -LiteralPath $ImagePath) -or -not (Test-Path -LiteralPath (Join-Path $BundleDirectory 'release.json'))) {
    throw 'Download and extract a complete AlgoTrader release ZIP first.'
}
$InstallerImage = (Get-Content -LiteralPath $ImagePath -Raw).Trim()
if ($InstallerImage -notmatch '^ghcr\.io/[a-z0-9./_-]+@sha256:[0-9a-f]{64}$') {
    throw 'Invalid installer image in release bundle.'
}
$ControllerName = 'algotrader-setup-' + [guid]::NewGuid().ToString('N')
$DockerArguments = @(
    'run', '--rm', '--interactive', '--tty', '--name', $ControllerName,
    '--volume', '/var/run/docker.sock:/var/run/docker.sock',
    '--volume', "${ConfigDirectory}:/config", '--volume', "${DataDirectory}:/data",
    '--volume', "${StateDirectory}:/state", '--volume', "${BundleDirectory}:/bundle:ro",
    '--env', "ALGOTRADER_CONTROLLER_NAME=$ControllerName",
    '--env', "ALGOTRADER_INSTALLER_IMAGE=$InstallerImage",
    $InstallerImage
)
if ($Command -eq 'upgrade') {
    if ($FromBundle) { $DockerArguments += 'apply-bundle' }
    else {
        $DockerArguments += 'update'
        if ($Prerelease) { $DockerArguments += '--prerelease' }
    }
} else { $DockerArguments += $Command }
Write-Host "Configuration: $ConfigDirectory"
Write-Host "State and backups: $StateDirectory"
& docker @DockerArguments
exit $LASTEXITCODE
