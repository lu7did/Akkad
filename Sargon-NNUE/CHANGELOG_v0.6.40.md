# Sargon-NNUE v0.6.40 — --shuffle

- Agrega `--shuffle PCT` al entrenador (NumPy y PyTorch).
- Se mantiene el split por **partidas** y su validación completa.
- Solo se muestrea, sin reemplazo, el porcentaje de **posiciones de entrenamiento** fijado por el argumento.
- La muestra de entrenamiento es estable durante todos los epochs; cambia solamente el orden de procesamiento.
- `--shuffle 100` (predeterminado) mantiene el comportamiento anterior.
- Entrenamiento fijo y online se calculan sobre la muestra seleccionada; validación permanece íntegra.
- Mismo objetivo PGN/Stockfish en entrenamiento y validación, sin ejecutar Stockfish durante train.
- Ninguna modificación a sargon-prepare.py ni al esquema .pb.
