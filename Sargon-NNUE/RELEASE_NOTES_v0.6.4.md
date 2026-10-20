# Sargon-NNUE v0.6.4

## Listener concurrente multi-partida

- El listener TCP acepta múltiples conexiones UCI simultáneas.
- Cada conexión tiene su propio `UCISession`, `chess.Board`, evaluator y player.
- Se elimina la política v0.6.3 que reemplazaba/cerraba la sesión anterior.
- Se elimina el lock global alrededor de `player.choose()`: búsquedas de sesiones distintas pueden ejecutarse concurrentemente.
- Cada player se cierra exclusivamente cuando finaliza su propia sesión.
- Una desconexión o partida truncada no afecta a las demás sesiones activas.
- El listener mantiene un registro de sesiones sólo para telemetría y cierre limpio al apagar el servidor.
- Los modelos NNUE no se comparten todavía entre sesiones; el aislamiento funcional se prioriza sobre la optimización de memoria.

## Compatibilidad

No se modifican algoritmos de evaluación ni búsqueda. La modificación está limitada a infraestructura TCP/UCI y ciclo de vida de sesiones.
