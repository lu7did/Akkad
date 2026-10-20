Sargon-NNUE v0.6.103 — admisión de dmax en brains.json

Instalar únicamente src/sargon_nnue/brains.py.
Se incorpora dmax a ENGINE_KEYS y a defaults para sargon-plus.
Se preserva la validación mediante argparse y la conversión a argumentos --dmax.
Requiere los módulos cli_common.py, factory.py, players/__init__.py y players/sargon_plus.py de v0.6.98 o posterior.
No modifica los players, BOOST, TURBO, RALLY, MATCH ni estadísticas.
