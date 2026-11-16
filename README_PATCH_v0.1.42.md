# picoAlpha C++ v0.1.42 — corrección MSVC de min/max

## Diagnóstico
`windows.h` puede publicar macros `min` y `max` que expanden los nombres `std::min(...)` y `std::max(...)`, provocando C2589 y errores de tipo secundarios en `src/main.cpp`.

## Corrección
- Define `NOMINMAX` antes de incluir `windows.h`.
- Usa `(std::min)(...)` / `(std::max)(...)` para evitar expansión incluso si alguna cabecera los define.
- Actualiza el identificador de versión y el script de construcción a v0.1.42.

## Instalación
Descomprimir el ZIP en la raíz de `akkad`, sobre v0.1.41. Desde `akkad/picoAlpha` ejecutar:

```powershell
.\tools\ps\build.ps1
```

No requiere limpiar `X86/build`: CMake recompila `main.cpp`.

## Verificación realizada
Se compiló con g++ C++17 en Linux y con g++ simulando el entorno Windows (`_WIN32` y cabecera `windows.h` con macros min/max condicionadas por NOMINMAX). El ejecutable respondió `--help`. No se ejecutó MSVC en esta plataforma; el resultado final de Visual Studio debe confirmarse en Windows.

Sin cambios en búsqueda, mailbox, formatos de pesos ni inferencia.
