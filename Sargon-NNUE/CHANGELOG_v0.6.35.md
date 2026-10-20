# v0.6.35 — auditoría de datasets .pb
- Nuevo comando independiente `sargon-audit-pb.py`; no modifica el dataset ni los checkpoints.
- Revisa distribución de partidas, integridad básica, duplicados de posición/halfmove y etiquetas PGN contradictorias.
- Baseline constante de entrenamiento y MSE en validación.
- Si se proporciona `--network`, calcula MSE segmentado por material de fase, etapa heurística, resultado y ply.
- Informes JSON y CSV opcional.
- No altera prepare, train, player ni evaluador.
