# Hive v0.2.0 — prototipo Python

Concentrador UCI dual (`stdin/stdout` y TCP `:6250`), distribuido entre endpoints UCI de tipo `tcp` o `uci` (proceso local). No implementa un motor de ajedrez propio.

## Dependencias y ejecución

```bash
python -m pip install -r hive/requirements.txt
python hive/src/hive.py --hive hive/etc/hive.yml
```

**Por defecto** `hive.py` exige `hive.yml` en el directorio de ejecución actual. `--hive` permite cualquier ruta válida. Los scripts `hive/tools/{ps,bash,macOS}/run.*` pasan el YAML de `hive/etc` si no se indica otro.

La configuración YAML es obligatoria, sin fallback a JSON. Al iniciar, intenta conectar motores configurados y somete a cada conexión exitosa a una prueba de un solo movimiento. `type: tcp` reintenta periódicamente; `type: uci` arranca y prueba una sola vez. Los motores TCP dinámicos se prueban con cada nueva conexión efectivamente establecida después de un anuncio, sin política de retry independiente del broadcast.

Para habilitar descubrimiento, `broadcast: true` anuncia por UDP/6251 el nombre, IP, puerto TCP y **suma de NPS observados en las pruebas**. `hive_network: true` escucha estos anuncios e intenta conectar Hives anunciados bajo una regla anticíclos de orden de identificadores.

Todas las salidas diagnósticas se imprimen exclusivamente en `stderr`; `stdout` se reserva a la sesión UCI exterior. Con `verbose: true` se registran comandos UCI internos de motores y el flujo de las sesiones exteriores en `stderr`.

## Límites conocidos

- La política de elección final es **MAX_CP experimental**; centipeones de motores heterogéneos no son necesariamente comparables.
- La fórmula `k_i=delta_i/sum(delta)` expresa *coste relativo*, no capacidad: el scheduler usa su recíproco para otorgar más movimientos a los motores rápidos. No hay recalibración durante partidas.
- Un mismo endpoint solo ejecuta una búsqueda a la vez. Si dos sesiones UCI exteriores buscan simultáneamente, comparten el pool de motores sin compartir tablero, comandos ni respuestas. La demanda concurrente puede producir una respuesta `bestmove 0000` si no quedan recursos libres.
- `go` implementa `depth`, `movetime`, `qdepth` (extensión) y `searchmoves`. No implementa todavía control de reloj UCI (`wtime`, `btime`, etc.). Un motor sin opción `QDepth` no recibe esa opción.
- Se prohíben ciclos entre Hives mediante **orden estricto de UUID**: solo se conecta de identificador mayor a menor. Esto restringe la dirección de algunas conexiones, incluso configuradas manualmente, para evitar ciclos bajo carreras concurrentes. No existe contratación ni reservas.
- `stop` cancela y descarta la transacción con workers activos para evitar que una respuesta atrasada contamine la siguiente búsqueda. Podría provocar `bestmove 0000` si no hay resultados consolidados.
- `info time`/`nodes` de distintos motores no necesariamente representan mediciones individuales comparables; Hive mide el tiempo de pared de cada transacción.
- No hay control de autenticación para el listener TCP, pensado inicialmente para LAN de confianza.

## Cambios v0.2.1

- Sesiones que compiten por todos los endpoints TCP ocupados esperan un motor libre, incluso si exceden `movetime`; `stop` cancela la espera.
- Cuando se necesitan más motores locales UCI, se inician procesos adicionales independientes, con una prueba por instancia.
- Reparto interno recalculado con `k_i = delta_i / sum(delta_i)` y pesos de asignación inversos.
- Broadcast agrega `engines`, cantidad de endpoints actualmente conectados.
- Un Hive descubierto es probado con `engines` transacciones UCI concurrentes (máximo `max_hive_probe_jobs`, default 32). Su tiempo equivalente de prueba es el tiempo de pared conjunto dividido por el número de respuestas.
- Pruebas: `python hive/tests/test_v020.py` y `python hive/tests/test_v021.py`.

Consultar `docs/prototype_v0.2.1.md`.
