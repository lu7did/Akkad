# Nurse v0.1.14 — Nombres, TCP y unicidad de brains

- type=nurse o type=uci: el encabezado del benchmark usa el ID de `brains.json`.
- type=external: el encabezado usa `id name` UCI recibido durante el handshake; no se valida ni exige que coincida con el ID local.
- Línea TCP compacta: `🌐 TCP host:port DNS=[ip,...] name=<id name>`; no muestra peer/local.
- `brains.json`: claves duplicadas en cualquier objeto JSON, incluidos los IDs de `brains`, se rechazan mediante `object_pairs_hook`, antes de ejecutar motores. La regla ya estaba en v0.1.13 y continúa vigente.
- La información completa de sockets sigue registrada en telemetría de diagnóstico.
- No cambia el transporte TCP, la política de búsqueda ni los algoritmos de los motores.
