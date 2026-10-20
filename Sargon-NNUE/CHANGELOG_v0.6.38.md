# v0.6.38

- Incorporado `--resample NN`, `--input`, `--seed` a `sargon_prepare.py`.
- Selección al azar de partidas enteras de un `.pb` existente, reproducible por semilla.
- Copia de posiciones y metadatos de partida conservando esquema PB v1.
- Reevaluación Stockfish opcional mediante reconstrucción y verificación de los 781 bits de cada posición.
- Conservación del archivo de entrada por acceso de solo lectura, creación atómica de salida independiente y validación de integridad.
- Se mantiene preparación PGN anterior; no se modifica `sargon_train.py`.
