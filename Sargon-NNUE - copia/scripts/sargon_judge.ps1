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
#* sargon_judge.ps1
#* Analyzes match results and reports statistics
#=================================================================================================================*
# Sargon-NNUE — Análisis estadístico de encuentros
# Autor y copyright: Pedro E. Colla Copyright (c) 2026
# Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
# Software entregado "AS IS", sin garantía de ningún tipo.
# Versión del lanzador: v0.6.53
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Arguments
)
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = 'python'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $Python -m sargon_nnue.sargon_judge @Arguments
exit $LASTEXITCODE
