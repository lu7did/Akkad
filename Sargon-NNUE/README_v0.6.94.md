# Sargon-NNUE — v0.6.94 (parche acotado de fidelidad algorítmica)

## Alcance
- `player=sargon`: búsqueda **única, profundidad fija**, alpha-beta, sin quiescence, TT, ordenamiento táctico, profundización iterativa, ni desempate aleatorio.
- `player=sargon-plus`: **sin cambios**. Continúa heredando de `SargonCore`, que se deja intacto deliberadamente para no alterar el torneo ni BOOST/TURBO.
- Todos los evaluadores se mantienen intercambiables; las reglas de integración de Stockfish no se modifican.
- No se modifican `brains.json`, RALLY, MATCH, ni herramientas UCI.

## Interpretación de parámetros Sargon
- `depth`: cantidad fija de plies, obligatoria en la semántica de búsqueda; conserva default de fábrica 2.
- `qdepth`: se acepta por compatibilidad pero se **ignora** y la profundidad táctica efectiva es cero. Así no se invalidan brains previos con `qdepth=2`.
- `iterative_deepening`: se acepta por compatibilidad, pero Sargon ejecuta exclusivamente la profundidad indicada.
- `tmax`: se acepta como parámetro de infraestructura, pero no interrumpe esta búsqueda de profundidad fija. Esto puede causar tiempos grandes a profundidades elevadas; queda indicado en el registro `tmax_enforced=false`.
- `seed`: no interviene en el desempate; el primer máximo se conserva.

## Advertencias de fidelidad
No es una emulación de la máquina histórica ni una traducción literal del ensamblador SARGON 1978. Las funciones de generación de movimientos, evaluación estática y Exchange Evaluator POINTS/XCHNG no se han contrastado bit a bit con el original. Se prioriza conservar el contrato de evaluadores externos de Sargon-NNUE. El modo CLASSIC no es necesariamente equivalente a la evaluación posicional histórica.

## Instalación
Copiar `src/sargon_nnue/players/sargon_historical.py` (nuevo) y reemplazar **únicamente** `src/sargon_nnue/players/__init__.py` sobre la distribución actual, conservando copia del original. No reemplazar `sargon.py` ni `sargon_plus.py`.

## Pruebas
```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" -m pytest -q tests/test_sargon_historical.py
```

La prueba funcional requiere `python-chess`. No considerar validado el comportamiento histórico hasta correr también el preflight y el test de integración con MATCH en Windows.

## Efecto en torneos
El brain `buddy` pasará a usar el nuevo player histórico si instalás este parche. No compares sus resultados posteriores con los de `buddy` de la campaña anterior sin identificar explícitamente la versión. `classic`, `smart` y todos los brains sXXXX/sTXX seguirán usando el código previo de Sargon-Plus.
