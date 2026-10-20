# Sargon Arbiter v0.6.157 — experimental

Compara la **evaluación estática** de uno o más brains sobre los mismos FEN. No ejecuta `Player.choose()` ni una búsqueda alfa-beta/MCTS: compara los evaluadores y no la fuerza del jugador.

## Instalación

Copiar `src/sargon_nnue/sargon_arbiter.py` dentro del paquete del proyecto Sargon-NNUE v0.6.156. El archivo `fens_ejemplo.txt` es una muestra de entrada. No se modifica ningún otro módulo.

## Ejemplos

Desde la raíz del proyecto, en el entorno `ufasta` que ya contiene las dependencias de Sargon-NNUE:

```powershell
python -m sargon_nnue.sargon_arbiter --brain data\brains\brains.json --ids doc grumpy flash --fen data\test\posiciones.fen --tolerance 30 --out data\test\arbiter.csv --summary data\test\arbiter_pairs.csv
```

El argumento `--ids` recibe los **identificadores de brains**, no los nombres de los evaluadores: `doc` y `grumpy` son ejemplos solo si efectivamente existen como claves de `brains.json`.

```powershell
python -m sargon_nnue.sargon_arbiter --brain data\brains\brains.json --fen fens_ejemplo.txt
```

Sin `--ids` intenta todos los brains. Los que tengan `evaluator=null` o dependencias no disponibles se informan en stderr y no participan en comparaciones. El proceso devuelve código 2 cuando hay brains no evaluables, 1 ante error general y 0 si todos se evaluaron y existen al menos dos comparables.

## Entrada

Texto UTF-8 con un FEN por línea. Se ignoran comentarios que comienzan con `#` y líneas vacías. Opcionalmente: `etiqueta<TAB>FEN`. Los FEN deben ser posiciones válidas para `python-chess`.

## Salidas

* `arbiter_results.csv`: posición, FEN y una columna por brain evaluado; valores en centipeones desde el punto de vista de las blancas.
* `arbiter_summary.csv`: para cada pareja, error absoluto medio (MAE), diferencia máxima y cantidad de posiciones dentro/fuera de la tolerancia.

Por defecto, la tolerancia de similitud es de ±30 centipeones. Esta tolerancia es **operativa, no estadística**: evaluadores distintos pueden emplear escalas y calibraciones diferentes. Comparar sus diferencias no mide fuerza, precisión ni Elo.

**Advertencia sobre LC0:** un FEN aislado no contiene el historial de posiciones que algunas redes LC0 requieren. En modo `allow-incomplete`, su evaluación puede diferir de la obtenida en una partida real. Para estudios de paridad estricta se necesitaría un formato de posiciones con historial, todavía no implementado aquí.

**Advertencia sobre Stockfish:** `player=stockfish` usa `evaluator=null` y no es comparable en este modo. Un brain con `evaluator=stockfish` sí se puede evaluar si dispone de un `stockfish-path` válido.

La v0.6.157 no actualiza los Elo, no altera los brains ni reescribe las posiciones.
