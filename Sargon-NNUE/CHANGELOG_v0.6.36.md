# Sargon-NNUE v0.6.36

- Auditoría `.pb`: baselines independientes por fase/etapa/ply entrenadas únicamente con train.
- Auditoría de calibración del checkpoint (`--calibration-bins`).
- Se añaden nuevas secciones al JSON y tipos de fila al CSV (cambia el encabezado CSV respecto de v0.6.35).
- Escaneo en dos pasadas para no almacenar el dataset completo en memoria RAM.
- Entrenador NumPy, PyTorch, PGN, Stockfish y formato `.npz` sin cambios.
