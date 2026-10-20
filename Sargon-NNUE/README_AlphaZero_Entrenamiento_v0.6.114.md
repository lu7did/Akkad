# Sargon-NNUE — Parche AlphaZero experimental v0.6.114

## Alcance y compatibilidad

El parche **no sustituye ni modifica** los programas originales `sargon_prepare.py`, `sargon_train.py`, `pb_data.py`, `torch_train.py`, ni los scripts PowerShell existentes. La nueva modalidad de `sargon_train` es el módulo **independiente** `sargon_nnue.az_train`, invocado por `scripts/sargon_az_train_seed.ps1`. `sargon_nnue.az_prepare`, `sargon_nnue.az_policy` y `sargon_nnue.az_seed_train` son también módulos experimentales aislados.

Esta distribución **incluye los componentes de v0.6.113** para poder instalarse directamente sobre la línea de base sin el parche anterior, o actualizar sobre él. Al actualizar desde v0.6.113, **se reemplazan únicamente archivos experimentales** `az_*`, scripts `sargon_az_*` y pruebas AZ; no se sobrescribe código legado. No incluye aún jugador ni evaluador AlphaZero.

Los dos acuerdos de v0.6.114 son:

1. Política **P**: contar jugadas observadas desde posiciones idénticas y dividir cada conteo por el número de observaciones de esa posición, **sin** usar Stockfish, Sargon, resultado ni otras evaluaciones para ponderar las jugadas. Registrar todas las alternativas legales (conteo cero si no aparecen). Separar partidas de train y validación **antes** del agregado.
2. Valor **V**: extraer cada evaluación directamente desde `positions` y `games` de la base anotada, usando Stockfish, Sargon clásico, resultado (suavizado optativo) o mezcla normalizada; **no existe ninguna tabla nueva de valores**. Usar también los registros terminales válidos para V aunque carezcan de una etiqueta de política para la jugada posterior.

## Instalación

Descomprimir `Sargon_NNUE_AlphaZero_Train_v0.6.114_patch.zip` en la **raíz** de Sargon-NNUE (donde están `src` y `scripts`). Ejecutar en `ufasta` con PyTorch, NumPy y python-chess instalados. Los scripts individuales intentan `C:\Users\pedro\ufasta\Scripts\python.exe` y, si no existe, usan `python`.

La base original es **solo lectura**: por seguridad se crea una **copia nueva** `.pb` que contiene las mismas tablas históricas (sin alterar filas) más `az_policy_games`, `az_policy_positions`, `az_policy_moves` y dos claves nuevas en `meta`. Esto duplica físicamente la base para preservar el archivo original; **no duplica los valores en nuevas tablas**. Hace falta espacio libre suficiente para la copia y las frecuencias. Si ya se usó v0.6.113, no reutilizar un antiguo `.pb` de self-play para entrenar la semilla; se requiere la base histórica enriquecida por la nueva función.

### 1. Construir la política histórica (script individual nuevo)

```powershell
.\scripts\sargon_az_prepare_policy.ps1 `
  --input "data\historical.pb" `
  --out "data\az\historical_policy.pb" `
  --validation 10 --seed 42
```

**Qué almacena** (en `historical_policy.pb`):

- `az_policy_games(game_id, split)`: la asignación persistente de cada partida a `train` o `validation`.
- `az_policy_positions(id, split, features, halfmove, legal_actions, appearances)`: un registro por entrada NNUE única **dentro de cada partición**, con conjunto exacto de acciones legales y total de veces observada.
- `az_policy_moves(position_id, action, count)`: una fila para **cada jugada legal**, incluso si su cuenta es 0. La política objetivo se deriva en la lectura mediante `count/appearances`, sin guardar probabilidades redundantes.

Los estados se identifican por los 781 bits de Sargon y el halfmove. Los bits incluyen piezas, turno, enroque y posibilidad de captura al paso. La red **no representa el historial completo** para reclamación por repetición; los estados distintos solo en ese historial se agrupan si tienen la misma entrada neuronal. Como la base histórica contiene el tablero **después** de cada jugada, el primer movimiento de cada partida no se incluye en P cuando falta su posición anterior. Tampoco se produce un objetivo P para la última posición sin sucesora. Sin embargo, **ambas posiciones pueden producir objetivos V** cuando existen sus etiquetas históricas.

La generación de estadísticas aborta si hay transiciones ilegales/no reconstruibles, plies discontinuos, acciones inconsistentes o sumas de visitas diferentes a las apariciones. El original no se modifica, incluso si hay un error.

### 2. Entrenar la semilla P,V (script individual ya existente, actualizado)

```powershell
.\scripts\sargon_az_train_seed.ps1 `
  --input "data\az\historical_policy.pb" `
  --outdir "data\az\seed_v001" `
  --weight-stockfish 1 --weight-classic 0 --weight-result 0 `
  --validation 10 --seed 42 --epochs 10 --batch-size 64 --device xpu
```

La **semilla** inicializa una red nueva 781+1 → 128 → 64 con una cabeza de política de 4.672 logits (acciones ilegales enmascaradas) y una salida valor `tanh` en [-1,1]. En `bootstrap` el nuevo entrenador:

- Lee los ejemplos V **de `positions` JOIN `games` JOIN `az_policy_games`**, tomando **todas las posiciones elegibles** de cada conjunto; usa la perspectiva del jugador al turno y la normalización de fuentes existente en el parche experimental.
- Lee los ejemplos P **de `az_policy_positions` JOIN `az_policy_moves`**, transformando conteos exactos en distribuciones. Solo la frecuencia histórica define las probabilidades, **ninguna evaluación modifica P**.
- Entrena conjuntamente el tronco con dos batches (uno P y uno V) en cada paso, y computa dos pérdidas independientes: `MSE_V` y entropía cruzada `CE_P`. Si hay cantidades de batches distintas, el conjunto más pequeño se recorre cíclicamente durante un epoch; se indica porque puede repetir posiciones.
- `--policy-weighting frequency` (predeterminado) usa `appearances` como **peso estadístico de la posición** en la pérdida de P, equivalente a entrenar sobre observaciones individuales en el caso ideal. **No es ponderación por Stockfish**. `--policy-weighting uniform` da igual peso a cada posición distinta.
- Permite `--sample-pct` para seleccionar una fracción aleatoria de registros V y de posiciones P **solo de train**, y `--max-samples`, `--max-policy-samples`, `--max-validation` para acotar memoria. La validación queda separada y no se aplica `--sample-pct` sobre ella.

Para un ejemplo de combinación de fuentes V, exclusivamente:

```powershell
.\scripts\sargon_az_train_seed.ps1 --input "data\az\historical_policy.pb" `
  --outdir "data\az\seed_mix" `
  --weight-stockfish 0.6 --weight-classic 0.3 --weight-result 0.1 `
  --validation 10 --seed 42 --epochs 10 --device xpu
```

Las ponderaciones de valor no negativas deben sumar 1. `stockfish_value` o WDL Stockfish blanco [0,1]; `classic_cp` se transforma por sigmoide; resultado real `games.result/2` o `result_value` con `--result-smoothed`. Las etiquetas seleccionadas que falten provocan error claro, no se rellenan silenciosamente.

### ¿Cómo funciona la validación?

La reserva del porcentaje se realiza por **partidas completas**, **antes** de contar políticas. Por ejemplo, para 1.000 partidas y `--validation 10`, se separan 100 partidas completas (aproximadamente; se redondea según cantidad), y ningún registro de esas partidas forma parte del entrenamiento. Desde entonces:

- `train P`: únicamente frecuencias de jugadas tomadas de partidas `train`.
- `validation P`: frecuencias **calculadas separadamente** de partidas reservadas `validation`. El error CE y `top1` se miden contra esa distribución de validación.
- `train V`: evaluaciones de `positions` pertenecientes a partidas `train`.
- `validation V`: evaluaciones de `positions` pertenecientes a partidas `validation`; su MSE se calcula con la red congelada al terminar cada epoch.

Para una posición `s` reservada, `CE_P = -Σ_a π_val(a|s) log P_θ(a|s)`; para la misma partición, `MSE_V = promedio (V_θ(s_i)-v_i)^2`. La CE de política se pondera por apariciones salvo `--policy-weighting uniform`; el MSE de valor promedia todas las evaluaciones seleccionadas. `validation_loss = policy_weight*CE_P + value_weight*MSE_V` selecciona `az_best.pt` y controla el scheduler/early-stopping. `az_metrics.csv` contiene las métricas independientes y la pérdida conjunta.

**Precisión:** la misma posición puede aparecer en partidas distintas de train y validación; esto no filtra observaciones reservadas al entrenamiento, pero puede facilitar la predicción de posiciones frecuentes. `az_config.json` informa el número de entradas de P compartidas entre ambas particiones muestreadas. Para medir generalización a posiciones nunca vistas sería necesario otro ensayo adicional con partición por posición o apertura; **no se ha implementado ni se promete aquí**.

El **mismo `--seed` y `--validation`** usado al crear las tablas debe usarse al entrenar; el entrenador rechaza discrepancias para no producir validaciones engañosas.

### 3. Entrenamiento posterior con visitas MCTS (sin cambios en el contrato v0.6.113)

Este parche incluye las funciones y scripts separados:

```powershell
.\scripts\sargon_az_prepare_init.ps1 --out "data\az\generation_001.pb"
.\scripts\sargon_az_prepare_import.ps1 --input "data\az\generation_001_games.jsonl" --out "data\az\generation_001.pb"
.\scripts\sargon_az_prepare_finalize.ps1 --input "data\az\generation_001.pb"
.\scripts\sargon_az_train_refine.ps1 --input "data\az\generation_001.pb" `
  --network "data\az\seed_v001\az_best.pt" `
  --outdir "data\az\generation_001_network" --epochs 10 --device xpu
```

Refinamiento: P viene de las visitas MCTS; V del resultado real de la partida. Los checkpoints de entrada y las épocas anteriores se preservan. Aún no incluye el player/evaluador MCTS ni un generador automático de esas partidas; `import` espera un JSONL compatible con la especificación documentada para v0.6.113. Se rechazan checkpoints ausentes, corruptos o incompatibles.

### 4. Pruebas y reversión

```powershell
$env:PYTHONPATH = "$PWD\src"
& "C:\Users\pedro\ufasta\Scripts\python.exe" -m pytest `
  tests\test_az_experiment_v06113.py tests\test_az_policy_v06114.py -q
```

Revertir: eliminar **solo** los archivos enumerados en el manifiesto experimental, sin tocar código legado ni sus bases originales. Las bases `historical_policy.pb` generadas por el parche son archivos nuevos independientes, por lo que también pueden archivarse/borrarse separadamente.

**Verificación efectuada al distribuir:** análisis de sintaxis Python, un entrenamiento real PyTorch CPU sobre una base SQLite sintética con P/V almacenados independientemente, comprobación sintética de agregación de frecuencias y conservación byte a byte de la base de origen. Las pruebas integradas con movimientos de ajedrez reales requieren `python-chess` y deben ejecutarse en `ufasta`; no fue posible ejecutarlas en el entorno de construcción. No se afirma convergencia ni mejora de Elo.
