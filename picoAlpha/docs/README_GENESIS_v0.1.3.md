# picoAlpha — Genesis v0.1.3

Se agrega `picoAlpha/tools/train/run_genesis.ps1`, orquestador PowerShell para los seis wrappers existentes del pipeline. Se basa en el `run_genesis.ps1` aportado por el usuario (dos pasos activos y cuatro ejemplos comentados).

## Ejecución

Desde `picoAlpha/tools/train`:

```powershell
.\run_genesis.ps1 -Help
.\run_genesis.ps1 -HistoryDir 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha' -PgnPattern 'C:\Users\pedro\github\Bobby\Chess_History_pb\pgn\*.pgn' -Engine 'C:\Chess\stockfish.exe'
```

Los valores iniciales se encuentran en el bloque `param(...)` al inicio del script y pueden sobrescribirse mediante parámetros de ejecución.

| MON | Paso | Entrada | Salida |
|---:|---|---|---|
| 0 | Crear base | — | `<HistoryDir>/history.pb` (se reemplaza) |
| 1 | Cargar PGN | `<PgnPattern>` | `<HistoryDir>/history.pb` |
| 2 | Muestrear | `history.pb` | `<HistoryDir>/sample_history.pb` (se reemplaza) |
| 3 | Teacher Stockfish | `sample_history.pb` | Etiquetas en la misma base |
| 4 | Train PyTorch | `sample_history.pb` | `picoAlpha/assets/checkpoints/epoch_*.pt` y `best.pt` |
| 5 | Exportar | `picoAlpha/assets/checkpoints/best.pt` | `picoAlpha/assets/picoalpha_nnue_weights.hpp` |

`MON` inicia en 0. Cada paso comprueba que `MON` coincida con su número, imprime `⚙️ Paso xx - propósito`, ejecuta el wrapper y sólo incrementa `MON` si termina exitosamente. En cualquier error la ejecución se interrumpe. No hay avance ni reintento automático.

**Precaución:** esta secuencia es una ejecución desde cero: `create.py` elimina el histórico previo. `sampler.py` reemplaza la muestra, y los checkpoints de la carpeta configurada pueden sobrescribirse si tienen los mismos nombres. Conviene respaldar resultados antes de ejecutar de nuevo. La variable MON no queda persistida entre invocaciones.

El valor `best.pt` es un checkpoint PyTorch; para usarlo desde Nurse debe existir y cumplir el contrato de arquitectura implementado en picoAlpha Training v0.1.1.

El cambio no modifica los seis programas Python ni sus wrappers ni el directorio `Crypt`. Este entorno no dispone de PowerShell, por lo que no se ejecutó el pipeline de punta a punta.
