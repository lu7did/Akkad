# Sargon-NNUE v0.6.99 — RALLY anomalías e inicialización

Reemplazar exclusivamente `src/sargon_nnue/sargon_rally.py`.

## Nueva persistencia

Al arrancar una corrida nueva después del preflight, se inicializan `ranking.resultados`, `scores`, `match_incidents`, `abnormal_terminations`, `status`, `errors` y `elapsed_seconds`. El resto de la definición del torneo se conserva. No se borran registros al ejecutar `--scores` o `--preflight-only`.

`abnormal_terminations` registra una entrada por partida terminada sin marcador definitivo que MATCH haya persistido en CSV (`GAME_INCOMPLETE` con `reason` original), o por partida inconclusa debido a watchdog (`MATCH_TIMEOUT`), salida anormal sin registro de la partida (`MATCH_PROCESS_ERROR`) o fin prematuro del enfrentamiento (`MATCH_INCOMPLETE`). Se registra el identificador de MATCH, número de partida inferido, ambos participantes y detalles disponibles. Los timeouts continúan también en `match_incidents` para compatibilidad.

`--scores` prefiere la nueva lista `abnormal_terminations` para contabilizar una incidencia a cada participante, sin modificar los puntos. En archivos antiguos utiliza las fuentes previas `ranking.resultados` y `match_incidents`. No se cuentan partidas futuras que nunca empezaron como si hubieran sufrido timeout.

## Advertencias

La causa de una interrupción puede no determinarse con precisión si MATCH termina sin escribir su CSV; el registro indica `MATCH_PROCESS_ERROR` y su exit code, no adjudica responsabilidad a un brain. El juego afectado se infiere como el siguiente después de los registrados. RALLY no modifica MATCH ni recupera los mensajes anteriores que solo estaban en consola.
