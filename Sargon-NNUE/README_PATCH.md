# Sargon-NNUE v0.6.183 — propagación del parámetro model para picoAlpha

## Instalación
Extraer desde la raíz `Akkad/` (el ZIP comienza en `sargon-NNUE/`), sobre la instalación que ya tiene **v0.6.182**.

## Error corregido
`brain badGyal` puede declarar `"model": "picogyal"`; antes `brains.py` rechazaba `model` como clave desconocida, `sargon_match.py` no admitía `--a-model` o `--b-model`, y `sargon_listen` no reconocía `--model`. Se corrigen **las tres capas**:

- `brains.py`: `model` entre las claves permitidas; validación `tinygyal|picogyal`, únicamente para el player `picoalpha`.
- `sargon_match.py`: define `--a-model`/`--b-model` y retransmite `--model` al listener.
- `cli_common.py`: expone `--model` a `sargon_listen` y `brains.engine_parser`.

`factory.py` y los adaptadores del parche **v0.6.182** ya propagan el argumento `model` y arrancan el motor con `--model picogyal`. No se vuelven a incluir en este parche incremental.

## Ejemplo opcional explícito
```json
"badGyal": {
  "player": "picoalpha",
  "evaluator": "null",
  "model": "picogyal",
  "engine-path": "../../picoAlpha/x86/picoAlpha/build/picoAlpha.exe",
  "network": "../../picoAlpha/data/runs/lc0/picogyal-20261026.pb.gz",
  "az-simulations": 1000,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "timeout": 30000
}
```
Si se omite `model`, el adaptador v0.6.182 lo infiere de `picogyal` o `tinygyal` en el nombre del archivo.

## Verificación
Se valida el parseo Python, el reconocimiento del modelo en el JSON, `--a-model`/`--b-model`, el traslado a `--model` en la orden del listener, y la integridad del ZIP. No se ha probado el match real en Windows.
