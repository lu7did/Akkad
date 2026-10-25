param([string]$Weights)
$exe = Join-Path $PSScriptRoot '..\build\AlphaZero.exe'
if (!(Test-Path $exe)) { throw "Missing executable: $exe" }
@('uci','isready','position startpos','go nodes 8 movetime 3000','stop','quit') |
  & $exe --weights $Weights --backend eigen
