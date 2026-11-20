# picoGen — PGPE Grumpy FP32 v0.1.55 — referencia Stockfish en centipeones

Base: parche v0.1.54. El ZIP es **incremental**, con rutas relativas a la raíz de `akkad`.

## Cambios autorizados

1. **Único objetivo de actualización**: `mean(((NNUE_cp - Stockfish_cp)/2000)^2)` para *ambas* ramas PGPE y Adam. El factor 2000 únicamente normaliza unidades; no altera el mínimo ni la dirección de mejora respecto del MSE en cp. Se conserva el ranking centrado de EvoTorch para PGPE y el refinamiento analítico en CPU/XPU. El error probabilístico se calcula únicamente como telemetría diagnóstica.
2. **Selección del mejor checkpoint**: se evalúa el candidato preferido de cada generación por RMSE **en T77 excluyendo etiquetas cp=0**. `best.npy` y `best.active.json` cambian solamente si ese RMSE es menor que el mejor obtenido hasta ese momento. T77 nunca se usa en cálculo de gradientes o actualización de distribución. Se informan RMSE de generación y mejor RMSE para no confundir tendencias.
3. **Más datos, mismos CSV**: de 500.000 a 800.000 posiciones elegibles T79 en el pool (de las 865.882 disponibles); de 20.000 a 40.000 posiciones para fitness PGPE por generación. Validación de 1.000 a hasta 150.000 posiciones, con exclusión cp=0 y de solapamiento: de acuerdo con la corrida anterior hay unas 147.000 T77 elegibles. **No regenerar** `train.csv` ni `validation.csv` para este parche.
4. **Memoria GPU**: T77 se mantiene en RAM y las predicciones se evalúan en bloques de 2.048 posiciones. La auditoría MON 8 también evalúa Grumpy por bloques para evitar crear un gran tensor de activaciones. Adam permanece en CPU y solo envía gradientes a XPU.
5. **Compatibilidad**: checkpoint de entrenamiento v3 independiente de v2. La arquitectura/manifest de inferencia `picogen-grumpy-pgpe-fp32-v1` no cambia. Los artefactos v0.1.54 se archivan al solicitar un nuevo MON 7 explícito.
6. **Rendimiento y validación**: se mantienen 100 generaciones, 50 individuos PGPE y 4 pasos Adam por generación. Tests de regresión verifican la equivalencia de los cálculos cp, la selección por RMSE ignorando probabilidad, la evaluación en bloques, la aritmética Grumpy y el manejo de tensores de solo lectura.

## Ejecución en PowerShell desde `picoGen/tools/train`

```powershell
.\run_genesis_binpack.ps1 --mon 7 --generations 100
```

El script aplica por defecto `--pgpe-pool 800000`, `--pgpe-batch 40000` y `--validation-sample 150000`; estos parámetros se admiten como modificaciones explícitas de entrenamiento sin cambiar la identidad de T79/T77. MON 8 se ejecuta después de MON 7.

## Criterio de aceptación

El parámetro principal de calidad es **RMSE cp en T77 sin ceros**, más pequeño es mejor. MAE, bias, porcentaje de signo incorrecto y MSE probabilístico son diagnósticos auxiliares y no determinan la selección. Los resultados aún deben verificarse en Intel XPU; las pruebas locales no constituyen una corrida completa de 100 generaciones.
