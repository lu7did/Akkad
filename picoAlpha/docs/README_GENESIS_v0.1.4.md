# picoAlpha Genesis v0.1.4 — Diagnóstico de rutas y bases

- `run_genesis.ps1`: llama directamente a los scripts Python para impedir que defaults de wrappers sustituyan rutas absolutas. Los seis pasos `MON=0..5` se conservan.
- Antes y después de las fases de bases de datos se informa la ruta absoluta real, existencia, tamaño, tablas y conteos de partidas/posiciones.
- `verify_database.py --in PATH [--min-games N]`: verificación **de solo lectura**, no crea archivos por error de ruta. La validación del histórico después de crear/importar se realiza **antes** de avanzar MON.
- `sampler.py` verifica la base de entrada antes de abrir SQLite y registra el origen exacto.
- Los pasos se invocan con rutas absolutas definidas por `-HistoryDir`; el script muestra `CWD`, carpeta del script y patrón PGN.
- Codificación PowerShell UTF-8 BOM y salida UTF-8 para mejorar la visualización de ⚙️ en Windows. La consola debe usar una fuente compatible con Unicode.

**Atención:** el paso 0 **elimina** `history.pb`, comportamiento anterior preservado. Si se quiere conservar un histórico existente, no ejecutar Genesis completo hasta añadir una modalidad explícita de continuación.

Pruebas en este entorno: verificador real con SQLite y error de base inexistente/incorrecta; sin intérprete `pwsh` disponible para probar la ejecución completa en Windows.
