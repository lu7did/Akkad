# Monitor UCI (FICS-UCI v0.2.19 + Challenger v0.2.2)

## FICS-UCI

`python fics-uci/src/fics_uci.py --config fics-uci/etc/config_macia.yml --monitor 6201`

El argumento opcional `--monitor PORT` abre un listener de observación en todas las interfaces IPv4. Sin este argumento no se abre el socket. Un error al abrirlo no detiene el puente FICS-UCI. Cada observador recibe los frames UCI de entrada y salida en el orden en que el puente los procesa. Las líneas con emoji son telemetría local, no parte del stream TCP.

El monitor **no es un segundo servidor UCI**: solo difunde frames, no acepta órdenes de juego. Cuando FICS confirma una movida, publica también un frame `position` actualizado, incluso si la partida terminó y no habrá otra búsqueda. Anuncia el resultado con `info string monitor gameover RESULT`. Se envía una posición actual como instantánea a cada observador que se conecte durante la partida. Si hay varios clientes, cada uno tiene su propia cola limitada; un cliente lento o caído se desconecta sin bloquear la partida. Sin historial previo no puede reconstruirse una partida iniciada fuera del estado conocido por FICS-UCI.

## Challenger

`challenger --monitor macia:6201` o `python -m challenger.cli --monitor 192.168.1.50:6201`

Abre una ventana de observación que no juega una partida propia. Se reconecta automáticamente cuando se corta el TCP. Usa `position startpos moves ...` / `position fen ... moves ...` como única fuente de posiciones confirmadas. La jugada `bestmove` solo se presenta como sugerencia hasta que FICS confirme. El color local se infiere del turno al recibir `go`. Se muestran el turno y las últimas jugadas confirmadas de cada bando, y el botón RESET restablece el tablero inicial (la próxima actualización UCI podrá volver a sincronizarlo). El tablero conserva la última posición al finalizar la partida.

El monitor escucha sin autenticación: limitar el acceso mediante firewall y no exponer el puerto a Internet.
