# picoSargon v0.2.60 — revisión multinúcleo x86 / Debian / macOS

## Alcance y fuente

Incremental respecto de v0.2.59, basado en la copia de trabajo con el parche Hive UCI aplicado sobre `akkad(20261122-184526).zip`. Los tres targets compilan `picoSargon/x86/src/{engine,host_main}.cpp`; no se cambian fuentes ARM.

## Arquitectura verificada y mejoras

- `--cores N` acota el pool a `min(N, núcleos físicos detectados, movimientos raíz)`. La opción UCI `setoption name Cores value N` también existe.
- Una sola instancia coordinadora lee/escribe UCI y espera una barrera por profundidad; no escribe ninguna línea de resultado final antes de que terminen todos los workers.
- Cada worker posee su instancia `Board`, su `Engine` (TT, killers, history, buffers, contadores) y una copia de la NNUE Grumpy; solo comparte la sincronización y un alpha raíz atómico.
- Una cola atómica asigna un movimiento raíz cada vez; los workers rápidos consumen más movimientos. Se mantiene profundización iterativa y los resultados del último nivel completamente terminado.
- **Corrección:** `searchmoves` ahora participa del alpha compartido. Antes, la rama restringida desactivaba por completo la ventana alpha global.
- El alpha compartido se actualiza únicamente con valores raíz **verificados** por búsqueda de ventana completa. Los otros workers pueden hacer una exploración *scout* de ventana nula. Si la jugada no supera el alpha compartido, el valor retornado se publica como **cota superior** UCI (`score cp ... upperbound`), nunca como evaluación exacta. Si lo supera, se verifica con una ventana completa y se publica un valor exacto. Esta es la diferencia matemática necesaria para combinar poda con evaluaciones por jugada: **no se puede prometer que todas las puntuaciones parciales sean exactas** y simultáneamente omitir la verificación de las que pierden con el alpha actual.
- Se informa `core N` dentro de `info ... string` en cada raíz y `CORE_WORK core[N] depth=D moves=M elapsed_ms=T` en stderr por profundidad. Se conserva la telemetría `🧮` anterior para compatibilidad.
- El límite `movetime` es global. Se espera la terminación de todos los workers y no se publican profundidades incompletas como si fueran finales. Si venció el deadline, cada worker lo detecta mediante su verificación periódica; no existe preempción dura de un hilo arbitrario.

## Uso

```text
uci
setoption name QDepth value 9
position startpos
go depth 9 movetime 10000 searchmoves e2e4 d2d4 g1f3
```

Arranque del programa: `picoSargon --weights <red> --cores 4`. Para probar únicamente una jugada, indicar un solo `searchmoves`. Para cada línea `multipv`, `score cp` estará acompañado por `upperbound` cuando represente una cota y no una evaluación exacta. `bestmove` se elige de valores verificados. La profundidad de `info` es el último nivel completado, y `qdepth` es el límite configurado, no una medición de quiescencia efectivamente alcanzada.

## Limitaciones y riesgos

- Los porcentajes de rendimiento no son garantizados; compartir un alpha reduce trabajo en los scouts perdedores pero la verificación completa de ganadores puede duplicar búsqueda. Un `score cp ... upperbound` **no debe tratarse como un valor exacto para ordenar todos los movimientos en Hive**. Para exigir puntuación exacta de *todas* las jugadas hace falta una segunda pasada de verificación o desactivar esa poda para la evaluación individual.
- El UCI del host es síncrono: no puede atender `stop` mientras se ejecuta `go`; `movetime` sí se aplica y es el límite operativo. No se modificó esa semántica en este parche.
- La versión macOS requiere build y test reales en macOS; Windows/MSVC requiere build y test reales en Windows. La prueba verificada fue Linux GCC, con los mismos archivos C++.
