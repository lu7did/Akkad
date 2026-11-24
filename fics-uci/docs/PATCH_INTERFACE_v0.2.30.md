# FICS-UCI v0.2.30
Base: parche interface v0.2.29. Corrige AttributeError en main(): inicializa a.interface = None antes de fusionar YAML y defaults. Conserva interface exclusivamente YAML, valor vacío por defecto y envío tras autenticación. Agrega telemetría de configuración efectiva. No cambia otras opciones.

Pruebas: 7 casos pytest (carga real de YAML con main y Bridge simulado, envío inicial, ausencia, vacío, no repetición). Sin conexión real a FICS.
