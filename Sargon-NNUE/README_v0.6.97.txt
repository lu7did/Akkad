SARGON-NNUE v0.6.97 — RALLY: incidentes persistidos y --scores

INSTALACIÓN:
  Reemplazar únicamente src/sargon_nnue/sargon_rally.py.
  Mantener respaldo del archivo anterior.

CAMBIOS:
  1) Al comenzar una nueva ejecución de RALLY, crea el arreglo
     tournaments.<id>.match_incidents = [].
  2) Cuando el watchdog supera max_game_seconds, persiste de manera
     atómica un registro MATCH_TIMEOUT con match, brains, game,
     completed_games, planned_games y limit_seconds, ANTES de matar
     el proceso MATCH. Se registra una sola incidencia por proceso.
  3) --scores cuenta MATCH_TIMEOUT para ambos brains del registro;
     además cuenta los resultados persistidos con motivo
     MAX_PLIES_INCOMPLETE como ya hacía v0.6.96. No suma puntos
     ni partidas puntuables por estos eventos.
  4) No cambia MATCH, BOOST, TURBO, scoring ni otras funciones.

IMPORTANTE:
  Los timeouts de corridas antiguas, que sólo figuran en la consola,
  no pueden reconstruirse automáticamente en rally.json.
  Si el watchdog aborta el proceso durante la partida N, cuenta
  un incidente de timeout (para ambos brains), no las partidas
  pendientes del enfrentamiento.

VALIDACIÓN:
  - py_compile correcto.
  - Prueba funcional de --scores con 9 timeouts + 3 partidas de 200
    plies verificó las cuentas classic=5 s0040=5 s0100=5
    chimera=4 sT01=3 blend=2.
  - Comprobado que --scores no escribe rally.json.
  - Prueba real con procesos UCI en Windows pendiente.
