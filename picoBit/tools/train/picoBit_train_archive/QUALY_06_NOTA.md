# QUALY_06 — Normalización de escala INT8 (v0.1.25)

## Alcance

Prueba experimental de tres modelos: `HYBRID` (control inalterado de
QUALY_04), `HYBRID_NORM` (misma topología/STE/AdamW con escalas INT8 de
mayor granularidad) y `FP32` (control).

El ÚNICO cambio en `HYBRID_NORM` respecto de `HYBRID` es el cálculo del
factor de escala en `int8_ste`:

- Conv2D (NHWC): máximo absoluto por **muestra y canal**, tomado sobre H y W.
- Dense: máximo absoluto por **muestra y bloque de 32 características**.

Se conserva cuantización simétrica a [-127,127], redondeo, desescalado y el
STE identidad original `x + stop_gradient(q-x)`. No se reemplaza BatchNorm;
es una normalización del rango de activaciones para INT8, no RMSNorm.

No cambia: cuantizador ternario absmean de pesos, maestros FP32 y clipping
[-1,1], arquitectura CNN y residual, cabezal lineal, Huber cp/400,
AdamW, batch, tasas de aprendizaje, BN y recalibración, teacher material,
selección de posiciones o gates de material. Ningún modelo productivo se altera.

## Ejecución

Desde `picoBit/tools/train`, con `qualy_01.py` y `bnn_core.py` instalados:

    python .\qualy_06.py --in "C:\\ruta\\sample_history.pb" --no-manifest

Salida en `picoBit/data/qualy_06/<fecha>/` con históricos, checkpoints y
`summary.json`. `HYBRID_NORM` se acepta sólo si supera gate material y
es comparable a FP32 en fase final. Se informa por separado su diferencia
contra HYBRID.

## Límite del método

Este estudio **no prueba RMSNorm** ni una técnica de normalización de activaciones
a través de una capa nueva. Prueba una **granularidad mejorada del factor de
escala INT8**; requiere almacenar/especificar esas escalas en una futura
implementación de inferencia. No afirmar mejora ni velocidad antes de medir.

## Medidas que quedan sin incorporar

- RMSNorm como reemplazo de BN; normalizaciones por grupo aprendibles.
- SGD con momentum frente a AdamW.
- Aumento del ancho (filtros/neuronas) o cambio a arquitectura MLP/NNUE.
- Cuantización estocástica y otros niveles de precisión.
- Nueva función objetivo o tamaños de batch distintos.
- Cambios experimentales de STE/escala/lr de QUALY_05, que empeoraron
  resultados y por eso no se incluyen aquí.
