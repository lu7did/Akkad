# Ecosistema de validación Sargon-NNUE v0.6.41

Tres herramientas independientes:

1. **sargon_audit** inspecciona `.pb` en modo lectura, con progreso, análisis en consola, CSV y JSON. `--network` es opcional; sin él no se calculan métricas de predicciones. Fases del juego heurísticas, no clasificación normativa. La telemetría muestra duplicados, contradicciones PGN, WDL, cobertura, MSE por fases, baselines y calibración cuando hay red.
2. **sargon_match** instancia dos UCI autónomos vía STDIN, con los mismos parámetros de `sargon_listen`, prefijos `--a-...` y `--b-...`, aperturas emparejadas y colores invertidos. Produce CSV y PGN si se solicitan. Sin servidores TCP.
3. **sargon_judge** lee el CSV y presenta resultados, colores, terminaciones, tiempos y una medida orientativa de incertidumbre. Acepta también CSV del torneo anterior (sin tiempos).

## Ejemplos

Desde la raíz del proyecto, con `PYTHONPATH=src`:

```
python -m sargon_nnue.sargon_audit --input data/pb/boot_sf_10pct.pb --network data/nnue/sf_shuffle20/nnue_epoch_004.npz --stockfish --weight-stockfish 1 --csv data/audit.csv --out data/audit.json

python -m sargon_nnue.sargon_match --a-player sargon-plus --a-evaluator classic --a-depth 2 --b-player sargon-plus --b-evaluator npz --b-network data/nnue/sf_shuffle20/nnue_epoch_004.npz --b-depth 2 --pairs 3 --csv data/match.csv --pgn data/match.pgn --heartbeat 5

python -m sargon_nnue.sargon_judge --input data/match.csv
```

Para jugadores Stockfish: `--a-player stockfish --a-evaluator null --a-engine-path RUTA`; para evaluador Stockfish: `--a-evaluator stockfish --a-stockfish-path RUTA`. También se admiten `--a-nodes`, `--a-elo`, `--a-movetime`, `--a-tmax`, `--a-turbo`, `--a-boost` y equivalentes `--b-*`. `--a-extra` y `--b-extra` permiten opciones nuevas del listener si fueran necesarias.

No se modifican entrenamiento, datasets ni motores; el `sargon_match.py` utiliza `python-chess`. La ejecución de partidas completas requiere el entorno Python y los motores del usuario.
