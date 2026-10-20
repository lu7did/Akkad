# Sargon-NNUE — MATCH v0.6.140

## Cambio específico

- En la línea de cierre de cada Game, mostrar `⌛A(n) ⌛B(n)` con segundos enteros sin indicación de unidad.
- Conservar cada medición real en punto flotante y sumar las esperas de cada motor A/B a lo largo de toda la corrida. El resumen `📊 Final` incorpora `⌛A(total) ⌛B(total)`.
- Los segundos se **truncan** al presentar (p. ej. 44,9 s -> `⌛A(44)`), tal como solicitó el ejemplo; NO se truncan antes de acumular.
- Las identidades A y B no cambian cuando se alternan los colores; las jugadas con excepción o timeout conservan el tiempo realmente consumido, porque ya se medían mediante `finally`.
- Se mantiene la precisión decimal interna de las mediciones, las salidas CSV/PGN, la lógica UCI y los algoritmos de búsqueda. No se modifica ninguna fórmula ajedrecística.
- El argumento `--version` ahora muestra la versión actual (`0.6.140`), en vez de una etiqueta heredada.

## Instalación

Extraer el ZIP sobre la raíz de Sargon-NNUE, sustituyendo únicamente los archivos enumerados en este parche.

## Pruebas desde la raíz de Sargon-NNUE (PowerShell)

```powershell
$py = 'C:\Users\pedro\ufasta\Scripts\python.exe'
$env:PYTHONPATH = (Resolve-Path .\src).Path
& $py -m unittest discover -s .\tests -p 'test_match_telemetria_totales_v06140.py' -v
```

## Telemetría ilustrativa

```
🔄 Game(1) ⚪ (beavys)   ⚫ (butthead) ♟️ 200 ⏱️ 113.2s (*) (MAX_PLIES_INCOMPLETE) ⌛A(44) ⌛B(68)
📊 Final Games(2) Moves(400) (beavys) (0.0 | 0.0) (butthead) ⏰(228.1 secs) ❌(2) ⌛A(89) ⌛B(136)
```

Las cifras son demostrativas, no mediciones reales. La suma de los segundos **mostrados** por partida puede diferir de los acumulados **mostrados** en el resumen por el truncamiento únicamente al formatear.

## Validación local

5 pruebas automatizadas (sin motores externos, reloj y UCI simulados) y sintaxis Python correctas. Las partidas reales deben comprobarse en el entorno del usuario.
