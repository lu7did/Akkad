# Sargon-NNUE — Benchmark de brains v0.6.132

## Alcance de este parche

Ajustes exclusivos al benchmark v0.6.131: estructura del ejecutable Python, resumen compacto, tiempo por nodo, gráfico comparativo y nombres finales de los archivos. Sin cambios a `sargon_match.py`, `sargon_listen.py`, `brains.py`, al backend LC0, a la red neuronal ni a los algoritmos de los players.

**Ubicaciones:**

- `src/sargon_benchmark.py`: entrada Python principal, ahora en `src/`.
- `src/sargon_nnue/sargon_benchmark.py`: implementación dentro del paquete, necesaria para `python -m` y reutilización de imports existentes.
- `scripts/sargon_benchmark.ps1`: solo el lanzador PowerShell de conveniencia, para preservar el comando `.\sargon_benchmark.ps1`.
- `tests/test_sargon_benchmark_v06132.py`: pruebas de regresión aisladas con motores simulados, sin conexión a GPU.

**Migración desde v0.6.131:** descomprimir el ZIP en la **raíz de Sargon-NNUE** (no en `scripts/`) y eliminar el obsoleto `scripts/sargon_benchmark.py` de v0.6.131. Ese lanzador Python ya no forma parte de la entrega:

```powershell
# Desde la raíz del repositorio, una vez instalado el ZIP:
Remove-Item .\scripts\sargon_benchmark.py
```

El comando anterior elimina el antiguo wrapper, no `src/sargon_nnue/sargon_benchmark.py` ni `src/sargon_benchmark.py`. Si querés mantener el wrapper antiguo por compatibilidad, no interfiere con el lanzador `.ps1`, pero dejaría un `.py` en la ubicación que se pidió abandonar.

## Uso

Desde la **raíz** del proyecto:

```powershell
python .\src\sargon_benchmark.py --brain .\data\brains\brains.json --ids alphie sophie --positions 6 --rounds 2
```

O desde `scripts`, conservando el lanzador PS1:

```powershell
.\sargon_benchmark.ps1 --brain ../data/brains/brains.json --ids alphie sophie --positions 6 --rounds 2
```

El modo `play` usa el mismo formato para el resumen y el gráfico:

```powershell
.\sargon_benchmark.ps1 --brain ../data/brains/brains.json --ids alphie sophie --mode play --plies 8 --rounds 1
```

## Telemetría

Formato al terminar las mediciones (números ilustrativos):

```text
📊 Resumen:
🧠 (alphie) ⚙️ (eigen) [6/6] 📈[avg 150.8 msec/P95 202.3 msec] ⏳(0.252 msec/nodo)
🧠 (sophie) ⚙️ (onnx-dml) [6/6] 📈[avg 83.1 msec/P95 95.5 msec] ⏳(0.138 msec/nodo)

📊 Tiempo por nodo (menor es mejor):
🧠 (sophie) ⚙️ (onnx-dml) ⏳ █████████████ 0.138 msec/nodo
🧠 (alphie) ⚙️ (eigen) ⏳ ████████████████████████ 0.252 msec/nodo
✅ CSV detalle: moves.csv
✅ CSV resumen: summary.csv
✅ Configuración: manifest.json
```

El gráfico está ordenado por **milisegundos por nodo crecientes**, no por nombre de brain. Las barras tienen escala lineal relativa (máximo 24 bloques); el valor numérico junto a cada barra permite la comparación exacta.

El indicador `⏳` se calcula como `sum(wall_ms) / sum(nodes)` **sobre las mismas jugadas exitosas**. No es la media simple de los cocientes por jugada, sino un promedio ponderado por nodos. `wall_ms` incluye comunicación UCI y espera de `bestmove` (no incluye inicialización ni calentamiento), por lo que describe **latencia observada por nodo**, no tiempo puro de inferencia neuronal. Si faltan nodos o hay cero nodos en una de las decisiones exitosas, `ms_per_node` es `N/D`, y ese brain figura después de los que sí se pueden ordenar. No se inventan nodos.

Para números menores que 0,1 ms se muestran más decimales para evitar que tiempos válidos aparezcan como `0.0`.

El CSV `summary.csv` incorpora la nueva columna `ms_per_node` y conserva las anteriores (`nodes_per_second` sigue calculándose con el tiempo `info time` UCI cuando está disponible; **no** es necesariamente el recíproco de la métrica basada en `wall_ms`). `moves.csv` y `manifest.json` mantienen su estructura y contenido.

Los mensajes finales imprimen **solo el nombre** de cada archivo. La carpeta completa sigue anunciándose al principio de la ejecución y el CSV/JSON se escribe normalmente en `data/benchmark/bench_v0.6.132_...`.

## Validación

Pruebas de sintaxis y 12 pruebas automatizadas de regresión: modos `positions` y `play`, UCI `info`, cálculo ponderado, nodos ausentes o cero, barras ordenadas, precisión sub-ms, salida de nombres de archivo y ubicación del entrypoint. Todas con motores simulados; no se realizaron nuevas pruebas de inferencia real CPU/GPU en Windows.
