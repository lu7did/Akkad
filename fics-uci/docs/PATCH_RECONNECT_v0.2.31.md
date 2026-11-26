# FICS-UCI v0.2.31 — Recuperación de conexión FICS

Base: parche v0.2.30. No se modifica el YAML operativo ni el algoritmo de selección de jugadas.

- Un EOF, timeout/error de lectura o fallo de envío de FICS no termina la aplicación ni envía quit a UCI. Se cierra solo FICS y se suspende la búsqueda en curso mediante stop. Si el motor no responde, se conserva el watchdog existente.
- Reconexión automática, con espera `retry` (mínimo 1 segundo) o 5 segundos si no está configurado. Login/resincronización tiene un límite de 60 segundos. Una sesión anterior aún activa durante recuperación provoca reintento; credenciales inválidas conservan el fallo explícito.
- Se restauran login, set interface, style 12 y demás parámetros de sesión; se solicita `refresh`. Se descartan eventos de sockets reemplazados y se impiden nuevas búsquedas y emisiones de movimientos hasta recibir estado actualizado.
- Si el servidor confirma que no hay partida, se limpia el estado local sin inventar un resultado. Si continúa la misma partida, se exige reconciliación del historial. Se conservan los movimientos verificados; si hay un salto de múltiples medias jugadas que el reconciliador no puede verificar, se bloquea el juego y solicita `moves` como antes. Esta versión no reconstruye automáticamente el historial a partir del listado `moves` ni garantiza reanudar una partida aplazada por el servidor.
- TCP keepalive en ambos sockets: Windows 60 s de inactividad y 15 s de intervalo; Linux 60/15/4 cuando las opciones están disponibles. Los fallos al configurar keepalive se registran sin impedir la conexión.

Pruebas: `python -m pytest fics-uci/tests -q` desde la raíz (requiere pytest). 13 pruebas superadas con conexiones y tablero simulados; pendiente validación contra FICS real y Windows. El intervalo de reconexión y el límite de login son decisiones de implementación, no nuevos parámetros YAML.
