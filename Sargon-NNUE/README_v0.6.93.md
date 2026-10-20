# Parche experimental 0.6.93 — auditor diferencial UCI por FEN

Agregar `src/sargon_nnue/boost_differential.py` y `scripts/sargon_boost_differential.ps1` al árbol **v0.6.92**. No reemplaza el player, listener, MATCH ni RALLY.

Ejecutar desde `scripts`, indicando el `moves.jsonl` **de la corrida deseada**:

```powershell
.\sargon_boost_differential.ps1 -Base classic -Test s0001 -Moves '..\data\test\audit\<run>\match_001\moves.jsonl' -Limit 20
```

Se genera un directorio único `data/test/differential/<run>` con `manifest.json`, `summary.json`, `decisions.csv`, `decisions.jsonl`, `divergences.jsonl` y `position_NNNN/{base,test}_engine.jsonl`, más stderr independiente para errores. Nunca mezcla dos corridas ni sobrescribe un directorio existente.

## Alcance

- Cada posición se analiza una vez con cada configuración en **procesos independientes**, reiniciados por posición. Se registran `bestmove`, puntuación CP, nodos, profundidad, timeout, latencia UCI, contadores BOOST/TURBO, y todas las divergencias de jugada/puntuación.
- Exige igualdad de configuración excepto BOOST, TURBO y ELO de metadatos, salvo `--allow-other-differences`.
- Los datos quedan persistidos y son comparables; **no miden por sí solos la calidad objetiva de la jugada**, ni trazan el primer nodo divergente del árbol. Un análisis contrafáctico más profundo se hará solo sobre las FEN divergentes.
- No depende de `python-chess` en el nuevo módulo; sí del listener existente y sus dependencias.
- La prueba funcional UCI real debe realizarse en el entorno Windows del proyecto. En este entorno se verificaron sintaxis, extracción de FEN y operaciones de informe, no partidas reales.
- El tiempo de cada búsqueda incluye el protocolo `go`→`bestmove`, por lo que para medir exclusivamente eficiencia del motor conviene utilizar `elapsed_ms` en los JSONL además del tiempo supervisor.
