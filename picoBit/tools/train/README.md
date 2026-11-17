# picoBit – cadena autónoma de entrenamiento BNN (v0.1.2)

Base: commit `e64cd7d4951c35413c0891f88e5f5adaf061f33b` de `lu7did/Akkad`. La implementación **no importa código de picoAlpha**. Únicamente lee el esquema de datos SQLite `.pb` que genera `teacher.py` (`positions.id`, `fen`, `teacher_cp`, `teacher_mate`, `teacher_at`). `.pb` **no** es Protocol Buffers.

## Dependencias

```shell
python -m pip install -r picoBit/tools/train/requirements.txt
```

## 1. Entrenar

```shell
python picoBit/tools/train/train.py --in picoAlpha/data/history.pb --sample 10000 --validation 20 --epoch 50 --lr 0.0001 --lrmin 0.000001 --checkpoints picoBit/assets/checkpoint
```

`--batch 128` y `--seed 42` son configurables. La muestra es uniforme **sin reemplazo** sobre registros etiquetados válidos. `--validation` admite 1..100, siempre que el redondeo deje al menos un elemento de entrenamiento y otro de validación (100% no satisface esta condición y se rechaza explícitamente). El split se mantiene fijo durante todos los epochs; no se reutilizan los ejemplos de validación para actualizar pesos.

La arquitectura es la de `kerasTrain2.py`: convolución binaria de 64 filtros 3×3 con entradas continuas, BN, convolución binaria 64 filtros 3×3 con activaciones binarizadas, BN, residual, Flatten, Dense binaria 256, BN, salida Dense(1) sigmoid. Pesos binarios por signo escalados por media absoluta, STE, acotamiento [-1,1]; Adam + binary crossentropy. Learning rate lineal por epoch desde `--lr` hasta `--lrmin` (si hay un solo epoch se usa `--lr`). La conversión Stockfish sigue `cp_to_prob = 1/(1+10^(-cp/400))` con `cp` acotado a ±1500.

**Convención de signos:** `teacher_cp` y `teacher_mate` están desde la perspectiva del turno de juego, mientras la cabeza de la BNN y CLASSIC son desde la perspectiva de **blancas**. Se invierte el signo para las posiciones con turno de negras. Los mates son ±1500 cp para la etiqueta de aprendizaje. Los registros etiquetados sin CP ni mate solo se admiten cuando el tablero es terminal y se infiere empate (0) o mate (-1500 desde el bando al turno).

**Métricas:** Train y Verify y Validation presentan `MSEmin` y `MSEavg` como **errores al cuadrado de la probabilidad [0,1]** respecto de la transformación de Stockfish. Train mide predicciones antes de cada actualización; Verify y Validation ejecutan inferencia congelada después de completar el epoch. Para TTY las barras de progreso se redibujan sobre la misma línea; salida redirigida entrega una sola línea final por etapa.

Archivos generados: `picoBit/assets/checkpoint/YYYYMMDD-HHMMSS/epoch_NNNN.bnn` y `history.json`, `validation_manifest.json`; `picoBit/assets/best.bnn`, `best_metadata.json`, `validation_manifest.json`. El mejor modelo se elige **únicamente** por menor MSE promedio de validación. Los `.bnn` son paquetes Keras nativos (`.keras`/ZIP) renombrados; conservan arquitectura y pesos, pero **no** son bitstreams de inferencia C++.

## 2. Exportar

```shell
python picoBit/tools/train/export.py --in picoBit/assets/best.bnn --checkpoints picoBit/assets/checkpoint/export
```

Crea `best.h` con datos `inline constexpr` para ubicar en FLASH: los signos binarios empaquetados LSB-first (1 equivale a +1), `alpha` FP32, BN gamma/beta/media/varianza/epsilon y última capa Dense FP32. El orden de pesos es TensorFlow, C-order. **No se crea ni modifica el evaluador C++**, que deberá implementar la inferencia, el padding, el residual y las operaciones usando exactamente este formato antes de utilizar el header.

## 3. Auditar

```shell
python picoBit/tools/train/Audit.py --in picoAlpha/data/history.pb --weights picoBit/assets/best.bnn --out picoBit/assets/audit
python picoBit/tools/train/Audit.py --in picoAlpha/data/history.pb --weights picoBit/assets/best.bnn --bin viejo.bnn --out picoBit/assets/audit
```

Opcional: `--manifest RUTA` cuando no se encuentre `validation_manifest.json` junto a `--weights`. El auditor **no vuelve a sortear posiciones**: lee exclusivamente los IDs de validación del manifiesto y rechaza un split solapado, ID faltante o ruta de database distinta. Genera `audit_validation.json` (una entrada por FEN) y `audit_summary.json` (resumen). La métrica de auditoría es MSE de **centipeones al cuadrado** y también RMSE/MAE expresados en centipeones. CLASSIC reproduce la heurística del archivo `Sargon-NNUE/src/sargon_nnue/evaluators/classic.py` v0.6.153, sin dependencia de dicho módulo.

## Alcance y compatibilidad

La extensión `.bnn` evita su confusión con la red `.keras` actualmente esperada por `picoBit/src/bnn.py` (que **no se modifica** en este parche). Para utilizar `best.bnn` con el evaluador existente será necesario un requerimiento específico de integración. Los archivos generados en tiempo de ejecución no se incluyen en el parche. No se invoca Stockfish durante el entrenamiento o la auditoría: se consumen exclusivamente sus etiquetas en `.pb`.
