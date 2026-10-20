# Sargon-NNUE v0.6.32

Base: v0.6.31.

- `sargon-train.py`: si `--input` apunta a un archivo inexistente, informa `❌ Dataset no existe: <ruta absoluta>` y termina con código 2, sin traceback ni creación de base SQLite.
- Si el archivo existe pero es inválido o ilegible, el error de apertura se informa concisamente sin traceback.
- La validación de entrada ocurre antes de crear `--nnuedir`, índices o checkpoints.
- No cambia la arquitectura 781-64-1, el algoritmo de entrenamiento, la generación de índices ni las métricas.
