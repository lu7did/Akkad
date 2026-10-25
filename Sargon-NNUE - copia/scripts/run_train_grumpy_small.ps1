# Modelo compacto experimental; NO genera grumpy.bin para el firmware.
$ErrorActionPreference = 'Stop'
$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
$Db = '..\data\pb\lex_sample.pb'
$Out = '..\data\runs\lex_grumpy_small\checkpoints'
& $Python -m sargon_nnue.sargon_train --input $Db --nnuedir $Out `
  --pytorch --architecture grumpy-small --device auto --torch-dtype float32 `
  --epoch 20 --validation 10 --batch-size 128 --lr 0.001 `
  --weight-result 0.30 --weight-stockfish 0.20 --weight-classic 0.10 `
  --weight-lc0 0.20 --weight-lc0-secondary 0.20 --weight-mcts 0.00
if ($LASTEXITCODE -ne 0) { throw 'Fallo entrenamiento grumpy-small' }
