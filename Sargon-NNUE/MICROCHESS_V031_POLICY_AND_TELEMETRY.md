# Microchess v0.3.1 — política común y telemetría

## Cambios

* El player aplica JANUS/STRATGY para ordenar y valorar los candidatos **con cualquier evaluador**. Ya no existe una condición basada en `isinstance(MicrochessEvaluator)` que cambie el algoritmo de búsqueda.
* En profundidad 1 se utiliza, para todo evaluador, `floor((STRATGY_candidato + E_hoja)/2)`. La contribución de STRATGY permanece constante al cambiar de evaluador; las diferencias proceden del evaluador de hoja. **La combinación 50/50 es una extensión experimental, no la fórmula de Jennings.**
* En profundidad superior, `floor((STRATGY_candidato + valor_continuación)/2)` se aplica en todos los nodos. La combinación es experimental y no equivale al Microchess original.
* Las puntuaciones de cada `(FEN, UCI)` se almacenan temporalmente durante `choose()`, evitando reevaluaciones de la raíz entre iteraciones. El caché se destruye al terminar cada decisión.
* `nodes` conserva el contrato de nodos de búsqueda del benchmark. El trabajo adicional se reporta en `player.last_metrics`: `candidate_calls`, `candidate_cache_hits`, `gnm_calls`, `gnm_moves`, `measure_calls`, `janus_states`, `exchange_nodes`, `eval_calls`, `eval_time_ms`, `janus_time_ms`, `search_nodes`, `wall_time_ms`, `historical_candidate_cache_entries`.
* En el cálculo de puntuaciones mixtas **no** se aplican cortes alfa-beta de forma incorrecta sobre cotas de una escala diferente. Esto prioriza corrección de resultados sobre velocidad.
* No se modifican los demás players, los contratos de las fábricas ni el esquema de brains.json.

## Advertencias de interpretación

1. El trabajo de GNM y TREE puede ser mucho más caro que una evaluación NPZ. Al ejecutar la **misma política** para todos los evaluadores, se espera que el NPS de las combinaciones externas disminuya en relación con la v0.3.0: es una corrección necesaria para la comparabilidad, no necesariamente una regresión de rendimiento intrínseca.
2. `gnm_moves` cuenta movimientos producidos en generación y medición, **no** posiciones ajedrecísticas únicas; `exchange_nodes` cuenta llamadas recursivas tácticas y puede superponerse con los movimientos generados. **No sumar estos contadores a `nodes`** para construir un NPS aparentemente común.
3. `depth=1,qdepth=0` con evaluador `microchess` ya no es una recreación pura de la selección histórica: mezcla STRATGY con la evaluación posicional. Para un ensayo histórico estricto se necesitará un modo de selección `historical_only` explícito, aplicable como política de búsqueda y no inferido de la clase del evaluador.
4. No se han optimizado todavía GNM/TREE; las secuencias de intercambio siguen siendo una reconstrucción y no una equivalencia demostrada con el ensamblador de 1976.

## Pruebas

```powershell
python -m pytest tests/test_microchess_metrics_v031.py -q
python -m pytest tests/test_microchess_historical_v030.py -q
```

Comparar NPS solo entre ejecuciones con idéntica semántica de `nodes` y revisar `last_metrics` para determinar dónde se consumió el tiempo.
