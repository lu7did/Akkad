# picoBit train.py v0.1.30 — cambio autorizado: muestreo temprano

**Problema anterior:** `load_rows` recorría todos los registros etiquetados, validaba FEN, filtraba posiciones tranquilas y ejecutaba Sargon, antes de aplicar `--sample`. Esto podía tardar ~1 hora.

**Nuevo orden**
1. Contar registros con teacher y obtener únicamente sus IDs ordenados (sin cargar FEN ni ejecutar Sargon). Barra `1/5 IDs SQLite`, porcentaje, procesados/total, velocidad y ETA.
2. Desordenar IDs reproduciblemente con `--seed` y recorrerlos en ese orden. Obtener FEN y etiquetas por lotes SQL de 512 IDs; validar FEN y estado quiet y calcular Sargon **sólo para los candidatos examinados**. Los candidatos descartados se reemplazan por los siguientes IDs hasta reunir `--sample` posiciones **elegibles y únicas**. Barra `1/5 Filtrar muestra` = aceptadas/objetivo, ETA estimado por tasa efectiva de aceptación. Se informan IDs realmente examinados y descartes.
3. Dividir la muestra obtenida en training/validation (`--validation`, 20% por defecto) sin solapamiento; calibrar Sargon exclusivamente con training; entrenar BNN sin otros cambios.

`--sample` pasa a **10.000 por defecto** para evitar el barrido exhaustivo accidental. `--sample 0` permite expresamente el barrido de toda la base. `--scan-limit N` limita el universo de candidatos a los primeros N IDs etiquetados, **no** limita el número de seleccionadas; se conserva el significado de límite inicial del código anterior. El manifiesto registra método, universo, solicitadas, examinadas y descartes.

**Cambio estadístico explícito**: la selección ahora es aleatoria de IDs *antes* de aplicar los filtros, con reposición de candidatos rechazados. Se mantiene el filtro quiet y la deduplicación; se modifica qué posiciones entran a la muestra respecto de v0.1.29 usando una misma semilla, porque cambió el orden del sorteo. No comparar checkpoints suponiendo que usaron el mismo split. El esquema del manifiesto no cambia.

No se modifican `export.py`, `audit.py`, `sargon.py`, arquitectura, loss, optimizador, calibración, filtrado quiet, fórmulas ni formato de checkpoint.

**Pruebas realizadas**: `py_compile`; SQLite temporal de 1.000 filas con dobles de `chess.Board`/Sargon para validar muestreo determinista, reposición, ausencia de duplicados, split 80/20 y modo exhaustivo. No se ha ejecutado entrenamiento real con python-chess y base del usuario.
