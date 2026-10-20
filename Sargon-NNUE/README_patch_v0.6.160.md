# Parche Sargon-NNUE v0.6.160 — Doc/Grumpy en Benchmark

## Error corregido

`sargon_benchmark.py` obtiene los perfiles mediante `brains.get()`, que llama a `brains.validate()`.
La tabla `PLAYER_CHOICES` no incluía `doc` y `EVALUATOR_CHOICES` no incluía `grumpy`.
Además, el parser común `cli_common.add_engine_args()` no contemplaba `grumpy`.

## Archivos

- `src/sargon_nnue/brains.py`: registra `doc`, `grumpy` y actualiza VERSION.
- `src/sargon_nnue/cli_common.py`: acepta `--evaluator grumpy`.
- `src/sargon_nnue/__init__.py`: actualiza la versión global.

No modifica `brains.json`, Benchmark, Doc, Grumpy ni los cálculos.

## Verificación

Compilación sintáctica de los tres módulos y comprobación de las listas de opciones.
No se ejecutó un benchmark real: el entorno de creación no tiene `python-chess`.

## Ejemplo

```powershell
python -m sargon_nnue.sargon_benchmark --brain data\brains\brains.json --ids dwarf --mode positions --positions 3
```

Aplicar sobre v0.6.159; también requiere que estén instalados los archivos de Doc/Grumpy de v0.6.156.
