# Sargon-NNUE — MATCH, tiempos por jugador — v0.6.130

## Cambio autorizado

Se modifica exclusivamente `src/sargon_nnue/sargon_match.py`, partiendo de la versión v0.6.127 (identidades provenientes de `brains.json`). La versión mostrada al iniciar pasa a v0.6.130.

Al finalizar **cada partida**, la línea existente conserva las identidades de los brains, la cantidad de plies, la duración de la partida, el resultado y el motivo de terminación. Se agregan los tiempos acumulados del motor A y del motor B:

```
🔄 Game(1) ⚪ (alphie) ⚫ (sophie) ♟️  65 ⏱️  97.9s (1-0) (CHECKMATE) ⌛A(38.4 secs) ⌛B(57.2 secs)
```

Los tiempos del ejemplo son ilustrativos.

- `⌛A`: suma de los tiempos de respuesta de las jugadas solicitadas al proceso UCI **A** durante esa partida.
- `⌛B`: suma equivalente del proceso UCI **B**.
- Se miden con `time.monotonic()`, desde el envío de la posición y `go` hasta recibir `bestmove`, incluyendo el tiempo de comunicación. Un timeout o fallo también contabiliza el tiempo transcurrido en la solicitud fallida.
- El tiempo total `⏱️` sigue representando la duración de la partida y puede incluir operaciones adicionales ajenas a ambos motores (p. ej., auditoría).
- A y B conservan su identidad al intercambiar blancas y negras. Los acumuladores se reinician al comenzar cada partida.
- No se alteran los argumentos, la selección de brains, la lógica UCI, la selección de jugadas ni los formatos CSV/PGN.

## Instalación

Descomprimir el ZIP sobre la **raíz** del proyecto Sargon-NNUE. Respaldar el archivo existente antes de sobrescribirlo.

Desde `scripts`:

```powershell
.\sargon_match.ps1 --brain ../data/brains/brains.json --pairs 2 --idA alphie --idB sophie
```

## Verificación

Pruebas automatizadas sin motor externo: 7 casos, incluyendo reversión de colores, mismo `player/evaluator` con brains diferentes, tiempos por A/B, timeout y regresiones de v0.6.127. `py_compile` también aprobado. No se ejecutaron partidas reales en Windows.
