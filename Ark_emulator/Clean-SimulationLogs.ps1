<#
.SYNOPSIS
Preview or remove completed simulation logs, preserving sources and live runs.
.DESCRIPTION
-RunDirectory E:/ArkSimLogs/runs/manual_001 names an explicitly completed run.
That scoped command uses age zero; live-process protection remains active.
Without -RunDirectory the policy age remains fifteen minutes.
#>
param([switch]$Apply, [switch]$Legacy, [string]$RunDirectory)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
$cleanupPath = Join-Path $projectRoot 'tools\cleanup_simulation_logs_v2.py'
$cleanupArgs = @($cleanupPath)
if ($Apply) { $cleanupArgs += '--apply' }
if ($Legacy) { $cleanupArgs += '--legacy' }
if ($RunDirectory) { $cleanupArgs += @('--run-dir', $RunDirectory, '--minimum-age-minutes', '0') }
& $pythonPath @cleanupArgs
exit $LASTEXITCODE
