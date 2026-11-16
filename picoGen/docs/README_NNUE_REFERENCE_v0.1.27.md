# picoGenus NNUE v0.1.27 — contrato de referencia `train.py`

**Fuente normativa:** archivo `train(2).py` suministrado por el usuario, sin reinterpretaciones genéticas.

## Algoritmo, representación y escalas

- Entradas: 768 (12 pieza/color × 64 casillas), 16 neuronas ocultas, salida única, 12321 parámetros.
- Ponderaciones `int16` durante evolución y al publicar la red; comienzo aleatorio uniforme entero de -15 a +15.
- `hidden=clip(sum(w1[indices])+b1,0,127)`; salida `hidden @ w2+b2` **sin divisor 256**.
- `fitness=-mean((predicciones_cp-etiquetas_cp)**2)`, `RMSE=sqrt(-fitness)` en cp.
- Cinco élites copiadas, selección uniforme de padres entre los 20 mejores (o todos si la población tiene menos de 20), cruce de **un punto** en índice [0,12321), mutación por peso de probabilidad 0.03, delta entero uniforme [-6,+6], límites [-127,+127], y conversión a `int16`.
- Únicas diferencias autorizadas respecto de `train.py`: lectura SQLite, partición train/validation, contadores, puntos de control, publicación y persistencia. `numpy.default_rng` en lugar del generador global permite reanudar de manera determinista; la distribución y las operaciones se conservan, pero las secuencias de números aleatorios no son idénticas para la misma semilla.

## Etiquetas y validación

- Solo se usan filas de `positions` con `teacher_cp` y `teacher_at` y `teacher_mate IS NULL`, igual que en `trainNNUE.py`.
- Stockfish guarda `teacher_cp` con respecto al bando que mueve. Para una posición con `b` en FEN, el signo se invierte una vez, produciendo etiquetas desde las blancas. No se consulta Stockfish.
- Partición reproducible indicada con `--validation_sample` (20 %). No se seleccionan padres por validación. Una partición por registro no evita posiciones muy similares de una misma partida entre ambos conjuntos.
- Checkpoint JSON por generación: **todos los cromosomas int16 comprimidos**, fitness, MSE, RMSE, selección `best`, estado RNG, métricas de validación, distribución cp de predicciones y etiquetas, saturación en 0/127, diversidad genética (porcentaje de genes polimórficos y desviación estándar media), cambios genéticos efectivos respecto del cruzamiento anterior, RMSE inicial. La mejor red global se guarda por separado y se publica con `.active.json`.
- El checkpoint formato v4 no admite `--resume` desde v3 porque se modificó el algoritmo, dtype y escala. Los modelos `int8` previos siguen siendo interpretados con divisor 256 solo para inferencia histórica. Nurse y `genAudit.py` aceptan ambos tipos.

## Definición de métricas

- `best`: RMSE del mejor individuo de la generación.
- `mean`: promedio de los RMSE individuales (no RMSE de un modelo promedio).
- `global`: RMSE del mejor individuo de entrenamiento de todas las generaciones.
- `val_mse`, `val_rmse`: error sobre el conjunto disjunto de validación de ese **mejor global**.
- `diversity`: porcentaje de genes con más de un valor en la población.
- `mutated`: cantidad de pesos que cambiaron realmente durante las mutaciones generadoras de la población; no cuenta diferencias debidas al cruzamiento.
- `sat0`, `sat127`: porcentaje de activaciones ocultas exactamente 0 y 127 para la mejor red global en entrenamiento.
- Distribuciones: mínimo, percentiles 5/50/95, máximo, promedio y desviación estándar de evaluación predicha y etiqueta Stockfish (en `global_best_train_metrics` y `global_best_validation_metrics`).
- `initial_metrics` registra el mejor y el promedio RMSE de la **población inicial** antes de seleccionar o reproducir, para comparar mejoras posteriores.

## Comando

```powershell
python .\genNNUE.py --in "C:\ruta\muestras.pb" --out "C:\ruta\genus_nnue.npy" --poblacion 80 --generaciones 500 --seed 42 --validation_sample 20
```

## Límites explícitos

1. Con 768 entradas se omiten el turno, el enroque y la casilla de captura al paso. No se modifica esta representación porque es la del ejemplo original.
2. El `int16` de los nuevos archivos no debe reinterpretarse como `int8`; `active.json` indica su formato.
3. Los parámetros de la red no implican capacidad de generalización: se evalúa por separado el RMSE de validación.
4. `genAudit.py` mantiene su auditoría histórica de movimientos de EPD, que **no** mide por sí sola precisión de un evaluador estático; se adapta solamente la carga de NNUE.
