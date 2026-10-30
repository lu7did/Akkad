param(
  [string]$Network = ".\small.mul.int8.tflite",
  [string]$StaticNetwork = ".\small.static.int8.tflite",
  [string]$Exe = ".\build\Release\picoKeras.exe"
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot
if (-not (Test-Path $Network)) { throw "No existe modelo INT8: $Network" }
$python = (Get-Command python -ErrorAction Stop).Source
& $python (Join-Path $projectRoot 'tools\staticize_reshape.py') --input $Network --output $StaticNetwork --report '.\staticize_reshape_v0.1.42.json'
if ($LASTEXITCODE -ne 0) { throw "Staticize fallo; el modelo original no se modifico" }
if (-not (Test-Path $Exe)) { throw "No existe ejecutable $Exe" }
$netPath=(Resolve-Path $StaticNetwork).Path
Write-Host '[picoKeras v0.1.42] Iniciando UCI con modelo de formas estáticas...'
@('uci','isready','position startpos','go') | & $Exe --network $netPath --stdio
if ($LASTEXITCODE -ne 0) { throw "picoKeras devolvio exit $LASTEXITCODE" }
