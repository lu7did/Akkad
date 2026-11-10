# Nurse Dryrun v0.1.15

## Uso (directorio `akkad/nurse`)

```powershell
python nurse_dryrun.py --brains etc/brains/brains.json --id fishy picoSargon emma
```

Opcionales: `--port 6200` (TCP local, por defecto 6200), `--seed 123` (reproduce la posición aleatoria). Debe estar instalada la dependencia `python-chess` del proyecto.

El programa valida todo el JSON (incluidas claves repetidas), todos los IDs y sus configuraciones **antes** de abrir el listener. `type` debe ser `nurse`, `uci` o `external`. En caso de clave duplicada, devuelve código 2 sin ejecutar motores.

El wrapper escucha **solamente en 127.0.0.1:6200** y sirve secuencialmente una sesión Nurse por cada ID. Para cada uno, realiza `uci`/`uciok`, `isready`/`readyok`, `ucinewgame`, `position fen ...`, `go movetime <tmax>` y `bestmove`. El backend se obtiene estrictamente de la configuración del brain: `nurse` utiliza el worker Python, `uci` un subprocess UCI, y `external` el destino TCP configurado. No cambia direcciones remotas a localhost.

Muestra el intercambio completo de cliente-wrapper UCI en ambas direcciones y las estadísticas `depth`, `nodes`, `time` si fueron informadas. Valida `bestmove` frente a las jugadas legales con `python-chess`. Si UCI emite `info string nurse error`, se considera fallo. El campo `búsqueda` mide desde el envío de `go` hasta recibir `bestmove`; `total` incluye handshake y cierre. Si no comienza la búsqueda, el resultado se ordena por tiempo total. El resumen se ordena ascendentemente por la duración indicada, e identifica ✅/❌. Para `external`, usa exclusivamente `id name` remoto como nombre informativo; para `nurse` y `uci`, el ID local.

Si el puerto local 6200 ya está ocupado, el programa falla explícitamente (puede escogerse otro con `--port`), sin intentar apropiarse de la conexión o reutilizar el listener existente. Salida 0 si todos los brains resuelven, 1 si falla uno o más, 2 en error de configuración/puerto.

## Pruebas

`PYTHONPATH=src python -m unittest discover -s tests -p test_dryrun_v015.py -v`

La prueba de integración utiliza un servidor UCI simulado en un socket TCP local; no depende de firmware real. Para ejecutarla es necesario `python-chess` instalado (como el resto de Nurse).
