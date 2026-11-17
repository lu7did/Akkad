param([Parameter(Mandatory=$true)][ValidateRange(1,3)][int]$Mon,
      [string]$In='C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb',
      [string]$Epd='C:\Users\pedro\github\Bobby\Akkad\picoGen\etc\bratko_kopec.epd',
      [string]$Stockfish='C:\Users\pedro\github\Bobby\stockfish\stockfish.exe',
      [string]$Assets='C:\Users\pedro\github\Bobby\Akkad\nurse\assets',
      [int]$Sample=25000,
      [double]$Fraction=10,
      [double]$Validation=20,
      [int]$Epoch=10,
      [double]$Lr=0.0001,
      [double]$MinLr=0.000001,
      [int]$Batch=64,
      [int]$Seed=42,
      [string]$Device='auto')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
if(!$Assets){$Assets=Join-Path (Split-Path -Parent $root) 'assets'}
New-Item -ItemType Directory -Path $Assets -Force | Out-Null
$best=Join-Path $Assets 'best.npz'
$report=Join-Path $Assets 'audit.json'

# MON is 1-based: 1=TRAIN, 2=AUDIT, 3=EXPORT.
# Preserve the user's Sample=5000 and Fraction=10 defaults without passing
# mutually exclusive switches to run_train.ps1. An explicitly supplied
# -Fraction takes precedence over the implicit default -Sample; vice versa.
$explicitSample=$PSBoundParameters.ContainsKey('Sample')
$explicitFraction=$PSBoundParameters.ContainsKey('Fraction')
if($explicitSample -and $explicitFraction -and $Sample -gt 0 -and $Fraction -gt 0){
  throw 'Use either -Sample or -Fraction, not both'
}

for($step=$Mon;$step -le 3;$step++){
  Write-Host "⚙️ MON=$step / paso $step de 3" -ForegroundColor Cyan
  if($step -eq 1){
    if(!(Test-Path -LiteralPath $In -PathType Leaf)){throw "MON=1 requires an existing -In SQLite .pb: $In"}
    $invoke=@{In=$In;Out=$Assets;Validation=$Validation;Epoch=$Epoch;Lr=$Lr;MinLr=$MinLr;Batch=$Batch;Seed=$Seed;Device=$Device}
    if($explicitFraction -and $Fraction -gt 0){
      $invoke.Fraction=$Fraction
      Write-Host "🎲 Muestra: fraction=$Fraction% de partidas" -ForegroundColor DarkCyan
    } elseif($Sample -gt 0){
      $invoke.Sample=$Sample
      Write-Host "🎲 Muestra: sample=$Sample partidas" -ForegroundColor DarkCyan
    } elseif($Fraction -gt 0){
      $invoke.Fraction=$Fraction
      Write-Host "🎲 Muestra: fraction=$Fraction% de partidas" -ForegroundColor DarkCyan
    } else {
      Write-Host '🎲 Muestra: todas las partidas' -ForegroundColor DarkCyan
    }
    & (Join-Path $root 'run_train.ps1') @invoke
  } elseif($step -eq 2){
    if(!(Test-Path -LiteralPath $best -PathType Leaf)){throw "MON=2 requires completed training checkpoint: $best"}
    $invoke=@{Npz=$best;Out=$report}
    if($Epd){
      if(!(Test-Path -LiteralPath $Epd -PathType Leaf)){throw "MON=2 EPD does not exist: $Epd"}
      $invoke.Epd=$Epd
      if($Stockfish){$invoke.Stockfish=$Stockfish}
    } elseif($In){
      if(!(Test-Path -LiteralPath $In -PathType Leaf)){throw "MON=2 database does not exist: $In"}
      $invoke.In=$In
    } else {throw 'MON=2 requires -In or -Epd'}
    & (Join-Path $root 'run_audit.ps1') @invoke
  } elseif($step -eq 3){
    if(!(Test-Path -LiteralPath $best -PathType Leaf)){throw "MON=3 requires completed training checkpoint: $best"}
    & (Join-Path $root 'run_export.ps1') -In $best -Int8 (Join-Path $Assets 'best_int8.npz') -Hpp (Join-Path $Assets 'best_int8.hpp')
  }
  Write-Host "✅ MON=$step completo; próximo MON=$($step+1)" -ForegroundColor Green
}
