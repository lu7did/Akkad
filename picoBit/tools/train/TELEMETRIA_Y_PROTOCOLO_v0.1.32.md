# picoBit v0.1.32 — corrección de protocolo de épocas y telemetría

Parche incremental sobre la versión v0.1.31. Modifica solamente `train.py`.

- Mantiene `--validation` (20 por defecto) y la partición fija de posiciones únicas sin cruces.
- Calibra `alpha` y `beta` solamente con TRAIN usando regresión lineal a etiquetas Stockfish recortadas.
- Cada época realiza tres pasos: actualizaciones de gradiente sobre TRAIN, verificación de TODO TRAIN con pesos actualizados, y validación de VALID sin gradientes.
- Informa por época conteos reales y MAE en cp de Sargon calibrado y Sargon+BNN en TRAIN y VALID; registra las tres fases en `history.jsonl`.
- Barras de progreso transitorias con retorno de carro, porcentajes, n/total y ETA; únicamente la línea de métricas por época permanece.
- Checkpoint seleccionado por pérdida sigmoide en VALID como en v0.1.31. No se modifica Sargon, la representación, el objetivo, la arquitectura, los filtros, el optimizador ni el muestreo.
- Si el último lote tiene un único registro, se excluye de gradientes por BatchNorm, pero sí de la verificación. Esto se informa en pantalla.

## Límites de verificación

Se comprobó la sintaxis y los invariantes estructurales del script. No se ejecutó una corrida real SQLite porque esta máquina no tiene `python-chess`.
