# Inspect IL metadata without loading game assemblies or executing stubs.
param([switch]$Check)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Reflection.Metadata
$taskRoot = (Resolve-Path "$PSScriptRoot\..").Path
$paths = @("$taskRoot\..\Ark_data\DummyDll\Assembly-CSharp.dll", "$taskRoot\..\Ark_data\Cpp2IL_DummyDll\Assembly-CSharp.dll")
$rows = @()
foreach ($path in $paths) {
    $absolute = (Resolve-Path -LiteralPath $path).Path
    $stream = [System.IO.File]::OpenRead($absolute)
    $pe = [System.Reflection.PortableExecutable.PEReader]::new($stream)
    try {
        $metadata = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
        $types = @()
        foreach ($handle in $metadata.TypeDefinitions) {
            $type = $metadata.GetTypeDefinition($handle)
            $name = $metadata.GetString($type.Name)
            if ($name -notin @('HpRatioToggleChecker','ToggleablePassiveBuffAbility','PassiveAttachmentAbility','PhysicsRange')) { continue }
            $methods = @()
            foreach ($methodHandle in $type.GetMethods()) {
                $method = $metadata.GetMethodDefinition($methodHandle)
                $rva = $method.RelativeVirtualAddress
                $bytes = [byte[]]@()
                $errorText = $null
                if ($rva -ne 0) {
                    try { $bytes = [System.Reflection.Metadata.PEReaderExtensions]::GetMethodBody($pe,$rva).GetILBytes() }
                    catch { $errorText = $_.Exception.Message }
                }
                $methods += [ordered]@{ name=$metadata.GetString($method.Name); rva=$rva; implementation_attributes=[string]$method.ImplAttributes; il_bytes=[Convert]::ToHexString($bytes); error=$errorText }
            }
            $types += [ordered]@{ name=$name; namespace=$metadata.GetString($type.Namespace); methods=$methods }
        }
        $rows += [ordered]@{ path=$absolute; sha256=(Get-FileHash -LiteralPath $absolute -Algorithm SHA256).Hash.ToLowerInvariant(); bytes=(Get-Item -LiteralPath $absolute).Length; types=$types }
    }
    finally { $pe.Dispose(); $stream.Dispose() }
}
$out = "$taskRoot\packages\campaign\chapter02_behavior\skulsr.managed_bodies.reference.json"
$result = [ordered]@{ schema='ark-sim/skulsr-managed-body-probe/v1'; reader='System.Reflection.Metadata PEReader, no assembly execution'; assemblies=$rows; source_tool_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant(); native_binary_body_recovered=$false }
$json = ($result | ConvertTo-Json -Depth 12) + [Environment]::NewLine
if ($Check) {
    if ([System.IO.File]::ReadAllText($out) -cne $json) { throw 'Managed body source/output drift' }
} else { [System.IO.File]::WriteAllText($out,$json,[System.Text.UTF8Encoding]::new($false)) }
$rows | ForEach-Object { [pscustomobject]@{ path=$_.path; classes=$_.types.Count; hpIL=($_.types | Where-Object name -eq 'HpRatioToggleChecker').methods.il_bytes } } | ConvertTo-Json -Depth 4
