# picoAlpha — cadena de entrenamiento v0.1.1

## Contrato de datos

Se usa **SQLite 3 con extensión `.pb`**, **no** un formato binario PyBase ni Protocol Buffers. Los documentos aportados no especifican la estructura de un formato `pybase`; se optó por un almacén reproducible, relacional, con transacciones, integridad referencial y soporte de actualizaciones. Si `.pb` debía ser un formato propietario, será necesaria su especificación antes de declarar interoperabilidad.

- `games(id, source_file, source_ordinal, headers_json, result, start_fen, imported_at)`; la pareja archivo absoluto + ordinal evita duplicar partidas al volver a cargar un archivo. Partidas de archivos distintos se acumulan incluso con los mismos movimientos.
- `positions(id, game_id, ply, fen, played_uci, teacher_uci, teacher_cp, teacher_mate, teacher_value, teacher_depth, teacher_at)`.
- Cada fila de `positions` representa el tablero **antes** de la jugada `played_uci`; los índices `ply` están ordenados en la partida.
- Los FEN incluyen campo en passant original (`en_passant='fen'`) en vez de ocultarlo: es imprescindible para reconstruir el estado completo.
- `teacher.py` **sobrescribe** las etiquetas anteriores. Conserva la historia PGN, la partida y la jugada original. Reintentos tras interrupción recalculan todas las posiciones.
- `sampler.py` recrea desde cero el destino, copia partidas completas con todas sus etiquetas y admite `--seed` para reproducibilidad.

## Arquitectura

La especificación consolidada usa **780 entradas**: 768 para piezas/casillas relativas al turno, cuatro derechos de enroque (propios y rivales), ocho columnas de en passant. El reloj de 50 jugadas y la repetición se gestionarán con reglas del motor MCTS; no están codificados en los pesos. El flujo es `EmbeddingBag(780,16,sum) → ReLU → value(16,1,tanh), from(16,64), to(16,64)`; son **14.544 parámetros**, ~14.2 KiB en INT8 sin incluir metadatos y código.

La política es **factorizada**: un movimiento legal recibe puntaje `from_logits[src]+to_logits[dst]`; MCTS debe aplicar softmax exclusivamente sobre jugadas legales. **Límite conocido:** no se distingue entre promociones al mismo origen/destino que eligen distinta pieza; antes de integrar el motor se debe definir un tratamiento explícito para promociones. No se sustituyó el objetivo de Stockfish por la jugada humana del PGN.

El valor está expresado desde el punto de vista del jugador activo, mediante `tanh(centipawns/400)`; mate favorable = +1, desfavorable = -1. Para posiciones terminales sin política válida, `teacher_uci` es nulo y se excluyen de entrenamiento (conservadas en DB).

## Uso rápido (PowerShell)

Desde `picoAlpha/tools/train`:

```powershell
python -m pip install -r requirements.txt
.\run_create.ps1 --help
.\run_create.ps1 --out ..\..\data\train.pb
.\run_loader.ps1 --in 'C:\PGNs\c*.pgn' --out ..\..\data\train.pb
.\run_sampler.ps1 --in ..\..\data\train.pb --out ..\..\data\sample.pb --sample 20 --seed 42
.\run_teacher.ps1 --in ..\..\data\sample.pb --engine 'C:\chess\stockfish.exe' --depth 10
.\run_train.ps1 --in ..\..\data\sample.pb --out ..\..\assets\checkpoints --epoch 20 --validate 20 --method AdamW --lr 0.005 --lr_min 0.0001
.\run_export.ps1 --in ..\..\assets\checkpoints\best.pt --out ..\..\assets\picoalpha_nnue_weights.hpp
```

Cada `run_*.ps1` tiene un bloque editable `$Defaults` y acepta opciones de la implementación Python. `--help` exhibe la ayuda Python y los valores predeterminados del wrapper. Las rutas relativas de entrada/salida se resuelven con respecto a `tools/train` desde PowerShell.

`loader.py` recibe glob de archivos (`*.pgn`, `c*.pgn`), no una expresión regular de sintaxis Python. Las barras de progreso usan una línea actualizada con retorno de carro (`\r`), con texto de ancho limitado.

## Entrenamiento y evaluación

Se cargan **solo posiciones con etiqueta de valor y movimiento maestro válidos**. Se barajan, se aparta la proporción `--validate` de **posiciones** solicitada y se entrena con mini-batches. La función objetivo es `cross_entropy(from)+cross_entropy(to)+value_weight*MSE(value)` (por defecto value_weight=2). Se calculan individualmente CE de política, MSE de valor y loss combinado en entrenamiento y validación. `--lr` se reduce por coseno hasta `--lr_min` a lo largo de las épocas. Se guarda un `.pt` por época, `best.pt` (menor pérdida total de validación), `best.json` y `history.json`.

**Precaución metodológica:** posiciones de la misma partida pueden quedar en entrenamiento y validación, porque se solicitó el *shuffle* por movimientos. Esto puede producir fuga de información y un error de validación optimista. Para medir generalización real habrá que agregar un split por partida y por posición repetida. `--validate 0` usa la pérdida de entrenamiento como criterio de checkpoint best; no constituye validación.

## INT8 y Flash

`export.py` carga el checkpoint, cuantiza **cada matriz** de forma simétrica a int8 en [-127,127] y emite arrays C++ `static const int8_t` y sus `constexpr float ..._SCALE`. Los arrays no se copian a RAM por construcción del header; para garantizar Flash en RP2350 será necesario verificar el archivo `.map` y el enlazado final. El entrenamiento en PyTorch usa FP32; esto es **cuantización posterior al entrenamiento (PTQ)**, no entrenamiento cuantizado (QAT). Comprobar precisión de la red cuantizada contra FP32 antes de medir fuerza ajedrecística.

**Sin motor aún:** este parche implementa la cadena de datos/entrenamiento/exportación, no el ejecutable C++ ni un MCTS. No se consultaron servicios, repositorios ni documentación externos, y no se utilizaron los archivos de `picoAlpha/Crypt`.
