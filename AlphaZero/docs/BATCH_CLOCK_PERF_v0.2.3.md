# AlphaZero C++ v0.2.3: inferencia agrupada, reloj UCI y diagnóstico

Cambios compartidos entre Windows X86, macOS y Debian; versión del adaptador
Sargon-NNUE `v0.6.199`. **Recompilar** AlphaZero tras aplicar el parche.

## MCTS

`BatchSize` (opción UCI o `--batch-size`), valor inicial 8, rango 1..256:
selecciona hasta N hojas distintas con reservas virtuales PUCT y evalúa
con `Backend::EvaluateBatch`. Se liberan las reservas antes de retropropagar.
La evaluación de la raíz se mantiene separada. Los lotes pueden ser menores
por falta de hojas independientes, límite de simulaciones/nodos o tiempo.
El nuevo agrupamiento puede cambiar las decisiones porque cambia el orden de
las simulaciones. No se garantiza aceleración: probar 1, 4, 8 y 16 en cada
backend, especialmente Eigen CPU donde el lote 8 podría ser más lento.

## Tiempo

Con `go wtime W btime B winc WI binc BI movestogo M`, el presupuesto es
`remaining / M + 0.8*increment`, con M=30 si falta, menos reserva del 5%
(o 100 ms mínimo). `TMax` sigue siendo un techo, al igual que `Timeout`.
`movetime` explícito tiene prioridad sobre el reloj. `go nodes N` sigue
representando N simulaciones MCTS, no nodos expandidos, por compatibilidad.
Un lote de inferencia en curso no es interrumpible: puede exceder ligeramente
el límite. No hay aún estimación adaptativa basada en complejidad de posición.

## Telemetría

`stdout`: exclusivamente líneas UCI (`info`, `bestmove`, `readyok`, etc.).
`stderr`: `⚙️` rutas y presupuesto; `🧠` `nn_ms`, `selection_ms`,
`expansion_ms`, `backup_ms`, `other_ms`, `nn_evals`, `batches`, `avg_batch`,
`max_batch`, `stop` y rendimiento. Las magnitudes son tiempos de pared
instrumentados; `other_ms` agrupa todo tiempo no medido por etapa.

## Prueba en macOS

```
python3 AlphaZero/tests/uci_batch_clock_smoke.py \
  --engine AlphaZero/macOS/build/AlphaZero \
  --weights /ruta/real/a/weights.pb.gz --backend eigen --batch-size 8
```

Comparar también `--batch-size 1`, con la misma red y posición. Ejecutar
pruebas análogas en Windows y Debian. La prueba no demuestra mejora de
rendimiento ni fuerza de juego; registra cumplimiento del protocolo y
telemetría, y requiere motor compilado y pesos reales.
