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
#* sargon_lc0_match.ps1
#* Runs chess matches using LC0
#=================================================================================================================*
# Lanzador individual MATCH: AlphaZero/LC0 frente a Sargon-Plus/CLASSIC.
# Usa el MATCH real; cambia los parámetros del contrincante con el lanzador genérico si lo necesitas.
param(
  [Parameter(Mandatory=$true)][string]$Weights,
  [string]$Backend='blas',
  [ValidateRange(1,1000000)][int]$Simulations=128,
  [ValidateRange(0.001,100)][double]$Cpuct=1.5,
  [ValidateRange(1,100000)][int]$Pairs=2,
  [ValidateRange(10,86400)][double]$Timeout=120,
  [string]$Pgn='data/match_alphazero_lc0.pgn',
  [string]$Csv='data/match_alphazero_lc0.csv'
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_match.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Lanzador base no encontrado: $launcher" }
if (-not (Test-Path -LiteralPath $Weights -PathType Leaf)) { throw "Pesos LC0 no encontrados: $Weights" }
$argv = @('--a-player','alphazero','--a-evaluator','lc0',
          '--a-lc0-weights',$Weights,'--a-lc0-backend',$Backend,
          '--a-az-simulations',[string]$Simulations,
          '--a-az-cpuct',$Cpuct.ToString([System.Globalization.CultureInfo]::InvariantCulture),
          '--b-player','sargon-plus','--b-evaluator','classic',
          '--pairs',[string]$Pairs,
          '--timeout',$Timeout.ToString([System.Globalization.CultureInfo]::InvariantCulture),
          '--pgn',$Pgn,'--csv',$Csv)
& $launcher @argv
exit $LASTEXITCODE
