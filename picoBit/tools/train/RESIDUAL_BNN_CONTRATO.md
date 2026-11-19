# picoBit — contrato experimental de la nueva BNN residual (v0.1.27)

**Línea base de trabajo consultada:** `lu7did/akkad`, `main`, commit identificado
`c53d3e6b3f9b0c3ee7f61c5f7804283731a41f4c`. El parche no escribe en GitHub.

## Archivos y alcance

- `train.py`: reemplazo **del anterior entrenador** por uno PyTorch.
- `export.py`: exportación **en Python** de un `.h` C99/C++ con datos y funciones de inferencia futura.
- `audit.py`: **sólo inferencia** sobre los mismos IDs de validación; no vuelve a muestrear ni recalibrar.
- `sargon.py`: **dependencia compartida necesaria**: transcripción del último algoritmo `evaluate_sargon` escrito por el usuario, con valores 16/48/48/80/144. No usa `classic.py` ni el `sargon.py` adjunto anteriormente (100/300/300/500/900), reemplazado explícitamente por el nuevo código.

No se tocan `bnn_core.py`, motores, `assets`, ni archivos `qualy_*`. Estos entrenadores anteriores quedan históricos/fallidos y no son dependencias de esta implementación. **No mover ni borrar esos archivos automáticamente.**

## Definiciones explícitas

- Etiqueta: `positions.teacher_cp` desde perspectiva de quien juega; se transforma a POV blancas. Se excluyen registros con `teacher_mate` no nulo, `teacher_cp` faltante, posiciones ilegales y estados terminales si `quiet` está activo.
- Fuente `.pb`: SQLite con `positions(id,fen,teacher_cp,teacher_mate,teacher_at)`.
- Ejemplos `quiet`: *no estar en jaque y no disponer de capturas legales o promociones en el turno actual*. Es un criterio observable y conservador; **no supone disponer de quiescence search**, y **no garantiza ausencia de tácticas a mayor profundidad**. `--all-positions` desactiva conscientemente ese filtro.
- Evitar leakage: posiciones repetidas que comparten los cuatro primeros campos FEN se reducen a la de menor ID antes del split. Split aleatorio reproducible con `--seed`; `--validation` default 20 %; calibración por OLS exclusivamente sobre train.
- Sargon da **puntos de su escala propia**, no cp. `alpha` en cp/punto y `beta` en cp. Son los únicos parámetros de calibración: `S_cal=alpha*S+beta`.
- Stockfish y Sargon calibrado se limitan por separado a `[-clip,+clip]` (default ±1500 cp); el residuo es `clip(SF_clamped−Sargon_clamped)`.
- Red: 781 entradas **0/1** = 768 pieza/casilla + 1 turno + 4 derechos de enroque + 8 archivos de en-passant. Dos capas ocultas de 64 neuronas: fc1 INT8 simétrica por neurona en *forward* (peso maestro FP32), BN1 + activación ±1; fc2 peso binario ±1 con factor XNOR `alpha=mean(abs(w))` por neurona, BN2 + activación ±1; salida FP32 en **centipeones residuales**. Dos pesos maestros FP32 durante entrenamiento, recorte `fc2` a [-1,+1] después de actualizaciones.
- STE `sign`: gradiente HardTanh dentro de [-1,1], 0 fuera. FC1 usa fake quant INT8 con STE identidad para redondeo.
- Loss **sigmoide para regresión continua**, no clasificación: `BCEWithLogits(pred_cp/T, sigmoid(target_residual_cp/T))`, T=400 cp por defecto. Optimizador AdamW (`lr=0.003`), scheduler coseno, según referencia entregada. Mejor checkpoint seleccionado por **pérdida sigmoide de validación**, no por MAE.
- Evaluación informada: el MAE del **valor final** `S_cal + BNN` contra Stockfish (ambos POV blancas), además de la línea base `S_cal`.

## Portabilidad planificada, sin port prematuro

- fc1 INT8 `[64][781]` (49.984 bytes de pesos en FLASH), suma de columnas activas en un acumulador int32[64] (256 bytes RAM). La API de actualización incremental recibe eventos de activación/desactivación de características individuales; el futuro código del motor deberá suministrarlos para capturas, promoción, enroques, EP y turno. No pretende resolver ajedrez internamente.
- fc2 64 máscaras de 64 bits = 512 bytes, 64 productos de XNOR/popcount por evaluación; la escala XNOR por neurona queda absorbida en el umbral BN2.
- BN1 y BN2 se pliegan con umbral entero y dirección de comparación invertida para `gamma<0`; `gamma=0` usa salida constante determinada por beta.
- Salida INT16 `[64]` con una escala FP32 y sesgo FP32; suma intermedia int32.
- La cabecera `.h` emite una implementación **de referencia** para futura integración C++ x86 / Raspberry Pico. La presencia de `__builtin_popcountll` no presupone una instrucción nativa rápida en el Pico; puede tener implementación por software. La viabilidad temporal se medirá después de validar la red en Python.
- La calibración `alpha/beta` y el evaluador Sargon deben portarse fielmente y medirse también en el dispositivo final.

## Comandos

Desde `picoBit/tools/train`:

```powershell
python .\train.py --self-test
python .\train.py --in "C:\ruta\sample_history.pb" --sample 10000 --validation 20 --epoch 50 --out "C:\ruta\experimento_residual"
python .\audit.py --run "C:\ruta\experimento_residual"
python .\export.py --in "C:\ruta\experimento_residual\best.pt" --manifest "C:\ruta\experimento_residual\manifest.json" --out "C:\ruta\experimento_residual\picoBit_residual.h"
```

**DEPENDENCIAS:** PyTorch, NumPy, python-chess. No se usa TensorFlow.

## Límites de verificación de esta entrega

Se verificaron sintaxis de los cuatro Python, forward/backward de PyTorch y gradientes presentes, guardado/carga de checkpoint, generación de `.h`, compilación C99 con GCC y equivalencia de inferencia numérica C99 vs referencia entera Python (40 ejemplos de entrada binaria). No se pudieron ejecutar el entrenamiento completo ni la base `.pb` ni partidas reales porque `python-chess` no está instalado en este entorno y no hay red para instalarlo. Antes de aprobar una red para inferencia, exigir MAE de exportación contra la implementación PyTorch en posiciones legales: el reporte `.export.json` lo cuantifica y no oculta errores.

## Investigación

No hay nuevas pruebas QUALY. Cualquier modificación futura debe proponer hipótesis y autorización separada. La selección quiet y el formato de estado se documentan como decisiones necesarias para cumplir las características solicitadas, no como mejoras demostradas.
