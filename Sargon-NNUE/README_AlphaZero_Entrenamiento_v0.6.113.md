# Parche experimental AlphaZero P,V para Sargon-NNUE — v0.6.113

**Alcance:** exclusivamente preparación de datos y entrenamiento de la red inicial y posteriores refinamientos. No contiene todavía player MCTS, evaluador MCTS ni generador automático de self-play. No se modifica ningún archivo Python ni script PowerShell preexistente.

## Aplicación segura

1. Hacer copia de seguridad de Sargon-NNUE y de los `.pb` / `.npz` / checkpoints existentes.
2. Descomprimir `Sargon_NNUE_AlphaZero_Train_v0.6.113_patch.zip` en la **raíz del proyecto** (donde están `src/` y `scripts/`). El parche contiene únicamente archivos nuevos.
3. Usar Python del entorno `ufasta` con `chess==1.11.2`, `numpy` y `torch` instalados. Los lanzadores PowerShell eligen `C:\Users\pedro\ufasta\Scripts\python.exe` si está disponible.
4. Ejecutar `python -m pytest tests/test_az_experiment_v06113.py` desde la raíz, con `PYTHONPATH=src` configurado, como prueba de humo local.
5. **No** ejecutar `--resample` legado sobre un `.pb` AlphaZero: el resampler original desconoce las tablas `az_*`. En ningún momento el parche llama a ese resampler.

Para revertir: borrar exclusivamente los archivos nuevos enumerados en `MANIFEST_v0.6.113.txt`. Los archivos originales son idénticos; las bases creadas por el modo AZ están separadas.

## Enfoque

- La base histórica `.pb` se **lee solamente**, nunca se altera. Se usa como fuente de supervisión inicial.
- La red nueva es siempre `sargon-az-782-128-64-p4672-v1`: entrada NNUE actual de 781 bits más `halfmove/100`, tronco 128/64, salida de política de 4672 índices y valor `tanh` en [-1,1]. Su codificación de acciones es absoluta, con direcciones queen-like, saltos de caballo y 9 planes de promociones menores; se enmascaran las jugadas ilegales.
- La entrada de Sargon-NNUE mantiene su **limitación histórica**: los 781 bits y halfmove no identifican toda la historia de repeticiones; la red no observa repetición completa. `state_fen` y la secuencia de movimientos preservan información para una ampliación futura si fuera necesaria.
- Bootstrap: se reconstruyen posiciones consecutivas **después de cada jugada**, se busca la transición legal única y se imita la jugada histórica para `P`. Para `V`, se utiliza la etiqueta de la **posición anterior** (Stockfish WDL, CLASSIC sigmoide, resultado de partida o mezcla). Las primeras jugadas se omiten porque la base no guarda etiqueta de valor del estado inicial.
- Refinamiento: `P` procede de las visitas MCTS de la raíz; `V` del resultado final (+1/0/-1 desde quien juega). No consulta evaluadores externos. **La retropropagación del entrenamiento es distinta del backup estadístico realizado previamente por MCTS.**
- Validación aislada por partida, MSE de valor, entropía cruzada de política, exactitud top-1, pérdida ponderada y checkpoints por epoch. Se conserva `az_best.pt`, y todos los checkpoints anteriores permanecen en sus propios directorios.
- El trainer lee los datos con muestras reservoir limitadas (`--max-samples`, `--max-validation`) y fracción `--sample-pct`, para no cargar bases inmensas enteras en memoria. La extracción desde la base sigue teniendo costo de escaneo y reconstrucción.

## Función 1: crear la semilla desde la base histórica

```powershell
.\scripts\sargon_az_train_seed.ps1 `
  --input "data\historical.pb" `
  --outdir "data\az\seed_v001" `
  --weight-stockfish 1 --weight-classic 0 --weight-result 0 `
  --epochs 10 --validation 10 --batch-size 64 --device xpu
```

Si la base tiene `classic_cp`, ejemplo de mezcla de escala compatible:

```powershell
.\scripts\sargon_az_train_seed.ps1 --input "data\historical.pb" `
  --outdir "data\az\seed_mix" --weight-stockfish 0.6 `
  --weight-classic 0.3 --weight-result 0.1 --epochs 10 --device xpu
```

`stockfish_value` se interpreta desde blancas en [0,1]; si es NULL, se permite `w,d,l` **solo si** `wdl_source` es `STOCKFISH` o `TERMINAL`. `classic_cp` se convierte mediante `sigmoid(cp/400)`. La etiqueta de resultado usa `games.result/2` por defecto; `--result-smoothed` solicita `result_value` cuando está presente. Las fuentes seleccionadas faltantes provocan error explícito. El valor supervisado se convierte a [-1,1] desde el jugador al turno.

**Importante:** la política inicial imita la jugada registrada en el PGN. No la confunda con una distribución MultiPV de Stockfish ni con una política MCTS. Es una semilla barata y deliberadamente imperfecta.

## Función 2: inicializar una nueva base AlphaZero

```powershell
.\scripts\sargon_az_prepare_init.ps1 --out "data\az\generation_001.pb"
```

Crea el mismo núcleo de tablas `meta`, `games`, `positions` de Sargon más `az_games` y `az_samples`; nunca sobrescribe una base existente. Las tablas añadidas guardan los estados previos a jugar, jugadas legales, visitas de raíz, total de simulaciones, resultado final y procedencia de generación.

## Función 3: importar partidas completas del futuro player MCTS

```powershell
.\scripts\sargon_az_prepare_import.ps1 `
  --input "data\az\generation_001_games.jsonl" `
  --out "data\az\generation_001.pb"
```

**Contrato JSONL de entrada** (una partida completa por línea, codificación UTF-8):

```json
{"id":"generation-001-game-0001","generation":1,"start_fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","result":"1/2-1/2","moves":[{"uci":"e2e4","visits":{"e2e4":57,"d2d4":31,"g1f3":12},"simulations":100},{"uci":"e7e5","visits":{"e7e5":78,"c7c5":22},"simulations":100}]}
```

El ejemplo de arriba es **esquemático**: contiene solo dos jugadas, por lo que el resultado de empate presupone adjudicación externa; no es una partida finalizada por reglas normales. Para uso real se exige un resultado definitivo y una lista válida de jugadas. El jugador MCTS deberá conservar visitas de raíz **antes de ejecutar** cada movimiento. La suma de visitas puede ser inferior al número declarado de simulaciones (por la expansión inicial), y `P` se normaliza sobre la suma de visitas de aristas.

Se valida legalidad de jugadas y de todas las alternativas con visitas. El archivo JSONL se importa transaccionalmente: una línea errónea cancela todas las importaciones de esa ejecución. No se modifica ningún `.pb` histórico.

## Función 4: asociar el resultado a cada posición MCTS

```powershell
.\scripts\sargon_az_prepare_finalize.ps1 --input "data\az\generation_001.pb"
```

Completa `value_target` de cada estado anterior a jugar, usando el resultado de la partida desde la perspectiva de su turno. Marca la partida como `finalized`; el trainer rechaza partidas pendientes. No reanaliza ni evalúa con otro motor.

## Función 5: refinamiento desde checkpoint anterior

```powershell
.\scripts\sargon_az_train_refine.ps1 `
  --input "data\az\generation_001.pb" `
  --network "data\az\seed_v001\az_best.pt" `
  --outdir "data\az\generation_001_network" `
  --epochs 10 --validation 10 --batch-size 64 --device xpu
```

También se admite `--random-init` **en lugar de** `--network`, para ensayos de control. Un checkpoint inexistente, incompatible o corrupto es un error. El directorio de salida debe ser nuevo o vacío, y no puede ser el directorio del checkpoint de entrada. No se sobrescriben generaciones.

Cada directorio de entrenamiento incluye:

- `az_config.json` con parámetros, origen, cantidades de partidas y muestras;
- `az_metrics.csv` por epoch (MSE_V, CE_P, top1, loss);
- `az_epoch_NNN.pt` por epoch y `az_best.pt` según pérdida de validación;
- cada checkpoint incluye pesos de P/V y estados del optimizador/scheduler para auditoría (refine carga pesos, no reanuda automáticamente el estado del optimizador).

## Seguridad y límites

- **Ninguno de los archivos originales** `sargon_prepare.py`, `sargon_train.py`, `pb_data.py`, `torch_train.py`, `scripts/sargon_prepare.ps1`, `scripts/sargon_train.ps1`, ni otros, se reemplaza. La integración se realiza a través del paquete `sargon_nnue` y cinco scripts nuevos, independientes.
- No se implementa player/evaluador AlphaZero en este parche; importar datos presupone que el futuro player exporte JSONL con el contrato anterior.
- No hay prueba aún de convergencia ni de mejor calidad de juego. Los MSE y CE son indicadores de imitación/generalización a partidas retenidas, no de fuerza Elo.
- La primera generación necesita al menos dos partidas diferentes para la separación de validación; la política inicial es comportamiento observado y puede aprender jugadas deficientes.
- La selección de ejemplos se hace una vez por corrida, no se generan muestras nuevas desde el motor en cada epoch. Un replay buffer multigeneración será decisión futura.
- No editar manualmente checkpoints ni bases durante su procesamiento.

## Pruebas

```powershell
$env:PYTHONPATH = "$PWD\src"
& "C:\Users\pedro\ufasta\Scripts\python.exe" -m pytest tests\test_az_experiment_v06113.py -q
```

Las pruebas incluidas cubren: codificación de acciones con promociones, reconstrucción histórica, creación/importación/finalización PB MCTS, creación de checkpoint, refinamiento desde él, prohibición de sobrescritura y conservación byte a byte de una base histórica. Las pruebas requieren python-chess y PyTorch instalados.
