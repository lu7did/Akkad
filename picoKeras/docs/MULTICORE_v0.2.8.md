# picoKeras v0.2.8 — MULTICORE desktop (Windows x86 / Debian / macOS)

## Alcance

No se modifica `picoKeras/ARM`. Todo el código de búsqueda reside en `picoKeras/src/multicore.{hpp,cpp}` y se incluye solo si CMake tiene `MULTICORE=ON` (default).

- `--cores 1`: **ruta anterior sin cambios algorítmicos**, evaluación por lotes de los hijos inmediatos, profundidad 1 y un solo intérprete. Aunque se pase `--depth N`, esta ruta conserva profundidad 1.
- `--cores N` con N > 1: se limita a `std::thread::hardware_concurrency()`; reparto de jugadas raíz entre trabajadores (`std::thread`, índice atómico), con instancias de evaluador privadas.
- B, inferencia paralela: el presupuesto se divide entre trabajadores y paralelismo interno de TensorFlow. Windows configura `intra_op_parallelism_threads` en la sesión TensorFlow C con `TF_SetConfig`; Debian/macOS usan `tflite::Interpreter::SetNumThreads()`. No se comparte el estado mutable de TensorFlow entre trabajadores.
- C, búsqueda paralela: por defecto profundidad 2 para N > 1 (`--depth N` puede elevarla hasta 8); `negamax` con alfa-beta en niveles interiores y evaluación neuronal por lotes en las hojas adyacentes. Cada raíz se evalúa independientemente, con desempate por orden de jugadas; esto no es alfa-beta global entre las raíces.
- `--tmax MS` (default 15000) limita cooperativamente la búsqueda. `go movetime MS` impone el menor de los dos límites. No se pueden interrumpir inferencias TensorFlow ya iniciadas; el tiempo puede exceder el presupuesto durante un `Invoke` o `TF_SessionRun`.
- Una búsqueda parcial no se presenta como profundidad completa: `info depth 0` con `status=partial`. Si ninguna raíz terminó, se devuelve la primera jugada legal, no `bestmove (none)`.

## Planificación de hilos

| Cores disponibles/solicitados | Trabajadores de búsqueda | Hilos internos por evaluador | Total nominal |
| --- | ---: | ---: | ---: |
| 1 | 1 | 1 | 1 |
| 2 | 2 | 1 | 2 |
| 4 | 2 | 2 | 4 |
| 8 | 4 | 2 | 8 |

El planificador no excede el número de unidades lógicas reportado por el sistema. No fija afinidad: macOS puede distribuir sobre núcleos P/E. Más intérpretes consumen más memoria; no hay garantía de escalabilidad.

## Compilación

**Windows** (PowerShell):

```powershell
.\picoKeras\tools\ps\build.ps1 -Multicore ON
```

**Debian**:

```bash
MULTICORE=ON bash picoKeras/tools/bash/build.sh
```

**macOS**:

```bash
bash picoKeras/tools/macOS/build.sh --multicore ON
```

Cambiar ON por OFF elimina la búsqueda paralela de la compilación. `--cores 2` o superior en un binario OFF produce un error explícito.

## Invocación UCI/TCP

```bash
picoKeras/macOS/build/picoKeras --weights /ruta/modelo.tflite --cores 4 --depth 3 --tmax 15000 --stdio
picoKeras/macOS/build/picoKeras --weights /ruta/modelo.tflite --cores 4 --depth 3 --tcp --host 0.0.0.0 --port 6200
```

En Windows, la ruta de pesos sigue apuntando a un directorio SavedModel; en Debian/macOS a un `.tflite`. En modo Nurse, agregar los argumentos `--cores`, `--depth` y `--tmax` a `args` del brain correspondiente, sin cambios en Nurse o Sargon-NNUE.

El `run_listen.sh` de macOS acepta estas opciones para `--direct`; en modo `--id` Nurse lanza el programa con las opciones de `brains.json`. En Debian el script `run_listen.sh` reenvía los argumentos restantes, y Windows `run_listen.ps1` acepta `-Cores`, `-Depth`, `-Tmax`.

## Telemetría

Por búsqueda en stderr y `info string` UCI:

```text
MULTICORE=ON cores=4 workers=2 infer_threads=2 depth=3 nodes=... leaves=... batches=... evals=... worker_nodes=[..., ...] infer_ms=... elapsed_ms=... nps=... status=complete
```

- `nodes`: nodos visitados, **no equivale exactamente** a un contador de evaluaciones de hoja.
- `leaves`: hojas generadas antes de evaluar, incluidas terminales.
- `batches`: número de invocaciones a red, salvo rutas terminales.
- `evals`: tableros evaluados efectivamente por la red.
- `worker_nodes`: distribución de nodos entre trabajadores para estimar desbalance.
- `infer_ms`: suma de tiempos de inferencia de todos los trabajadores; puede superar `elapsed_ms` por ejecutar simultáneamente.
- `elapsed_ms`: tiempo de búsqueda de pared; excluye la carga del modelo, pero incluye coordinación de hilos.
- `nps`: nodos visitados/segundo.

**Para medir aceleración**, comparar igualdad de redes, posición, compilación, profundidad, deadline y backend. La ruta `--cores 1` permanece a profundidad 1; por lo tanto, **no** comparar directamente su tiempo contra multicore profundidad 2 o 3 como si midieran el mismo trabajo. Para medir eficiencias multihilo a profundidad fija en futuras versiones conviene agregar un modo monotrabajador con profundidad configurable, conservando el comportamiento por defecto.

## Validación

`python3 picoKeras/tests/test_multicore_smoke.py` compila y ejecuta el núcleo con un evaluador simulado en C++ y comprueba ambas variantes ON/OFF, la comunicación UCI, los resultados legales básicos, las profundidades y la prohibición de usar varios núcleos en OFF.

La compilación completa con bibliotecas TensorFlow C/TFLite en Windows, Debian y macOS y la medición de velocidad con redes reales **no han sido ejecutadas en el entorno de creación del parche**.
