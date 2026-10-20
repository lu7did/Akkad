# Sargon-NNUE v0.6.71 — preflight Windows y RANDOM/NULL

Reemplazar los tres archivos en `src/sargon_nnue/`:
- `sargon_rally.py`: el bloqueo temporal de `uci.log` durante la eliminación no invalida un UCI/bestmove exitoso; se reintenta la limpieza y, si Windows lo mantiene abierto, se conserva el registro como diagnóstico.
- `brains.py`: `random` admite `evaluator=null`, igual que `stockfish`; no se relaja la restricción para otros players.
- `sargon_match.py`: aplica la misma regla, evitando que RANDOM/NULL pase preflight pero falle al comenzar MATCH.

Primero ejecutar `sargon_rally.ps1 ... --preflight-only`, después el torneo normal.

**Nota:** los bloqueos de archivo pueden deberse a procesos UCI que conservan manejadores; este parche evita el falso fallo al limpiar logs, pero no reemplaza el análisis de eventuales procesos hijos que queden activos. No se cambian algoritmos de juego ni archivos JSON.
