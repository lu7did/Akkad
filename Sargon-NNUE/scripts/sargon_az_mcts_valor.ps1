# Sargon-NNUE v0.6.163 — standalone AlphaZero-MCTS labeling launcher
[CmdletBinding()]
param(
 [string]$Python = '',[Parameter(Mandatory=$true)][string]$InputPb,
 [Parameter(Mandatory=$true)][string]$Weights,[string]$Backend='auto',
 [string]$BackendOptions='',[ValidateSet('strict','allow-incomplete')][string]$History='allow-incomplete',
 [int]$Simulations=128,[double]$Cpuct=1.5,[int]$TmaxMs=0
)
$ErrorActionPreference='Stop'
if (-not $Python) { $Python = if ($env:SARGON_PYTHON) {$env:SARGON_PYTHON} else {'python'} }
$root=Split-Path -Parent $PSScriptRoot
$old=$env:PYTHONPATH
try {
 $env:PYTHONPATH=(Join-Path $root 'src')+[IO.Path]::PathSeparator+$old
 $fmt=[Globalization.CultureInfo]::InvariantCulture
 & $Python -m sargon_nnue.az_mcts_label --input $InputPb --weights $Weights --backend $Backend `
  --backend-options $BackendOptions --history $History --simulations $Simulations `
  --cpuct ($Cpuct.ToString('G17',$fmt)) --tmax-ms $TmaxMs
 if ($LASTEXITCODE -ne 0) { throw "AlphaZero-MCTS fallo con exit code $LASTEXITCODE" }
} finally { $env:PYTHONPATH=$old }
