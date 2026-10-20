# Sargon-NNUE AlphaZero v0.6.115: 03_valor_resultado_suavizado; una sola operacion.
# Ejecutar en la raiz del proyecto. Los parametros no especificados los maneja Python.
param(
  [Parameter(ValueFromRemainingArguments=$true)]
  [string[]]$Arguments
)
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $Root 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $Python -m sargon_nnue.sargon_prepare --update result @Arguments
exit $LASTEXITCODE
