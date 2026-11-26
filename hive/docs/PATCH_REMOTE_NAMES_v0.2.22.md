# Hive v0.2.22 — nombres operativos remotos
Base: Hive v0.2.21 (parche de recalibración).
El nombre declarado en el beacon se usa en conexión, transporte, asignación, Ki,
exclusiones y resultados. La identidad interna discovered-<node_id> se conserva
para deduplicación, asignación, desempates y reconexión. El handshake conserva
remote_id para auditoría. Un nuevo beacon actualiza el nombre visible sin cambiar
la clave interna ni reconectar. Los nombres duplicados siguen siendo recursos
independientes; se recomienda usar nombres únicos para legibilidad.
No cambia el optimizador ni el protocolo. El nivel verbose=2 conserva los
mensajes de protocolo y el JSON original para diagnóstico.
Pruebas: 38 unittest (chess simulado si no instalado), sintaxis Python.
Pendiente: validación con Hive físicos en Windows/Linux.
