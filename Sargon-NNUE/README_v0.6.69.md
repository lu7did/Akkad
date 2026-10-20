# Sargon Rally v0.6.69 — Unicode subprocess MATCH

Reemplazar `src/sargon_nnue/sargon_rally.py`.

Corrección puntual: para lanzar MATCH con `stdout=PIPE`, ahora RALLY fija `PYTHONIOENCODING=utf-8` y `PYTHONUTF8=1` en el entorno del subprocess. Evita `UnicodeEncodeError` en Python Windows cp1252 al imprimir emojis. Se conserva el preflight de v0.6.68 y la decodificación UTF-8 de la telemetría.

Para ejecutar desde `scripts`:

```powershell
.\sargon_rally.ps1 --id mdqopen --brain ..\data\brains\brains.json --rally ..\data\rally\mdqopen.json --verbose
```

Si quedó `INCOMPLETE` y el directorio `..\data\rally\.rally_mdqopen` contiene temporales del intento fallido, archivarlo o moverlo ANTES de repetir. No borrar resultados de partidas válidas sin revisarlos.

No se cambian MATCH, los motores, brains.json, el formato del torneo, ni el sistema de puntuación. Validación: compilación Python, comprobación ZIP y test sintético de salida Unicode con proceso hijo; no se ejecutó Windows PowerShell ni el torneo real.
