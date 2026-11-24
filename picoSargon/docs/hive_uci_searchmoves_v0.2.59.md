# picoSargon x86 / Debian / macOS — búsqueda UCI por movimientos (v0.2.59)

## Alcance

Parche incremental para Akkad, base `akkad(20261122-184526).zip`. El buscador común se encuentra en `picoSargon/x86/src` y `picoSargon/x86/include`. Debian y macOS compilan esas fuentes, por lo que no se duplica la implementación.

**No modifica ARM, otros motores ni el coordinador Hive.**

## Interfaz UCI

Se aceptan los comandos estándar:

```text
position startpos
go depth 9 movetime 10000 searchmoves e2e4 d2d4
```

`depth` controla el objetivo de profundización iterativa y `movetime` es el límite máximo de pared para la solicitud. El motor puede devolver una profundidad menor si vence el límite; los campos `depth` publicados siempre indican la última profundidad completada. El límite es global para el lote, no un límite por movimiento.

La quiescencia se ajusta mediante la opción UCI anunciada:

```text
setoption name QDepth value 9
```

Adicionalmente, se acepta la extensión **no estándar** `go qdepth 9`, aplicada solo a esa búsqueda sin alterar la opción persistente:

```text
go depth 9 qdepth 9 movetime 10000 searchmoves e2e4
```

`go` sin `searchmoves` mantiene la búsqueda raíz habitual. `searchmoves` solo admite movimientos legales UCI en la posición actual; rechaza listas vacías, duplicados e ilegales. Un error devuelve `info string ERROR ...` y `bestmove 0000` sin finalizar la sesión.

## Resultados

Si `searchmoves` está presente y se completó al menos una profundidad, el motor emite una línea UCI por cada raíz autorizada, ordenadas de mejor a peor, usando `multipv` y la primera movida de `pv`:

```text
info depth 8 multipv 1 score cp 11 nodes 118409 time 6194 nps 19116 pv e2e4 string qdepth 9 qnodes 88835 root e2e4
info ply 0 depth 8 score cp 11 nodes 176624 time 10002 nps 17658 string qdepth 9 qnodes 135483
bestmove e2e4
```

**Semántica:**

- `score cp`: evaluación de cada jugada desde la perspectiva del bando al turno (convención UCI), no siempre de las blancas.
- `depth`: último nivel **completado para todo el lote**; las evaluaciones de niveles incompletos no se presentan como finales.
- `time`, `nodes`, `nps`, `qnodes` de las líneas `multipv`: trabajo acumulado en esa raíz durante los niveles completados, no solo durante el nivel final. `time` se mide en milisegundos de pared. En multihilo los tiempos de raíces paralelas se solapan y **no se deben sumar** para estimar el tiempo total del lote.
- `qdepth`: límite solicitado de quiescencia; es un límite del algoritmo, no una profundidad efectiva alcanzada medida por rama. Se informa en la extensión `string`.
- La última línea `info ply ...` resume la búsqueda completa y la acompaña el único `bestmove` estándar.
- Si vence el plazo sin completar ningún nivel, se informa `depth 0`, sin inventar evaluaciones individuales finales.

Para que todas las puntuaciones individuales sean comparables dentro de una misma solicitud, la búsqueda con `searchmoves` calcula cada raíz con ventana alpha-beta completa. No modifica el mecanismo habitual de búsqueda de `go` sin filtro, que conserva sus optimizaciones previas. Este modo restringido puede consumir más nodos que una búsqueda conjunta optimizada.

## Verificación

Prueba sin dependencias externas:

```bash
python3 picoSargon/tools/tests/test_hive_searchmoves.py \
  --binary /ruta/a/picoSargon --weights /ruta/a/grumpy.bin --cores 2
```

`--cores` se omite para builds sin MULTICORE.

Se ha compilado y probado con GCC en Linux para combinaciones MULTICORE ON/OFF y STEROIDS ON/OFF, y con el target Debian/Linux. No se ha podido compilar ni ejecutar nativamente macOS o Windows/MSVC en el entorno de preparación. Esas plataformas comparten las fuentes modificadas, pero requieren su propia verificación final.

## Exclusiones deliberadas

No se agrega listener TCP, no se implementa el scheduler Hive, no se transmite telemetría intermedia y no se cambian reglas de selección por puntuaciones provenientes de motores distintos.
