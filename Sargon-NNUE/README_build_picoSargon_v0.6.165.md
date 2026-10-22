# Sargon-NNUE v0.6.165 — compilacion Windows picoSargon

Parche incremental: **solo agrega** `scripts/build_picoSargon.ps1`. No altera fuentes C++, evaluadores, partidas, ni `data`.

## Uso desde terminal PowerShell de VS Code

```powershell
cd 'C:\Users\pedro\github\Bobby\Akkad\Sargon-NNUE'
.\scripts\build_picoSargon.ps1
```

El script: (1) detecta MSVC o lo inicializa mediante `vswhere.exe` y `vcvars64.bat`; (2) configura y compila Release con Visual Studio 18 2026 mediante `native/picoSargon/build_host.py`; (3) busca `picoSargon_host.exe`; (4) ejecuta el smoke test UCI (`uci`, `isready`, `position startpos`, `go depth 2`, `quit`); (5) falla con codigo 1 si hay problemas.

Opciones:

```powershell
.\scripts\build_picoSargon.ps1 -Clean
.\scripts\build_picoSargon.ps1 -SkipTest
.\scripts\build_picoSargon.ps1 -Generator 'Visual Studio 18 2026'
```

`-Clean` elimina **solo** `native/picoSargon/build-host-windows`. Se utiliza tras cambiar generador CMake. La salida esperada es `native/picoSargon/build-host-windows/Release/picoSargon_host.exe`.

Prerrequisitos: VS 2026 Community con Desktop development with C++, CMake y Python (`ufasta`) instalados. Si cambian sus rutas, usar `-Python` y `-CMake`.

**Validacion:** script creado y revisado estaticamente en este entorno Linux. La ejecucion real con MSVC y el exe Windows debe probarse en el PC del usuario.
