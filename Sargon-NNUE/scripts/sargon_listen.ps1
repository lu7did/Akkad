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
#* sargon_listen.ps1
#* Starts the listening service for Sargon-NNUE
#=================================================================================================================*
# Sargon-NNUE — Listener UCI TCP/STDIN con perfiles brain
# Autor y copyright: Pedro. Copyright (c) 2026 Pedro.
# Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
# Software entregado "AS IS", sin garantía de ningún tipo.
# Versión del lanzador: v0.6.53
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Arguments
)
# PowerShell 7 works on Windows, Debian and macOS.
$Python = $env:SARGON_PYTHON
if (-not $Python) {
  $projectRoot = Split-Path -Parent $PSScriptRoot
  $candidates = @(
    (Join-Path $projectRoot '.venv/Scripts/python.exe'),
    (Join-Path $projectRoot '.venv/bin/python'),
    (Join-Path $projectRoot 'venv/Scripts/python.exe'),
    (Join-Path $projectRoot 'venv/bin/python'))
  foreach ($candidate in $candidates) { if (Test-Path $candidate) { $Python=$candidate; break } }
  if (-not $Python) {
    $Python = if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' } else { 'python' }
  }
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $Python -m sargon_nnue.sargon_listen @Arguments
exit $LASTEXITCODE
