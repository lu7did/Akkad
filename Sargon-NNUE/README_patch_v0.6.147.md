# Sargon-NNUE — parche v0.6.147

## Cambios

- Nuevo `sargon_brainmaker.py --level --brain ... --rally ... [--k-factor 32] [--save]`.
- Todos los jugadores requieren `rating_elo` inicial finito; no se inventan valores.
- Calcula variación Elo por partida: `K * (S - E)` donde `E = 1/(1+10^((Elo_opp-Elo_self)/400))`.
- Todas las expectativas se calculan contra el Elo **anterior al rally**, evitando dependencia del orden del JSON. Actualización *batch*, no secuencial.
- Resultados `1-0`, `0-1`, `1/2-1/2` suman; `*` y otros estados incompletos se omiten.
- Verifica identidades conocidas y claves de partidas duplicadas cuando hay `match` y `game`.
- Por defecto solo lista Elo anterior, nuevo y delta. `--save` escribe de manera atómica exclusivamente `rating_elo` de jugadores con partidas válidas.
- Si reejecutás `--level --save` con el **mismo rally**, se aplicarán los resultados por segunda vez. Conservá respaldo del JSON antes de guardar.

## Invocación (desde scripts/tools)

```powershell
.\sargon_brainmaker.ps1 --level --brain ..\..\data\brains\brains.json --rally ..\..\data\rally\rally.json
.\sargon_brainmaker.ps1 --level --brain ..\..\data\brains\brains.json --rally ..\..\data\rally\rally.json --k-factor 16 --save
```

Ajustar la ruta al JSON real de Rally. Alternativamente usar `python -m sargon_nnue.sargon_brainmaker` con `PYTHONPATH=src` desde la raíz del proyecto.

## Stockfish

En su perfil del archivo `brains.json`, usar `player=stockfish`, `evaluator=null`, `elo=max`, `depth=20` (o 24), `nodes=0` para desactivar tope de nodos, `stockfish-threads=2` (según CPU), `stockfish-hash=256` (o 512 si hay RAM), `timeout=60000` (ms), y `engine-path` al ejecutable Stockfish. El `rating_elo` del brain **no** regula la fuerza Stockfish. Stockfish usa búsqueda `go depth N [nodes M]`; `movetime` no se aplica.

La eliminación del tope `nodes` puede aumentar mucho el tiempo por jugada; medir velocidad y considerar los límites de tiempo por partida del Rally.

## Tests

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p test_brainmaker_level_v06147.py -v
```
