# picoGenus — corrección de cierre v0.1.13

## Error

`genPST.py` y `genNNUE.py` imprimían `dst` al finalizar, pero esa variable no existía en `main()`. Esto provocaba `NameError` **después** de ejecutar la evolución y escribir checkpoints, causando que Genesis informara falsamente un fallo del entrenamiento.

## Corrección exacta

- `genPST.py`: `output={dst}` pasa a `output={args.out}`.
- `genNNUE.py`: `output={dst}` pasa a `output={a.out}`.

No hay cambios en algoritmos genéticos, métricas, checkpoints, telemetría ni `run_genesis.ps1`.

## Cómo leer el error PST

Para cada cromosoma se prueban las `N` posiciones etiquetadas mediante una búsqueda de un ply con el evaluador PST. `H` es el número de jugadas elegidas que coinciden exactamente con `teacher_uci`. El error observado para ese cromosoma es `E=N-H`, medido en **jugadas no coincidentes**, no en centipeones. `error_min` indica el menor `E` entre los individuos evaluados en la generación. `error_mean` es el promedio aritmético de `E` en esa generación (o entre los individuos ya evaluados mientras progresa). El criterio evolutivo sigue siendo maximizar `fitness=H**2`.

Ejemplo: con `N=1000`, si el mejor individuo obtiene `H=230`, `error_min=770` y `fitness=52900`. Si los errores de los 100 individuos promedian 820, `error_mean=820`. El porcentaje de aciertos del mejor sería 23%, pero la telemetría `error_min` no es un porcentaje.

La evaluación por coincidencia de una única jugada de búsqueda superficial no equivale a medir el error numérico de Stockfish ni demuestra la fuerza ajedrecística del motor.

## Validación

`tests/test_final_output_v0113.py` prueba el recorrido de cierre de ambos `main()` con evolución simulada: escritura de salida y checkpoint por generación y ausencia de `NameError`. Pasa 2/2 en el entorno de prueba. Se simula `chess` en la importación de PST porque `python-chess` no está instalado; no se ha ejecutado entrenamiento real en Windows.
