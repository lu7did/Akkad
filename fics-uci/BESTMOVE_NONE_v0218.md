# fics-uci v0.2.18: bestmove vacío en posición no terminal

- Diagnóstico: al recibir `bestmove (none)` o `0000`, registra ply, halfmove,
  número de jugadas legales, posibilidad de reclamar tablas de 50 jugadas o
  triple repetición y terminación sin reclamaciones opcionales.
- Si el tablero es no terminal y existen movimientos legales, cierra el socket
  UCI y lo reconecta para **un** reintento por posición. Conserva el historial
  FICS verificado y no envía ningún movimiento inventado.
- Si el motor vuelve a devolver `(none)`, bloquea la emisión, solicita `moves`
  y deja constancia diagnóstica. No es un mecanismo para suplir un motor que
  interpreta incorrectamente reclamaciones opcionales de tablas.
- Para eliminar la causa, revisar en el motor el uso de `board.is_game_over(claim_draw=True)`:
  solamente deben impedir una búsqueda las terminaciones reglamentarias
  automáticas; el derecho a reclamar tablas se maneja como decisión aparte.
- Es una corrección del puente, **no** del motor remoto.
- Aplicar el ZIP desde la raíz Akkad. No incorpora secrets ni config.yml.
