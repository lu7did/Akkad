# Bellman-Restricted — versión experimental BR-1 (Python)

## Archivos
- `bellman_prepare.py`: reconstruye el libro a partir de `.pb` y PGN originales (no es posible inferir acciones desde el `.pb` solo).
- `bellman_analyze.py`: distribución completa y poda en una nueva DB.
- `bellman_export.py`: volcado streaming JSON.
- `bellman_common.py`: esquema, claves y función estadística.
- `evaluators/bellman_r.py`: tabla hash en memoria, Dirichlet y penalización.
- `players/bellman.py`: elige por BR o busca con Grumpy enteramente en Python.
- `etc/brains/bellman_example.json`: perfil de ejemplo.

## Ejecución en entorno Sargon-NNUE

```powershell
python -m sargon_nnue.bellman_prepare --in data/games.pb --out data/bellman.db --pgn-root data
python -m sargon_nnue.bellman_analyze --in data/bellman.db
python -m sargon_nnue.bellman_analyze --in data/bellman.db --prune 1 --out data/bellman_pruned.db
python -m sargon_nnue.bellman_export --in data/bellman_pruned.db --json data/bellman.json
```

Los scripts `.ps1` son comandos directos de ejemplo y pueden requerir adaptar las rutas.

## Semántica de datos
- SARGON .pb: SQLite contiene `games(source,source_index,result,npositions)` y `positions.features` (posteriores a la jugada); **no contiene movimientos UCI**. Cada PGN de origen debe seguir disponible. Se valida cantidad de movimientos y resultado contra `.pb` antes de agregar.
- BR `.db`: `(state,action,N,W,D,L,R)`, resultado desde quien mueve, `R=W-L`. Posición `board.fen()` primeros cinco campos, sin contador de jugada completa. La historia de repeticiones no puede representarse fielmente solo con FEN; limitar uso en estados con reclamaciones de tablas.
- `gamma`: parámetro reservado para una etapa futura de Bellman backup; en BR-1 las observaciones son retorno terminal sin descuento (gamma efectivo = 1). No puede sustituirse R=W-L por resultados descontados sin ampliar el esquema.
- `score=(W-L)/(N+3*alpha)-lambda/sqrt(N+3*alpha)`; usar respaldo si no quedan acciones legales con N>=Nmin o si todas sus medias suavizadas son negativas.
- Los estimadores BellmanR de acciones son retornos en [-1,1], **no centipeones**. El player reporta una proyección a cp para telemetría (`400*media`), no debe interpretarse como calibración contra la escala de Grumpy.
- El contrato genérico `evaluate(board)` del evaluador BellmanR devuelve su evaluación alternativa de Grumpy; no hay valor posicional Bellman matemáticamente definido sin elegir acción. El player consulta `lookup(board)` para decisiones BR.
- La búsqueda Python incluye alfa-beta, ordenación de capturas, TT, killer/history, quiescence consciente de jaque e iterative deepening. **No es una traducción 1:1 de todas las heurísticas de picoSargon** (PVS, ventanas de aspiración, LMR y razoring están aproximados; verificación de SEE, márgenes y paridad de extensiones/podas sigue pendiente).
- El cambio de evaluator=bellmanR a otros players utiliza su función de evaluación posicional Grumpy; no activará la política BR del player.

## Validación
Sintaxis de módulos verificada con compileall. Sin python-chess ni un `.pb`/PGN real en este entorno no fue posible ejecutar integración ni benchmark real.
