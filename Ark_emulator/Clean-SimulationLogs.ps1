param([switch]$Apply, [switch]$Legacy)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
$cleanupPath = Join-Path $projectRoot 'tools\cleanup_simulation_logs.py'
$cleanupArgs = @($cleanupPath)
if ($Apply) { $cleanupArgs += '--apply' }
if ($Legacy) { $cleanupArgs += '--legacy' }
& $pythonPath @cleanupArgs
exit $LASTEXITCODE
