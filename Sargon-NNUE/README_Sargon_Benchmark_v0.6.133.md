# Sargon-NNUE — Benchmark v0.6.133 — Alineación de telemetría

## Instalación

Extraer el ZIP en la **raíz** del proyecto Sargon-NNUE, conservando las rutas internas. Reemplaza los archivos de la v0.6.132:

- `src/sargon_nnue/sargon_benchmark.py` — único archivo con cambio funcional (formato de salida).
- `src/sargon_benchmark.py` — entrada Python en `src/`, solo actualización del comentario de versión.
- `scripts/sargon_benchmark.ps1` — lanzador existente, solo actualización del comentario de versión.
- `tests/test_sargon_benchmark_v06133.py` — 15 pruebas con motores simulados.

**No** se modifica el cálculo de tiempo por nodo, P95, medición de jugadas, modos `positions`/`play`, brains, CSV, manifest, evaluadores ni algoritmos de búsqueda.

## Salida alineada

Las columnas se dimensionan dinámicamente considerando **todos** los brains de la ejecución, tanto por longitud de nombre como por backend, marcador de muestras y anchura de los valores. Los números promedio y P95 están alineados a la derecha.

El gráfico conserva el orden ascendente por costo por nodo. El inicio de las barras y la columna de valores numéricos quedan alineados aunque las barras tengan longitudes diferentes. Un brain sin telemetría completa de nodos aparece al final, con N/D en la columna de valor.

Ejemplo utilizando exactamente los números ilustrativos facilitados por el usuario:

```text
📊 Resumen:
🧠 (alphie)  ⚙️ (eigen)    [6/6] 📈[avg  4963.8 msec/P95  5026.8 msec] ⏳(38.8 msec/nodo)
🧠 (sophie)  ⚙️ (onnx-dml) [6/6] 📈[avg  1370.4 msec/P95  1393.8 msec] ⏳(10.7 msec/nodo)
🧠 (locus)   ⚙️ (onnx-cpu) [6/6] 📈[avg  7194.2 msec/P95  8161.9 msec] ⏳(11.6 msec/nodo)
🧠 (frankie) ⚙️ (eigen)    [6/6] 📈[avg 15027.7 msec/P95 15038.5 msec] ⏳(21.3 msec/nodo)

📊 Tiempo por nodo (menor es mejor):
🧠 (sophie)  ⚙️ (onnx-dml) ⏳ ███████                  10.7 msec/nodo
🧠 (locus)   ⚙️ (onnx-cpu) ⏳ ████████                 11.6 msec/nodo
🧠 (frankie) ⚙️ (eigen)    ⏳ ██████████████           21.3 msec/nodo
🧠 (alphie)  ⚙️ (eigen)    ⏳ ████████████████████████ 38.8 msec/nodo
```

Se incorporó una función ligera de ancho visible Unicode (biblioteca estándar) para que nombres con caracteres de ancho doble no desplacen el resto de las columnas. Como los emojis se repiten en todas las filas, sus diferencias de representación en cada terminal no afectan los espacios calculados entre valores de una misma columna. La visualización óptima requiere una fuente monoespaciada en la consola.

## Ejecución

Desde `scripts`:

```powershell
.\sargon_benchmark.ps1 --brain ../data/brains/brains.json --ids alphie sophie locus frankie --positions 6
```

Modo `play`:

```powershell
.\sargon_benchmark.ps1 --brain ../data/brains/brains.json --ids alphie sophie --mode play --plies 8
```

Desde la raíz:

```powershell
python .\src\sargon_benchmark.py --brain .\data\brains\brains.json --ids alphie sophie --positions 6
```

## Pruebas

```powershell
python -m unittest discover -s tests -p test_sargon_benchmark_v06133.py -v
```

Se validó sintaxis de los módulos y se ejecutaron 15 pruebas automatizadas con UCI simulado en esta sesión. No se realizaron mediciones de los motores reales en Windows.
