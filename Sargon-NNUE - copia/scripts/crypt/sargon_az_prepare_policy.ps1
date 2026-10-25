# SARGON-NNUE AlphaZero v0.6.114 - politica historica separada
# Copia el .pb origen y agrega SOLO tablas experimentales de politica.
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Arguments
)
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $Root 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $Python -m sargon_nnue.az_policy @Arguments
exit $LASTEXITCODE
