# Sargon-NNUE v0.6.79 — Brainmaker ELO

Copiar los archivos `src/sargon_nnue/sargon_brainmaker.py` y `src/sargon_nnue/brains.py` en el proyecto.

Desde `scripts`:

```powershell
.\sargon_brainmaker.ps1 --elo --brains ..\data\brains\brains.json --elo-reference classic --elo-score 1000 --rally ..\data\rally\mdqopen.json
```

Agregar `--save` para guardar los ELO calculados en `brains.json`.

El cálculo agrega los resultados terminados de los torneos presentes en el JSON indicado, pero exclusivamente los enfrentamientos directos entre el brain calculado y la referencia. P = (victorias + 0.5 * tablas) / partidas. Cuando P es exactamente 0 o 1 se sustituye por 0.1 o 0.9, respectivamente. ELO = ELO_referencia + 400 * log10(P/(1-P)). No se calcula rating si no hubo enfrentamientos directos y no se reemplaza uno previamente guardado en ese caso.

Se almacena en `rating_elo` en lugar de `elo` porque `elo` ya es un parámetro del *motor Stockfish* usado para limitar su fuerza. `brains.py` permite `rating_elo` como metadato y lo omite al construir argumentos de motor. Se conserva `elo` de Stockfish sin alterarlo.

`--elo` exige `--elo-reference`, `--rally` y acepta `--brains` como alias de `--brain`. `--elo-score` vale 1000 por defecto. `--save` es optativo y realiza reemplazo atómico del JSON. No modifica el archivo del torneo.

Si un mismo `rally.json` contiene múltiples entradas en `tournaments`, se suman sus resultados. Se ignoran partidas sin resultado definitivo (`1-0`, `0-1` o `1/2-1/2`). La referencia recibe exactamente la puntuación indicada. Las puntuaciones calculadas son estimaciones directas contra la referencia, no un sistema Elo iterativo.
