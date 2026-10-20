# Sargon-NNUE v0.6.138 — AlphaZero con ZNPZ y ZCLASSIC (experimental)

## Alcance

Este parche **no modifica el algoritmo PUCT**, la búsqueda, los contadores `N/W/Q`, el backup ni los límites de simulaciones del player AlphaZero. Añade dos evaluadores con el **mismo contrato `evaluate_pv(board)`** utilizado por el evaluador neuronal LC0:

- `player=alphazero`, `evaluator=lc0`: sin cambios (política y WDL de la red LC0).
- `player=alphazero`, `evaluator=znpz`: política sintetizada desde un checkpoint NPZ **existente** y valor procedente del mismo evaluador NPZ.
- `player=alphazero`, `evaluator=zclassic`: política sintetizada desde el evaluador Classic de Sargon y valor de ese evaluador.

No se entrenan nuevos pesos ni una cabeza de política. `znpz` **rechaza un checkpoint ausente, incompleto o de arquitectura incompatible**; no genera una red aleatoria de reemplazo.

## Contrato P/V

Sea `s` la posición actual, `a_i` cada movimiento legal y `cp_blancas(s)` el resultado del evaluador original, expresado en centipawns desde la perspectiva de blancas. Sea `sign=+1` cuando mueve blancas y `sign=-1` cuando mueve negras:

- `V(s) = tanh(sign * cp_blancas(s) / z_value_scale)` (predeterminado 800 cp).
- `v_i = sign * cp_blancas(s después de a_i)` (signo **siempre desde el jugador que elige**).
- `P(s,a_i) = (1-epsilon) * softmax(v_i / temperature) + epsilon / num_legales`.
- `temperature=100.0` cp y `epsilon=0.01` predeterminados; Softmax estable mediante resta del máximo.
- Si la jugada termina la partida, se asigna a esa candidata el puntaje exacto de victoria/derrota/tablas a efectos de priorización, sin delegarlo a las heurísticas.
- Para entregar el contrato `NeuralEvaluation`, la no-terminal se codifica como `W=(1+V)/2`, `D=0`, `L=(1-V)/2`; el valor de PUCT es `Q = W-L = V`. **No son probabilidades WDL calibradas estadísticamente.** En estados terminales se entrega W/D/L exacto.

**Importante:** `P` es una distribución heurística sobre movimientos legales; **no se precargan visitas `N`, totales `W` ni valores `Q` de MCTS**. Dichos contadores siguen iniciándose en cero y solo las simulaciones reales del player los modifican.

## Parámetros

| CLI / brain | Por defecto | Descripción |
| --- | ---: | --- |
| `--player alphazero` | — | Motor MCTS PUCT existente. |
| `--evaluator znpz` | — | Requiere `--network` apuntando a un `.npz` entrenado. |
| `--evaluator zclassic` | — | Evaluación Classic; no requiere red. |
| `--z-temperature` | `100.0` | Temperatura Softmax en centipawns (finito, >0). |
| `--z-value-scale` | `800.0` | Escala para transformar CP a `[-1,+1]` (finito, >0). |
| `--z-uniform-mix` | `0.01` | Mezcla uniforme: `0 <= epsilon < 1`. |
| `--az-simulations` | `128` | Máximo de simulaciones MCTS por jugada (sin cambios). |
| `--az-cpuct` | `1.5` | Constante de exploración PUCT (sin cambios). |
| `--tmax` | `15000` | Tiempo cooperativo máximo por jugada, milisegundos (sin cambios). |

Los parámetros `z-*` solo afectan `znpz`/`zclassic`. El evaluador LC0 previo mantiene su comportamiento.

## Ejemplo `brains.json`

Añadir dentro del objeto `"brains"` existente:

```json
"alphazero_znpz": {
  "player": "alphazero",
  "evaluator": "znpz",
  "network": "C:/ruta/a/mi_checkpoint_entrenado.npz",
  "az-simulations": 128,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "z-temperature": 100.0,
  "z-value-scale": 800.0,
  "z-uniform-mix": 0.01
},
"alphazero_zclassic": {
  "player": "alphazero",
  "evaluator": "zclassic",
  "az-simulations": 128,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "z-temperature": 100.0,
  "z-value-scale": 800.0,
  "z-uniform-mix": 0.01
}
```

**Sustituir `network` por un checkpoint realmente existente.** El ejemplo representa entradas dentro del JSON, no un JSON completo.

Desde `scripts`:

```powershell
.\sargon_match.ps1 --brain ../data/brains/brains.json --pairs 2 --idA alphazero_znpz --idB alphazero_zclassic
```

O probar el UCI STDIN de manera directa:

```powershell
.\sargon_stdin.ps1 --player alphazero --evaluator zclassic --az-simulations 16 --tmax 15000
```

## Observaciones experimentales

- En una posición con `M` movimientos legales, cada expansión no terminal realiza aproximadamente **M+1 evaluaciones** del evaluador subyacente, frente a una inferencia de LC0 que entrega conjuntamente política y valor. La latencia puede ser sustancialmente diferente.
- `msec/nodo` entre motores de diferente arquitectura **no es una medida uniforme**. Comparar tanto tiempo fijo como simulaciones fijas.
- Softmax es una priorización de búsqueda, **no una probabilidad calibrada de ganar**.
- Con el mismo evaluador, comparar primero `P` uniforme versus `P` derivada de Softmax sería un control experimental útil; no incluido como nueva modalidad en este parche.
- El evaluador entrega centipawns orientados a blancas para jugadores clásicos si también se utiliza en ellos; la ruta AlphaZero consume `evaluate_pv`.

## Archivos modificados

```text
src/sargon_nnue/__init__.py
src/sargon_nnue/brains.py
src/sargon_nnue/cli_common.py
src/sargon_nnue/evaluators/__init__.py
src/sargon_nnue/evaluators/zpolicy.py   (nuevo)
src/sargon_nnue/factory.py
src/sargon_nnue/players/alphazero.py
src/sargon_nnue/sargon_match.py
tests/test_zpolicy_v06138.py           (nuevo)
```

No se modifica `src/sargon_nnue/players/sargon_plus.py`, los demás players, los pesos NPZ ni la función `_simulation`/`_expand`/`pick` de AlphaZero.

## Validación

Se comprobó en el entorno de generación: compilación de sintaxis de todos los archivos Python, rutas de argumentos CLI/brains/MATCH y pruebas aisladas de normalización/signos/terminales usando un tablero simulado. **No se dispone aquí de `python-chess` y la red NPZ entrenada del usuario**, por lo que no se certifica un torneo real ni una ejecución integral; se incluye prueba automatizada para ejecutarse en `ufasta`:

```powershell
cd C:\Users\pedro\github\bobby\sargon-nnue\Sargon-NNUE
$env:PYTHONPATH = (Resolve-Path .\src).Path
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m unittest discover -s tests -p 'test_zpolicy_v06138.py' -v
```

A continuación probar una partida corta antes de lanzar un rally, especialmente con `znpz`.
