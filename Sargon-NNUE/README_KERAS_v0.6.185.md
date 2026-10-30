# Corrección KERAS v0.6.185 — TensorFlow nativo

Parche incremental posterior a v0.6.184. Extraer desde Akkad/.

## Corrección
- `keras-INT8.py` NO utiliza TFLite. Cuantiza capas Keras compatibles mediante `model.quantize('int8')` y exporta un SavedModel TensorFlow como directorio `.INT8.tf`.
- `keras-TF.py` registra procedencia `.keras` en `assets.extra/keras_source.json`; `keras-INT8.py` también acepta los SavedModel antiguos si junto a `small.tf` existe `small.keras`.
- `KerasEvaluator` carga `tf.saved_model.load()`, valida entrada `(None,8,8,12)`, evalúa la salida escalar y convierte a centipawns desde la perspectiva blanca. No utiliza `tf.lite.Interpreter`.
- La cuantización INT8 es de capas compatibles (Dense/EinsumDense y proyecciones internas compatibles); no equivale a un grafo de operaciones enteras extremo a extremo. Se comprueba que existan pesos INT8 antes de exportar.

## Ejecución
```powershell
python .\keras-TF.py --in ..\data\runs\keras\small.keras --out ..\data\runs\keras\small.tf
python .\keras-INT8.py --in ..\data\runs\keras\small.tf --out ..\data\runs\keras\small.INT8.tf
```

Si `small.tf` ya existe desde v0.6.184 y `small.keras` está en el mismo directorio, basta con ejecutar el segundo comando. Para crear nuevamente una salida existente, retirarla o utilizar otra ruta. `small.INT8.tf` debe ser un directorio con `saved_model.pb`, no un archivo TFLite.

Brain: `"network": "../data/runs/keras/small.INT8.tf"`.

## Pruebas
Verificada sintaxis e integridad del parche. No se pudo ejecutar conversión TensorFlow real en este entorno: se debe validar `model.quantize('int8')` con la versión local de Keras y el modelo ViT original.
