# Sargon-NNUE v0.6.104 — DMAX en parser de brains

## Defecto reproducible
`brains.py` v0.6.103 incorpora `dmax` en su lista permitida y transforma el campo a `--dmax 9`; pero `brains.engine_parser()` delega en `cli_common.add_engine_args()`. Una copia obsoleta de `cli_common.py` produce `error: unrecognized arguments: --dmax 9` y bloquea preflight.

## Sustitución
Reemplazar **solo** `src/sargon_nnue/cli_common.py` por el de este archivo ZIP. Se basa en el `cli_common.py` con soporte `--dmax` de v0.6.98. Conservar `brains.py` v0.6.103 y el resto de módulos.

## Comprobación de importación (desde scripts)
```
& "C:\Users\pedro\ufasta\Scripts\python.exe" -c "from sargon_nnue.brains import engine_parser; import sargon_nnue.cli_common as c; print(c.__file__); print(engine_parser().parse_args(['--player','sargon-plus','--dmax','9']).dmax)"
```
Debe informar la ruta bajo el proyecto y `9`. Si indica otro directorio, se está importando una copia distinta del paquete.

Esta corrección no altera BOOST, TURBO, RALLY, la búsqueda o las puntuaciones. Requiere prueba UCI completa en el entorno del usuario.
