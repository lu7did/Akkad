# picoGenus — completitud de la heurística PST (v0.1.15)

## Fuentes y alcance

Se toma como autoridad **David, van den Herik, Koppel y Netanyahu**, *Genetic Algorithms for Evolving Computer Chess Programs*, sección III, figura 3, y como referencia operativa `entrenar_david_ga(1).py` entregado por el usuario.

Se mantienen los 35 parámetros (peón fijo a 100; 34 evolucionables), el cromosoma Gray de 224 bits, evaluación de cada jugada legal con búsqueda 1-ply, fitness `H**2`, selección proporcional, cruzamiento uniforme 0.75, mutación bit a bit 0.005, elitismo. Los **23 parámetros evolucionables implementados en la función del archivo de referencia no se modifican**.

**Limitación documental importante:** el artículo enuncia los 35 términos, presenta sus valores después de evolucionar y explica cómo entrenarlos, **pero no entrega una fórmula exacta de extracción para cada característica**. Los 11 términos omitidos en el ejemplo se implementan abajo mediante definiciones convencionales explícitas. Son una operacionalización razonada de la terminología del artículo, **no una reproducción demostrable, bit a bit, del evaluador privado de los autores**. No se introducen nuevos parámetros ni operadores, ni se alteran los existentes.

## Definiciones operativas de los 11 términos omitidos

El puntaje se computa en centipeones desde la perspectiva de blancas; cada característica se suma para blancas y se resta para negras (`signo=+1/-1`).

| Coeficiente | Extracción de característica | Contribución al bando |
|---|---|---|
| `BACKWARD_PAWN_PENALTY` | Número de peones sin peón vecino propio en la misma fila o detrás y cuya casilla de avance inmediato está controlada por un peón enemigo | Penalización por peón |
| `WEAK_SQUARE_PENALTY` | Número de casillas de columnas c–f en la mitad propia, atacadas por adversarios y no defendidas por peones propios | Penalización por casilla |
| `ROOK_ATTACK_KING_ADJ_FILE_ABGH` | Torre en columna adyacente a la del rey adversario, siendo la columna de ese rey a, b, g o h | Bonificación por torre |
| `ROOK_CONNECTED` | Al menos dos torres propias alineadas en fila o columna, sin piezas entre ellas | Bonificación única |
| `ROOK_BEHIND_PASSED_PAWN` | Torre detrás de un peón pasado propio en la misma columna | Bonificación por torre |
| `ROOK_ATCK_WEAK_PAWN_OPEN_COLUMN` | Torre en columna sin peón propio que contiene un peón enemigo atrasado o aislado | Bonificación por torre |
| `ROOK_COLUMN_MULT` | Torre en columna semiabierta: 1 unidad; abierta: 2 unidades | Bonificación por torre multiplicada |
| `KING_FRIENDLY_PAWN_ADVANCED1` | Peón propio en alguno de los tres archivos del escudo del rey, a distancia de dos filas delante del rey | Bonificación por peón |
| `KING_NO_ENEMY_PAWN` | No hay peones adversarios en la columna del rey propio | Penalización única |
| `KING_NO_ENEMY_PAWN_ADJ` | No hay peones adversarios en cada columna adyacente existente al rey propio | Penalización por columna |
| `KING_PRESSURE_MULT` | Cantidad de ataques de piezas propias no-rey que alcanzan el anillo de 8 casillas del rey enemigo o la casilla del rey | Bonificación por ataque |

Estas definiciones concretas se incluyen para permitir entrenamiento y revisión reproducibles. No reemplazan definiciones publicadas si se obtuviera posteriormente el código original de los autores. La terminología y los rangos sí proceden del artículo.

## Compatibilidad

- La salida JSON conserva el formato `picogenus-pst-v1` y las 34 claves actuales. **Un checkpoint PST previo no cambia de valores, pero sí cambia su interpretación** al activarse estas 11 características; se recomienda reentrenar.
- `nurse/src/nurse/genus_eval.py` ya importa `gen_pst_core` desde `picoGenus/tools/train`, por lo que Nurse y `genPST.py` ejecutan exactamente el mismo evaluador. No se duplica código ni se altera Nurse o Genesis.
- `genNNUE.py` y su función de entrenamiento quedan intactos.
- La prueba `tests/test_pst_35_v0115.py` verifica los 224 bits, el orden de genes y la activación efectiva de los 11 coeficientes en posiciones de control; requiere `python-chess`.

## Ejecución

Desde `picoGenus/tools/train`: `python -m unittest discover -s tests -p 'test_pst_35_v0115.py'`.

El script Genesis y sus rutas personalizadas no se modifican. El entrenamiento PST se puede iniciar con `--mon 2`; la red NNUE existente no requiere cambios.
