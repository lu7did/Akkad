# picoSargon — telemetría simplificada v0.1.48

Corrige la presentación de la cadena de entrenamiento FP32+QAT sin modificar la función de pérdida, los parámetros, el formato GRMP0001, los checkpoints ni la selección de `best_quant.pt`.

- Barras gráficas Unicode `█░` en lugar de `#-`, con actualización sobre una línea en consola interactiva.
- Solo una barra de progreso por epoch de entrenamiento. `REPLAY`, `VALID` y evaluación exacta se siguen ejecutando y registrando en `picoSargon/data/{network}_history.json`, pero no saturan la consola.
- Resumen por epoch con MSE(value) continuo, MSE(value) del binario de 6 bits, mejora porcentual de este último frente a la referencia, y número de coeficientes cuantizados que cambiaron.
- `run_genesis.ps1`, rutas personalizadas, entrada SQLite, referencia `grumpy.bin` y lógica MON permanecen sin cambios.
- La métrica comparable con picoAlpha es MSE(value), calculada sobre `tanh(cp/400)`. No debe confundirse con MSE(cp²) ni asumirse que distintas arquitecturas y conjuntos de datos tienen que tener el mismo valor de MSE.
