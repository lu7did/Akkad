# picoSargon v0.2.40 - normalizacion efectiva de carpetas

El ZIP es incremental y se extrae desde la raiz akkad. **Descomprimir un ZIP NO elimina carpetas antiguas.**

Desde la raiz akkad, ejecutar:

- Windows: `python picoSargon/tools/migrate_layout_v0.2.40.py --check` y `python picoSargon/tools/migrate_layout_v0.2.40.py --apply`
- macOS/Debian: `python3 picoSargon/tools/migrate_layout_v0.2.40.py --check` y `python3 picoSargon/tools/migrate_layout_v0.2.40.py --apply`

Movera **todos** los archivos de `x86/picoSargon/` a `x86/`, de `debian/picoSargon/` a `debian/`, de `macOS/picoSargon/` a `macOS/` y reclasificara `tools/scripts/` como `tools/uci/`. Los scripts PowerShell van a `tools/ps`, los de ARM a `tools/ARM`, manteniendo `ARM/build.ps1`.

Los arboles build obsoletos de las ubicaciones antiguas se eliminan (artefactos regenerables). `x86/build-host-windows` se conserva en su nuevo lugar, pero se elimina `CMakeCache.txt` para que se regenere con las rutas correctas. Nunca se sobrescribe un archivo canonico; archivos antiguos diferentes se resguardan fuera del repo, en una carpeta hermana `akkad-picoSargon-backup-v0.2.40`.

Las carpetas antiguas solo se eliminan despues de vaciarse. La operacion es repetible. Revisar el `git status` antes de confirmar cambios. Si hay enlaces o permisos especiales que impidan una eliminacion, se informa el problema y se conserva el elemento.

Rutas canonicas: `picoSargon/ARM`, `picoSargon/debian`, `picoSargon/macOS`, `picoSargon/x86`, `picoSargon/tools/{ARM,bash,macos,ps,uci}`.

Validar despues: `./picoSargon/macOS/build.sh`; en Debian `./picoSargon/tools/bash/build.sh`; en Windows `./picoSargon/tools/ps/build.ps1`.
