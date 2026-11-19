# AKKAD picoBit — QUALY_07 v0.1.26 (diagnóstico de checkpoints, sin entrenamiento)

## Objetivo y criterio de interpretación

**No se entrena ninguna red.** El objetivo es explicar la brecha observada de MAE entre FP32 (~10,08 cp), HYBRID (~24,71 cp) e HYBRID_NORM (~20,79 cp), sin proponer otra optimización antes de localizar un mecanismo de error. Los tres checkpoints deben proceder de **la misma corrida de QUALY_06**, fase `03_generalizacion`, pues comparten la muestra de validación y presupuesto.

### Hipótesis falsables

- **H1: composición y magnitud.** Si el error se concentra en un rango material o en tableros más poblados, aparece en `observations.*.strata`. Si el error general es grande pero algunas categorías tienen error pequeño, perseguir un único MAE global puede resultar engañoso.
- **H2: invariancia material.** Cambiar una pieza de casilla conservando los conteos no cambia el teacher. `interventions.move` mide cuán lejos está la diferencia predicha de cero. Se incluyen tanto grupos de posiciones reales de igual composición (`natural_material_invariance`) como movimientos sintéticos; **los sintéticos pueden ser ilegales**, por lo tanto medirán sensibilidad de la red, no sólo calidad de generalización en posiciones ajedrecísticas.
- **H3: aditividad de piezas.** `interventions.remove` compara el efecto de retirar una pieza con exactamente ±100/320/330/500/900 cp, según color. La desviación revela dependencia de contexto y/o calibración; los contrafactuales pueden ser ilegales.
- **H4: error de inferencia inducido por discretización.** Con los **mismos pesos latentes del checkpoint**, correr cuatro forwards: `full_qat`, `weights_only`, `activations_only`, `no_quantization`. Se verifica antes que `full_qat` reproduzca la salida original de Keras con máximo 0,1 cp de discrepancia, o el programa aborta (no reporta ablaciones engañosas). Estas ablaciones **NO** reentrenan los pesos, y sus efectos no son aditivos. Si quitar cuantización reduce la MAE, hay un efecto inmediato en la inferencia con pesos fijos; si no la reduce, no demuestra que cuantización no perjudique el proceso de entrenamiento.

## Ejecución

El parche se extrae **desde la raíz de `akkad`** y añade sólo `picoBit/tools/train/qualy_07.py` y esta nota.

Desde `picoBit/tools/train`:

```powershell
python .\qualy_07.py --self-test
python .\qualy_07.py --run06 "C:\Users\pedro\github\Bobby\Akkad\picoBit\data\qualy_06\20261118-215138" --in "C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb"
```

Sin `--run06`, el script busca la última carpeta válida en `picoBit/data/qualy_06`; sin `--in`, lee la ruta de `dataset_info.json` de la corrida. Requiere `tensorflow`, `numpy`, `python-chess`, `bnn_core.py`, `qualy_01.py`, `qualy_06.py` accesibles en la misma carpeta o entorno. No funciona con `--manifest` actualmente: detiene con explicación para evitar reconstruir datos distintos. Si la corrida original utilizó distinto `--candidate-limit` del predeterminado, indicar ese argumento, o fallará la comprobación de la validación.

Para una auditoría más breve, `--observed 512 --interventions 120`; en ese caso no se puede verificar automáticamente el MAE de las 2000 posiciones de validación. El valor predeterminado procesa las 2000.

## Salidas

- `summary.json`: diagnósticos H1-H4 para los tres modelos, validación contra el MAE guardado en QUALY_06, limitaciones y métricas por pieza/color.
- `interventions.csv`: resultados individuales para movimiento y retirada; incluye FEN original, FEN modificado, delta esperado, delta observado y marca de posible ilegalidad.
- `dataset_audit.json`: selección, semilla, fuentes y cantidad de datos.

**No** modifica base de datos, archivos de pesos, modelos productivos, `bnn_core.py`, `qualy_06.py` ni scripts de entrenamiento. No depende del teacher Stockfish.

## Decisión a partir del diagnóstico

1. Si el error de predicción se correlaciona con movimientos de igual composición y es alto respecto FP32, investigar la **dependencia posicional** de CNN y sus capas cuantizadas, antes de cambiar el optimizador.
2. Si las dispersiones posicionales son pequeñas pero retirar piezas produce grandes sesgos consistentes, investigar **calibración de aportes materiales**, no normalización arbitraria.
3. Si una ablación baja drásticamente el MAE sin reentrenar, enfocar la siguiente hipótesis en el mecanismo de discretización responsable; verificar el efecto de interacción con otras ablaciones.
4. Si las ablaciones con pesos fijos no explican la diferencia, enfocar en **optimización QAT** o en la representación; sin más entrenamientos hasta tener una prueba localizada.

Una diferencia de MAE en un único split no mide incertidumbre entre semillas: el informe es diagnóstico y no prueba generalización estadística universal.
