<#
.SYNOPSIS
Run a V2 content package in the fixed log directory and clean after exit.
.EXAMPLE
.\Run-Simulation.ps1 -Content packages/custom/custom_guard.json -Ticks 30
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Content,
    [ValidateRange(0, 2147483647)][int]$Ticks = 300,
    [int]$Seed = 0,
    [string]$Commands,
    [string]$Ruleset
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
$runnerPath = Join-Path $projectRoot 'tools\run_with_log_cleanup.py'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$suffix = ([guid]::NewGuid().ToString('N')).Substring(0, 8)
$runDirectory = "E:/ArkSimLogs/runs/manual_${stamp}_${suffix}"
$runArgs = @(
    $runnerPath, '--run-dir', $runDirectory, '--', $pythonPath,
    '-m', 'ark_sim', 'run', $Content, '--ticks', [string]$Ticks,
    '--seed', [string]$Seed, '--output', '{run_dir}/snapshot.json',
    '--replay-output', '{run_dir}/replay.json'
)
if ($Commands) { $runArgs += @('--commands', $Commands) }
if ($Ruleset) { $runArgs += @('--ruleset', $Ruleset) }
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath @runArgs
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $runExitCode
