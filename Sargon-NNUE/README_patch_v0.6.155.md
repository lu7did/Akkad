# Sargon-NNUE v0.6.155 — argumentos opcionales LC0

## Defecto corregido

`--lc0-uci-options` se enviaba a `argparse` con un valor vacio, causando `expected one argument`. `--lc0-backend-options` tenia el mismo defecto latente.

## Cambio

`scripts/sargon_pipeline.ps1`: agrega estos argumentos a la lista solo cuando su valor no esta vacio; aplica tanto al metodo `lc0-uci` como al metodo `lc0`. Conserva los argumentos cuando poseen valor, por ejemplo `gpu=0`. Se actualiza la telemetria local de la etapa a v0.6.155.

No se modifica `run_pipeline.ps1`, `sargon_prepare.py`, la muestra PB ni los parametros de entrenamiento.

## Prueba

Repetir la etapa de valorizacion LC0 desde `run_pipeline.ps1`. La linea impresa ya no debe contener `--lc0-uci-options` sin un valor.

Nota: este parche solo resuelve el error de argumento vacio identificado. No se ejecuto el pipeline real en Windows ni se verifico el proceso LC0 con GPU.
