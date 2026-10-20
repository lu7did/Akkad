# picoSargon v0.2.3 — Windows host tools (parche incremental)

Este parche reemplaza exclusivamente `build.ps1` de picoSargon v0.2.2.

## Problema corregido

Al compilar para `pico_w`, CMake detectaba correctamente GNU Arm, pero intentaba construir `pioasm` y `picotool` para **Windows**, y no había compilador C/C++ de Windows en el entorno. Los binarios precompilados entregados por la extensión Raspberry Pi Pico evitan esa construcción auxiliar.

`build.ps1` ahora especifica:

- `pioasm_DIR=C:\Users\pedro\.pico-sdk\tools\2.3.1\pioasm`
- `picotool_DIR=C:\Users\pedro\.pico-sdk\picotool\2.3.1\picotool`

El script exige que existan las configuraciones CMake de ambas herramientas; si no están, muestra un error específico antes de comenzar. No modifica el entorno global de Windows.

El directorio de compilación es nuevo: `build-pico-w-v023` (Pico 2 W: `build-pico2-w-v023`). Esto evita que se reutilicen tareas auxiliares de compilaciones CMake anteriores. La carpeta antigua NO se borra.

## Instalación

1. Copiar el archivo `build.ps1` en la raíz del proyecto reemplazando el anterior.
2. Asegurar que ya están instalados los archivos del parche v0.2.2 (`CMakeLists.txt` y `config/lwipopts.h`).
3. Desde PowerShell en la raíz: `./build.ps1` (en Windows PowerShell: `.\build.ps1`).
4. Resultado esperado: `build-pico-w-v023\picoSargon.uf2`.

## Si falta una de las herramientas

Antes de recompilar, comprobar en PowerShell:

```powershell
Get-ChildItem "$HOME\.pico-sdk\tools" -Recurse -Filter pioasm-config.cmake
Get-ChildItem "$HOME\.pico-sdk\picotool" -Recurse -Filter picotool-config.cmake
```

Si esas rutas están en otro lugar, ajustar únicamente `$PioasmDir` o `$PicotoolDir` en el script usando la carpeta que **contiene** el archivo `*-config.cmake`. Si no existen, completar la instalación de las herramientas auxiliares de Pico SDK desde la extensión Raspberry Pi Pico. La alternativa es instalar/configurar un compilador nativo Windows (MSVC, MinGW o clang) para construirlas, lo cual no es necesario cuando se dispone de los binarios precompilados.

El parche resuelve este bloqueo de configuración observado. No garantiza que no aparezcan errores posteriores del código C++ ni sustituye la prueba real en Windows/Pico.
