# Bellman Prepare: compatible con Bellman Upload

Este parche reemplaza `src/sargon_nnue/bellman_prepare.py` para operar exclusivamente sobre la base acumulativa creada por `bellman_upload.py`.

## Secuencia

```powershell
python -m sargon_nnue.bellman_upload --path "data\pgn\**\*.pgn" --out "data\bellman_games.pb"
python -m sargon_nnue.bellman_prepare --in "data\bellman_games.pb"
```

`--in` identifica la misma base `.pb`; no necesita PGNs externos ni `--out`.

El importador guarda el PGN íntegro en `pgn_games` y su resultado y cantidad de plies en `games`. `bellman_prepare` reconstruye cada tablero desde el PGN embebido y agrega las observaciones `(posición anterior, jugada UCI)` en `bellman_actions` con `N,W,D,L,R`, desde la perspectiva de quien mueve. Regenera `bellman_actions` y `bellman_meta` en una sola transacción, sin tocar las partidas ni sus índices.

La base debe contener el texto PGN de **todas** las partidas registradas. Las bases `.pb` antiguas que solamente contienen features y rutas no son suficientes; se debe usar la base propia creada con `bellman_upload.py`.

La clave es FEN de cinco campos, mediante el módulo `bellman_common.py` que ya se incluyó en el parche de alineación anterior; este ZIP lo incluye para funcionar de manera autocontenida.
