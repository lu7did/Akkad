# v0.6.39 — corrección `--quick` de validación
- `torch_train.py`: validación siempre usa el mismo objetivo `(1-z2)*R+z2*S` que entrenamiento.
- El modo `--quick` deja de imponer etiquetas PGN en validación.
- Comprobación WDL en ambas particiones cuando `weight_stockfish > 0`.
- Modo normal, partición, optimizadores y checkpoints sin cambios.
- Nota: v0.6.34 ya evaluaba la validación con el objetivo híbrido. No reinterpretar su log como MSE PGN.
