# Cambio de nombre tinyAlpha a picoAlpha

Cambio de identidad, sin cambios en los algoritmos de búsqueda, evaluación, red ni protocolo UCI.

- Proyecto CMake y ejecutables: `picoAlpha.exe` (INT8 default), `picoAlpha32.exe` (FP32 referencia).
- Directorio de fuentes: `native/picoAlpha/`.
- Player CLI/configuración: `picoalpha`; adaptador Python: `players/picoalpha_uci.py`.
- En brains.json, configuraciones externas y scripts de terceros se deben actualizar manualmente las referencias anteriores al player y al executable.
- El directorio generado `native/tinyAlpha/build_windows/` fue excluido: contiene cachés CMake y binarios de la identidad anterior. Recompilar para regenerarlos.
- Los instaladores y registros históricos con el nombre anterior permanecen como evidencia histórica y **no deben ejecutarse** para una instalación actual.
- `picoSargon` no se modificó.

## Compilar en VS Code/PowerShell

```powershell
cd .\native\picoAlpha
.\build_windows.ps1 -VcpkgRoot "C:\Users\pedro\vcpkg"
```

Si no se pasa el parámetro, se prueba `VCPKG_ROOT` y luego `$HOME\vcpkg`. Necesita `zlib:x64-windows` instalado en vcpkg y un generador Visual Studio compatible (se puede pasar `-Generator`).

Esta entrega no certifica la compilación en Windows: debe ejecutarse en el equipo destino para validar Visual Studio y dependencias.

- A partir de v0.6.180 cualquier binario legado `picoAlphaFP32.exe` o `picoAlphaInt8.exe` debe descartarse.
