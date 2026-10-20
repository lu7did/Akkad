# Sargon-NNUE — Auditoría ZNPZ / ZCLASSIC v0.6.141

**Paquete exclusivamente diagnóstico. No modifica los motores ni su versionado instalado.**

## Hechos corroborados mediante lectura de código fuente v0.6.138–140

- `ClassicEvaluator.evaluate(board)` devuelve centipawns con signo positivo favorable a blancas.
- `NpzEvaluator.evaluate(board)` devuelve `int(forward_raw * CALIBRATION_FACTOR)` sobre su representación blanca; el signo no se invierte según `board.turn`.
- `ValuePolicyEvaluator.evaluate_pv(board)` define `sign = +1` si mueve blancas y `-1` si mueve negras. Su valor `q` es `tanh(sign * white_cp / z_value_scale)`.
- Para cada movimiento legal el adaptador aplica `board.push(move)`, evalúa la sucesora, **mantiene el signo del jugador que debía mover antes del push**, restaura el estado con `board.pop()` y aplica Softmax con mezcla uniforme. Para finales inmediatos utiliza resultados terminales exactos.
- En MCTS, `AlphaZeroPlayer._simulation` invierte el valor de la hoja en cada ply de backup.
- MATCH utiliza la misma apertura en ambos colores de cada pareja. Si `--opening` no se indica, todas las parejas parten de la posición inicial. PUCT es determinista por defecto (no usa `self.random` en la decisión).
- MATCH finaliza si `board.is_game_over(claim_draw=True)`. Por ello una repetición **reclamable** puede terminar la partida antes de una reclamación explícita. `MAX_PLIES_INCOMPLETE` es incompleta, no empate.

## Ejecutar prueba de signos y backup

Desde la **raíz** de Sargon-NNUE, después de extraer este ZIP:

```powershell
$py = "C:\Users\pedro\ufasta\Scripts\python.exe"
$env:PYTHONPATH = (Resolve-Path .\src).Path
& $py -m unittest discover -s .\tests -p "test_zpolicy_perspectiva_v06141.py" -v
```

Este conjunto usa un evaluador simulado cuyo contrato es centipawns desde blancas y comprueba ambas orientaciones, normalización, `push/pop` y backup por un ply. No necesita un checkpoint real.

## Auditar un MATCH ya realizado

MATCH debe haberse ejecutado con `--csv`, por ejemplo `--csv data/test/match_zpolicy.csv`. Desde la carpeta `scripts`:

```powershell
$env:PYTHONPATH = (Resolve-Path ..\src).Path
python .\audit_zpolicy_v06141.py --csv ..\data\test\match_zpolicy.csv
```

El diagnóstico agrupa por color y apertura, cuenta trayectorias UCI distintas y verifica cada final. Informa `rep_actual` (posición ya repetida tres veces) y `rep_reclamable` (derecho de reclamar empate). No cambia resultados.

## Auditar la política con un brain real

Desde `scripts`:

```powershell
$env:PYTHONPATH = (Resolve-Path ..\src).Path
python .\audit_zpolicy_v06141.py --brain ..\data\brains\brains.json --id beavys
python .\audit_zpolicy_v06141.py --brain ..\data\brains\brains.json --id butthead
python .\audit_zpolicy_v06141.py --brain ..\data\brains\brains.json --id beavys --moves "e2e4 e7e5"
```

Verifica el signo de `V(s)`, la cobertura de jugadas legales, suma de `P=1`, y muestra el orden de las primeras jugadas y los centipawns de sus posiciones sucesoras, desde la perspectiva del jugador al turno.

## Ensayos con aperturas diferentes

Usar igual apertura para A/B dentro de cada pareja, alternando colores; ejecutar varias parejas con aperturas distintas:

```powershell
.\sargon_match.ps1 --brain ..\data\brains\brains.json --idA beavys --idB butthead `
    --pairs 4 --max-plies 300 --csv ..\data\test\match_zpolicy.csv `
    --opening "e2e4 e7e5" --opening "d2d4 d7d5" `
    --opening "c2c4 e7e5" --opening "g1f3 d7d5"
```

## Limitaciones

La auditoría estática no sustituye la ejecución de los tests en `ufasta` ni la inspección del PGN/CSV real. No se incluye cambio funcional porque el síntoma por sí solo no demuestra un error de signo. Los resultados de una apertura determinista no son muestras estadísticamente independientes.
