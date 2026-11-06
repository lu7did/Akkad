# picoSargon macOS v0.2.40

La implementación reside en `akkad/picoSargon/macOS`, sin subdirectorio intermedio.
Todo el tooling macOS de picoSargon reside en `akkad/picoSargon/tools/macos`.
El núcleo C++ es compartido con `picoSargon/x86`.

## Compilación desde la raíz de Akkad

```bash
./picoSargon/macOS/build.sh
```

## Ejecución UCI local (sin TCP)

```bash
./picoSargon/tools/macos/run.sh
```

## Servidor UCI/TCP, con telemetría por stderr

```bash
./picoSargon/tools/macos/run_listen.sh
# Puerto por defecto: 127.0.0.1:6200
./picoSargon/tools/macos/run_listen.sh --host 0.0.0.0 --port 6200
```

## Pruebas

```bash
./picoSargon/tools/macos/uci_smoke.sh
./picoSargon/tools/macos/tcp_smoke.sh # con listener activo en otra terminal
```

## Limpieza integral de las estructuras obsoletas

```bash
python3 picoSargon/tools/migrate_layout_v0.2.40.py --apply
```

El migrador recoloca los archivos de los directorios intermedios y elimina
los builds duplicados. Los conflictos se respaldan fuera del repositorio.

`build.sh` es el único script macOS de picoSargon fuera de `picoSargon/tools/macos`.
El ejecutable generado es `picoSargon/macOS/build/picoSargon`, sin extensión `.exe`.
La red sigue alojada en `picoSargon/x86/assets/grumpy.bin`.

## Telemetría del listener (v0.2.40)

La salida del servidor es local por stderr, con hora HH:MM:SS y emojis.
Se presentan encabezado y rutas, conexión (IP y puerto de origen), comandos
`position` y `go`, respuestas `info` y `bestmove`, desconexión y cierre.
Los mensajes UCI sobre TCP se transmiten sin alteraciones. No se registra
la advertencia de firewall en el arranque.
