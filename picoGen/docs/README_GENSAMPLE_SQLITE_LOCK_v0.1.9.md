# picoGenus — genSample.py v0.1.9

## Error corregido

En Windows, `os.replace(temporal, destino)` podía fallar con `WinError 32` porque `with sqlite3.connect(temporal) as out:` hace commit/rollback, **pero no cierra** la conexión SQLite. Al finalizar ese bloque, el archivo temporal podía seguir abierto en el mismo proceso Python.

`genSample.py` ahora usa `with closing(sqlite3.connect(tmp)) as out, out:`. Al terminar el bloque, la transacción se confirma y después se cierra explícitamente el handle de SQLite; solo entonces se ejecuta `os.replace`.

## Alcance

- No cambia la selección aleatoria, el filtro de etiquetas completas (`teacher_value` y `teacher_at`), los contadores, las barras de progreso, el esquema SQLite ni los argumentos.
- No cambia `run_genesis.ps1`. Las rutas y cambios del archivo `run_genesis(4).ps1` aportado por el usuario quedan intactos.
- La base de entrada sigue abriéndose en modo lectura (`mode=ro`), lo que permite lectura concurrente siempre que el otro proceso permita la lectura y SQLite pueda obtener los bloqueos necesarios.
- La salida `genus.pb` puede sobrescribirse tras la copia; si otro proceso tiene **la salida** abierta y bloqueada, Windows aún puede impedir el reemplazo. Este parche resuelve el handle filtrado por este mismo programa, no bloqueos externos sobre el destino.

## Aplicación

Extraer el ZIP desde la raíz `akkad` y volver a ejecutar `./run_genesis.ps1 --mon 1`. El fallo ocurrió antes del reemplazo del destino; se puede repetir el muestreo. No borrar ni renombrar manualmente bases de picoAlpha.

## Pruebas

Cinco pruebas Python superadas: cuatro pruebas preexistentes de muestreo y una nueva de cierre previo a `os.replace`. No se ha probado la reproducción de `WinError 32` en Windows nativo.
