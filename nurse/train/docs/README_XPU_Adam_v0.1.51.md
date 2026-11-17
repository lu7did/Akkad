# Nurse train v0.1.51 — Intel XPU Adam: corrección OOM

## Defecto observado

`RuntimeError: level_zero backend failed with error: 39 (UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY)`
originado en `torch._foreach_div_` dentro de `_multi_tensor_adam` en la primera época.

## Cambio

El constructor de Adam en `nurse/train/train.py` especifica `foreach=False, fused=False` y anuncia estas opciones en la telemetría. Se conserva PyTorch Adam, `float64`, la arquitectura 781–64–1, el objetivo MSE, el tamaño de lote, los datos, la partición y el esquema de checkpoints.

## Límites de la verificación

La corrección elimina la ruta `_multi_tensor_adam` del optimizador, no garantiza que toda carga XPU quepa en memoria. Si el controlador vuelve a producir OOM, ejecutar con `--device cpu` o disminuir `--batch`. Evitar reintentar indiscriminadamente con un contexto XPU ya agotado; terminar el proceso previo y verificar uso de memoria.

No se modificó `run_genesis.ps1` ni ningún archivo de rutas configuradas por el usuario.
