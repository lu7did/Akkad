# picoSargon macOS v0.2.37

La implementación reside en `akkad/picoSargon/macOS`, sin subdirectorio intermedio.
Todo el tooling macOS de picoSargon reside en `akkad/picoSargon/tools/macos`.
El núcleo C++ es compartido con `picoSargon/x86/picoSargon`.

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

## Limpieza de la estructura equivocada (v0.2.35 / v0.2.36)

```bash
./picoSargon/tools/macos/cleanup_old_layout.sh
```

El script borra solamente los archivos originales de los dos parches antiguos si su
SHA-256 sigue siendo idéntico. Preserva cualquier archivo editado o desconocido.
Nunca borra automáticamente la carpeta general `akkad/tools` si tiene otros contenidos.
En Windows puede utilizarse `picoSargon/tools/macos/cleanup_old_layout.ps1`.

`build.sh` es el único script macOS de picoSargon fuera de `picoSargon/tools/macos`.
El ejecutable generado es `picoSargon/macOS/build/picoSargon`, sin extensión `.exe`.
La red sigue alojada en `picoSargon/x86/picoSargon/assets/grumpy.bin`.
