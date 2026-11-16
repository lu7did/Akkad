# picoAlpha teacher — recuperación y reanudación v0.1.10

Parche incremental sobre picoAlpha v0.1.9. No modifica esquemas ni archivos de bases existentes.

## Uso

Desde `picoAlpha/tools/train`:

```powershell
.\run_genesis.ps1 -Mon 3 -Resume
```

O directamente:

```powershell
python teacher.py --in "C:\ruta\sample_history.pb" --engine "C:\ruta\stockfish.exe" --depth 10 --resume
```

El parámetro `-EngineRetries 3` de Genesis o `--engine-retries 3` de `teacher.py` controla el máximo de reinicios al producirse una falla del motor **por posición**. Si Stockfish muere o pierde la conexión, el proceso intenta reiniciarlo y reanalizar solamente esa posición. Si también fracasan los reintentos, **termina con error** preservando todas las evaluaciones ya confirmadas. No borra posiciones por una caída de proceso.

`--resume` inicializa el motor de la misma manera que una ejecución normal. Recorre **todas** las posiciones en orden de `id`, actualiza la barra de avance y omite rápidamente las posiciones que tienen **ambos** campos `teacher_at` y `teacher_value` poblados, sin abrir su FEN y sin invocar a Stockfish. No presupone que las evaluaciones estén contiguas: también procesa huecos previos y posiciones pendientes posteriores. La línea final exhibe `scanned`, `pending`, `skipped`, `labeled`, `invalid_removed` y `bad_engine`. Cada evaluación se confirma en SQLite inmediatamente, facilitando recuperarse de interrupciones.

Cuando un FEN es inválido se elimina su fila de `positions`, conservando las demás filas de la partida. Si Stockfish entrega un análisis incoherente **como resultado de una llamada completada** (puntuación ausente/no numérica/no finita, PV mal formada o primera jugada PV ilegal), se elimina **sólo esa posición**, se cuenta en `bad_engine` y se continúa. Los primeros ocho descartes se muestran **al terminar**, sin romper la única línea de progreso. Para restaurar posiciones descartadas, es necesario reconstruir la muestra de la fuente original; `--resume` no lo hace.

Distinción importante: un resultado incoherente **no equivale** a una caída del proceso de Stockfish. La primera situación descarta la posición; la segunda intenta reiniciar el motor. Los fallos persistentes de arranque o comunicación siguen siendo fatales para evitar eliminar datos sanos indiscriminadamente.

`-Mon 3` evita recrear `history.pb` y `sample_history.pb`. **No ejecutes `-Mon 0` ni `-Mon 2` sobre bases que quieras conservar:** esos pasos son destructivos.

## Verificación

Pruebas unitarias de resumir con huecos, conservar posiciones etiquetadas, reinicio limitado ante caída, cierre tolerante cuando el motor murió, validación del análisis incoherente y continuidad: 26/26 superadas en entorno de pruebas, sin Stockfish real y sin PowerShell de Windows. La prueba integral Windows/Stockfish queda pendiente.
