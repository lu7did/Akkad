# Microchess en Sargon-NNUE — reconstrucción algorítmica experimental

Esta ampliación incorpora **GNM**, la transición conceptual de **JANUS/STATE**,
la expresión publicada **STRATGY** y seis semijugadas selectivas de intercambios
(**WCAP0/1/2, BCAP0/1/2**). No es un port del ensamblador de 1976.

- `gnm(board, color)` recorre piezas y genera jugadas una a una, delegando
  la legalidad del ajedrez moderno a `python-chess`.
- `State` identifica INITIAL, CANDIDATE, CONTINUATION, RESPONSE,
  EXCHANGE_0..3, LEGALITY y STRATEGY. El control se expresa por etapas
  de métodos Python, no por el mismo autómata ensamblador JANUS.
- `measure` calcula movilidad (jugadas de dama ponderadas por dos), MAXC y
  CC (valor de las piezas distintas amenazadas).
- `exchanges` recorre hasta tres capturas por bando en orden alternado,
  con poda selectiva de **una** captura por turno por defecto. Es una
  **aproximación greedy** a las cadenas de capturas históricas; no recupera
  la exploración de TREE ni los cortes históricos especiales.
- `strategy_quarters` utiliza aritmética entera con los coeficientes
  publicados en el documento. Se conserva el `BMAXC` duplicado como -12.
- `MicrochessEvaluator.evaluate_candidate(board, move)` ofrece la evaluación
  específica por jugada para el player microchess, incluyendo los valores
  previos `P*`, las amenazas `W*`/`B*` y los intercambios. Retorna centipeones
  **desde el lado que movió**; no forma parte del contrato general.
- `MicrochessEvaluator.evaluate(board)` expone evaluación **desde blancas**
  compatible con SARGON y SARGON-PLUS. Es una evaluación de posición
  (material, movilidad y amenazas), **no** la fórmula histórica de jugadas,
  ya que el contrato compartido no recibe la posición anterior ni la jugada.
- `MicrochessPlayer` utiliza STRATGY al seleccionar candidatos iniciales y
  aplica búsqueda iterativa con `depth` y capturas de quiescence con `qdepth`.
  Cuando depth > 1 emplea la evaluación estática en hojas; es una adaptación
  contemporánea y no una réplica de la política histórica.

## Ejecución de pruebas

Desde `Akkad/Sargon-NNUE`, con el entorno Python del proyecto activado:

```sh
python -m pytest tests/test_microchess_integration.py -q
```

La prueba funcional no pudo ejecutarse en el entorno donde se generó el parche
por ausencia de `python-chess`; la sintaxis se verificó con `compileall`.
