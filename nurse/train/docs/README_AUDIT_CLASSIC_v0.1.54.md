# Nurse — Auditoría de NPZ, CLASSIC y Stockfish (v0.1.54)

La auditoría usa **la implementación existente de Nurse** en `nurse/src/nurse/_legacy/evaluators/classic.py` (`ClassicEvaluator`). No reconstruye la heurística histórica Sargon III ni añade un evaluador alternativo. Ambos modelos devuelven centipeones desde la perspectiva de blancas, y se comparan contra la **misma etiqueta Stockfish**, en el mismo FEN y sin recomputar el teacher para datos SQLite.

## Auditoría del conjunto de validación original

Desde `akkad/nurse/train`:

```powershell
.\run_audit_validation.ps1
```

El script obtiene la ruta a la base desde `nurse/assets/split_manifest.json`, por lo que no requiere editar paths en `run_genesis.ps1`. Utiliza, por defecto, `nurse/assets/best.npz` y escribe `nurse/assets/audit_validation.json`. Puede usarse `-Npz`, `-Manifest`, `-In`, `-Out`, `-Assets` para alterar las rutas, o `-Split train` para auditar entrenamiento. `-Limit 0` significa todas las posiciones.

Equivalente directo:

```powershell
python .\audit.py --npz ..\assets\best.npz --in "RUTA\sample_history.pb" --manifest ..\assets\split_manifest.json --split validation --out ..\assets\audit_validation.json
```

Se exige coincidencia exacta con el conteo `validation_positions` del manifiesto (85.019 en la ejecución mostrada), salvo que se use `--limit`. La división está definida por IDs de **partidas**, no por posiciones: no se vuelve a sortear. **La base no contiene un archivo autónomo de 85.019 posiciones**: esas posiciones se leen del SQLite original. Si el manifiesto fue sobrescrito por otra ejecución, es posible que ya no corresponda al mismo entrenamiento.

## Métricas

- `normalized_mse`: MSE NPZ vs teacher, con la misma `sigmoid(clamp(raw,-15,15))` y `sigmoid(cp_white/400)` que utiliza `train.py`.
- `classic_normalized_mse`: MSE CLASSIC vs la misma etiqueta, usando `sigmoid(classic_cp/400)`.
- `normal_cp_mae`, `normal_cp_mse`, `normal_cp_rmse`: NPZ vs Stockfish, sin mates.
- `classic_cp_mae`, `classic_cp_mse`, `classic_cp_rmse`: CLASSIC vs Stockfish, sin mates.
- `npz_better_abs_cp`, `classic_better_abs_cp`, `tied_abs_cp`: comparación posición por posición, sin mates, por menor error absoluto contra Stockfish.
- `sign_correct` y `classic_sign_correct`: concordancia del signo de centipeones con la etiqueta (ceros indeterminados).

El campo `mate_positions` contabiliza los mates por separado: los puntajes sintéticos de mate ±100000 **nunca** se incluyen en estadísticas de centipeones. Sí quedan en los MSE normalizados con la misma saturación del entrenamiento. Los registros JSON incluyen `teacher_cp_white`, `npz_cp_white`, `classic_cp_white`, diferencias y pérdidas individuales; pueden ser voluminosos con 85.019 registros.

La auditoría EPD sigue evaluando la posición **posterior** a la jugada `bm`, con Stockfish externo (requiere `--stockfish`) y calcula las mismas comparaciones contra esa etiqueta nueva.

## Alcance de la validación

Se comprobó sintaxis Python y una prueba SQLite sintética que ejercita el manifiesto, comparaciones entre dos evaluadores y escritura JSON, pero no pudo ejecutarse con `python-chess`, el CLASSIC real ni la base de 85.019 posiciones en este entorno. Las pruebas sintéticas usan un CLASSIC simulado **solo dentro del test**; la implementación de producción importa obligatoriamente el evaluador real, y falla si no lo encuentra. No se modificaron ni `train.py`, ni `run_genesis.ps1`, ni rutas previamente personalizadas.
