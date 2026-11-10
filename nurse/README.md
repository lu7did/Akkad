# Nurse v0.1.0 — front-end UCI independiente de Akkad

**Estado:** primera implementación funcional de la nueva arquitectura, con compatibilidad de algoritmos mediante una copia interna congelada del código original. No modifica `Sargon-NNUE/` ni reutiliza su instalación en ejecución.

## Estructura

```text
nurse/
├── src/
│   ├── sargon-nurse.py
│   ├── sargon-listen.py
│   ├── sargon-benchmark.py
│   ├── sargon-match.py
│   ├── sargon-rally.py
│   └── nurse/
│       ├── uci.py               # frente UCI
│       ├── transport.py         # proceso y TCP
│       ├── worker.py            # player RPC persistente
│       ├── evaluator.py         # evaluador RPC persistente
│       ├── evaluator_client.py  # evaluador externo y material interno
│       ├── players/             # una entrada por algoritmo
│       ├── evaluators/          # una entrada por evaluador
│       └── _legacy/             # snapshot privado de algoritmos existentes
├── scripts/
├── etc/brains/brains.json
├── data/benchmark, data/match, data/rally, data/logs
├── tests/
└── docs/
```

## Instalación

Desde `akkad/nurse`:

```powershell
python -m pip install -e .
python -m nurse.uci --brains etc/brains/brains.json --id nurse_classic
```

En Linux/macOS: `python3 -m pip install -e .` y `python3 -m nurse.uci ...`.

**UCI** en `stdout`, telemetría fechada y con emojis solo por `stderr`:

```text
uci
isready
position startpos
go movetime 1000
quit
```

El ejemplo `fishy` incluye una ruta Stockfish ilustrativa; comprobar `engine-path` por plataforma. Los demás perfiles de ejemplo requieren las dependencias y pesos correspondientes. El parámetro `retry` de `external` se expresa en **segundos**; `timeout` en **milisegundos**. `ELO` es metadato, no configura el motor.

## Formato de brains.json

Archivo raíz `{ "brains": { "nombre": { ... } } }`.

* `type=nurse`: `player="sargon.py"`, `evaluator="classic.py"` o `"null"`, `network` opcional por plataforma, `arguments` objeto, `Depth`, `QDepth`, `timeout`, `ELO`.
* `type=uci`: `player` mapa `windows/debian/macOS` de ejecutables, `evaluator="null"`, `args` opcional como array de strings; también se puede indicar un intérprete Python y el script en `args`.
* `type=external`: `ipaddress`, `port`, `retry`, `timeout` y `ELO`; abrirá un socket UCI sobre TCP.

Se aceptan perfiles sin `ELO`. Un ID inexistente causa error *antes* de iniciar el motor. Los paths se resuelven respecto de `brains.json` y de rutas históricas de Akkad, con trazas de las rutas candidatas si el archivo falta.

## Contrato de player

Módulos individuales `python -m nurse.players.<nombre>`. Para `sargon-plus` se usa `sargon_plus`.

```text
--version               nombre y versión del módulo
--id                    UUID estable por tipo de módulo
--analyze '{"fen":"..."}'  analiza una posición e informa JSON
--serve --config '{...}' servidor JSON Lines persistente por stdin/stdout
```

En modo servidor, entrada: `{"cmd":"choose","fen":"...","go":"go movetime 1000"}`. Salida: `{"ok":true,"bestmove":"e2e4","score_cp":20,"depth":2,"qdepth":0,"nodes":123,"time":10,"nps":12300,"turn_white":true}`. Se pueden enviar `{"cmd":"ready"}` y `{"cmd":"quit"}`. El worker permanece cargado durante toda la sesión; no se crea un proceso para cada jugada.

## Contrato de evaluador

`python -m nurse.evaluators.classic --version` (o `--id`, `--serve`, `--analyze`). Un evaluador retorna **cp desde blancas**, nunca desde el lado que mueve. El comando externo equivalente usa JSON Lines por `stdin`/`stdout`:

```json
{"cmd":"evaluate","fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","move":"e2e4"}
```

Respuesta: `{"cp":23,"perspective":"white"}`. El campo `move` es opcional: cuando existe, la posición indicada por `fen` se evalúa *después* de esa jugada legal. En modo `type=nurse`, `evaluator` también puede ser una ruta a un evaluador JSON Lines ejecutable o un script Python; se mantiene un único proceso hasta el cierre de la sesión. Si `evaluator="null"`, el player usa su lógica interna disponible o, en búsquedas heredadas que precisan evaluación, una heurística material básica. Evaluadores especializados que exigen semántica de políticas neuronales pueden requerir su evaluador compatible.

**Canal de salida:** los mensajes UCI externos solo aparecen en `stdout` de Nurse. Los módulos worker usan `stdout` exclusivamente para JSON RPC y `stderr` para telemetría; esto resuelve la ambigüedad de permitir texto libre de los players sin corromper ambos protocolos.

## Herramientas

```powershell
python -m nurse.listen --brains etc/brains/brains.json --id fishy --ip 0.0.0.0 --port 6200
python -m nurse.benchmark --brain etc/brains/brains.json --ids fishy nurse_classic --positions 10
python -m nurse.benchmark --brain etc/brains/brains.json --ids fishy --bratko-kopec
python -m nurse.match --brain etc/brains/brains.json --idA fishy --idB nurse_classic --pairs 1
python -m nurse.rally --help
```

`benchmark`, `match` y `rally` son copias adaptadas de sus algoritmos de control de torneos y estadísticas: **todos** arrancan `nurse.uci` como motor hijo. Se conserva el análisis Bratko–Kopec de la versión Sargon-NNUE 0.6.210, con matriz y gráfico de barras en telemetría. Las pruebas de partidas/torneos reales deben ejecutarse en el entorno con `python-chess` instalado.

## Consideraciones de concurrencia y seguridad

* `go` se ejecuta en un hilo para no bloquear lectura de `stop`/`quit`. En UCI nativo y TCP, `stop` se reenvía. En players Python heredados, la búsqueda no es interrumpible de manera preemptiva; finaliza según su timeout interno o se libera al terminar el proceso. Es una limitación explícita de esta fase.
* Cada sesión TCP del listener tiene su propio objeto Nurse y su propio proceso motor, para evitar entremezclar partidas.
* En `external`, el primer fallo de conexión es explícito; después de una desconexión se reintenta con intervalo `retry`. Una búsqueda interrumpida produce `bestmove 0000`: **no** se vuelve a emitir silenciosamente una búsqueda con estado posiblemente desincronizado.
* `engine-path` y argumentos se pasan como lista, sin shell, evitando sustituciones de comandos.
* `rating_elo` histórico se denomina `ELO`; Nurse no lo interpreta como ajuste de fuerza.

## Límites de verificación

Pruebas automatizadas de handshake, `bestmove`, proceso persistente, configuración inválida y socket inalcanzable. No se ejecutaron motores neuronales reales ni partidas completas en este entorno porque `python-chess` no está instalado y no hay conectividad para instalarlo. **No presentar esta versión como sustitución lista para producción de Sargon-NNUE** hasta completar pruebas end-to-end para todas las combinaciones de players/evaluadores. El snapshot `_legacy` permite preservar el comportamiento sin afectar el repositorio original, pero sigue pendiente la reimplementación nativa independiente de cada algoritmo si se desea eliminar esa dependencia interna.

## Temporización uniforme (v0.1.2)

`tmax` es el presupuesto máximo de búsqueda por jugada, `timeout` el margen de comunicación y `warmup_movetime=tmax`. Todos se expresan en milisegundos y aplican a `nurse`, `uci` y `external`. Ver `docs/timing-v0.1.2.md` para reglas, límites y pruebas.
