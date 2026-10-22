# Sargon-NNUE v0.6.179 — Validación de evaluador NULL en MATCH

## Defecto corregido

`sargon_match.py` mantenía una whitelist anticuada para `--a-evaluator null` y `--b-evaluator null`: rechazaba a `tinyalpha`, a pesar de que `brains.py` ya lo reconocía. El mensaje de error además ignoraba a `lc0` y `picosargon`.

## Corrección

El instalador ajusta solamente DOS guardas de `sargon_match.py`, en ambos lados (`a` y `b`), de forma simétrica:

* Exigen `evaluator=null` para los jugadores integrados `stockfish`, `lc0`, `picosargon`, `tinyalpha`.
* Admiten `evaluator=null` para `stockfish`, `lc0`, `random`, `picosargon`, `tinyalpha`.

No altera motores, FEN, buffers, fuentes de la red, ejecutables, arquitectura de MCTS o archivos `data`/`docs`. No reconstruye versiones antiguas del programa. No altera otras políticas no relacionadas.

## Instalación

Extraer este ZIP en la raíz de Sargon-NNUE. Desde allí:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" .\scripts\patch_match_null_v06179.py --check
& "C:\Users\pedro\ufasta\Scripts\python.exe" .\scripts\patch_match_null_v06179.py
```

El instalador crea una copia `.before_v0.6.179.bak`, verifica la sintaxis ANTES de escribir y es idempotente. Ante una estructura fuente no reconocida falla sin escribir; NO intenta adivinar un reemplazo.

## Prueba

Ejecutar `scripts\run_match.ps1` con `player=tinyalpha` / `evaluator=null` para `b` y para `a`. La corrección elimina el rechazo de argparse que informaba `requiere player stockfish o random`. Pueden aparecer errores independientes de configuración de rutas o protocolo UCI; este parche no pretende corregirlos.

## Validación realizada

Probado el instalador sobre los archivos reales `sargon_match.py` incluidos en la copia de Sargon-NNUE y el parche v0.6.164. En ambos casos cambió dos guardas, la sintaxis fue válida, y la segunda ejecución fue idempotente. No hay acceso a la instalación Windows del usuario para verificar su ejecución directa.
