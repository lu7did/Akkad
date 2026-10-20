# --shuffle PCT

Ejemplo:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_train `
  --pytorch `
  --input "..\data\pb\boot_sf_10pct.pb" `
  --nnuedir "..\data\nnue\sf_shuffle20" `
  --validation 5 --seed 42 `
  --shuffle 20 `
  --stockfish --weight-stockfish 1 `
  --optimizer adamw --lr 0.0001 --batch-size 64 `
  --epoch 10 --device xpu --torch-foreach off
```

Con la muestra anterior (121090 posiciones de train), `--shuffle 20` utiliza unas 24218 posiciones seleccionadas una sola vez; conserva íntegras las 6858 posiciones de validación. Los epochs reutilizan las posiciones seleccionadas en distinto orden. La selección de partidas en validación se realiza **antes** de muestrear las posiciones y depende de `--seed`, `--validation` y el archivo .pb. La salida se debe dirigir a un directorio nuevo.

Nota: `--shuffle` representa **porcentaje de movimientos de entrenamiento**, no porcentaje de partidas; no debe confundirse con el orden aleatorio de cada epoch.
