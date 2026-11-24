# Implementación inicial de Hive — v0.1.0

La implementación es un **experimento**, no una arquitectura cerrada. Conserva los documentos `hive/docs` presentes en la línea de base `akkad(20261124-175149).zip` sin reemplazarlos.

## Flujo

1. El frontend UCI `stdin/stdout` reconstruye la posición con `python-chess` y enumera jugadas legales.
2. Un thread de conexión reintenta endpoints estáticos configurados cada `reconnect_seconds`.
3. `go` asigna subconjuntos de `searchmoves` según pesos locales; cada motor recibe `position`, `go movetime`, opcional `depth` y al final `searchmoves`.
4. Una tarea por endpoint procesa la respuesta, valida `bestmove` y obtiene el último `info` con PV correspondiente.
5. Se mide el tiempo de pared local. Se selecciona el mayor CP **solo como política experimental** (mates a favor con prioridad, cotas excluidas si existen exactos).
6. Se emite un único `info ... pv` y un único `bestmove`.

## Limitaciones y riesgos

- No se deben confundir puntuaciones CP numéricamente homogéneas con evaluaciones de calidad equivalente.
- La observación `tiempo/movimiento` es inválida si `movetime` se agota; se evita aprender de respuestas próximas al deadline. El scheduler sigue siendo una **hipótesis**, no un balanceador demostrado.
- Un motor `MultiPV` puede emitir datos globales de nodos/tiempo; estos no son medidas independientes por movimiento.
- Los endpoints deben cumplir realmente `searchmoves`; no se ha agregado aún una prueba formal de conformidad.
- Las respuestas sin score o de motores desconectados no producen una jugada útil; `bestmove 0000` no es una salida segura para juego real cuando hay movimientos legales.
- El frontend no emite info intermedia; evita tráfico innecesario, y mantiene toda la telemetría de endpoints local.
- Durante `stop`, se interrumpe la espera y la conexión del motor ocupado se invalida si es necesario; se requiere perfeccionar propagación y cierre.
- La estructura de directorios `hive/src` está destinada al prototipo Python y a futuros fuentes C++.

## Pendientes prioritarios

1. Política robusta ante timeouts, `stop`, posiciones y sesiones concurrentes.
2. Descubrimiento UDP de endpoints dinámicos, sin reintento de reconexión activa para esos nodos.
3. Prueba con motores TCP UCI reales (picoSargon, Stockfish, AlphaZero, etc.).
4. Diseño del scheduler adaptativo y consolidación de puntuaciones heterogéneas.
5. Hierarquías sin ciclos y uso exclusivo de frontend cuando un Hive es subordinado.
