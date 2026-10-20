# Sargon-NNUE — Benchmark v0.6.134 — Resumen clasificado por msec/nodo

## Corrección solicitada

La telemetría de `📊 Resumen` se ordena ahora **por tiempo por nodo ascendente**,
con el mismo criterio que el gráfico `📊 Tiempo por nodo (menor es mejor)`.

- Brains con `ms_per_node` válido: de menor a mayor.
- Brains con `ms_per_node` sin determinar: al final.
- En caso de empate: se conserva el orden original de ejecución.
- La alineación dinámica de las columnas permanece intacta.
- **No se altera el orden de filas de `summary.csv`**, ni el de `moves.csv`;
  no se modifica la ejecución de los motores, los nodos, las medidas o las
  fórmulas de las métricas.
- Se aplica a los dos modos: `positions` y `play`.

## Ejemplo (datos aportados por el usuario)

```text
📊 Resumen:
🧠 (sophie)  ⚙️ (onnx-dml) [6/6] 📈[avg 15010.4 msec/P95 15016.8 msec] ⏳(11.3 msec/nodo)
🧠 (locus)   ⚙️ (onnx-cpu) [6/6] 📈[avg  8120.8 msec/P95  8796.3 msec] ⏳(13.1 msec/nodo)
🧠 (frankie) ⚙️ (eigen)    [6/6] 📈[avg 15017.9 msec/P95 15038.7 msec] ⏳(21.4 msec/nodo)
🧠 (alphie)  ⚙️ (eigen)    [6/6] 📈[avg 15020.8 msec/P95 15029.1 msec] ⏳(38.9 msec/nodo)
```

## Instalación

Extraer el ZIP sobre la **raíz del proyecto**, conservando las rutas internas:

- `src/sargon_nnue/sargon_benchmark.py` — cambio funcional localizado en `report()`.
- `src/sargon_benchmark.py` — actualiza solamente el comentario de versión.
- `scripts/sargon_benchmark.ps1` — actualiza solamente el comentario de versión.
- `tests/test_sargon_benchmark_v06134.py` — 17 pruebas de regresión.

El lanzador sigue ejecutándose desde `scripts` con:

```powershell
.\sargon_benchmark.ps1 --brain ../data/brains/brains.json --ids alphie sophie locus frankie --positions 6
```

## Validación

Se ejecutaron 17 pruebas automatizadas con UCI simulado, incluyendo el orden
solicitado, la alineación, los empates, métricas faltantes y los modos de
benchmark. **No se ejecutaron motores reales en Windows**.

```powershell
python -m unittest discover -s tests -p test_sargon_benchmark_v06134.py -v
```
