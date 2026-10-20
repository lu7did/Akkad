# Sargon-NNUE v0.6.38 — Resample desde `.pb`

El nuevo `--resample NN` en `sargon-prepare.py` toma **NN% de partidas completas** del archivo `--input` en vez de leer PGN. La base original se abre **en modo lectura** y el archivo `--out` es independiente; se crea de forma temporal y solo se publica tras verificar la integridad SQLite. `--seed` (42 por defecto) permite reproducir el muestreo. `--override` sirve para reemplazar una salida previamente existente, nunca la entrada.

## Uso sin Stockfish (copiar WDL existentes)

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_prepare `
  --input "..\data\pb\boot.pb" `
  --resample 10 --seed 42 `
  --out "..\data\pb\boot_10pct.pb"
```

## Uso con Stockfish (recalcular WDL)

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_prepare `
  --input "..\data\pb\boot.pb" `
  --resample 10 --seed 42 `
  --stockfish --stockfish-path "C:\Users\pedro\github\bobby\stockfish\stockfish.exe" `
  --stockfish-depth 10 --stockfish-threads 2 `
  --out "..\data\pb\boot_sf_10pct.pb"
```

## Entrenamiento normal, sin cambios

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_train `
  --pytorch --input "..\data\pb\boot_sf_10pct.pb" `
  --validation 5 --stockfish --weight-stockfish 1 `
  --nnuedir "..\data\nnue\sf_sample1" `
  --optimizer adamw --lr 0.0001 --batch-size 64 --epoch 3 `
  --device xpu --torch-foreach off --seed 42
```

**Importante**: no usar `--quick` al entrenar esa base reducida si se desea utilizar el 95% para entrenamiento y el 5% para validación. Los WDL se calculan para todas las posiciones de las partidas seleccionadas, incluso aquellas destinadas posteriormente a validación; durante la validación la red **no consulta** Stockfish. Cuando `--weight-stockfish 1`, comprobar la métrica de validación frente a WDL además de PGN si se requiere medir la tarea de entrenamiento: el backend PyTorch anterior utiliza PGN para la validación. Stockfish solo se ejecuta durante la preparación.

## Consideraciones de reconstrucción

El `.pb` almacena vector de 781 bits, contador de 50 movimientos y número de ply, suficiente para reconstruir la **posición codificada**; no incluye la historia completa de repetición. Se valida la correspondencia exacta entre el vector reconstruido y el original antes de solicitar Stockfish. No se recupera la historia de triple repetición; Stockfish analiza la posición actual y no el historial original. Si la reconstrucción no es exacta o falla el motor, el proceso aborta sin publicar salida parcial.

**Pruebas**: comprobación de sintaxis Python completada. La reevaluación real de Stockfish y la reconstrucción sobre la base completa requieren ejecutar en un entorno con `python-chess` y Stockfish. La salida se genera en un archivo temporal y se verifica con `PRAGMA integrity_check` antes de publicar.
