# picoBit NNUE FP32 — v0.1.38

**Origen:** parche v0.1.37 entregado inmediatamente antes. No se reconstruyeron archivos desde GitHub.

**Único cambio de modelo:** 781 → 64 → 64 → 1, ahora con pesos y activaciones FP32. Se preservan BatchNorm, ClippedReLU `[0,1]`, tamaño, salida residual en cp y representación de entrada. Se eliminan los fake quantizers INT8 en las capas y activaciones; se elimina el clipping `fc2.weight.clamp_(-1,1)` después del optimizador, pues pertenecía a la restricción binaria y carece de sentido en FP32 convencional.

**Preservado del último parche:** Sargon original sin modificaciones, calibración exclusiva en TRAIN, muestreo temprano y división configurable TRAIN/VALID (20 % default), sigmoide, AdamW, `--lr`, `--lrmin`, Train/Verif/Valid en cada época, telemetría, y selección de `best.pt` por menor `validSig` (no se cambia a MAE).

**Identificadores nuevos:** checkpoint `picobit-residual-nnue-fp32-v1`, manifiesto `picobit-residual-nnue-fp32-manifest-v1`; salida `data/residual_nnue_fp32`. No cargar checkpoints BNN ni INT8 anteriores como FP32.

**Exportador:** `export.py` ahora genera `.h` con matrices y sesgos FP32 y BatchNorm plegada por multiplicación afín, con sumador incremental FC1 también FP32. *No* se aplican nuevos cambios de cuantización. El tamaño nominal de matrices FP32 es 216.576 bytes (781×64 + 64×64 + 64 + 1 pesos, multiplicado por cuatro), además de BN plegada/coeficientes/código. La viabilidad final en Raspberry Pico queda pendiente de mediciones.

**Audit:** mismo análisis y posiciones del manifiesto, pero verifica el nuevo identificador FP32.
