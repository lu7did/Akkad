# Microchess v0.3.0 / Sargon-NNUE v0.6.194 — reconstrucción experimental

Parche **incremental** sobre la rama que ya incorpora `microchess` en las fábricas,
`brains.json` y CLI. No sobrescribe dichas fábricas ni las otras herramientas.

## Implementado

- Tabla de piezas: hasta 32 entradas de identidad estable (más piezas extra en
  FEN con promociones). Las casillas son 0..63, `8*rank+file`, y las capturas
  utilizan el marcador 0xFF. Aplicar y deshacer capturas, enroque, al paso y
  promociones preserva la tabla; `python-chess` mantiene legalidad e historia.
- GNM: `NEWP` (tabla de piezas), `NEX` (direcciones), avance por distancia de
  piezas deslizantes, con comprobación de bordes. El resultado se filtra por
  movimientos legales de `python-chess`; enroque, al paso y promociones se
  recuperan mediante esa autoridad. No se ordenan candidatos arbitrariamente.
- JANUS: coordinador ejecutable con fases INITIAL, CANDIDATE, LEGALITY,
  CONTINUATION, RESPONSE, intercambio y STRATEGY; registro de estados trazable.
- MOB: movimientos geométricos de dama con peso doble; MAXC y CC: mejor
  captura y suma única de piezas amenazadas. El análisis de ambos bandos no
  altera artificialmente el turno.
- TREE: explora hasta tres capturas por bando (6 plies), varios candidatos por
  etapa, parada anticipada y decisiones alternativas. La referencia WCAP0 es
  la captura del candidato; WCAP1 y WCAP2 proceden de las siguientes propias.
  BCAP0,1,2 proceden de las respuestas adversarias.
- STRATGY: coeficientes enteros `4*V` documentados; se conserva el `BMAXC`
  duplicado del documento, representado como -12.
- Player: a profundidad 1 usa selección directa por STRATGY. Profundidades
  superiores conservan evaluación por jugada en cada nivel, usando una
  **extensión moderna** minimax; `qdepth=0` permite no usar quiescence.
- Compatibilidad: el evaluador sigue ofreciendo `evaluate(board)` en cp
  **desde blancas** para SARGON/SARGON-PLUS y demás buscadores; el player puede
  usar CLASSIC, NPZ, LC0 u otros evaluadores con ese contrato. La evaluación
  posicional intercambiable sigue siendo una *proyección* de MOB/MAXC/CC y
  material, no la STRATGY contextual exacta.

## Límites de fidelidad aún existentes

1. El listado ensamblador original debe usarse para verificar el orden de
   piezas, valores originales del material, el detalle de las transiciones
   JANUS/TREE y terminación de intercambios con peones/reyes. Se evita
   atribuir equivalencia de instrucción a instrucción sin esa verificación.
2. TREE es una búsqueda de capturas alternadas limitada por `branch=2` en el
   player para contener el costo Python. No impone casilla única y no ha sido
   demostrado que reproduzca exactamente las heurísticas del original.
3. Los estados y estadísticas históricos se reconstruyeron desde la descripción
   documental; `python-chess` implementa jaques, enroque, al paso y promoción.
4. La correspondencia exacta del estado previo `P`, las amenazas `W/B` y los
   niveles `CAP` debe validarse con posiciones y trazas del ensamblador.
5. El evaluador compatible con otros players no puede calcular la STRATGY de
   **una jugada** sin recibir también la jugada candidata. No se cambia el
   contrato `evaluate(board)` para forzar un significado inexistente.
6. La profundidad superior a 1 y quiescence siguen siendo extensiones no
   históricas. La combinación de puntuaciones a profundidad mayor que 1 se
   define como promedio del valor contextual inmediato y la continuación.
7. El cálculo contextual puede resultar **mucho más lento** que el anterior;
   el límite de tiempo se verifica entre candidatos, pero no interrumpe una
   sola evaluación TREE a mitad de ejecución.

## Uso

```json
{"player":"microchess","evaluator":"microchess","depth":1,"qdepth":0}
```

Para comparaciones cruzadas: `player=microchess,evaluator=npz` o
`player=sargon-plus,evaluator=microchess` con las opciones usuales de red.

## Verificación

```powershell
python -m pytest tests/test_microchess_historical_v030.py -q
python -m pytest tests/test_microchess_integration.py -q
```

En el entorno de preparación del parche se comprobaron sintaxis y estructura
ZIP, pero no pudo ejecutarse `pytest` porque no está instalado `python-chess`
y no existe acceso a su paquete desde la red. Por tanto, el parche **no está
validado funcionalmente**; exige las pruebas indicadas en el entorno de Akkad.
