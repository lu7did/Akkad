# picoGenus — telemetría y checkpoints v0.1.12

## Conservación del algoritmo

No se modifican las funciones objetivo ni los operadores genéticos anteriores.

- **PST**: `fitness = hits ** 2`, `error_min = total_positions - max(hits)` y `error_mean = mean(total_positions - hits)`; se cuentan desaciertos frente a la jugada recomendada (`teacher_uci`). No se introduce un término de Stockfish CP al fitness.
- **NNUE**: aptitud por error cuadrático medio (MSE) de valor en CP; la telemetría `min` y `avg` muestra **RMSE en centipeones**, `sqrt(min(MSE))` y `mean(sqrt(MSE))` sobre individuos ya evaluados en la generación. No son aciertos de jugadas.

## Telemetría

La barra `█░` se actualiza sobre el mismo renglón durante la generación; contiene porcentaje, posiciones, generación y errores mínimo/medio de individuos completados en la generación actual. Al terminar cada generación se finaliza la línea con un salto y comienza una nueva. La presentación se adapta al ancho de la consola y reserva columnas numéricas. El ETA puede omitirse si no cabe sin desplazar columnas. La salida redirigida usa una línea por generación, sin retornos de carro.

## Persistencia

Para `--out C:\\modelos\\genus_pst.json`:

- `genus_pst.json`: mejor cromosoma encontrado globalmente, actualizado al mejorar la aptitud.
- `genus_pst.best.json`: copia explícita del mejor global.
- `genus_pst.gen00001.json`, `genus_pst.gen00002.json`, ...: mejor cromosoma **de cada generación completa** (no necesariamente mejor global), con `generation`, `error_min`, `error_mean`.

Para `--out C:\\modelos\\genus_nnue.npy`:

- `genus_nnue.npy`: mejor vector NNUE INT8 global.
- `genus_nnue.best.npy`: copia explícita del mejor global.
- `genus_nnue.best.json`: generación y MSE/RMSE del mejor global.
- `genus_nnue.gen00001.npy` ...: mejor vector NNUE de cada generación completa.
- `genus_nnue.gen00001.json` ...: métricas y metadatos de esa generación.

La escritura usa archivo temporal y reemplazo atómico en el mismo directorio; si se interrumpe una escritura previa no se sobreescribe el checkpoint anterior con un archivo incompleto.

## Ctrl+C

Ambos programas interceptan KeyboardInterrupt, cierran la línea de progreso, informan dónde quedan los checkpoints y finalizan con código 130, sin ejecutar generaciones adicionales. El archivo principal `--out` queda utilizable si al menos un individuo terminó su evaluación. Si se interrumpe antes del primer individuo completo, aún no existe un checkpoint nuevo. Los archivos `.genNNNNN` solo se crean al completar esa generación.

**Esto no es reanudación del algoritmo genético.** No se almacenan población ni estado del generador aleatorio para retomar la misma corrida exactamente. Los checkpoints permiten usar el mejor modelo sin perderlo; reanudar generaciones requeriría una implementación adicional que no se solicitó.

No se modificó `run_genesis.ps1`, las rutas definidas por el usuario ni los formatos de inferencia de Nurse.
