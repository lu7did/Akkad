# picoAlpha v0.2.46 — parche incremental sobre v0.2.45

Se reemplaza únicamente `picoAlpha/tools/picoDistiller/picoDistiller.py`.

- Corrige la carga previa en RAM de los tensores de toda la base (~19 GB para 665.367 posiciones). Mantiene solo pares `position_id/game_id` en memoria y recupera P/V y 112 planos por muestra desde SQLite en modo solo lectura.
- Muestra telemetría al arrancar, durante indexación y durante cada época con barra, P, V, total y LR.
- Ctrl+C captura la interrupción y guarda `epoch_interrupted.pt` con los pesos actuales cuando ya comenzó una época. Conserva los checkpoints completos existentes y `epoch_best.pt`. Sale con código 130. No reanuda automáticamente el estado del optimizador.
- Sin cambios en arquitectura 112×1×8, pérdidas, scheduler y firmware.

Ejecutar el mismo script PowerShell de entrenamiento después de extraer en el directorio Akkad.

Validación: compilación sintáctica Python; no se dispone aquí de la base etiquetada real ni del entorno XPU para una ejecución completa.
