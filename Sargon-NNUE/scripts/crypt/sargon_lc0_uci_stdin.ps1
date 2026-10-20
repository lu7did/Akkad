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
#* sargon_lc0_uci_stdin.ps1
#* Starts standard-input mode for LC0 through UCI
#=================================================================================================================*
# Sargon-NNUE LC0-UCI v0.6.120. Función individual (PowerShell 7).
# Variables locales: no requiere run_pipeline ni estado compartido.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [string]$Weights='',
    [string]$Backend='auto',
    [string]$BackendOptions='',
    [int]$Nodes=800,
    [int]$Threads=1
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_stdin.ps1'
$argv = @('--player','lc0','--evaluator','null','--lc0-uci-path',$Executable,'--lc0-backend',$Backend,'--lc0-backend-options',$BackendOptions,'--lc0-uci-nodes',"$Nodes",'--lc0-uci-threads',"$Threads")
if ($Weights) {
    $prefix = if ('stdin' -eq 'match') { '--a-' } elseif ('stdin' -eq 'selfplay') { '--white-' } else { '--' }
    $argv += @($prefix + 'lc0-weights', $Weights)
    if ('stdin' -eq 'selfplay') { $argv += @('--black-lc0-weights', $Weights) }
}
& $launcher @argv
exit $LASTEXITCODE
