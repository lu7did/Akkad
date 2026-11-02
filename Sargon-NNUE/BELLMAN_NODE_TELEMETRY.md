# Bellman: telemetría de acciones legales examinadas

- Para una elección directa por tabla, `nodes` = cantidad de jugadas legales **enumeradas realmente** por `lookup_with_stats`. No equivale a expansiones recursivas de alfa-beta.
- `hash_hits` = acciones legales presentes en la tabla antes del umbral `Nmin`.
- `qualified` = acciones que pasan `Nmin`; `N` = frecuencia histórica de la acción elegida, **no** nodos.
- `time` de UCI está cuantizado en milisegundos enteros (mínimo 1 ms); el benchmark utiliza `elapsed_ms` de alta resolución de `info string bellman` para el cálculo de NPS de Bellman.
- `lookup(board)` antiguo continúa disponible; `lookup_with_stats(board)` expone métricas nuevas.
- Las decisiones de fallback NNUE conservan la contabilidad original de nodos de búsqueda. Los NPS de Bellman y alfa-beta corresponden a unidades de trabajo diferentes: compararlos como potencia de cómputo sería engañoso.
- `score cp` sigue omitido en UCI para decisiones de tabla, al no existir calibración WDL→cp.
