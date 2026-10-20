# Sargon-NNUE — MATCH, identidades de brain en telemetría — v0.6.127

## Objetivo

Identificar a los participantes de MATCH por el **ID del perfil en `brains.json`**
(`--idA` y `--idB`) en lugar de la combinación `player | evaluator`, que puede
ser idéntica para jugadores configurados con profundidades u otros parámetros diferentes.

## Cambio localizado

Se modifica **solo** `src/sargon_nnue/sargon_match.py`:

- Los mensajes `🔄 Game(...)` al comenzar la partida muestran los IDs de los brains en las posiciones blanca y negra.
- La línea de cierre de cada partida reutiliza exactamente las mismas etiquetas, respetando la inversión de colores.
- El resumen `📊 Final Games(...)` muestra los IDs de los brains participantes A y B.
- Sin archivo de brains, se mantiene el formato previo `(player | evaluator)`.
- Se actualiza la identificación de versión de MATCH a v0.6.127.

No se cambian los campos CSV, cabeceras PGN, protocolo UCI, parámetros de motor,
trazas de cada jugada ni el algoritmo de selección de movimientos.

## Uso

Desde la raíz del proyecto:

```powershell
.\scripts\sargon_match.ps1 `
    --brain ".\data\brains\brains.json" `
    --idA splus_depth2 `
    --idB splus_depth5 `
    --pairs 2
```

Ejemplo de telemetría:

```
🔄 Game(1) ⚪ (splus_depth2) ⚫ (splus_depth5) ♟️ -- ⏱️ --.-s (IN_PROGRESS)
🔄 Game(1) ⚪ (splus_depth2) ⚫ (splus_depth5) ♟️ ... (resultado) (terminación)
🔄 Game(2) ⚪ (splus_depth5) ⚫ (splus_depth2) ♟️ -- ⏱️ --.-s (IN_PROGRESS)
📊 Final Games(4) Moves(...) (splus_depth2) (... | ...) (splus_depth5) ...
```

## Aplicación

Extraer el ZIP en la **raíz del proyecto**, respetando las rutas internas y
reemplazando únicamente `src/sargon_nnue/sargon_match.py`. La prueba incluida
es optativa:

```powershell
python -m unittest discover -s tests -p 'test_match_brain_telemetry_v06127.py' -v
```

## Verificación

Sintaxis de Python, cuatro pruebas de regresión aisladas y ZIP validados.
No se ejecutaron partidas reales en este entorno: falta `python-chess`.
