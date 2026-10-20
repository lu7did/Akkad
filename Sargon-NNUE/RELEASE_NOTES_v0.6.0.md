# Sargon-NNUE v0.6.0 — notas de arquitectura

## Decisiones implementadas

1. Separación estricta entre `Evaluator` (posición -> centipawns, perspectiva blanca) y `Player` (tablero -> movimiento).
2. Cuatro ejecutables lógicos independientes: GUI, self-play, training y listener UCI.
3. La GUI no importa ningún evaluador/player: sólo usa TCP/UCI.
4. `sargon-listen` unifica TCP y STDIN; la telemetría se envía a stderr.
5. Managers iniciales: Classic, Sargon-NPZ v0.5.x y Cerebrum 2.0.
6. Players iniciales: RANDOM, SARGON, SARGON-PLUS, CEREBRUM experimental y wrappers UCI externos.
7. `SARGON-PLUS` conserva la idea de profundización selectiva del bootstrap anterior, pero queda expresada como player independiente, no como flag que contamina toda la arquitectura.
8. Los datos se separan en `data/pgn` y `data/nnue`; los scripts PowerShell son deliberadamente simples.
9. `docs/` queda fuera del ZIP de versión para evitar sobrescribir material acumulado.

## Corrección de ambigüedad de la especificación

La especificación denomina por error `RANDOM` tanto al player aleatorio como al Sargón clásico. En v0.6.0 se reserva `RANDOM` para juego aleatorio y se denomina `SARGON` al algoritmo alpha-beta clásico.

## Cerebrum

El manager implementa el contrato cuantizado real de Cerebrum 2.0, arquitectura por defecto `2x(768->256)->32->1`:

- texto cuantizado con cabecera `name`, `author`, `parameters`;
- binario `.nn` correspondiente a la estructura de inferencia oficial;
- feature mapping de dos perspectivas;
- aritmética cuantizada con `FACTOR=64` y truncamiento equivalente a C;
- normalización final a centipawns desde perspectiva blanca.

No se reinterpretan redes Stockfish `.nnue` como Cerebrum: requerirán su propio manager.

## Alcance deliberadamente no cerrado

- El player `CEREBRUM` está aislado como componente experimental, pero v0.6.0 usa una búsqueda alpha-beta conservadora. Una réplica exacta de un algoritmo de búsqueda externo sólo debe incorporarse después de definir y verificar ese algoritmo por separado.
- El entrenamiento local de v0.6.0 sólo modifica redes Sargon `.npz`. Cerebrum y otras redes externas rechazan `--train`; se entrenan con su infraestructura nativa y luego se consumen como artefactos de inferencia.
- No se añadió aún un manager Stockfish `.nnue`; el player Stockfish ya puede utilizarse por UCI externo.
