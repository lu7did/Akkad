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
#* sargon_lc0_uci_rally.ps1
#* Runs the chess rally for LC0 through UCI
#=================================================================================================================*
# Sargon-NNUE LC0-UCI v0.6.120. Función individual (PowerShell 7).
# Variables locales: no requiere run_pipeline ni estado compartido.
[CmdletBinding()]
param(
    [string]$Brain='examples/lc0_uci/brains_lc0_uci.json',
    [string]$Rally='examples/lc0_uci/rally_lc0_uci.json',
    [string]$Tournament='lc0_uci_vs_sargonplus',
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_rally.ps1'
$argv = @('--brain',$Brain,'--rally',$Rally,'--id',$Tournament)
if ($PreflightOnly) { $argv += "--preflight-only" }
& $launcher @argv
exit $LASTEXITCODE
