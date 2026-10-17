# Challenger v0.2.2 — intercambio estático inspirado en XCHNG

Solo se modifica `SargonEngine` para reemplazar la heurística aproximada de amenaza sobre una pieza sin defensa por una secuencia estática de capturas y recapturas sobre una casilla, usando el atacante legal de menor valor y permitiendo detener el intercambio. Se reconstruyen ataques revelados tras cada captura. No se agrega quiescence, tabla de transposiciones ni heurística moderna de búsqueda. `StockfishBrain`, `RandomBrain` y `HumanBrain` no se modifican.

## Fidelidad y límites
El diseño está informado por XCHNG/NEXTAD y POINTS del SARGON de 1978, pero **no es una traducción exacta**: emplea `python-chess` para legalidad; la combinación de intercambios usa el máximo riesgo adverso, no las reglas exactas de ajuste de POINTS; los valores son 1/3/3/5/9 y no los `PVALUE` históricos. Una secuencia codiciosa por el capturador de menor valor puede discrepar con todas las opciones legales. Esta versión debe considerarse una aproximación verificable, pendiente de equivalencia histórica.

## Comprobaciones
`python -m compileall -q src/challenger` y `python -m pytest -q tests/test_sargon_exchange.py tests/test_sargon_fidelity.py` en un entorno con dependencia `chess` instalada.
