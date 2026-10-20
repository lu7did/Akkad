#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_lc0_probe.ps1
#* Probes and verifies LC0
#=================================================================================================================*
# Sargon-NNUE AlphaZero/LC0 v0.6.117; PowerShell 7 cross-platform.
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)
$root = Split-Path -Parent $PSScriptRoot
$Python = $env:SARGON_PYTHON
if (-not $Python) { $Python = if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' } else { 'python' } }
$env:PYTHONPATH = (Join-Path $root 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
$values = @()

& $Python -m sargon_nnue.lc0_probe @values @Arguments
exit $LASTEXITCODE
