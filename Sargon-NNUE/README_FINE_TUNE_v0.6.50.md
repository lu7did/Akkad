# SARGON-NNUE v0.6.50 — Refinamiento opcional CLASSIC
Requiere un `.pb` con `classic_cp` y WDL Stockfish (`wdl_source=STOCKFISH` o `TERMINAL`) para todos los movimientos elegidos. La red base se conserva intacta. El directorio de salida debe estar vacío y ser diferente al origen.

## Ejemplo
```powershell
python -m sargon_nnue.sargon_train `
  --input "..\data\pb\boot_classic.pb" `
  --network "..\data\nnue\classic\nnue_epoch_009.npz" `
  --nnuedir "..\data\nnue\classic_refined" `
  --pytorch --device xpu --torch-foreach off --torch-dtype float64 `
  --classic --weight-classic 1 --fine-tune `
  --refine-stockfish-max-cp 10 --shuffle 20 `
  --validation 5 --seed 42 --optimizer adamw --lr 0.00001 --epoch 5
```
La corrección es `max_cp * clip(2*(S - sigmoid(C/400)), -1, 1)` centipawns.
El objetivo es `(C + corrección)/400`, y la misma fórmula se aplica a la validación. Se imprimen el MSE combinado y CLASSIC, baseline original y comparaciones por epoch.

**Precaución:** con `--refine-stockfish-max-cp 0` el fine-tuning entrena solo CLASSIC y no usa Stockfish. No se prometen mejoras de fuerza de juego sin MATCH.
