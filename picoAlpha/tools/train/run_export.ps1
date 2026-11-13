# picoAlpha training wrapper v0.1.1. Edit ONLY the defaults block below.
param(
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments=$true)] [string[]]$Overrides
)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Defaults = @{
    "in" = "..\..\assets\checkpoints\best.pt"
    "out" = "..\..\assets\picoalpha_nnue_weights.hpp"
    "int8" = "..\..\assets\checkpoints\best_int8.pt"
    "namespace" = "picoalpha_nnue"
}
if ($Help -or ($Overrides -contains '--help') -or ($Overrides -contains '-help')) {
    Write-Host 'run_export.ps1 [--option value ...] [--help]'
    Write-Host 'Editable defaults:'
    $Defaults.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host "  --$($_.Key) $($_.Value)" }
    & python (Join-Path $ScriptDir 'export.py') --help
    exit 0
}
if ($Overrides.Count % 2 -ne 0) { throw 'Overrides must be --name value pairs' }
for ($i=0; $i -lt $Overrides.Count; $i+=2) {
    $key=$Overrides[$i] -replace '^--',''
    if (-not $Overrides[$i].StartsWith('--') -or -not $Defaults.ContainsKey($key)) { throw "Unknown option: $($Overrides[$i])" }
    $Defaults[$key]=$Overrides[$i+1]
}
$Arguments = @()
foreach ($key in @("in","out","int8","namespace")) {
    if ($null -ne $Defaults[$key]) {
        $value=[string]$Defaults[$key]
        if ($key -in @('in','out','int8') -and -not [System.IO.Path]::IsPathRooted($value)) { $value=[System.IO.Path]::GetFullPath((Join-Path $ScriptDir $value)) }
        $Arguments += "--$key"; $Arguments += $value
    }
}
& python (Join-Path $ScriptDir 'export.py') @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
