# Sargon-NNUE v0.6.159 — Telemetría Arbiter

Parche incremental a partir de v0.6.158. Reemplazar los archivos según las rutas del ZIP.

- 🗄️ Ruta completa del archivo FEN y número de **posiciones FEN** (no movimientos de una partida).
- 📂 Directorio de destino de los CSV.
- ♟️ Detalle por posición: brain, player, evaluator, evaluación en cp y MAE de ese brain frente a los demás evaluadores válidos **en esa posición**. El MAE no es una propiedad individual: precisa un referente; con un solo evaluador aparece N/D.
- 📊 Comparación agregada por pares con semáforo: 🟢 MAE ≤ tolerancia; 🟡 tolerancia < MAE ≤ 2 × tolerancia; 🔴 MAE > 2 × tolerancia. Para tolerancia 0, solo igualdad exacta es verde.
- ✅ Rutas de cada CSV emitido.

No cambia la evaluación, el formato CSV, el tratamiento de fallos ni los argumentos CLI. La telemetría por FEN se presenta una vez concluidas las evaluaciones, antes del resumen. Una falla individual de evaluador mantiene el comportamiento anterior de descartar sus resultados.

La escala de centipeones de evaluadores heterogéneos puede diferir: el semáforo expresa distancia numérica, no calidad ajedrecística.
