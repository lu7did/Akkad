# picoAlpha v0.2.47 — parche incremental sobre v0.2.46

Archivo modificado: `picoAlpha/tools/picoDistiller/picoDistiller.py`.

- Para `--device xpu` (también `--device auto` si selecciona XPU), el optimizador Adam usa `foreach=False, fused=False`.
- Para CPU y CUDA no cambia la selección de implementación de Adam.
- Actualiza el banner de versión y muestra la configuración del optimizador.
- No cambia red, dataset, losses, batch, LR, checkpoints ni firmware.

Motivo: prueba aislada con PyTorch 2.14.0+xpu/Intel Arc 140V fallaba después del primer paso con los defaults de Adam, pero completó 5 pasos para batches 1, 8, 16, 32, 64 con ambas opciones desactivadas. **El entrenamiento real XPU completo no está verificado aún**.

Aplicación: extraer el ZIP desde el directorio padre de `picoAlpha` y ejecutar el mismo `run_distiller.ps1`.
