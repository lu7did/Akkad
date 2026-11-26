# Hive v0.2.21 — Interrupción segura de recalibración

Base: parche v0.2.20 (sobre v0.2.19 y v0.2.18). No modifica YAML, broadcasting, afinidad, fórmulas Kmin/Kmax/Ki ni FEN/depth del testigo.

- Un `go` válido registra interés antes de lanzar el hilo de búsqueda. Impide iniciar una calibración voluntaria o cancela la que esté en curso.
- Se usa el mecanismo existente de `stop` → `bestmove` → `isready`/`readyok`; el motor se descarta solo cuando el transporte no se puede recuperar. El test no publica muestras parciales si se cancela.
- Se restauran las mediciones previas de los transportes locales aún vivos y se recalculan las asignaciones con los recursos actualmente disponibles. Las capacidades remotas anunciadas no se revierten.
- No se actualiza el instante de la última calibración completa si se interrumpe. Se reintentará cuando haya inactividad. La calibración obligatoria (máximo distinto de -1) conserva el mecanismo de drenaje y bloqueo de nuevas asignaciones.
- Si no existe resultado evaluado, `bestmove 0000` en lugar de elegir el primer movimiento arbitrariamente. FICS-UCI ya contempla un reintento de bestmove vacío.
- Se registra el motivo del cierre TCP (quit, EOF, fallo de envío/recepción, rechazo, cierre de sesión).

Pruebas: `python -m unittest discover -s hive/tests -v` desde la raíz. 35 pruebas superadas bajo Linux, con tablero simulado por falta de python-chess. Incluyen regresiones de broadcasting y afinidad. Pendiente validación de cancelación bajo carga con motores reales y Windows.
