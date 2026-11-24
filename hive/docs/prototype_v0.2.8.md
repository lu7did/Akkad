# Hive v0.2.8 — Un único registro de cada `info` UCI

- Los frames UCI entrantes que comienzan con `info ` se registran exactamente una vez con `ℹ️`.
- Se elimina para esos frames la línea redundante `📮` sin modificar el mensaje UCI recibido ni el comportamiento de búsqueda.
- Los demás frames siguen con `📮`; `bestmove` conserva la telemetría existente.
- `stderr` continúa siendo el único destino de telemetría.
- Aplicar este parche incremental sobre Hive v0.2.7.
