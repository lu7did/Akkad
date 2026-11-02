# Bellman Prepare: telemetría compacta

Este parche modifica exclusivamente las líneas de progreso de `bellman_prepare.py`.

`python -m sargon_nnue.bellman_prepare --in data/bellman_games.pb`

En el inicio se muestra una línea fija por cada archivo fuente registrado en la tabla `games`, con su número de partidas y movimientos, y el total global. La etapa de procesamiento presenta una sola línea dinámica (`\r`) con porcentaje, barra, partidas, movimientos y nombre del archivo fuente actual. No imprime líneas nuevas al cambiar de archivo; la línea se finaliza solamente cuando termina todo el procesamiento.

La tabla de partidas sigue siendo `pgn_games`; las únicas tablas regeneradas son `bellman_actions` y `bellman_meta`. No se alteran la política ni la valoración Bellman.
