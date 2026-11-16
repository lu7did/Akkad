# picoGenus PST v0.1.32 — métricas numéricas exclusivas

* Elimina la función `move_agreement` y cualquier enumeración de movimientos para telemetría.
* Mantiene la función objetivo original de PST: MSE en centipeones de Stockfish, perspectiva blanca, exclusivamente en conjunto de entrenamiento.
* Reporta `train_rmse`, `train_mean_rmse`, `global_train_rmse`, `validation_rmse`, `validation_mse`, tamaños de ambos subconjuntos.
* Comparte `gen_dataset_split.py` con `genNNUE.py`, selección determinista por seed y separación de partidas por `game_id`.
* La validación es exclusivamente observacional; no interviene en la selección genética.
* V3 de checkpoints PST preservado, pues no cambian los operadores ni la partición de v0.1.31. Los checkpoints anteriores a v3 no son compatibles.
* El indicador de progreso `min/avg` corresponde a RMSE del conjunto de ENTRENAMIENTO; la validación se calcula al completar cada generación.
* La línea de inicio debe decir `genPST.py v0.1.32` y `split=picogenus-shared-game-split-v1`. Si no aparecen, se está ejecutando otro archivo/versión.
