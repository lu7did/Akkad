# Parche incremental de final de partida y diagnóstico – Sargon-NNUE v0.6.169

## Base y aplicación

- Partir de las líneas de base ZIP proporcionadas, con los parches previos de MCTS dinámico v0.2.13 y resiliencia Sargon-NNUE v0.6.168 ya aplicados.
- Sustituir SOLO los archivos incluidos. **No** tocar data, docs, pesos, configuraciones Wi-Fi ni directorios de build.
- Los archivos `picoAlpha/src/mcts.cpp` e `include/mcts.hpp` conservan la lógica dinámica del parche v0.2.13. Las fuentes `picoAlpha/src/pico_main.cpp` y `picoSargon/src/pico_main.cpp` acumulan los cambios anteriores de LED/recuperación.

## Cambios

- Sargon-NNUE: `uci.py` conserva `move_stack` para el jugador EXTERNAL, y `tcp_external.py` reconstruye `position startpos moves ...` o `position fen <raíz> moves ...`. La secuencia de jugadas deja de perderse.
- picoSargon: arreglado el bloque `try` abierto en `run_search()` (error del compilador en línea ~95), eliminado patrón LED duplicado, instrumentado búsqueda por ID y estado terminal. La búsqueda da precedencia a mate frente a reclamación de tablas.
- picoAlpha: IDs secuenciales de búsqueda, registro de fase, historial y terminal; MCTS evalúa movimientos legales antes de tablas, no marca expansión antes de asegurar memoria, y restaura pila de tablero/historial ante excepciones.
- Ambos: watchdog de hardware a 8 segundos, alimentado únicamente desde el ciclo principal y servicio. El arranque informa si hubo reset de watchdog, cuando DEBUG está habilitado. **No** alimentarlo desde interrupciones o callbacks autónomos: debe detectar falta de progreso.
- La prueba nativa C++ para el tablero comprueba FEN del incidente, mate, ahogado, insuficiencia de material y triple repetición. Incluida bajo `tests/`, fuera del árbol de firmware.

## Validaciones ejecutadas aquí

- Python: `py_compile` de las dos fuentes modificadas.
- g++ nativo: compila y ejecuta correctamente `test_board_terminal.cpp` enlazado con board.cpp de picoSargon; 5 pruebas OK.
- g++ nativo: `-fsyntax-only` de `engine.cpp` de picoSargon.
- Revisión estructural de `run_search()` con un único bloque `try/catch`.

## Validaciones PENDIENTES

No se dispone aquí de la toolchain `arm-none-eabi-g++` ni de Pico SDK. No se ha compilado el firmware de ambas placas ni comprobado su funcionamiento físico; el bloqueo original no está reproducido. Es importante validar ambos con `build.ps1`, test TCP, prueba de recuperación del watchdog, match corto y prueba prolongada.

## Prueba sugerida

1. Ejecutar `build.ps1` en cada firmware, cargarlos y comprobar `BOOT watchdog_reboot=0` en USB. picoSargon construye por defecto `pico_w` (RP2040): no usar el binario de picoAlpha/Pico 2 W.
2. Ejecutar dos veces `position fen 8/8/8/4pp2/8/8/5k1K/8 b - - 1 49` + `go`, confirmar `bestmove` legal y logs SEARCH_ID.
3. Repetición real de posiciones enviando `position startpos moves g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8`; verificar que el firmware registra `rep=3` y el árbitro no envía `go` si considera terminada la partida.
4. Comprobar que el match continúa tras una partida terminada y que una desconexión se registra como incidencia técnica, no `bestmove` legal.
5. En prueba controlada de watchdog, detener el progreso deliberadamente en firmware de prueba (NO en producción), verificar reinicio y campo `watchdog_reboot=1`.

## Límites explícitos

- No se implementó cambio de representación a árbol segmentado ni se reconfiguró el high watermark de RAM; corresponden a una revisión independiente para no mezclar corrección de fin de partida con un cambio mayor en memoria.
- El watchdog reinicia un programa totalmente bloqueado: **no asegura** la continuidad de la partida perdida, ni corrige la causa del bloqueo. El torneo deberá usar la política de recuperación TCP/UCI del parche v0.6.168.
- `DEBUG=false` suprime parte de la telemetría serie. Activar DEBUG para las pruebas de regresión.
