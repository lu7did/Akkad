# picoSargon v0.2.42 — Reutilización de memoria y telemetría multinúcleo

Parche incremental para aplicar desde la raíz `akkad`, sobre v0.2.41. No se modifica `picoSargon/ARM`.

## Predeterminados

- `STEROIDS=ON` y `MULTICORE=ON` en CMake x86, Debian y macOS y sus scripts de compilación.
- Se pueden desactivar explícitamente (`-DSTEROIDS=OFF -DMULTICORE=OFF` o variables de entorno equivalentes). En PowerShell `-steroids $false -multicore $false`.
- En Windows, `picoSargon/tools/ps/build.ps1` ofrece las opciones correspondientes.
- La cantidad de trabajadores de ejecución sigue definida por `--cores N` o UCI `setoption name Cores value N`; el valor predeterminado es 2. `--cores 1` usa la búsqueda secuencial.
- Importante: CMake conserva la configuración previa en cachés existentes; los scripts de compilación envían explícitamente sus valores predeterminados.

## Memoria, paralelismo y temporización

- Reserva anticipada de 256 movimientos por nivel para las listas legales y pseudo-legales, antes de comenzar la búsqueda; `Board::legal` admite reutilizar un buffer de candidatos.
- Reserva anticipada del historial/undo del tablero por trabajador (longitud actual + MAX_PLY + margen), sin realocaciones esperadas durante las búsquedas de hasta MAX_PLY.
- Ordenación estable por inserción con almacenamiento automático (array de 256 elementos) para evitar asignaciones temporales de `stable_sort` y `std::vector<Rated>`; selección SEE conservada.
- Trabajadores y copias inmutables de NNUE creados una sola vez por búsqueda; hilos, TT, killers, historial de heurísticas y buffers se reutilizan entre profundidades.
- Sin asignaciones dinámicas explícitas en el núcleo de generación/ordenación y búsqueda de cada profundidad. El programa todavía usa memoria dinámica durante la preparación (vectores, hilos y objetos Engine), así como en el procesamiento UCI fuera del cálculo; no se ha realizado una instrumentación global de `operator new` que demuestre ausencia absoluta de asignaciones de dependencias externas.
- Un coordinador sincroniza mediante condition_variable al final de cada profundidad; registra datos por trabajador. Si la profundidad se interrumpe, se conserva el mejor movimiento del último nivel completado.
- Quiescencia, SEE, razoring, PVS/LMR y tabla de transposiciones permanecen activos con su configuración correspondiente.

## Telemetría

Emisión solo por **stderr** (no contamina UCI/stdout):

`[hh:mm:ss] 🧮 core[0] level=04 status=completed nodes=19367 qnodes=2042 elapsed=98 msec`

`status` usa ancho fijo 9, `completed` o `stopped`; `nodes`, `qnodes`, `elapsed` son los valores **de ese trabajador en ese nivel**, no acumulados globales. Los datos se imprimen desde el coordinador al cierre de cada profundidad en orden de núcleo. Los hilos que finalizan su parte antes de los demás esperan la barrera.

## Pruebas

`python3 picoSargon/tools/tests/test_multicore.py --serial <binario-secuencial> --parallel <binario-paralelo> --weights <grumpy.bin>`

`python3 picoSargon/tools/tests/test_multicore_telemetry.py --engine <binario> --weights <grumpy.bin>`

Las pruebas locales Linux/Debian abarcan búsqueda secuencial, paralela de 2 y 3 núcleos, exceso solicitado, telemetría y cancelación. La compilación en macOS y Windows debe verificarse en esos sistemas.
