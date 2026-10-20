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
#* sargon_lc0_rally.ps1
#* Runs the chess rally for LC0
#=================================================================================================================*
# Lanzador individual RALLY: usa brains.json y rally.json con perfiles AlphaZero/LC0.
# No crea ni modifica los archivos JSON ni cambia resultados previos silenciosamente.
param(
  [string]$Brain='examples/lc0/brains_lc0.json',
  [string]$Rally='examples/lc0/rally_lc0.json',
  [string]$Tournament='lc0_vs_sargonplus',
  [switch]$PreflightOnly,
  [switch]$VerboseMoves
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_rally.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Lanzador base no encontrado: $launcher" }
if (-not (Test-Path -LiteralPath $Brain -PathType Leaf)) { throw "Brain JSON no encontrado: $Brain" }
if (-not (Test-Path -LiteralPath $Rally -PathType Leaf)) { throw "Rally JSON no encontrado: $Rally" }
$argv = @('--brain',$Brain,'--rally',$Rally,'--id',$Tournament)
if ($PreflightOnly) { $argv += '--preflight-only' }
if ($VerboseMoves) { $argv += '--verbose' }
& $launcher @argv
exit $LASTEXITCODE
