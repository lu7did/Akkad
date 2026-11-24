# Hive v0.2.7 — Telemetría UCI

Parche incremental **sobre v0.2.6**. No modifica la semántica de UCI, `kmin`, las preferencias ni las sesiones concurrentes. Todas las trazas se escriben en **stderr**, bajo un bloqueo único para impedir líneas intercaladas, sin contaminar stdout ni los sockets UCI.

## Eventos

| Marca | Evento |
|---|---|
| 🌐 | Listener TCP activo |
| 🔗 | Comienza/termina sesión UCI por stdin/stdout |
| ⚡ | Intento de conexión/inicio de motor, con ruta y argumentos o IP:puerto |
| ⛔ | Error de conexión, prueba fallida o apagado |
| ✅ | Motor conectado y posición FEN de prueba |
| ⚙️ | Argumentos multilínea, métricas de prueba, índice de latencia y prioridad |
| ✉️ | Comando UCI enviado a un motor interno, incluidos handshake, `position` y `go` |
| 📮 | Mensaje UCI recibido del motor interno |
| ℹ️ | Mensaje `info` recibido (se muestra además su frame crudo 📮) |
| 🧠 | Mensaje `bestmove` recibido (también se muestra el frame crudo 📮) |
| ➡️ | Comando UCI recibido por cualquier sesión exterior, con etiqueta `stdio` o `tcp:host:port` |
| ⬅️ | Respuesta UCI enviada por Hive a la sesión exterior |
| 🚨 | Broadcast enviado (payload JSON exacto) |
| ⚖️ | Probabilidad efectiva por motor conectado, solo cuando cambia el equilibrio |

Las etiquetas de motor se alinean en un campo de ancho mínimo 12; si existe un motor configurado con un nombre mayor, la anchura se amplía para el proceso. Los argumentos extensos aparecen en varias líneas `⚙️` sin truncarse. `verbose: true` habilita además stderr de los motores locales.

Las preferencias se registran como `latency_k`, `kmin`, `priority`, `wall_test_ms` y `total_priority`, mientras que el equilibrio `⚖️` representa **priority**, no el índice de latencia. La serie `⚖️` se actualiza cuando cambia el conjunto de motores o sus prioridades, sin emitir líneas redundantes por cada búsqueda.

## Pruebas

- `python -m unittest discover -s hive/tests -p 'test_v0*.py' -v` (36 pruebas, incluye 4 nuevas pruebas de telemetría).
- `python -m py_compile hive/src/hive.py hive/tests/test_v027.py`.

El test histórico `test_prototype.py` fue escrito para API v0.1.0, ya retirada, por lo que no representa la regresión de v0.2.x. Se conserva sin cambios.
