# Ajustar únicamente las rutas: etiqueta LC0 bindings adicional en .pb ya muestreado.
$ErrorActionPreference = 'Stop'
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
$Db = '..\data\pb\lex_sample.pb'
$Weights = '..\data\networks\tinygyal-8.pb.gz'
& $Python -m sargon_nnue.sargon_prepare --input $Db --update lc0-secondary `
  --lc0-secondary-weights $Weights --lc0-backend auto --lc0-history allow-incomplete
if ($LASTEXITCODE -ne 0) { throw 'Fallo etiquetado LC0-secondary' }
