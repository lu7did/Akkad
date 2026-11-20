# picoGen PGPE v0.1.49 — escala estructural de la salida

Base: parches v0.1.44 a v0.1.48, en orden. Parche incremental para aplicar en la raíz `akkad`.

## Corrección

En PGPE la capa oculta sigue `clip(0,1)`; se optimizan coeficientes de salida adimensionales `u` y `beta`. La función objetivo evalúa `cp = 400*(sum(h*u)+beta)`. El `best.npy` se exporta convirtiendo exactamente los 16 pesos de salida y su bias a centipeones (`*400`), sin escalar los 12.288 pesos de entrada ni los 16 sesgos ocultos. Nurse conserva `output_scale=1` y el mismo formato de manifiesto, sin cambios en inferencia. La función objetivo sigue siendo MSE probabilístico mediante sigmoid(cp/400) frente a Stockfish; T77 sigue solo para validación.

El nuevo formato de checkpoint `picogen-pgpe-768x16-prob-scaled-output-v2` y los archivos `best.pgpe-v2.*` son incompatibles deliberadamente con la versión 0.1.48; no se puede mezclar el optimizador antiguo. El checkpoint guarda parámetros INTERNOS (adimensionales en la última capa); `best.npy` tiene parámetros EXTERNOS (centipeones).

## Ejecución nueva de 100 generaciones

Desde `picoGen/tools/train`, en la corrida anterior que tenía 1000 generaciones configuradas:

```powershell
.\run_genesis_binpack.ps1 --mon 7 --generations 100
```

MON 7 archiva el modelo PGPE previo bajo `assets/binpack-pgpe-001/history/nnue-...` y recomienza desde G1 con 100 generaciones. MON 8 audita PST y NNUE. MON 1–6 no se repiten. No alterar `best.active.json` manualmente.

## Telemetría nueva

Por generación: `val_pred_std_cp`, `val_pred_range_cp`, `output_bounds_cp`, `output_signs=+N/-N` y sigma, además de los MSE/RMSE habituales. Atención: los límites de salida son algebraicos, no necesariamente alcanzables en posiciones legales. El signo de salida no está forzado; su evolución depende del optimizador.

## Pruebas

`python -m unittest discover -s picoGen/tools/train/tests -p test_pgpe_output_scale_v0149.py` desde raíz de Akkad. Necesita NumPy y PyTorch, sin requerir hardware XPU. En ambiente sin EvoTorch las pruebas verifican matemáticas y exportación, pero no el ciclo completo XPU.
