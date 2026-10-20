# picoSargon v0.2.10 - Configuracion unica config.h

**Instalar solamente los archivos presentes en este parche**, manteniendo el resto de picoSargon v0.2.8/v0.2.9.

Editar `include/config.h` directamente desde VS Code y configurar SSID/contraseña (texto claro).
El firmware NO incluye credenciales reales. Valores por defecto:

- `UCI_NAME = "picoSargon v0.2.10 C++"`
- `SSID = "CAMBIAR_SSID"`
- `PASSWORD = "CAMBIAR_PASSWORD"`
- `PORT = 6110`
- `TIMEOUT_MS = 15000` (0 deshabilita límite)
- `DEPTH = 4`
- `QDEPTH = 2`
- `DEBUG = false` (reservado para futuro)

`QDEPTH` llega al constructor de `Engine` y controla exclusivamente la quiescencia.
`DEPTH` pasa a `Engine.search` para búsquedas UCI. Se conserva la regla histórica de extensión de jaques y MAX_PLY.

`build.ps1` ya NO exige `generated_config.hpp`, y no regenerará secretos. Ejecutar:

```powershell
.\build.ps1 -Board pico_w
```

Verificar en serie `SEARCH begin max_depth=4 qdepth=2 timeout_ms=15000` y en UCI `id name picoSargon v0.2.10 C++`.

El archivo `config.h` se excluye de Git (contiene password). Al instalar este parche sobre el proyecto existente, el archivo se proporciona como plantilla; editarlo localmente. No incluir secretos reales en ZIP de distribucion.

Se ha probado la compilacion y busqueda del host Linux. La compilacion ARM Pico SDK queda pendiente en Windows.
