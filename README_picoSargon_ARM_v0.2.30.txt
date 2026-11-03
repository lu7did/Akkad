Parche incremental picoSargon ARM v0.2.30
LINEA BASE EXCLUSIVA: akkad(10).zip
Aplicar desde la raiz Akkad (sobrescribir rutas contenidas).

Cambios:
- pico_main.cpp: usar config::UCI_NAME para id name y banner USB; eliminar VERSION literal.
- Telemetria BOOT: imprimir DEPTH/QDEPTH/TIMEOUT_MS compilados.
- build.ps1: mostrar parametros y SHA256 del config.h de origen, sin exponer credenciales.
- CMakeLists.txt: version 0.2.30.

config.h NO se modifica ni se incluye en el parche, para preservar las credenciales locales.
En la base akkad(10).zip DEPTH=6, QDEPTH=2, TIMEOUT_MS=150.
La telemetria previa con depth=4 y timeout=15000 NO coincide con la base.

Compilar desde picoSargon/ARM con .\build.ps1 y cargar el UF2 de la
ruta exacta que el script imprime; no reutilizar un UF2 anterior.
Comprobar por USB: BOOT config depth=6 qdepth=2 timeout_ms=150.
Nota: 150 ms puede detener iteraciones antes de llegar a profundidad 6.
Si se quiere permitir 15 segundos, editar TIMEOUT_MS=15000 en el config.h local
antes de compilar (no se cambia silenciosamente este valor).
