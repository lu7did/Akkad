# picoAlpha training wrapper v0.1.1. Edit ONLY the defaults block below.
param(
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments=$true)] [string[]]$Overrides
)
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Defaults = @{
    "in" = "..\..\data\train.pb"
    "out" = "..\..\assets\checkpoints"
    "validate" = 20
    "epoch" = 20
    "method" = "AdamW"
    "lr" = 0.005
    "lr_min" = 0.0001
    "batch" = 64
    "seed" = 42
    "device" = "cpu"
    "value_weight" = 2.0
}
if ($Help -or ($Overrides -contains '--help') -or ($Overrides -contains '-help')) {
    Write-Host 'run_train.ps1 [--option value ...] [--help]'
    Write-Host 'Editable defaults:'
    $Defaults.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Host "  --$($_.Key) $($_.Value)" }
    & python (Join-Path $ScriptDir 'train.py') --help
    exit 0
}
if ($Overrides.Count % 2 -ne 0) { throw 'Overrides must be --name value pairs' }
for ($i=0; $i -lt $Overrides.Count; $i+=2) {
    $key=$Overrides[$i] -replace '^--',''
    if (-not $Overrides[$i].StartsWith('--') -or -not $Defaults.ContainsKey($key)) { throw "Unknown option: $($Overrides[$i])" }
    $Defaults[$key]=$Overrides[$i+1]
}
$Arguments = @()
foreach ($key in @("in","out","validate","epoch","method","lr","lr_min","batch","seed","device","value_weight")) {
    if ($null -ne $Defaults[$key]) {
        $value=[string]$Defaults[$key]
        if ($key -in @('in','out') -and -not [System.IO.Path]::IsPathRooted($value)) { $value=[System.IO.Path]::GetFullPath((Join-Path $ScriptDir $value)) }
        $Arguments += "--$key"; $Arguments += $value
    }
}
& python (Join-Path $ScriptDir 'train.py') @Arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
