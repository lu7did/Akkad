# Hive Python v0.2.0 — protocolo y alcance

## Casos de uso implementados

1. Frontend `stdin/stdout` UCI y listener TCP UCI por defecto puerto 6250, independientes y simultáneos; sesiones TCP concurrentes se tratan independientemente.
2. `position startpos [moves...]`, `position fen ... [moves...]`, `ucinewgame`, `isready`, `go depth ... movetime ... searchmoves ...`, `stop`, `quit`.
3. Cliente UCI persistente `tcp` y proceso local `uci`, con handshake UCI y prueba real de un movimiento.
4. Registro de resultados de prueba: `elapsed_ms`, `nps`, `k_i=delta_i/sum(delta)` recalculado al conectarse o desconectarse un endpoint.
5. Reparto de movimientos legales en lotes disjuntos, consulta simultánea, recolección de `info` por movimiento, y `bestmove` único.
6. Broadcast UDP del propio Hive y descubrimiento opcional de otros Hive; conexión UCI y prueba de movimiento.
7. Mensajes de diagnóstico/errores a `stderr` y protocolo UCI aislado en cada frontend.

## Identidad, jerarquías y ciclos

El nodo UCI Hive declara `option name HiveNodeID type string default <uuid>` además de `id name`.
Todo Hive cliente reconoce el ID y rechaza una arista A→B salvo cuando `id(A)>id(B)`. Un orden estricto sobre IDs hace imposible cualquier ciclo dirigido (inclusive carreras). El `node_id` debe ser UUID hexadecimal fijo por nodo en `hive.yml`; si se omite, el arranque genera uno efímero, con topología menos estable. La regla también se aplica a endpoints estáticos que se declaren como Hive.

La recepción de broadcast no implica contratación; las conexiones son UCI normales y los motores trabajan con `searchmoves` sin conocer si la petición pertenece a una partida o un análisis aislado.

## Semántica de rendimiento y consolidación

Los deltas por endpoint son tiempos de pared de la prueba fija. Se calcula el índice pedido `k_i=delta_i/sum(delta)` (si hay división por cero u observaciones inválidas, se usa `1/n`). **Como k alto significa mayor lentitud**, el planificador asigna en función de `1/k`, no directamente de `k`. Los NPS agregados anunciados son suma informativa de los NPS de las pruebas, nunca una unidad de capacidad universal.

`score cp` es orientado al bando que mueve en la raíz. `mate` se ordena por signo y distancia. Las cotas superior/inferior son conservadas en `info` y las puntuaciones exactas son preferidas para la decisión. MultiPV puede incluir CP de cada jugada solo si el motor los proporciona; el mejor movimiento exige puntuación UCI válida.

## Por verificar en infraestructura real

- Windows PowerShell, Linux, macOS, los distintos motores Akkad y `python-chess` instalado.
- Simultaneidad con motores muy lentos y watchdog en operaciones TCP de salida.
- Topología de broadcast multihost y restricciones de orden UUID.
- Política de recursos cuando dos frontends reciben `go` simultáneo; actualmente no se bloquea esperando motores ocupados.
- Distribución con motores que solo emiten `info score` sin `pv` o no respetan `searchmoves`.
