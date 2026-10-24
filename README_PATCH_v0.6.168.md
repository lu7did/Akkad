# Parche incremental de resiliencia — Sargon-NNUE v0.6.168 / picoAlpha / picoSargon

Base del módulo match: Sargon-NNUE v0.6.161 incluida en el ZIP del usuario. Esta revisión preserva la semántica del adaptador v0.6.167. El adaptador TCP actualizado procede del parche ya aplicado de telemetría v0.6.167; **no retroceder** si la instalación actual tiene una versión más nueva. Si existe una versión posterior en su entorno, comparar antes de aplicar manualmente.

Base picoAlpha: firmware con crecimiento MCTS dinámico y diagnóstico de memoria, compatible con el parche anterior v0.2.13. Base picoSargon: ZIP suministrado.

Solo copiar los archivos incluidos en cada subcarpeta hacia la raíz de su proyecto respectivo. No copiar archivos `data` ni `docs`. Conservar copia de seguridad.

## Comportamiento

- Al fallar un `go`, el puente UCI emite `info string error ...` y `bestmove (none)` para finalizar el comando; el match reconoce ese marcador como error técnico (no jugada).
- La partida se cierra mediante **derrota técnica** del lado que falló, con etiqueta `TECHNICAL_FORFEIT`, no como jaque mate. No se reintenta automáticamente la jugada para no alterar los resultados del torneo.
- Tras cada incidencia, se cierran ambos procesos de interfaz UCI y se crean dos procesos nuevos con archivos de log diferenciados `.recovery.gameN.log`. Antes de cada partida se comprueba `isready`.
- Si la reconstrucción falla, el torneo se detiene, conservando resultados ya escritos. No se generan cadenas de ocho partidas fallidas.
- LED: fijo=Ready; lento=Thinking; triple destello=Sin Wi-Fi; **doble destello corto (120ms cada uno, ciclo 1600ms)=error de sesión recuperable**; destello rápido=Fatal. El nuevo patrón puede volver a fijo al aceptar una nueva conexión.
- Los firmwares capturan errores de búsqueda (`std::exception`) y envían `info string error ...` seguido de `bestmove 0000` para que el cliente no espere indefinidamente; el estado recuperable queda señalizado.

## Limitaciones y precauciones

- **No se instala watchdog físico**: un bloqueo total del procesador no puede detectarse ni señalizarse desde el bucle bloqueado. El timeout principal del match es la protección disponible, y hay que conectar watchdog independiente para recuperación de cuelgues físicos.
- Un `ping` correcto no certifica salud UCI. Una ausencia de respuesta a ping puede ser radio Wi-Fi, alimentación o firmware bloqueado.
- La pérdida física de Wi-Fi y ciertos errores de transporte pueden cambiar el patrón del LED al estado Sin Wi-Fi: ese estado predomina sobre el error recuperable.
- No se ha compilado en hardware. Los módulos Python sí pasaron validación sintáctica. Probar una partida corta y luego inyectar deliberadamente una desconexión de red antes de ejecutar un torneo largo.

## Secuencia de validación

1. Compilar ambos firmwares por separado; comprobar `uci` e `isready` desde TCP.
2. Buscar una posición con cada motor, observar Thinking y vuelta a Ready.
3. Cortar la red o apagar una placa durante una búsqueda; comprobar `TECHNICAL_FORFEIT` y `RECOVERY_FAILED` o restablecimiento controlado, sin falsa jugada.
4. Restaurar el motor y correr un match de 2 partidas; verificar archivos `*.recovery.gameN.log`, CSV y PGN.

Nota: el diseño de la recuperación puede registrar derrota técnica de un motor que sufre un fallo de conectividad externo. Es política operativa del torneo, no una inferencia sobre calidad de juego.
