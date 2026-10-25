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
#* sargon_lc0_uci_train.ps1
#* Trains models for LC0 through UCI
#=================================================================================================================*
# Sargon-NNUE LC0-UCI v0.6.120. Función individual (PowerShell 7).
# Variables locales: no requiere run_pipeline ni estado compartido.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$InputPb,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [double]$WeightClassic=0.15,
    [double]$WeightStockfish=0.05,
    [double]$WeightResult=0.4,
    [double]$WeightLc0=0.4,
    [int]$Epochs=10,
    [double]$Validation=10,
    [double]$Shuffle=20,
    [string]$Device='auto' 
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'sargon_train.ps1'
$argv = @('--input',$InputPb,'--nnuedir',$OutputDir,'--pytorch','--lc0-source','uci','--weight-classic',"$WeightClassic",'--weight-stockfish',"$WeightStockfish",'--weight-result',"$WeightResult",'--weight-lc0',"$WeightLc0",'--epoch',"$Epochs",'--validation',"$Validation",'--shuffle',"$Shuffle",'--device',$Device)
& $launcher @argv
exit $LASTEXITCODE
