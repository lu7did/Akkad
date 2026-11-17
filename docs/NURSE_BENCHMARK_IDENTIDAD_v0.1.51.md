# Nurse BENCHMARK — Corrección de identidad v0.1.51

Corrección de `nurse/src/nurse/display.py` sobre v0.1.50. El encabezado ya no aplica una plantilla de player/evaluator de Nurse a procesos `type=uci`.

- `uci`: `dopey (UCI | picoSargon.exe | pesos=dopey.bin)`; `pico (UCI | picoSargon.exe | pesos=grumpy.bin)`.
- `nurse`: `dalia (Nurse | mctsp | mctse)`.
- `external`: `pixie (TCP | <nombre UCI informado>)`.

Las rutas de ejecutable y pesos son las **configuradas** en `brains.json`, no una atestación de carga por el motor. El ID real de brain sigue encabezando la línea. No se cambian comandos UCI, validaciones, ejecución, cálculos ni archivos CSV.

Prueba: `python -m unittest discover -s nurse/tests -p 'test_benchmark_identity_v0151.py' -v`.
