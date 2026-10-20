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
#* sargon_lc0_uci_selfplay.ps1
#* Runs self-play for LC0 through UCI
#=================================================================================================================*
# Sargon-NNUE LC0-UCI v0.6.120. Función individual (PowerShell 7).
# Variables locales: no requiere run_pipeline ni estado compartido.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Weights='',
    [string]$Backend='auto',
    [int]$Nodes=800,
    [int]$Games=2,
    [string]$Pgn='data/lc0_uci_selfplay.pgn' 
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_selfplay.ps1'
$argv = @('--white-player','lc0','--white-evaluator','null','--white-lc0-uci-path',$Executable,'--white-lc0-backend',$Backend,'--white-lc0-uci-nodes',"$Nodes",'--black-player','lc0','--black-evaluator','null','--black-lc0-uci-path',$Executable,'--black-lc0-backend',$Backend,'--black-lc0-uci-nodes',"$Nodes",'--games',"$Games",'--pgn',$Pgn)
if ($Weights) {
    $prefix = if ('selfplay' -eq 'match') { '--a-' } elseif ('selfplay' -eq 'selfplay') { '--white-' } else { '--' }
    $argv += @($prefix + 'lc0-weights', $Weights)
    if ('selfplay' -eq 'selfplay') { $argv += @('--black-lc0-weights', $Weights) }
}
& $launcher @argv
exit $LASTEXITCODE
