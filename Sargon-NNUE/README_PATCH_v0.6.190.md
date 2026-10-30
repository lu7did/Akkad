# Sargon-NNUE v0.6.190 — KERAS batch + nodes plies

Descomprimir en `Akkad/` y ejecutar **una vez** desde `Akkad/sargon-NNUE`:

```powershell
.\apply_v0.6.190.ps1
```

Este pequeño instalador modifica solo la línea de valor predeterminado de `nodes` en `factory.py`, sin reemplazar todo el archivo ni deshacer las correcciones de otras versiones.

`player=keras` usa `nodes` como profundidad minimax en **plies**: ausente 1, 2 significa dos plies, etc. Otros jugadores preservan el significado anterior de `nodes`. Un brain KERAS puede contener `"nodes": 2`.

`KerasEvaluator.evaluate_batch()` agrupa posiciones en una inferencia si la firma SavedModel admite lote variable; si exige exactamente batch=1, usa micro-lotes de una posición respetando la interfaz pública. Los evaluadores sin evaluate_batch conservan inferencia individual. Evaluación relativa a blancas y selección minimax correcta. No cambia TensorFlow ni el formato de los modelos.

Nota: la expansión minimax es de ancho completo y crece exponencialmente con `nodes`.
