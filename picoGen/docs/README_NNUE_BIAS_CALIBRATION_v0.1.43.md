# picoGen NNUE FP32 v0.1.43 — calibración analítica del bias de salida

## Base y ámbito

Base GitHub `lu7did/Akkad` main `3f192903aec6012b2ec97f2ae554aa8b98311ec7`, con parche v0.1.42 instalado previamente (en este commit los ficheros v0.1.42 aún no están publicados). Rutas del ZIP relativas a raíz `akkad`.

Único cambio funcional: en `genNNUE.py`, cada cromosoma recibe la corrección exacta en mínimos cuadrados de su **último peso FP32** (bias de salida) sobre **T79** antes de calcular el fitness MSE, comparar élites, exportar modelos y guardar los checkpoints. La corrección es `bias -= mean(prediction_train - target_train)`. El cálculo de MSE usa el desplazamiento FP32 realmente aplicado; por redondeo FP32, puede diferir mínimamente de recalcular toda la red. Las etiquetas T77 no se utilizan para corrección ni selección.

## Control de versiones

Los checkpoints del optimizador v0.1.43 se escriben como `best.evo-v3.genNNNNN.json`, `format: picogen-nnue-evolution-fp32-bias-v3`. No son compatibles con `evo-v2`. El modelo final `best.npy` continúa siendo float32[12321] y el manifiesto `best.active.json` mantiene su formato para Nurse. `run_genesis_binpack.ps1 --mon 7` archiva el entrenamiento anterior y reinicia desde G1; si se interrumpe, sin `--mon` recupera el checkpoint `evo-v3`.

## Comando

```powershell
.\run_genesis_binpack.ps1 --mon 7 --population 500 --generations 200 --mutation-sigma 5
```

Telemetría agrega `bias_shift_mean_abs=...cp`, promedio del valor absoluto de las correcciones por cromosoma en esa generación. No confundirlo con sesgo residual de la red ni con error MAE. En cada checkpoint se guarda también `max_abs_post_bias_cp` para detectar desviaciones de redondeo.

## Límites

Esta calibración elimina el sesgo medio sobre T79 con los restantes parámetros congelados; no elimina error residual dependiente de la posición. La magnitud de mejora depende de cuánto sesgo exista realmente. La comparación con corridas anteriores no controla la distinta representación del optimizador ni las cantidades de evaluaciones, a menos que se mantengan parámetros y dataset.
