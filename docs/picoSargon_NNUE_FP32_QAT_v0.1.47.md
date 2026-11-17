# picoSargon compact NNUE — Entrenamiento FP32 + QAT, v0.1.47

## Objetivo y contrato

- Red original `GRMP0001`, 1680 coeficientes de 6 bits, archivo de 1304 bytes.
- Inicialización y comparación con `picoSargon/assets/grumpy.bin`: **solo lectura**.
- Etiquetas SQLite `teacher_cp`, `teacher_value` calculadas desde el lado que mueve (STM); las etiquetas se convierten a perspectiva blanca para el evaluador compacto.
- Criterio de picoAlpha para el valor: **MSE(tanh(pred_cp/400), tanh(target_cp/400))**. Como tanh es impar, la conversión coherente STM→blancas conserva el error. PicoAlpha además tiene pérdida de policy: no corresponde incorporarla a esta red que solo produce valor.
- RMSE(cp) y MSE(cp²) siguen disponibles como diagnósticos; **no** controlan la selección de los checkpoints.

## Fases

1. `--epoch` epochs de pesos maestros FP32, acumulación continua y AdamW; activaciones [0,32] y mismo término fijo de material. El error FP32 continuo selecciona `<network>_best_fp32.pt`.
2. Cuantización directa del mejor FP32 a GRMP0001 e informe `DIRECT6` (mismo conjunto de selección).
3. `--qat-epoch` epochs con forward cuantizado a 6 bits y STE en pesos y truncamiento, manteniendo parámetros maestros FP32. Se parte del mejor modelo FP32.
4. Para **cada epoch de ambas fases**, la exactitud exportable se mide con `network.eval_encoded`, evaluador entero, y se selecciona `<network>_best_quant.pt` **solo si mejora** al modelo inicial en MSE(value). Un alias `<network>_best.pt` se mantiene para compatibilidad.
5. `export.py` requiere el checkpoint v2 y produce `.bin` + `.h`; `Audit.py` compara con la red de referencia y persiste el conjunto completo de posiciones de validación en JSON.

Se guarda un checkpoint por epoch y el historial en `picoSargon/data/<network>_history.json`, incluyendo métricas FP32 y cuantizadas y número de coeficientes modificados. Si ningún cuantizado supera al baseline, el entrenamiento devuelve error y Genesis no exporta. No se reemplaza el binario de referencia.

## Ejecución

Desde `picoSargon/tools/train`:

```powershell
.\run_genesis.ps1 -mon 1 -lr 0.01 -lrmin 0.001 -epoch 10 -qatEpoch 5 -qatLr 0.05 -qatLrmin 0.005
```

La ruta del SQLite y el nombre de la red `dopey` permanecen tal como se establecieron en el script del usuario. `-referenceBin` permite otro archivo GRMP0001. Las tasas por defecto son puntos de partida, no óptimos certificados.

## Limitaciones

- Con `--validation 0`, el best se elige sobre entrenamiento y `Audit.py` no puede efectuar la auditoría solicitada; para Genesis completo debe elegirse validación >0.
- El muestreo separa posiciones, no partidas completas; posiciones correlacionadas pueden aparecer en ambos conjuntos.
- Los pesos FP32 y la simulación QAT son aproximaciones de gradiente; **únicamente** `eval_encoded` y el `.bin` exportado determinan exactitud desplegable.
- La elección entre epochs se hace usando validación, por lo que para medir generalización sin sesgo haría falta un test independiente de partidas/posiciones.
- Los checkpoints v1 no son exportables mediante este exportador v2: regenerarlos con la nueva cadena.
