# picoSargon macOS v0.2.52 - cierre ordenado de sesiones TCP

## Error corregido

Una desconexion de escritura (EOF del socket), habitual al ejecutar
`printf 'uci\nisready\n' | nc -w 5 127.0.0.1 6200`, hacia que el
listener terminara el motor antes de entregar sus respuestas UCI.

## Cambio

- Si el cliente cierra su canal de escritura, el listener procesa un ultimo
  comando parcial (si lo hay), envía `quit` al proceso y espera su salida.
- Deja que el hilo de salida entregue las respuestas pendientes antes de
  cerrar la conexion, con tiempo de gracia acotado para motores bloqueados.
- No altera sesiones TCP que mantienen abierta la escritura.
- `stdout` se reenvía al cliente como UCI puro; diagnosticos y emojis quedan
  exclusivamente en `stderr`.
- Se mantiene el puerto 6200 y la IP predeterminada 0.0.0.0, así como la
  validacion de `--cores` y los argumentos existentes.

## Prueba

```bash
python3 picoSargon/tools/tests/test_macos_tcp_eof_v0.2.52.py
```

Después de compilar y arrancar el servidor:

```bash
./picoSargon/macOS/build.sh
./picoSargon/tools/macos/run_listen.sh --cores 4
```

En otra consola:

```bash
printf 'uci\nisready\n' | nc -w 5 127.0.0.1 6200
```

Se esperan `uciok` y `readyok`. La prueba automatizada también verifica
`info` y `bestmove` con un motor simulado.
