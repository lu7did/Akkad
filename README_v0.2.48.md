# picoAlpha v0.2.48 — exportador autónomo de checkpoints 1×8

Parche incremental sobre v0.2.47. No incluye redes `.pt`, datos `.pb` ni encabezados de coeficientes generados. No aplicar v0.2.43. Mantiene el selector CMake `PICOALPHA_NET=1x8` / `2x16`.

## Cambios

- `tools/picoDistiller/picoExport.py`: convierte `state_dict` de `epoch_best.pt` a 2 cabeceras C++.
- `src/net_1x8.cpp`: se sustituye el evaluador experimental de 13 planos, política de 1968 y modulo defectuoso por un evaluador TinyGyal-compatible (112 planos históricos, 1 residual, SE, política 80 canales, valor escalar) que reutiliza los kernels del `net.cpp` estable.
- `CMakeLists.txt`: versión 0.2.48 y verificación de ambas cabeceras para la red 1x8; conserva la elección en compilación.
- No toca ni modifica `net.cpp` (2x16), MCTS, `picoPrepare.py`, `picoDistiller.py`, sus checkpoints ni la base `.pb`.

## Uso (PowerShell en `picoAlpha/tools/picoDistiller`)

```powershell
python .\picoExport.py --input "..\data\runs\epoch_best.pt"
```

La ruta al checkpoint anterior es ilustrativa, especificar la ruta real. Sin `--out`, escribe automáticamente en `picoAlpha/include`:

- `generated_micro_az_1x8.hpp` (capas convolucionales, SE y FC2; BatchNorm plegada y convoluciones INT8)
- `generated_micro_az_1x8_fc_int8.hpp` (FC1 INT8 en bloques de 4 filas × 32 valores, escalas por fila)

Compilar con el habitual `./build.ps1` y la selección 1x8. Solo la red seleccionada se incorpora al UF2; la 2x16 se conserva para selección independiente. El exportador sobrescribe las dos cabeceras cada vez, sin necesidad de transferir archivos `.pt`.

## Detalles de compatibilidad

- La codificación 112 planos y `policy_index` son los del código C++ estable, sin mapeo `% 1968`.
- `model.py` sigue siendo la definición fuente. El conversor rechaza checkpoints con claves o tamaños incorrectos.
- Carga PyTorch con `weights_only=True`, solo CPU. Los tensores de origen pueden venir de un entrenamiento XPU.
- Convoluciones: cuantización simétrica INT8 por canal de salida, BN absorbida, activaciones INT8 dinámicas calculadas en el firmware.
- FC1: cuantización INT8 por fila y reorganización para el kernel de cuatro salidas. Los sesgos permanecen float32.
- SE, FC2 y escalas/sesgos usan float32, como el evaluador original. Esto **no** pretende que todos los coeficientes de la red sean INT8; mantiene el formato mixto del firmware estable.
- La conversión cuantizada es una aproximación de la red float32; debe verificarse P/V y desempeño ajedrecístico sobre posiciones reales antes de comparaciones de rendimiento.

## Pruebas realizadas

Se generaron ambas cabeceras desde un modelo 112/1/8 sintético y se compilaron con G++ C++17 del entorno de pruebas. Inferencia C++ en cero planos: V=-0.0596922 frente a -0.0597078 en PyTorch; logits de política también próximos. Se comprobó sintaxis del script. **No hay todavía validación con `epoch_best.pt` real ni compilación ARM Pico SDK ni prueba física.**
