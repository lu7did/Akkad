# picoSargon v0.2.63 — corrección CMake en PowerShell

## Defecto reproducible
`build.ps1` construía `$configure` incluyendo expresiones como `'-DMULTICORE='+$Multicore` dentro de `@(...)`. En Windows PowerShell se descomponían en `-DMULTICORE=` y `ON` separados, produciendo el aviso de CMake `Ignoring extra path from command line: "ON"`, opciones en blanco y fallo de la nueva comprobación `MULTICORE:BOOL`.

## Corrección
Se usan elementos literales interpolados completos: `"-DSTEROIDS=$Steroids"` y `"-DMULTICORE=$Multicore"`. Se imprime `[CONFIG]` con los argumentos para diagnóstico. Se conservan las verificaciones de `CMakeCache.txt`, `--help` y el SHA256 del binario. `MULTICORE=ON` en CMake, mientras el ejecutable usa un solo núcleo por defecto, según el parche v0.2.61.

## Aplicación
Sobre la secuencia de parches hasta v0.2.62, descomprimir este ZIP en la raíz de Akkad. En Windows, ejecutar:

```powershell
.\picoSargon\tools\ps\build.ps1 --multicore ON --steroids ON --clean
.\picoSargon\x86\build\picoSargon.exe --help
```

Esperado: `[CONFIG] ... -DSTEROIDS=ON | -DMULTICORE=ON`, `[CHECK] CMakeCache MULTICORE=ON` y `--cores 1..1024` en `--help`.

## Límites de verificación
Comprobada estáticamente la modificación y la integridad del ZIP; no se pudo ejecutar PowerShell/MSVC de Windows en este entorno. El resultado de compilación nativa queda pendiente de la prueba del usuario.
