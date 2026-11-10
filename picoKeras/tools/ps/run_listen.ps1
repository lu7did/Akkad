# picoKeras X86 UCI/TCP launcher v0.2.6
param(
 [Parameter(Mandatory=$false)][string]$Weights,
 [string]$Ip='0.0.0.0',
 [ValidateRange(1,65535)][int]$Port=6110,
 [ValidateSet('Release','Debug','RelWithDebInfo')][string]$Config='Release',
 [switch]$Help
)
$ErrorActionPreference='Stop'
if ($Help) { Write-Host 'Usage: run_listen.ps1 -Weights path_to_SavedModel.tf [-Ip 0.0.0.0] [-Port 6110] [-Config Release]';return }
if (-not $Weights) {throw 'Required: -Weights <SavedModel directory>'}
if (-not (Test-Path (Join-Path $Weights 'saved_model.pb'))) {throw "Missing SavedModel: $Weights"}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$exe=Join-Path $root "x86/build/$Config/picoKeras.exe"
if (-not (Test-Path $exe)) {$exe=Join-Path $root 'x86/build/picoKeras.exe'}
if (-not (Test-Path $exe)) {throw 'Build picoKeras X86 first'}
& $exe --weights ([IO.Path]::GetFullPath($Weights)) --tcp --host $Ip --port $Port
exit $LASTEXITCODE
