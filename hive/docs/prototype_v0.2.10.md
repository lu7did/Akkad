# Hive v0.2.10 — niveles de telemetría
Base: parche Hive v0.2.9. Aplicar desde la raíz de Akkad.

- verbose: 0: diálogo UCI del cliente externo, sin diagnóstico interno.
- verbose: 1 (default): añade conexión, balance, asignación y resultados de motores.
- verbose: 2: añade tráfico interno completo, info y diagnóstico detallado.
- YAML booleanos anteriores: false=0, true=1. CLI --verbose 0|1|2 prevalece.
- bestmove del worker se muestra una sola vez con 🧠 y estadísticas del movimiento elegido; los info internos usan ℹ️ exclusivamente.
- No se modifica el flujo de mensajes UCI ni el procesamiento de scores, scheduler o selección de movimientos. La asignación se muestra como resumen.
- No se reemplazan archivos YAML operativos. Un valor explícito previo sigue vigente.
- Corrección auxiliar: cálculo del ancho de etiquetas admite configuración sin motores.
- Validación: py_compile y 9 pruebas unitarias con transporte simulado. En el entorno de validación falta python-chess; se usó un módulo sustituto únicamente para STARTING_FEN/importación. Sin prueba integral contra motores reales.
