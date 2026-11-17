# picoSargon NNUE - corrección de telemetría v0.1.45

Corrige los cuatro defectos reportados durante el entrenamiento v0.1.44.

- `SAMPLE`: muestreo uniforme sin reposición mediante *reservoir sampling* sobre IDs elegibles, con progreso desde el escaneo SQLite; ya no usa `ORDER BY RANDOM() LIMIT ?`, que bloqueaba la telemetría durante el sort de 10 millones de posiciones. Ahora el `seed` determina también la muestra (si el conjunto y su orden de lectura permanecen iguales). `COUNT`, `LOAD` y `VERIFY` tienen telemetría; el manifiesto mantiene los IDs de train/validation. El conteo SQL aún debe completarse antes de conocer el denominador.
- En una terminal interactiva, las fases `SAMPLE`, `LOAD`, `VERIFY`, `TRAIN`, `REPLAY`, `VALID`, `EXPORT`, `AUDIT` muestran barra ASCII en una única línea actualizada con retorno de carro. Al redirigir a un log se emiten snapshots periódicos en líneas independientes (necesario para la legibilidad de un log permanente). Se muestran columnas estables, separadores de miles y barras compactas si el ancho de consola es insuficiente.
- Los cuatro `.ps1` del pipeline se guardan como UTF-8 con BOM para Windows PowerShell 5.1 y configuran consola y salida de Python UTF-8. Eso corrige mojibake como `âš™ï¸`.
- `RMSE (cp)` es la métrica legible y directamente comparable con ensayos anteriores; `MSE (cp²)` se conserva con unidad explícita. Relación exacta: `RMSE_cp = sqrt(MSE_cp2)`. La función objetivo del optimizador **no cambia** (`mean(((prediction-target)/400)^2)`); `TRAIN` mide error sobre pesos que cambian en línea, `REPLAY` usa los pesos finales del epoch. Checkpoint `best` sigue elegido por MSE de validación, o `REPLAY` si no hay validación.

No se modifica arquitectura, formatos GRMP0001 ni pesos de referencia. `--validation 100` sigue rechazado porque imposibilita entrenar.

### Verificación

Ejecutar `python test_telemetry.py` y luego el pipeline con un conjunto de prueba. PowerShell y la visualización exacta de los emojis deben confirmarse en Windows; no se dispuso de Windows PowerShell en este entorno.
