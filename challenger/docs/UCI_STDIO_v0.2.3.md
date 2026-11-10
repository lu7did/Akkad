# Challenger v0.2.3 — Motor UCI por stdin/stdout

Sin `--uci-engine`, Challenger conserva el transporte TCP actual mediante `--ip` y `--port`. Al proporcionar `--uci-engine EJECUTABLE`, lanza directamente un proceso hijo (sin shell) y habla UCI por entrada y salida estándar. Se aplica al motor **rival**; `--brain` continúa escogiendo el motor propio de Challenger.

`--uci-args CADENA` es un argumento único con todos los argumentos del ejecutable, incluyendo comillas para rutas con espacios. Sin límite de longitud impuesto por Challenger; siguen vigentes los límites del sistema operativo. Windows usa `CommandLineToArgvW` y Debian/macOS usan `shlex.split`. Cada token se entrega en `argv` al motor sin interpretación por un shell. Los mensajes del motor por `stderr` no se mezclan con el protocolo UCI en `stdout`. Toda telemetría `print()` de Challenger se dirige a `stderr`.

## Windows PowerShell

```powershell
python -m challenger.cli --brain sargon --uci-engine 'C:\Motores\picoKeras.exe' --uci-args '--weights "C:\Redes\medium.tf" --cores 4 --depth 3 --tmax 15000' --run 1
```

## Debian/macOS

```bash
python3 -m challenger.cli --brain sargon --uci-engine /usr/games/stockfish --uci-args '--threads 2' --run 1
```

`--uci-args` solo es válido con `--uci-engine`. `--monitor` continúa siendo TCP y no puede combinarse con `--uci-engine`. No es necesario indicar `--ip` o `--port` para el transporte por proceso. `--timeout` rige el handshake y el plazo por respuesta como en TCP.

Las partidas consecutivas reutilizan el mismo proceso vivo; si se produce un fallo UCI, Challenger cierra y reinicia el proceso antes de comenzar una sesión nueva. En el cierre normal envía `quit`, espera y termina el proceso si no sale por sí solo.
