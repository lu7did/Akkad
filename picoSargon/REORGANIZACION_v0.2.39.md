# picoSargon v0.2.39 - reorganizacion de estructura

- x86 y debian sin carpeta intermedia `picoSargon`.
- macOS usa `macOS/build` (CMake generado); eliminar el antiguo `macOS/picoSargon`.
- Scripts de macOS en `tools/macos`, Debian en `tools/bash`, Windows en `tools/ps`, ARM en `tools/ARM`; `ARM/build.ps1` se conserva.
- Herramientas generales (GUI, bridge TCP, pruebas) permanecen en `tools/scripts`: no son exclusivamente Windows ni ARM.
- **No mover caches CMake entre rutas**: son generados y contienen rutas absolutas. Recompilar despues de la limpieza.
- El archivo `Sargon-NNUE/etc/brains/brains.json` incluye rutas nuevas para los perfiles de picoSargon.

Aplicacion desde `akkad/`:

1. Extraer el ZIP en la raiz del proyecto.
2. Ejecutar `python3 picoSargon/tools/cleanup_layout_v0.2.39.py --check` (Windows: `python`).
3. Si los archivos originales coinciden con los nuevos, ejecutar `--apply`.
4. Reconstruir x86, Debian, macOS y ARM en sus plataformas.

La limpieza elimina solo archivos antiguos cuyo contenido sea identico al archivo nuevo o a la version origen conocida. Los build outputs obsoletos se eliminan solo con `--purge-build`, siempre que el script haya podido validar las reubicaciones. Nunca elimina archivos desconocidos ni caches de compilacion sin la opcion explicita.
