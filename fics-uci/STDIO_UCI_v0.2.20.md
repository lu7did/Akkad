# fics_uci.py v0.2.20 — UCI TCP o proceso local

Configuración en `fics-uci/etc/config.yml`:

```yaml
# Comportamiento anterior: se conserva si `type` falta.
type: tcp
ip: 127.0.0.1
port: 6110
```

```yaml
# Motor UCI local, conservando freechess.org por Telnet.
type: uci
exec: "C:/ruta con espacios/AlphaZero.exe"
args: '--weights "C:/ruta con espacios/red.pb.gz" --cores 4 --simulations 1200'
```

En macOS/Linux:

```yaml
type: uci
exec: "/home/pi/chess/akkad/AlphaZero/debian/build/AlphaZero"
args: '--weights "/home/pi/chess/akkad/AlphaZero/assets/red.pb.gz" --cores 4'
```

- `exec` es obligatorio solo para `type: uci`; indica la ruta completa del ejecutable (sin argumentos).
- `args` es opcional y debe ser un **único string**. Se tokeniza respetando las comillas según el sistema operativo; no se ejecuta shell.
- UCI `stdout` del motor se interpreta como protocolo; UCI `stdin` recibe los comandos. `stderr` del motor se retransmite sin prefijos a `stderr` del puente, conservando UTF-8.
- Toda la telemetría de `fics_uci.py` se envía también a `stderr`.
- Un proceso local se mantiene activo entre partidas FICS; el tipo TCP conserva su ciclo de conexión anterior. Al terminar voluntariamente `fics_uci.py`, se envía `quit` y se libera el proceso.
- Si el proceso termina o no entrega `uciok` / `readyok`, se reporta la falla y se conserva el mecanismo de reintento del puente. No se usa TCP como fallback del modo `uci`.
- `--retry` se conserva como parámetro opcional de reconexión; sin él, los errores de sesión se notifican y se gestiona la partida como anteriormente.

## Validación

`python -m pytest -q fics-uci/tests/test_uci_stdio_v0220.py fics-uci/tests/test_monitor_v0219.py`

Para pruebas de transporte en el entorno de generación se utilizó una sustitución de `python-chess`, que no está instalado allí. No se ha ejecutado el puente contra FICS real.
