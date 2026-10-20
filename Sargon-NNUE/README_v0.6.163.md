# Sargon-NNUE v0.6.163 — reconstrucción AlphaZero-MCTS

Parche incremental sobre el ZIP de línea de base `Sargon-NNUE - copia(5).zip`.
**No es una recuperación bit a bit del módulo v0.6.121 perdido.** Reimplementa su contrato conocido utilizando `AlphaZeroPlayer._expand/_simulation` existentes.

## Seguridad de los datos

- Nunca escribe ni altera `lc0_*`, `lc0_uci_*`, Stockfish, Classic ni resultado.
- Añade solamente columnas `az_mcts_*` a `positions`.
- Calcula una partida completa antes de escribir sus resultados en una transacción SQLite.
- Si una partida falla, se conserva la última transacción completada y la partida fallida queda sin modificar. No usar `--overwrite` implícito.
- Si un registro ya tiene etiqueta de otra configuración, **aborta**: no mezcla versiones ni redes.
- Las etiquetas terminales son resultados exactos de posición; no MCTS.
- MCTS usa 128 simulaciones por defecto, `cpuct=1.5`, sin tiempo límite si `-TmaxMs 0`.
- `q_white` corresponde al Q de la jugada raíz **más visitada**, convertido a perspectiva blanca. `az_mcts_value=(1+q_white)/2`.
- El módulo no modifica archivos bajo `data` salvo la base `.pb` indicada explícitamente al ejecutar el etiquetado (backup recomendado).

## PowerShell

```powershell
.\scripts\sargon_az_mcts_valor.ps1 -Python C:\Users\pedro\ufasta\Scripts\python.exe -InputPb .\data\pb\lex_sample.pb -Weights .\data\lczero\model.pb.gz -Backend onnx-dml -BackendOptions 'gpu=0' -History allow-incomplete -Simulations 128 -Cpuct 1.5 -TmaxMs 0
```

## Entrenamiento

Se agrega `--weight-mcts` (predeterminado 0.0) y `-WeightMcts` en `run_pipeline_train.ps1`. Los cinco factores Classic/Stockfish/Result/LC0/MCTS deben sumar exactamente 1.0 con tolerancia 1e-9. El entrenador valida que **todas** las posiciones tengan etiquetas coherentes, con un mismo identificador de configuración, antes de generar checkpoints. El peso MCTS 0 conserva el comportamiento anterior.

Ejemplo: `-WeightClassic 0.15 -WeightStockfish 0.05 -WeightResult 0.60 -WeightLc0 0.10 -WeightMcts 0.10`.

Limitación: no se realizó una prueba funcional física de LC0; la suite local puede probar parser y validación sin una red de pesos real. Respaldar primero el `.pb`.
