# Sargon-NNUE v0.6.14

## Corrección

- Se corrige el parser de `Final evaluation` del evaluator STOCKFISH.
- Stockfish puede emitir la línea tanto como `Final evaluation: +0.46 ...` como `Final evaluation      +0.46 ...`.
- La expresión regular anterior exigía los dos puntos y rechazaba una evaluación válida.
- Se agrega una prueba de regresión con la salida exacta observada en ejecución.
- No se modifican SARGON, SARGON+, ni la semántica de `--boost`.
