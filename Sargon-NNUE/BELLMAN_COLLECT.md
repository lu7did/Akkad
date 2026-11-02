# Bellman: recolección independiente de la telemetría

En `sargon_match.py`, `--collect` activa el registro acumulativo de misses Bellman sin imprimir información detallada por jugada. `--bellman-misses-jsonl RUTA` también activa la recolección implícitamente. `--telemetry` y `--verbose` ya no activan recolección por sí solos.

Ejemplos:

```powershell
python -m sargon_nnue.sargon_match --brain ../etc/brains/brains.json --idA emma --idB belly --pairs 1 --collect
python -m sargon_nnue.sargon_match --brain ../etc/brains/brains.json --idA emma --idB belly --pairs 1 --bellman-misses-jsonl ../data/bellman_misses.jsonl
```

Sin ruta explícita, `--collect` escribe `bellman_misses.jsonl` en el directorio padre de `--csv`, `--pgn` o `sargon_match` según la convención preexistente. El archivo se abre en modo agregar (append). No se cambian el formato de eventos (`fallback` y `game_end`) ni la lógica de destilación.

**Advertencia:** las partidas previas registradas con `--telemetry` siguen en el archivo, pero las futuras solo se registrarán con `--collect` o `--bellman-misses-jsonl`.
