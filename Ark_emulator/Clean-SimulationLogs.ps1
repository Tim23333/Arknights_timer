<#
.SYNOPSIS
Preview or remove completed simulation logs, preserving sources and live runs.
.DESCRIPTION
-RunDirectory E:/ArkSimLogs/runs/manual_001 names an explicitly completed run.
That scoped command uses age zero; live-process protection remains active.
Without -RunDirectory the policy age remains fifteen minutes.
-AllCompleted includes previous output locations and uses age zero.
Live-process and open-file protection remains active in every mode.
#>
param([switch]$Apply, [switch]$Legacy, [switch]$AllCompleted, [string]$RunDirectory)
$ErrorActionPreference = 'Stop'
if ($AllCompleted -and $RunDirectory) {
    throw 'Choose -AllCompleted or -RunDirectory, not both.'
}
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
$cleanupPath = Join-Path $projectRoot 'tools\cleanup_simulation_logs_v2.py'
$cleanupArgs = @($cleanupPath)
if ($Apply) { $cleanupArgs += '--apply' }
if ($Legacy -or $AllCompleted) { $cleanupArgs += '--legacy' }
if ($AllCompleted) { $cleanupArgs += @('--minimum-age-minutes', '0') }
if ($RunDirectory) { $cleanupArgs += @('--run-dir', $RunDirectory, '--minimum-age-minutes', '0') }
& $pythonPath @cleanupArgs
exit $LASTEXITCODE
