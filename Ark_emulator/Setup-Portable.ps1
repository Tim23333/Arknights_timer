<# Restore Git-contained frozen inputs without starting the paused task. #>
param([string]$Python = 'python', [string]$LogDriveBackingDirectory)
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
& git -C $repositoryRoot config core.longpaths true
if ($LASTEXITCODE -ne 0) { throw 'git config failed' }
& $Python -c "import sys; assert sys.version_info[:2] == (3,12), 'Use Python 3.12, preferably 3.12.10'; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 required' }
$venvPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    & $Python -m venv (Join-Path $repositoryRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
}
& $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements-simulator.txt')
if ($LASTEXITCODE -ne 0) { throw 'Simulator dependencies failed' }
& $venvPython (Join-Path $PSScriptRoot 'tools\portable\hydrate.py') --check-archive --restore
if ($LASTEXITCODE -ne 0) { throw 'Reference restore failed' }
if (-not (Test-Path 'E:\')) {
    if (-not $LogDriveBackingDirectory) {
        throw 'No E: drive. Rerun with -LogDriveBackingDirectory C:\ArkSimDrive (or another spacious local folder). This only mounts that folder as E:; no simulations start.'
    }
    $backing = [System.IO.Path]::GetFullPath($LogDriveBackingDirectory)
    New-Item -ItemType Directory -Force -Path $backing | Out-Null
    & subst.exe E: $backing
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the requested E: log-drive mapping' }
}
New-Item -ItemType Directory -Force -Path 'E:\ArkSimLogs\runs', 'E:\ArkSimLogs\receipts' | Out-Null
Write-Host 'Portable inputs restored. Task stays paused. Read HANDOFF_20261007.md before explicitly resuming.'
