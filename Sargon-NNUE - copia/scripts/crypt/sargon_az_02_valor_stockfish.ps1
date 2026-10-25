# Sargon AlphaZero v0.6.116 | 02_valor_stockfish | una operacion aislada.
# Se invoca desde la raiz del repositorio; argumentos unicamente de esta etapa.
$AzArgs = @($args) # Recibe solo los argumentos de ESTA etapa; no hay parametros globales.
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = 'python' }
$Root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = (Join-Path $Root 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
& $Python -m sargon_nnue.sargon_prepare --update stockfish @AzArgs
exit $LASTEXITCODE
