# Sargon-NNUE v0.6.30 — MSE con pesos congelados

Base: v0.6.29. Archivo modificado: `src/sargon_nnue/sargon_train.py`.

- Durante entrenamiento informa MSE online acumulado (pesos cambiantes).
- Al finalizar las actualizaciones del epoch, recorre **todas** las posiciones de entrenamiento sin actualizar parámetros y calcula `train_mse_frozen` con los pesos finales.
- Durante validación muestra el MSE de validación progresivo y el MSE fijo de entrenamiento como referencia constante.
- Checkpoints registran `train_mse_online`, `train_mse_frozen`, `val_mse`. El resumen usa el MSE fijo como MSE principal de entrenamiento.
- Se incluye el recorrido adicional de evaluación dentro de la duración reportada por epoch; esta lectura añade tiempo deliberadamente.
- Sin cambios a las etiquetas, partición, optimizador, modelo ni formato PB.
