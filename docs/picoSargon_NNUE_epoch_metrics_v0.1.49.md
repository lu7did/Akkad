# picoSargon — Ciclo de entrenamiento FP32/INT6 y aislamiento de referencia (v0.1.49)

## Contrato

Cada epoch (FP32 o QAT) ejecuta, en orden:

1. **TRAIN**: usa únicamente el conjunto de entrenamiento; actualiza parámetros maestros FP32 y registra el MSE(value) observado *mientras cambian* los pesos. Durante QAT, el forward de entrenamiento usa cuantización simulada.
2. **VERIFY**: recorre de nuevo **todas las posiciones de TRAIN**, con parámetros congelados; mide tanto el forward FP32 continuo como el evaluador entero INT6 exacto.
3. **VALID**: recorre **solo las posiciones reservadas** y mide FP32 e INT6, también con parámetros congelados. Ninguna posición validada participa en actualización de gradientes. Si `--validation 0`, no existe VALID; el checkpoint se selecciona según VERIFY.

`MSE(value) = mean((tanh(cp_pred/400) - tanh(cp_Stockfish/400))**2)`; es el mismo criterio de MSE de etiquetas normalizadas empleado por picoAlpha. La evaluación del modelo y el objetivo de Stockfish se convierten ambos a perspectiva de blancas. Menor MSE = mejor. La selección de `best_fp32.pt` utiliza la columna FP32; la de `best_quant.pt` utiliza la columna INT6 exacta. `TRAIN` y `VERIFY` no son comparables como si fueran corridas idénticas: el primero mide pesos que se actualizan durante el recorrido, el segundo mide los pesos finales.

## Referencia `grumpy.bin`

**Exclusivamente en Audit.py**: se pasa como `--bin` desde `run_genesis.ps1 -referenceBin ...`, nunca como inicialización ni línea base de TRAIN/VERIFY/VALID. Se eliminó el argumento `--init` del encadenamiento; `train.py --init` ahora falla explícitamente para evitar usos inadvertidos. La inicialización de pesos maestros FP32 es aleatoria reproducible con `--seed`, por lo que las curvas de aprendizaje **no serán idénticas** a las de v0.1.48, que comenzaban con los coeficientes originales de Grumpy. `grumpy.bin` permanece sin modificar.

La salida visible por epoch tiene tres etapas de progreso (`TRAIN`, `VERIFY`, `VALID`) y una única tabla de dos columnas (FP32, INT6). En `TRAIN` la columna INT6 se deja vacía porque durante la actualización no hay un único modelo congelado. Se siguen registrando ambos MSE y los detalles en `picoSargon/data/<network>_history.json`.

## Archivos incluidos

`picoSargon/tools/train/train.py`, `picoSargon/tools/train/run_genesis.ps1`, `picoSargon/tools/train/test_epoch_reporting.py`, `docs/picoSargon_NNUE_epoch_metrics_v0.1.49.md`.
