# Reconstrucción completa de AlphaZero Windows x64

Este parche sustituye `AlphaZero/build.ps1` en la nueva ubicación. No contiene binarios ni altera el núcleo C++.

## Procedimiento

En PowerShell de Visual Studio (con herramientas C++ instaladas):

```powershell
cd C:\Users\pedro\github\Bobby\akkad\AlphaZero
.\build.ps1 -CleanSource
```

Requiere Git, Python, Meson, Visual Studio C++ y conectividad a los repositorios LC0/NuGet. Descarga los pesos de red por separado. Usa `-Backend onnx` (predeterminado) para ONNX Runtime DirectML y alternativa Eigen incluida en LC0. Reconstruye `lc0-build` y, con `-CleanSource`, vuelve a clonar fuentes de LC0.

El script recopila DLLs producidas por Meson (incluida Abseil cuando se genera como DLL), copia ONNX y DirectML, e inspecciona imports directos del EXE mediante dumpbin. Si falta una DLL, falla con un nombre concreto. No presupone compatibilidad ABI con bibliotecas de otra construcción. Se recomienda validar además con Dependencies los imports transitivos.

## Prueba

```powershell
cd ..\Sargon-NNUE\scripts
.\diagnose_emma.ps1 -TimeoutSeconds 90
```

**Nota**: la construcción real en Windows/DirectML no se ha podido ejecutar en este entorno. Si Meson obliga a generar Abseil fuera de lc0-build, puede requerir adaptar la recolección a la ruta específica que informe el compilador.
