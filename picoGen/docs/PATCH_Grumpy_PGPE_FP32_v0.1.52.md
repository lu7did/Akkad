# picoGen v0.1.52 — Grumpy FP32 PGPE con residuo material y pérdida mixta

**Base:** archivos autorizados de Akkad `main` (commit leído `24b107e9d689438dbbb1a47c386bf4a12443052a`) y parches incrementales v0.1.49–v0.1.51 previamente suministrados. Aplicar este ZIP sobre la **raíz `akkad`**, después de v0.1.51.

## Arquitectura (referencia Grumpy GRMP0001)

- 1680 parámetros FP32: `192×8` factores por fila/columna, 8 biases, `8×16` pesos de salida por bucket de cantidad de piezas, 8 biases de bucket.
- Dos perspectivas compartiendo pesos, 8 acumuladores cada una, 16 activaciones `clip(0,32)`.
- Ocho buckets: `(piezas_en_tablero - 2) // 4`.
- Salida neuronal en centipeones de la perspectiva del jugador que mueve: `400/1024 * (sum(h_j*w_j) + 8*b_bucket)`.
- Material fijo **blancas menos negras**: peón 100, caballo 300, alfil 300, torre 500, dama 900, rey 0 cp. La salida total en perspectiva blanca es `material_blancas + (+1|-1) * neural_stm`.
- **FP32 sin cuantización**. El archivo `best.npy` es exactamente un vector de 1680 `float32`. Su manifest es `picogen-grumpy-pgpe-fp32-v1`; NO es compatible como NNUE 768×16; la auditoría reconoce ambos modelos.

## Pérdida y entrenador

- `L = mean[(sigmoid(pred/400) - sigmoid(label/400))²] + mean[((pred-label)/2000)²]` (peso de cp configurable con `--cp-weight`, por defecto `1`).
- **EvoTorch PGPE** sigue actualizando una distribución simétrica mediante ranking `centered` y Adam. No se sustituye el PGPE.
- **Refinamiento adicional por gradiente**: PyTorch/Adam optimiza un candidato separado con la *misma pérdida numérica sin ranking* (`--gradient-steps 4`, `--gradient-batch 2048`, `--gradient-lr 0.03`). Se conserva el mejor candidato de PGPE o del refinamiento según una muestra fija de T79; T77 solo se usa para reportar, nunca para elegir pesos.
- El candidato analítico puede reinicializarse desde un candidato PGPE si tiene mejor pérdida en el mismo T79 fijo. Por lo tanto el sistema es **híbrido PGPE+gradiente**, no «PGPE puro».
- Se inicializan factores pequeños y biases ocultos positivos para evitar un centro totalmente degenerado de gradiente nulo.
- Checkpoint nuevo (`best.grumpy-pgpe-v1.latest.pt`) distinto de los entrenadores PGPE anteriores.

## Ejecución directa reutilizando T79/T77

Requiere que existan `picoGen/assets/binpack-pgpe-nonzero-001/train.csv`, `validation.csv` y `pst/best.json` de la corrida previa. **No es necesario reextraer** ninguno de los dos datasets.

Desde `picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 7
```

Por defecto se crea `assets/binpack-grumpy-pgpe-fp32-001/nnue/`, toma los CSV existentes de `binpack-pgpe-nonzero-001` y el PST previo solo para la auditoría MON 8. Entrena **100 generaciones × 50 individuos PGPE (25 pares simétricos)**, con lote evolutivo de 20.000 posiciones por generación, pool T79 residente de 500.000 y 4 pasos extra de gradiente por generación con lotes de 2048. La validación informa RMSE, MAE, bias, MSE probabilístico, MSE cp normalizado, desviación y rango de las predicciones.

**Límite**: no se ejecutó el entrenamiento completo en Intel XPU aquí. La NNUE FP32 Grumpy exportada se audita desde `genAudit.py`, pero no se ha añadido un nuevo lector FP32 a los motores C++ ni al evaluador Grumpy INT6; nunca se debe cargar como `grumpy.bin` GRMP0001. La reducción efectiva de RMSE debe demostrarla la corrida, no está garantizada.
