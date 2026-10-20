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
#* sargon_lc0_uci_match.ps1
#* Runs chess matches using LC0 through UCI
#=================================================================================================================*
# Sargon-NNUE LC0-UCI v0.6.120. Función individual (PowerShell 7).
# Variables locales: no requiere run_pipeline ni estado compartido.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Weights='',
    [string]$Backend='auto',
    [int]$Nodes=800,
    [int]$Pairs=2
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_match.ps1'
$argv = @('--a-player','lc0','--a-evaluator','null','--a-lc0-uci-path',$Executable,'--a-lc0-backend',$Backend,'--a-lc0-uci-nodes',"$Nodes",'--b-player','sargon-plus','--b-evaluator','classic','--pairs',"$Pairs")
if ($Weights) {
    $prefix = if ('match' -eq 'match') { '--a-' } elseif ('match' -eq 'selfplay') { '--white-' } else { '--' }
    $argv += @($prefix + 'lc0-weights', $Weights)
    if ('match' -eq 'selfplay') { $argv += @('--black-lc0-weights', $Weights) }
}
& $launcher @argv
exit $LASTEXITCODE
