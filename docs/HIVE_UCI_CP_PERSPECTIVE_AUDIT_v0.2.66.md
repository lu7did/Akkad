# Akkad — auditoría de perspectivas de evaluación (v0.2.66)

**Base exclusiva:** `akkad(20261124-175149).zip`, verificada con `unzip -tq` (sin errores).  
**Alcance:** Nurse, picoSargon, picoBit, picoAlpha, picoGen, picoKeras, AlphaZero; inspección adicional de picoPixie por su relación con picoSargon y APIs remotas.  
**Estado:** se corrigieron inconsistencias demostradas en la interfaz de players heredados de Nurse. Se distinguen comprobaciones estáticas/ejecuciones locales de las plataformas que no pudieron compilarse aquí.

## Contratos que NO deben confundirse

- **UCI `info score cp`:** signo desde el **bando que mueve en la posición raíz (STM)**, sin importar si juega blanco o negro. `score mate` tiene la misma orientación.
- **Nurse `MoveChoice.score_cp` heredado:** desde **blancas (WHITE)**. `nurse/src/nurse/_legacy/uci.py` convierte WHITE → STM al emitir UCI; `nurse/src/nurse/worker.py` hace lo propio para jugadores heredados.
- **Evaluadores Nurse (`evaluate`, `evaluate_batch`, `evaluator_client`):** devuelven **WHITE**. Esto incluye los evaluadores Classic, Keras, GENUS, Bullet y NNUE cuando usan el contrato de evaluador Nurse.
- **MCTS (`value`, `q`) y negamax:** la perspectiva es relativa al nodo/raíz según las funciones internas; no deben confundirse con `score cp` UCI ni con etiquetas de entrenamiento.
- **Datasets/objetivos de entrenamiento:** `score_white_cp` y `score_stm_cp` son *campos diferentes y explícitos*. No se altera su signo ni se reetiquetan datasets.
- **Conversión:** `cp_white = cp_stm` si mueven blancas, y `cp_white = -cp_stm` si mueven negras. La conversión inversa tiene la misma fórmula.

## Defectos confirmados y cambios del parche

| Archivo | Hallazgo | Corrección |
|---|---|---|
| `nurse/src/nurse/_legacy/players/picosargon_uci.py` | Leía `score cp` UCI (STM) y lo devolvía directamente como `MoveChoice` WHITE. | Conversión STM → WHITE para ambos colores. |
| `nurse/src/nurse/_legacy/players/picoalpha_uci.py` | Mismo defecto. | Conversión STM → WHITE. |
| `nurse/src/nurse/_legacy/players/tinyalpha_uci.py` | Mismo defecto en el adaptador heredado. | Conversión STM → WHITE. |
| `nurse/src/nurse/_legacy/players/picokeras_uci.py` | Ignoraba el `score cp` que emite el motor y producía CP=0. | Leer el último `score cp` de la búsqueda, convertir STM → WHITE. Si no hay frame score, conserva el valor 0 como ausencia de telemetría histórica. |
| `nurse/src/nurse/_legacy/players/keras_player.py` | Calculaba valores WHITE durante minimax y volvía a invertirlos al devolver `MoveChoice` para negras. | Devolver directamente el valor WHITE; mantener selección MAX para blancas y MIN para negras. |
| `nurse/src/nurse/_legacy/players/uci_external.py` | El adaptador genérico UCI descartaba `info score`, devolviendo CP=0 incluso si había evaluación. | Recoger score/nodos/depth de la búsqueda, convertir STM → WHITE y tratar el signo del mate. |
| `nurse/src/nurse/_legacy/score_perspective.py` | No había punto de conversión declarado para los adaptadores corregidos. | Funciones explícitas `stm_to_white` y `white_to_stm`. |
| `nurse/tests/test_uci_stm_legacy_boundaries_v0266.py` | Faltaban pruebas específicas de estas fronteras. | Ocho tests de contrato, conversión por color y ejecuciones sintéticas de `EXTERNAL` y Keras. |

## Auditoría por proyecto y plataforma

| Proyecto | ARM | x86/Windows | Debian/Linux | macOS | Contrato observado |
|---|---|---|---|---|---|
| **picoSargon** | `ARM/src/pico_main.cpp` independiente, `r.score` STM | `x86/src/host_main.cpp` y buscador común, STM | CMake enlaza las fuentes x86; compilación Linux realizada | CMake enlaza las fuentes x86; compilación nativa pendiente | Negamax STM en frontera UCI; entrenamiento/Audit conserva WHITE explícito. |
| **picoKeras** | `ARM/src/main.cpp` y `ARM/src/pico_main.cpp`, CP STM | Frontend específico `x86/src/main.cpp`, CP STM | CMake utiliza `src/main.cpp`, CP STM; necesita TensorFlow Lite para compilar | Mismo `src/main.cpp` que Debian; compilación nativa pendiente | Red devuelve valor del rival; se invierte para calcular STM, sin segunda conversión WHITE. |
| **picoAlpha** | No hay frontend ARM independiente en esta base | `src/main.cpp` compartido, compilado aquí en Linux | Misma fuente C++ si se compila como host; compilación local hecha | No hay frontend macOS independiente en esta base | `mcts.cpp` invierte el valor del hijo para expresar `Result.value` desde STM; `src/main.cpp` publica CP STM. |
| **AlphaZero** | No se encontró variante ARM de frontend en esta base | `src/akkad_alphazero_main.cc` LC0, CP STM | Misma fuente del frontend en las variantes de host | Misma fuente del frontend; build nativo pendiente | Las copias de valor MCTS son desde STM; backup de hijos cambia signo por ply. |
| **picoBit** | Recursos y herramientas, sin interfaz UCI productora de score CP en la base | Evaluadores/entrenamiento | Python y modelos compartidos | Python y modelos compartidos | `src/bnn.py` y `native_bnn.cpp` exponen `cp_white`, datos y auditorías WHITE; sin cambio. |
| **picoGen** | Sin motor UCI por plataforma en esta base | Código de entrenamiento/evaluación | Python compartido | Python compartido | CSV controla que `score_stm_cp` corresponda a `score_white_cp` según el turno; objetivos WHITE deliberados. |
| **Nurse** | Un endpoint ARM puede ser cliente UCI de Nurse | Código Python común | Código Python común | Código Python común | Worker y UCI convierten WHITE a STM, excepto MCTSP que ya devuelve STM; adaptadores de entrada corregidos. |
| **picoPixie** *(control adicional)* | Firmware/NNUE y cloud. Local `r.score` STM, cloud se anuncia como WHITE y se convierte según turno | No aplica como frontend actual en esta base | — | — | Contrato remoto declarado WHITE; el proveedor real requiere prueba de integración para confirmar semántica de todas las APIs. |

## Rutas Nurse que NO se deben invertir

- `nurse/src/nurse/_legacy/players/tcp_external.py`: ya convierte UCI STM → `MoveChoice` WHITE.
- `nurse/src/nurse/_legacy/players/alphazero_x86_uci.py`: ya convierte UCI STM → WHITE.
- `nurse/src/nurse/_legacy/players/lc0_uci.py`: usa `score.pov(chess.WHITE)`; corresponde al contrato WHITE.
- `nurse/src/nurse/_legacy/players/alphazero.py`: MCTS convierte el `q` raíz a WHITE antes de `MoveChoice`.
- `nurse/src/nurse/_legacy/players/{sargon,sargon_plus,sargon_historical,bellman,doc,microchess}.py`: el contrato histórico es WHITE; la salida UCI debe convertirlo a STM, sin cambiar minimax ni pesos.
- `nurse/src/nurse/worker.py`: rama MCTSP = STM directamente, rama heredada = WHITE multiplicado por signo de turno. Es una distinción necesaria, no una inconsistencia.
- `nurse/src/nurse/evaluator.py` y `evaluator_client.py`: API de evaluador WHITE, que NO debe normalizarse globalmente a STM.

## Verificaciones realizadas

1. Integridad de la base ZIP: correcta.
2. Compilación Linux/GCC de picoSargon x86 con `MULTICORE=ON`, `STEROIDS=ON`: correcta.
3. Compilación Linux/GCC de picoAlpha (`src/main.cpp`, `mcts.cpp`, `nnue.cpp`): correcta.
4. Ejecución real UCI de picoSargon con negras, `go depth 2 ... searchmoves e7e5`: produjo `info ... score cp` y `bestmove` sin excepciones.
5. Test preexistente `picoSargon/tools/tests/test_uci_cp_perspective_v0.2.65.py`: pasó.
6. Ocho regresiones nuevas Nurse: pasan. Incluyen ejecución sintética para signos de ambos colores y validación de la elección Keras desde valores WHITE.
7. Sintaxis `py_compile` de todos los archivos Python modificados: correcta.

## Límites de verificación y tareas pendientes

- **No se compilaron Windows/MSVC, macOS ni Raspberry Pico ARM**: disponer de fuentes comunes no equivale a probar binarios en cada plataforma.
- **No se hizo integración completa de Nurse contra ejecutables reales**: en este entorno no está instalada la dependencia `python-chess`, y no se dispone de todos los pesos, backends y ejecutables configurados.
- Los `score cp` heurísticos de picoKeras, los CP derivados de MCTS y los de Stockfish son compatibles en **signo**, no necesariamente en escala estadística.
- Los parámetros `depth`, `qdepth`, `movetime`, `searchmoves` y `MultiPV` son otro eje de compatibilidad Hive; la auditoría aquí se limita a la perspectiva y su consumo.
- Hallazgo independiente **fuera de este parche**: el `info multipv` de picoSargon x86 incluido en el ZIP todavía contiene `core N` después de `string`, pese a la solicitud previa de dejar esa telemetría exclusivamente en stderr. No cambia CP, pero merece un parche separado para no mezclar alcances.
- **Nuevos modelos o providers cloud** requieren documentar la perspectiva a la salida de sus APIs y un test con negras antes de incorporarlos.

## Conclusión

El contrato consistente es **Nurse evaluador/MoveChoice heredado WHITE; protocolo UCI STM; conversión exactamente una vez en la frontera**. Este parche cierra seis defectos concretos del lado de Nurse sin cambiar algoritmos internos ni datos de aprendizaje. No se afirma certificación nativa de plataformas no probadas.
