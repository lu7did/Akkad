# Sargon-NNUE — benchmark de brains v0.6.131

## Objetivo

La nueva aplicación `sargon_benchmark.py` mide cuánto tarda en elegir **jugadas legales** cada perfil de `brains.json`, reutilizando **el listener STDIN/UCI y la implementación real del player**. No usa algoritmos simulados, no fuerza movimientos prefijados, no invoca un evaluador distinto del indicado en cada brain y no modifica ningún motor existente.

Compatible con las familias de player que acepta la instalación actual de Sargon-NNUE, por ejemplo Sargon-Plus, Sargon, Stockfish, Cerebrum, AlphaZero+LC0, LC0 monolítico, etc., sujeto a que sus dependencias y ejecutables estén disponibles.

## Instalación

Descomprimir el ZIP en la raíz del proyecto Sargon-NNUE, respetando las rutas:

- `src/sargon_nnue/sargon_benchmark.py`: aplicación principal.
- `scripts/sargon_benchmark.py`: lanzador Python.
- `scripts/sargon_benchmark.ps1`: lanzador PowerShell.

No se reemplaza `sargon_match.py`, `brains.py`, `sargon_listen.py`, `factory.py` ni `evaluators/lc0.py`.

## Invocación desde scripts (PowerShell)

```powershell
.\sargon_benchmark.ps1 `
    --brain ../data/brains/brains.json `
    --ids alphie sophie `
    --positions 6 `
    --rounds 2
```

También se puede ejecutar mediante Python:

```powershell
python .\sargon_benchmark.py --brain ../data/brains/brains.json --ids alphie sophie --positions 6
```

El lanzador `.ps1` utiliza la misma selección de intérprete que `sargon_match.ps1` (variable `SARGON_PYTHON`, `.venv` y finalmente el Python activo). Si la GPU es `onnx-dml`, ese **mismo Python** debe tener disponibles los bindings GPU y sus DLL. No instala dependencias ni modifica `ufasta`.

## Modos de ensayo

### `--mode positions` (predeterminado)

Evalúa cada brain sobre las **mismas posiciones**, derivadas de ocho aperturas conocidas, sin continuar las jugadas elegidas por el brain. `--positions 6` mide seis decisiones por brain en cada ronda. Se ejecuta `ucinewgame` antes de cada evaluación, pero el proceso y sus posibles cachés internos persisten hasta terminar todas las rondas del brain.

Para especificar posiciones se pueden repetir `--fen "<FEN>"` o `--opening "e2e4 e7e5 ..."` (no se mezclan). Si se solicitan más posiciones de las disponibles, las posiciones se reciclan en orden.

### `--mode play`

Cada brain juega **ambos bandos** sobre un tablero propio, decide legalmente cada jugada y recibe el nuevo estado después de su elección. Las trayectorias resultantes pueden divergir entre brains, por lo que los tiempos no son comparaciones sobre posiciones idénticas.

```powershell
.\sargon_benchmark.ps1 `
    --brain ../data/brains/brains.json `
    --ids alphie sophie `
    --mode play --plies 8 --rounds 1
```

Opcionalmente se puede partir de **una** `--opening "e2e4 e7e5"` o **una** `--fen`.

## Parámetros

| Argumento | Predeterminado | Función |
|---|---:|---|
| `--brain` | obligatorio | Ruta al JSON de brains |
| `--ids` | todos | IDs a evaluar, en orden |
| `--list` | — | Mostrar IDs del archivo sin arrancar motores |
| `--mode` | `positions` | `positions` o `play` |
| `--positions` | `6` | Posiciones en cada ronda (modo positions) |
| `--plies` | `8` | Jugadas en cada ronda (modo play) |
| `--rounds` | `1` | Cantidad de rondas por brain |
| `--warmup` | `1` | Inferencias desde posición inicial no medidas |
| `--timeout` | `90` | Tiempo máximo en segundos de respuesta por jugada |
| `--python` | actual | Ejecutable Python del motor hijo |
| `--out` | `data/benchmark` | Directorio base de reportes en la raíz del proyecto |
| `--verbose` | no | Mensajes de inicialización/espera UCI |

## Telemetría y resultados

Se crea automáticamente una carpeta independiente para cada ejecución bajo `data/benchmark/bench_v0.6.131_<fecha>_<id>/`:

- **`moves.csv`**: brain, player, evaluator, backend, modo, ronda, índice, posición FEN, color, jugada UCI, `wall_ms`, `engine_ms`, `nodes`, `depth`, estado y error.
- **`summary.csv`**: cantidad de mediciones válidas y fallidas, tiempo acumulado, media, mediana, p95, mínimo, máximo, nodos y NPS cuando hay datos UCI suficientes.
- **`manifest.json`**: parámetros del ensayo, perfiles efectivamente utilizados y FEN fijas de comparación.
- **`engine_01.log`, `engine_02.log`, ...**: errores/telemetría estándar de los motores hijos; consultar aquí si un backend no inicia.

`wall_ms` se mide desde el envío de la posición hasta recibir `bestmove`, incluyendo comunicación UCI. Se excluyen creación del proceso y calentamiento. `engine_ms`, `nodes` y `depth` vienen de `info` UCI y quedan vacíos cuando el player no los proporciona. **p95** utiliza el percentil de rango más cercano; con menos de 20 muestras puede coincidir con el máximo.

Los brains se ejecutan **secuencialmente**, sin competencia simultánea por GPU/CPU. Se comprueba la legalidad de cada jugada mediante el wrapper UCI utilizado por MATCH. Si hay error/timeout, se registra en CSV y se continúa con el siguiente brain; la aplicación retorna código de salida `2` si algún brain falla.

## Advertencias metodológicas

- Para comparar CPU/GPU con justicia utilizar `--mode positions`, idéntica red, búsqueda, simulaciones y otras opciones; modificar solamente backend/opciones GPU.
- Un calentamiento (`--warmup`) reduce ruido de primer uso de GPU, pero puede poblar cachés; no elimina variabilidad por carga del sistema, temperaturas, ni diferencias entre implementaciones.
- El benchmark mide **tiempo de cálculo de una jugada**; no estima ELO, fuerza de juego ni calidad de la decisión.
- La compilación y el registro de `onnx-dml` se verificaron previamente en `lc0-gpu-test`. En el entorno operativo `ufasta` debe haberse completado la activación GPU v0.6.129 para evaluar brains con `onnx-dml`.

## Validación de esta entrega

Sintaxis Python verificada. Se ejecutaron 6 pruebas automatizadas sin depender de hardware GPU: carga de IDs, transmisión de parámetros a UCI, extracción `info`, modos `positions` y `play`, CSV y registro de fallas. No se ejecutaron partidas reales ni inferencias GPU en este contenedor.
