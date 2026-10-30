# Sargon-NNUE v0.6.187 — corrección de cuantización Keras FP16 → INT8

Requiere v0.6.185/v0.6.186 previas. Sustituye solo `scripts/keras-INT8.py`.

El modelo descargado declara políticas float16 incompatibles con `model.quantize("int8")`. La herramienta clona sus capas con `dtype=float32`, conserva los pesos mediante `set_weights()` y luego aplica cuantización INT8 nativa Keras. No usa TFLite. La salida sigue siendo un directorio TensorFlow SavedModel.

Invocación sin cambios:

```powershell
python .\keras-INT8.py --in ..\data\runs\keras\small.tf --out ..\data\runs\keras\small.INT8.tf --verbose
```

No se ha probado conversión real ViT en este entorno sin TensorFlow; se verificó compilación sintáctica y estructura del parche. Si falla cuantización de otras capas, conservar el traceback completo.
