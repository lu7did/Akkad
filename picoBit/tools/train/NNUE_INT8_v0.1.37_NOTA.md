# picoBit v0.1.37 — NNUE INT8 residual, cambio de arquitectura

## Procedencia y alcance

**Origen exclusivo del entrenador:** último parche entregado `v0.1.36` (`picoBit/tools/train/train.py`). No se reconstruye desde GitHub. Se modifican los tres archivos `train.py`, `export.py` y `audit.py`; `sargon.py` del parche anterior queda **sin cambios** y debe conservarse instalado. No se modifican motores C++ ni la serie QUALY. Código de inferencia en `.h` solo como artefacto de exportación, no motor nuevo.

## Cambios arquitectónicos intencionales

- Dimensiones **inalteradas:** 781 → 64 → 64 → 1; 768 entradas pieza-casilla y 13 bits de estado.
- Eliminación completa de `SignSTE`, activaciones binarias, XNOR y escala mean-abs de FC2.
- `fc1` y `fc2`: pesos maestros FP32 durante entrenamiento y cuantización simulada INT8 simétrica **por neurona de salida** en *forward*, con STE de redondeo; inferencia INT8, acumuladores INT32.
- Cada `BatchNorm1d` precede a activación **ClippedReLU [0,1]**, cuantizada a enteros 0..127 (INT8 no negativo). El STE de redondeo deja pasar la derivada del clipping. El exportador repliega BatchNorm en **multiplicador + bias por neurona**, no en umbral de signo (sería incorrecto para una activación multivalor).
- Capa de salida FP32 durante entrenamiento; el exportador cuantiza sus 64 pesos a INT16, preservando escala y bias.
- Pérdida sigmoide con objetivos continuos, AdamW, `--lr`, `--lrmin`, `--validation`, filtrado quiet, selección aleatoria antes de procesar, Sargon original, calibración exclusiva sobre TRAIN, protocolo Train / Verif / Valid y barras de progreso de v0.1.36: **inalterados**.
- Checkpoints nuevos con formato `picobit-residual-nnue-int8-v1`; manifests `picobit-residual-nnue-int8-manifest-v1`; carpeta `data/residual_nnue_int8/`. **No** admiten pesos del BNN anterior. `export.py` y `audit.py` validan el formato y rechazan los anteriores.
- La etiqueta `S+B` de telemetría sigue significando Sargon más la red residual, ahora **NNUE INT8**. En JSON la clave pasa a `sargon_plus_nnue`.

## Memoria estimada de pesos para Pico

Pesos INT8: FC1 = 781×64 = 49.984 B, FC2 = 64×64 = 4.096 B, salida INT16 = 128 B. **54.208 B** de matrices de pesos, excluidos coeficientes BN plegados, calibración y código. Se almacenarán en FLASH; activaciones de 64 bytes por capa y acumuladores de 64×int32, sin necesidad de guardar la entrada densa ni utilizar PyTorch en Pico. `pb_fc1_init` y `pb_fc1_delta` admiten actualización incremental de características activas. El futuro motor deberá actualizar también los 13 bits de estado y todos los cambios de cada jugada.

El `.h` contiene multiplicadores y biases FP32 de BN plegada, dos arrays de 64 elementos por capa; por tanto no usa raíces cuadradas, medias ni varianzas en inferencia, aunque sí operaciones escalares FP32. **No se ha medido aún latencia real en Raspberry Pico**; capacidad de memoria no garantiza velocidad.

## Verificación y limitaciones

- Sintaxis Python de los tres programas verificada.
- PyTorch: forward, backward y gradientes finitos de cada parámetro, y carga de checkpoint, verificados.
- Referencia numérica INT8 en Python frente a PyTorch, 128 entradas binarias sintéticas: error máximo observado ~3,4×10⁻⁶ cp con red inicializada.
- Cabecera C99 compilada con GCC y probada con inicialización y actualización incremental de acumulador.
- Sin prueba de corrida completa con SQLite real/Stockfish ni ejecución en Raspberry Pico (falta `python-chess` en entorno de verificación).

## Ejecución

Desde `picoBit/tools/train`:

```powershell
python .\train.py --self-test
python .\train.py --in "C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb" --sample 50000 --validation 20 --epoch 50 --batch 256 --lr 0.001 --lrmin 0.00001
python .\audit.py --run "RUTA_NUEVA_CORRIDA"
python .\export.py --in "RUTA_NUEVA_CORRIDA\best.pt" --manifest "RUTA_NUEVA_CORRIDA\manifest.json" --out "RUTA_NUEVA_CORRIDA\picoBit_nnue_int8.h"
```

Los archivos anteriores se dejan intactos salvo los tres declarados. `best.pt` se elige con la misma métrica `validSig` de v0.1.36 (no se cambió silenciosamente a MAE).
