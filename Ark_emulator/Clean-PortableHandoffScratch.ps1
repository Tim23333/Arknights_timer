<#
.SYNOPSIS
Preview/remove the rejected 2026-10-07 portable handoff scratch restore.
.DESCRIPTION
Only E:/ArkSimLogs/portable_checks/20261007_p1 is eligible. The committed bundle,
real repository, real unpack_work, simulations and other log folders are never
selected. The script checks the pinned manifest, actual process command lines,
all directory reparse points and every actual file path before deletion.
Without -Apply it prints a preview. User execution is required for removal.
#>
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$targetDirectory = [System.IO.Path]::GetFullPath('E:\ArkSimLogs\portable_checks\20261007_p1')
$allowedParent = [System.IO.Path]::GetFullPath('E:\ArkSimLogs\portable_checks')
$manifestPath = Join-Path $PSScriptRoot 'reference\portable_20261007\manifest.json'
$expectedManifest = 'ab22b89682362fdfacdcefbea63b070daff305349d8b58bea8ffd2e6712bc315'

if ((Split-Path $targetDirectory -Parent) -ne $allowedParent -or
    (Split-Path $targetDirectory -Leaf) -ne '20261007_p1') {
    throw 'Resolved cleanup target is outside the explicitly named scratch directory.'
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw 'Run this script from the fully downloaded handoff repository: manifest missing.'
}
if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedManifest) {
    throw 'Pinned source manifest differs; no deletion performed.'
}
if (-not (Test-Path -LiteralPath $targetDirectory)) {
    Write-Host 'Scratch directory already absent; nothing to delete.'
    exit 0
}
$actualTarget = Get-Item -LiteralPath $targetDirectory -Force
if (-not $actualTarget.PSIsContainer -or $actualTarget.FullName -ne $targetDirectory) {
    throw 'Unexpected resolved target; no deletion performed.'
}
$ancestorPath = $targetDirectory
while ($ancestorPath) {
    $ancestor = Get-Item -LiteralPath $ancestorPath -Force
    if ($ancestor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw "Reparse point in target ancestry: $ancestorPath"
    }
    $nextAncestor = Split-Path $ancestorPath -Parent
    if ($nextAncestor -eq $ancestorPath) { break }
    $ancestorPath = $nextAncestor
}
$liveUsers = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and
    ($_.CommandLine.IndexOf($targetDirectory, [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
     $_.CommandLine.IndexOf($targetDirectory.Replace('\','/'), [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
})
if ($liveUsers.Count -gt 0) {
    $liveUsers | Select-Object ProcessId, Name, CommandLine | Format-List
    throw 'An active process references the scratch directory; close it before cleanup.'
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$allowedFiles = @{}
foreach ($entry in $manifest.entries) {
    $relative = [string]$entry.destination.path
    if ($relative.StartsWith('/') -or $relative.Contains(':') -or
        (($relative.Split('/')) -contains '..')) { throw 'Unsafe manifest path.' }
    $allowedFiles[$relative.ToLowerInvariant()] = [string]$entry.sha256
}
$allowedFiles['unpack_work/portable_state/legacy_paths.json'] = 'generated-path-map'
$directories = New-Object 'System.Collections.Generic.Stack[string]'
$directories.Push($targetDirectory)
$fileCount = 0
[long]$byteCount = 0
while ($directories.Count -gt 0) {
    $folder = $directories.Pop()
    foreach ($item in @(Get-ChildItem -LiteralPath $folder -Force)) {
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw "Reparse point inside scratch directory: $($item.FullName)"
        }
        if ($item.PSIsContainer) {
            $directories.Push($item.FullName)
        } else {
            if (-not $item.FullName.StartsWith($targetDirectory + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
                throw 'Enumerated file leaves the approved target.'
            }
            $relative = $item.FullName.Substring($targetDirectory.Length + 1).Replace('\','/').ToLowerInvariant()
            if (-not $allowedFiles.ContainsKey($relative)) {
                throw "Unexpected file in scratch restore; preserved: $($item.FullName)"
            }
            if ($allowedFiles[$relative] -ne 'generated-path-map' -and
                (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $allowedFiles[$relative]) {
                throw "Scratch source was edited after verification; preserved: $($item.FullName)"
            }
            $fileCount += 1
            $byteCount += $item.Length
        }
    }
}
Write-Host "Target: $targetDirectory"
Write-Host ("Files: {0}; bytes: {1}; GiB: {2:N3}" -f $fileCount, $byteCount, ($byteCount / 1GB))
if (-not $Apply) {
    Write-Host 'Preview only. Add -Apply to remove this validated scratch directory.'
    exit 0
}
Remove-Item -LiteralPath $targetDirectory -Recurse -Force
if (Test-Path -LiteralPath $targetDirectory) { throw 'Scratch directory remains; inspect filesystem errors.' }
Write-Host 'Removed only the approved portable handoff scratch restore.'
