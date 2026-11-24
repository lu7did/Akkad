# picoSargon host v0.2.61 — MULTICORE compilado, 1 núcleo por defecto

## Cambios

- `MULTICORE=ON` continúa siendo el valor predeterminado de CMake para x86, Debian y macOS y el de los scripts de compilación. No se cambia a OFF.
- Sin `--cores` y sin `setoption name Cores value ...`, el ejecutable usa **1 núcleo de búsqueda** incluso cuando MULTICORE está compilado.
- `--cores N` activa N workers (limitados por el número de núcleos físicos y movimientos legales), al igual que `setoption name Cores value N`.
- `uci` anuncia `option name Cores type spin default 1 min 1 max 1024` siempre que MULTICORE esté compilado.
- Si se compila expresamente con `MULTICORE=OFF`, se conserva el modo exclusivo mononúcleo y no se anuncia `Cores`.
- No se modifica el scheduler alpha-beta, el protocolo Hive `searchmoves`, STEROIDS ni la telemetría `multipv`.

## Windows: reconstrucción para evitar el cache de CMake

Desde la raíz de Akkad:

```powershell
.\picoSargon\tools\ps\build.ps1 --multicore ON --steroids ON --clean
.\picoSargon\x86\build\picoSargon.exe --help
```

Con `MULTICORE=ON` la ayuda debe incluir `--cores 1..1024`. `--cores` requiere que el binario esté compilado con esta opción; no alcanza con modificar argumentos de ejecución de un binario anterior.

## Comprobación UCI

- Arranque sin `--cores`: `uci` anuncia `Cores ... default 1`, y las búsquedas usan una instancia.
- Arranque con `--cores 4`: puede usar hasta cuatro workers.
- El modo UCI `setoption name Cores value 3` permite actualizar el número de workers antes del próximo `go`.

## Alcance

Parche incremental sobre **v0.2.60**. Rutas relativas a la raíz de Akkad. En el entorno Linux se puede comprobar compilación y UCI; Windows/MSVC y macOS requieren pruebas nativas.
