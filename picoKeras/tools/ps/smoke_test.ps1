# picoKeras X86 UCI smoke test v0.2.6
param([string]$Weights,[ValidateSet('Release','Debug','RelWithDebInfo')][string]$Config='Release',[switch]$Help)
$ErrorActionPreference='Stop'
if ($Help) {Write-Host 'Usage: smoke_test.ps1 -Weights path_to_SavedModel.tf [-Config Release]';return}
if (-not $Weights) {throw 'Required: -Weights <SavedModel directory>'}
if (-not (Test-Path (Join-Path $Weights 'saved_model.pb'))) {throw "Missing SavedModel: $Weights"}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$exe=Join-Path $root "x86/build/$Config/picoKeras.exe"
if (-not (Test-Path $exe)) {$exe=Join-Path $root 'x86/build/picoKeras.exe'}
if (-not (Test-Path $exe)) {throw "Executable missing: $exe"}
$python=Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {throw 'Python needed for BOM-free smoke test'}
& python (Join-Path $root 'tools/smoke_uci.py') --engine $exe --weights ([IO.Path]::GetFullPath($Weights))
if ($LASTEXITCODE -ne 0) {throw "UCI smoke failed ($LASTEXITCODE)"}
