# Sargon-NNUE v0.6.1

Refactorización arquitectónica de Sargon-NNUE orientada a separar **evaluación de posición** de **selección de jugada**.

## Programas

- `sargon-gui`: GUI humana. No importa evaluadores ni players; se conecta exclusivamente por TCP/UCI, por defecto a `127.0.0.1:6200`.
- `sargon-selfplay`: autojuego/evaluación directa en proceso. Permite configurar por separado los motores blanco y negro y opcionalmente entrenar redes NPZ locales con `--auto`.
- `sargon-train`: entrenamiento/evaluación sobre PGN. En v0.6.1 el aprendizaje local está implementado sólo para el formato NPZ heredado; evaluadores externos rechazan explícitamente `--train`.
- `sargon-listen`: servidor UCI único. `--mode TCP` usa red y tolera reconexiones; `--mode STDIN` usa stdin/stdout y envía toda telemetría a stderr.

## Evaluadores (`nnue-evaluator`)

Todos retornan un entero en **centipawns desde la perspectiva de blancas**.

- `classic`: Sargón clásico sin NNUE (manager dummy conceptual).
- `npz`: compatibilidad con los checkpoints `.npz` de Sargon-NNUE v0.5.x.
- `cerebrum-1.1`: manager Cerebrum 1.1 default `2x(768->128)->32->2`; acepta directamente `epoch-XX.txt` (float) y `epoch-XX-q.txt` (cuantizado), lee `wr=`/`mt=` y reproduce la combinación oficial de ambas salidas.
- `cerebrum-2`: manager Cerebrum 2.0 para la arquitectura cuantizada por defecto `2x(768->256)->32->1`; acepta el texto cuantizado (`network.txt` / `epoch-*-q.txt`) y el binario convertido `.nn`. El alias `cerebrum` se conserva para V2.0.

## Players (`nnue-player`)

- `random`: una jugada legal al azar; no necesita el valor del evaluador para decidir.
- `sargon`: negamax/minimax equivalente con alpha-beta a profundidad fija.
- `sargon-plus`: Sargón con profundización selectiva sucesiva. Primero analiza todas las jugadas a profundidad base, conserva las mejores candidatas y profundiza eliminando aproximadamente la mitad en cada ronda, sujeto a `--dmax` y `--tmax`.
- `cerebrum`: shell experimental separado; en v0.6.1 usa una búsqueda alpha-beta conservadora sobre el evaluador configurado para permitir futura divergencia.
- `stockfish`, `sunfish`, `external`: wrapper UCI de proceso externo mediante `--engine-path`.

## Estructura

```text
src/sargon_nnue/
  evaluators/
  players/
  sargon_gui.py
  sargon_selfplay.py
  sargon_train.py
  sargon_listen.py
data/
  pgn/
  nnue/
scripts/
tests/
```

`docs/` pertenece al espacio de trabajo pero se excluye deliberadamente de las entregas/versiones para no pisar documentación acumulada.

## Instalación

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m pip install -e .
```

o bien:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m pip install -r requirements.txt
```

Para ejecutar sin instalación editable, defina `PYTHONPATH=.\src`.

## Ejemplos

Listener clásico:

```powershell
python -m sargon_nnue.sargon_listen --mode TCP --port 6200 --evaluator classic --player sargon --depth 2
```

Mismo player con red Sargon-NNUE heredada:

```powershell
python -m sargon_nnue.sargon_listen --mode TCP --port 6200 --evaluator npz --network .\data\nnue\checkpoint.npz --player sargon --depth 2
```

Cerebrum evaluado por Sargón:

```powershell
python -m sargon_nnue.sargon_listen --mode TCP --port 6200 --evaluator cerebrum --network .\data\nnue\cerebrum-v2.0.nn --player sargon --depth 2
```

Stockfish como player exógeno:

```powershell
python -m sargon_nnue.sargon_listen --mode TCP --port 6200 --evaluator classic --player stockfish --engine-path C:\ruta\stockfish.exe --movetime 2000
```


### Cerebrum 1.1

No es necesario convertir la red entrenada por Cerebrum 1.1. Puede usarse directamente:

```powershell
C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_listen `
    --mode TCP --port 6200 `
    --evaluator cerebrum-1.1 `
    --network .\data\nnue\epoch-11-q.txt `
    --player sargon --depth 2
```

También se acepta `epoch-11.txt` (full precision). El evaluator detecta automáticamente si la red es estándar o cuantizada. Cerebrum 1.1 default usa `2x(768->128)->32->2`; una red entrenada con otra arquitectura se rechaza explícitamente.

## Alcance deliberado de v0.6.1

Esta versión establece el contrato modular y una línea funcional mínima verificable. No intenta importar directamente redes Stockfish `.nnue`: esas redes usan representaciones/arquitecturas específicas y se incorporarán mediante un manager separado, no mediante reinterpretación del formato Cerebrum o NPZ. Tampoco replica aún el algoritmo de búsqueda C de Cerebrum; el player `CEREBRUM` queda separado precisamente para que esa evolución no afecte a los evaluadores.

---

## Arquitectura consolidada SARGON / SARGON+ (v0.6.21)

### 1. SargonCore como única línea base

Desde v0.6.21 el player SARGON canónico está implementado por `SargonCore`.
`SargonPlayer` se conserva como alias público compatible de `SargonCore`. `SargonPlusPlayer`
hereda directamente de `SargonCore`; por lo tanto, una corrección futura del algoritmo base,
de la evaluación terminal, del qsearch, del manejo de tiempo o de un bug del core queda
automáticamente disponible para SARGON+ salvo que una extensión documentada intercepte
explícitamente el punto de extensión correspondiente.

Invariante de paridad: con `--boost 0 --turbo 0`, SARGON+ debe utilizar el mismo camino de
búsqueda que SargonCore. La suite incluye un test de paridad básico sobre posición inicial.

### 2. Política de tiempo del Core: depth 1 obligatorio y seguro

`--tmax` es un presupuesto total por jugada, pero **no puede interrumpir depth 1**.
La razón es semántica: el player debe producir al menos una comparación completa de todos
los movimientos raíz antes de permitir cualquier guardrail interno.

Secuencia:

1. Se ejecuta depth 1 completo sin deadline interno.
2. Se mide su tiempo real `T1`.
3. Si `T1 >= tmax`, se juega el resultado completo de depth 1 y no se inicia otro nivel.
4. Si `T1 < tmax`, el presupuesto restante para depth 2+ es `tmax - T1`.
5. Depth 2 y superiores pueden ser interrumpidos por el deadline total original.
6. Una iteración parcial nunca reemplaza al último nivel completo.

Si depth 1 por sí solo consume o supera `tmax`, la telemetría usa `❗`, no GUARDRAIL:

```text
❗ BASELEVEL SARGON time: levels=1/3 root=35/35 root_pct=100.0% ... action=stop-after-mandatory-level
```

No es un guardrail porque no quedan movimientos raíz de ese nivel sin calcular. El coste
real puede exceder `tmax`; esta regla garantiza una decisión completa frente al guardrail
interno, pero **no puede garantizar que el reloj externo de la partida no expire** si depth 1
resulta patológicamente caro.

Si el corte ocurre en depth >= 2, se conserva la semántica:

```text
⚠️ GUARDRAIL SARGON time: levels=2/3 attempted=3 root=17/49 root_pct=34.7% ... fallback=last-complete-level
```

### 3. Separación conceptual Core / BOOST / TURBO

- **SargonCore** define qué significa buscar a `--depth/--qdepth`, cómo producir siempre un
  nivel raíz completo y cómo aplicar `--tmax` a niveles superiores.
- **BOOST (`🚀`)** contiene optimizaciones del algoritmo de búsqueda: ordering, PVS, TT,
  SEE, LMR y podas. Su objetivo es reducir o reorganizar el árbol sin administrar el reloj.
- **TURBO (`⚡`)** queda reservado para administración adaptativa de recursos: clock
  controller, complexity model, full-width adaptativo y candidate selection adaptativa.
  TURBO debe observar el coste real del árbol que resulte del Core+BOOST y no depender de
  detalles internos de cada optimización BOOST.

### 4. Sintaxis uniforme de máscaras

`--boost` acepta una máscara de 16 bits (`0..65535`) y `--turbo` una máscara de 8 bits
(`0..255`). Ambos argumentos aceptan:

```text
13          decimal
0x000D      hexadecimal
1101b       binario con sufijo b
0b1101      binario convencional (también aceptado)
```

Los bits son independientes. Ya no existe la semántica acumulativa histórica de `--boost N`.
Por ejemplo, `--boost 13` significa máscara decimal 13 = `0x000D` = bits 0, 2 y 3.

### 5. Mapa BOOST de 16 bits

Las trece optimizaciones históricas se conservan individualmente en bits 0..12:

| bit | máscara | algoritmo |
|---:|---:|---|
| 0 | `0x0001` | History heuristic |
| 1 | `0x0002` | Killer moves |
| 2 | `0x0004` | PVS / NegaScout |
| 3 | `0x0008` | TT bounds |
| 4 | `0x0010` | Hash move first |
| 5 | `0x0020` | SEE pruning |
| 6 | `0x0040` | Aspiration windows |
| 7 | `0x0080` | Late Move Reductions |
| 8 | `0x0100` | Futility + Reverse Futility |
| 9 | `0x0200` | Delta pruning en qsearch |
| 10 | `0x0400` | Razoring |
| 11 | `0x0800` | Null Move pruning |
| 12 | `0x1000` | ProbCut + MultiCut |
| 13..15 | `0xE000` | reservados |

Cada bit activo se anuncia una vez al inicio mediante `🚀`. No se vuelca a consola cada
intervención interna de BOOST; esos eventos sólo deberán emerger si producen una condición
excepcional o mediante contadores/resúmenes específicos de auditoría.

La ruta avanzada de SARGON+ fue desacoplada de PVS: activar TT, SEE, LMR u otra función
avanzada ya no debe encender PVS implícitamente. PVS sólo usa ventanas nulas cuando su bit
`0x0004` está activo.

### 6. TURBO: arquitectura acordada

Máscara inicial:

| bit | máscara | actuador |
|---:|---:|---|
| 0 | `0x01` | Adaptive Full Width |
| 1 | `0x02` | Adaptive Candidate Selection |
| 2..7 | `0xFC` | reservados |

Los dos modelos compartidos no consumen bits:

- **Clock Controller**: estima el presupuesto real de la jugada a partir de `tmax` y, en
  una implementación futura, del reloj UCI remanente.
- **Complexity / Cost Model**: estima el coste del siguiente nivel usando datos observados
  de la misma búsqueda (tiempos, nodos, crecimiento efectivo, qsearch, latencia del
  evaluador, cache, re-searches, etc.).

Jerarquía prevista, para evitar controladores en conflicto:

```text
CLOCK CONTROLLER
      ↓
presupuesto B
      ↓
COMPLEXITY / COST MODEL
      ↓
¿cabe el próximo nivel full-width?
      ├─ sí → buscarlo completo
      └─ no → FULL WIDTH decide no iniciarlo
                    ↓
             CANDIDATE SELECTION
             usa el presupuesto sobrante
```

Propiedad requerida: si el `--depth/--qdepth` solicitado cabe dentro del presupuesto,
TURBO debe ser neutral y no cambiar la búsqueda.

#### Adaptive Full Width (`0x01`)

Debe decidir si conviene **iniciar** el siguiente nivel completo. No se basa en una tasa
binaria fija de fallos sino en el coste observado. Un timeout parcial aporta información
censurada: si se consumieron `t` segundos y se completó una fracción `p` del root, el coste
total del nivel puede estimarse inicialmente como `t/p`, sujeto a un modelo más robusto.
Los errores de predicción recalibran el modelo en las jugadas siguientes.

#### Adaptive Candidate Selection (`0x02`)

Sólo entra cuando existe al menos un nivel completo inferior. No debe usar un K fijo. La
cantidad de candidatos debe surgir del presupuesto y del coste proyectado del nivel superior.
Una primera aproximación conceptual es:

```text
fracción viable = tiempo disponible / coste full-width proyectado
K ≈ N * fracción viable
```

La versión más sólida utiliza coste individual proyectado por movimiento raíz y agrega
candidatos por ranking hasta que la suma de costes esperados alcance el presupuesto.

Precaución: alpha-beta/PVS puede devolver bounds y no scores exactos para todos los root
moves. La selección futura debe preservar `EXACT/LOWER/UPPER` o realizar una comparación
conservadora; no debe fingir que todos los valores parciales son scores minimax exactos.

### 7. Complejidad efectiva

No se fijará una regla rígida tipo `if legal_moves > 40`. La cantidad de movimientos legales
puede contribuir a una estimación inicial, pero la señal principal debe ser el crecimiento
observado del árbol:

```text
b_eff(d) = nodes(d) / nodes(d-1)
```

junto con tiempo real por nivel. Dos posiciones con igual número de movimientos legales
pueden tener complejidad muy distinta por jaques, capturas, qsearch y re-searches.

### 8. Clock Controller

El presupuesto final deberá respetar:

```text
B = min(tmax, B_clock)
```

`B_clock` no puede calcularse sin algún modelo de jugadas restantes si UCI no aporta
`movestogo`. No se fijará arbitrariamente `remaining/30`; la estrategia acordada es aprender
o estimar desde datos reales y permanecer no invasiva mientras la evidencia sea insuficiente.

### 9. Interacción BOOST ↔ TURBO

- History/Killer, TT/Hash y SEE son naturalmente compatibles con TURBO porque reducen o
  ordenan el coste que luego observa el modelo.
- PVS/Aspiration pueden provocar re-searches; el Cost Model debe aprender el coste total
  observado del nivel, no intentar predecir manualmente cada re-search.
- LMR, Futility, Razoring, Null Move y ProbCut/MultiCut acumulan selectividad interna.
  Combinarlos con Candidate Selection (selectividad en raíz) requiere benchmarking separado.
- Null Move (`0x0800`) y ProbCut/MultiCut (`0x1000`) son los casos de mayor cautela por
  selectividad compuesta y, en el caso de Null Move, posiciones propensas a zugzwang.
- ProbCut/MultiCut tiene poco efecto esperado en búsquedas de depth 3–4 porque sus umbrales
  actuales entran principalmente a depth 5/6 o superiores.

### 10. Estado de implementación en v0.6.22

El Core y BOOST conservan la arquitectura de v0.6.21 y TURBO pasa a estar operativo:

- `--turbo 0` es la línea de base estricta y delega en el scheduler canónico de `SargonCore`.
- `0x01` activa Adaptive Full Width: evita iniciar un nivel completo cuando el coste empírico
  proyectado supera el presupuesto restante.
- `0x02` activa Adaptive Candidate Selection: si el nivel completo no cabe, calcula `K` desde
  la fracción de presupuesto viable y profundiza sólo candidatos ordenados por el último nivel
  completo. No existe un `K` fijo.
- El Complexity/Cost Model aprende de tiempos full-width consecutivos. Un timeout parcial se
  incorpora como observación censurada `t/p`. Mientras no hay evidencia suficiente, TURBO es
  deliberadamente neutral.
- `0x03` combina ambos actuadores según la jerarquía Clock → Cost Model → Full Width → Candidates.
- Bits 2..7 continúan reservados.
