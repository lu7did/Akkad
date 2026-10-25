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
#* sargon_lc0_listen.ps1
#* Starts the listening service for LC0
#=================================================================================================================*
# Lanzador individual LC0/AlphaZero (requiere parche v0.6.117 + v0.6.118).
# Desde la raíz del proyecto: .\scripts\sargon_lc0_listen.ps1 -Weights data\lc0\model.pb.gz
param(
  [Parameter(Mandatory=$true)][string]$Weights,
  [string]$Backend='blas',
  [ValidateRange(1,65535)][int]$Port=6200,
  [string]$HostAddress='127.0.0.1',
  [ValidateRange(1,1000000)][int]$Simulations=128,
  [ValidateRange(0.001,100)][double]$Cpuct=1.5,
  [ValidateSet('strict','allow-incomplete')][string]$History='allow-incomplete',
  [ValidateRange(0,1000000)][int]$Cache=10000,
  [switch]$Once
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_listen.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Lanzador base no encontrado: $launcher" }
if (-not (Test-Path -LiteralPath $Weights -PathType Leaf)) { throw "Pesos LC0 no encontrados: $Weights" }
$argv = @('--mode','TCP','--host',$HostAddress,'--port',[string]$Port,
          '--player','alphazero','--evaluator','lc0','--lc0-weights',$Weights,
          '--lc0-backend',$Backend,'--lc0-history',$History,
          '--lc0-cache',[string]$Cache,'--az-simulations',[string]$Simulations,
          '--az-cpuct',$Cpuct.ToString([System.Globalization.CultureInfo]::InvariantCulture))
if ($Once) { $argv += '--once' }
& $launcher @argv
exit $LASTEXITCODE
