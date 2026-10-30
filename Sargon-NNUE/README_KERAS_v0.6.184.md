# Sargon-NNUE KERAS v0.6.184 (parche incremental)

Extraer desde Akkad/ (los archivos comienzan en sargon-NNUE/).

Dependencias: `pip install python-chess tensorflow keras huggingface_hub numpy`.

Desde `sargon-NNUE/scripts`:

```powershell
.\keras-getModel.ps1 --name ViT-Small --out ..\data\runs\keras\small.keras
.\keras-TF.ps1 --in ..\data\runs\keras\small.keras --out ..\data\runs\keras\small.tf
.\keras-INT8.ps1 --in ..\data\runs\keras\small.tf --out ..\data\runs\keras\small.INT8.tf
```

`.tf` es un **directorio SavedModel**; `.INT8.tf` es un archivo **TensorFlow Lite** binario, con firma `TFL3` y conversión estricta INT8.

Ejemplo de brain:
```json
"vitSmall": {"player":"keras", "evaluator":"keras", "network":"../data/runs/keras/small.INT8.tf", "rating_elo":400}
```

Player KERAS evalúa una vez cada jugada legal y selecciona el valor máximo para el jugador de raíz (mínimo del valor del oponente). Todos los evaluadores de sargon-NNUE proporcionan centipawns desde la perspectiva blanca.

No se incluyen los modelos; descargar con keras-getModel. Los ViT de Mateusz Grzyb usan tensores (1,8,8,12), no entrada FEN string.

Las conversiones requieren TensorFlow y el soporte del grafo correspondiente; si el conversor no soporta una operación INT8, falla sin producir modelo incompatible.
