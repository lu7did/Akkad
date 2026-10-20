# v0.6.34 — Diagnóstico de memoria XPU

- `--torch-foreach {off,auto,on}` (por defecto `off`) para los optimizadores PyTorch que soportan este parámetro. `off` limita buffers temporales multi-tensor que algunas implementaciones crean.
- Mensaje específico para `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY`, con alternativas verificables.
- Versión actualizada en telemetría.
- No modifica modelo, codificación, objetivos, persistencia ni el backend NumPy.

El defecto confirmado es la ausencia de diagnóstico específico de memoria; no está confirmado que foreach sea la causa del agotamiento XPU.
