# v0.6.77 — clasificación final de RALLY

Reemplazar `src/sargon_nnue/sargon_rally.py`.

Cambios: encabezado con estado, partidas registradas y duración; medallas a posiciones 1-3, diplomas para las demás; columnas con alineación dinámica para ID, puntuación, jugadas disputadas, victorias, tablas y derrotas.

Los contadores se obtienen de `scores`, sin inventar valores; `played` corresponde al número de partidas terminadas de ese brain. Ningún cambio en emparejamientos, preflight o ejecución de MATCH.
