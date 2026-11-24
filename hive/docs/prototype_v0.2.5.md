# Hive v0.2.5 — prioridades y telemetría de la prueba UCI

Base: Hive v0.2.4. Aplicar el ZIP incremental sobre v0.2.4.

## Defecto corregido

El valor `k_i = delta_i / sum(delta)` es una **fracción del tiempo**, que crece para motores lentos. No es una prioridad de asignación. El distribuidor ya utilizaba el inverso de la latencia, pero la etiqueta `PREFERENCES k=...` era equívoca. Ahora informa tanto `latency_k` como `priority`, donde:

`priority_i = (1/delta_i) / sum_j(1/delta_j)`.

El reparto utiliza explícitamente los tiempos de prueba `delta_i` y reserva motores por sesión. Si no hay medidas válidas, conserva el reparto uniforme del cálculo de preferencias.

Con delta Stockfish=1 ms, AlphaZero=1508 ms, picoSargon=1 ms:

| Motor | latency_k | priority efectiva |
|---|---:|---:|
| stockfish | 0.00066 | 0.49983 |
| alphazero | 0.99868 | 0.00033 |
| picoSargon | 0.00066 | 0.49983 |

## Telemetría UCI

Un registro TEST distingue:

- `wall_ms`: tiempo de pared de la petición completa, medido por Hive (con red y latencia de comunicación).
- `uci_time_ms`: último tiempo `info time` emitido por el motor; tiempo interno de búsqueda.
- `uci_nodes`, `uci_nps`: últimos valores informados mediante `info nodes` y `info nps`. Son métricas del motor y no tienen una semántica homogénea entre motores diferentes.
- `mcts_simulations`: campo `simulations=...` emitido por AlphaZero si está presente. **No se interpreta como nodos alfa-beta**.
- `cp`: evaluación de la jugada raíz, con perspectiva del bando que mueve.
- `depth_requested`, `movetime_requested_ms`: parámetros solicitados al motor en la prueba, que no garantizan búsquedas de igual coste.

El valor `nps=643` del registro anterior procede de la salida UCI de AlphaZero, que calcula NPS con sus nodos de árbol MCTS; no es un error de conversión aritmética en Hive, pero **no es directamente comparable con los NPS de Stockfish**. Asimismo Stockfish puede terminar rápidamente por el límite `depth`, mientras AlphaZero utiliza su presupuesto de simulaciones o tiempo: una prueba de profundidad 3 y movetime 1500 ms no constituye una calibración universal de capacidad.

No se modifica el motor AlphaZero, las puntuaciones, el algoritmo MCTS, las redes ni la prueba configurada en `hive.yml`.

## Verificación

31 pruebas automatizadas Python superadas en Linux, incluyendo las 29 anteriores. No se dispone de validación nativa Windows en este entorno.
