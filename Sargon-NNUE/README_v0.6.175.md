# Sargon-NNUE v0.6.175 — Corrección del script Windows de tinyAlpha

Cambio aislado de `native/tinyAlpha/build_windows.ps1`.

**Motivo**: v0.6.174 obligaba al generador Ninja y atribuía cualquier fallo de CMake a zlib.

El script usa por defecto `Visual Studio 18 2026` (Visual Studio 2026 Community), arquitectura x64, sin Ninja. Busca el ejecutable en `build_windows/Release/tinyAlpha.exe`. Permite configurar el toolchain de vcpkg con `-VcpkgRoot` o `$env:VCPKG_ROOT`.

## Uso

Desde `native/tinyAlpha`:

```powershell
.\build_windows.ps1
```

Si la configuración indica `Could NOT find ZLIB`, instalar vcpkg y su biblioteca para MSVC x64:

```powershell
& "C:\ruta\vcpkg\vcpkg.exe" install zlib:x64-windows
.\build_windows.ps1 -VcpkgRoot "C:\ruta\vcpkg"
```

**Importante**: si el directorio `build_windows` fue configurado previamente con otro generador, CMake puede indicar un conflicto de generadores. Borre **solo** `native/tinyAlpha/build_windows` y ejecute nuevamente. No borre el código fuente ni los datos.

Si la máquina tiene otra versión de Visual Studio, pase un generador compatible con su versión (por ejemplo `-Generator 'Visual Studio 17 2022'`).

No se modifica el motor, la red, el protocolo UCI, los brains ni otros componentes.

Este script no se ha ejecutado en Windows en este entorno; la comprobación se limita a inspección estática y contenido del paquete.
