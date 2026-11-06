# picoSargon macOS v0.2.36

Fuente C++ compartida con x86; un motor UCI por stdin **no** abre ningún puerto TCP.

## Compilar

```bash
./picoSargon/macOS/build.sh
```

## Modos de uso (desde raíz akkad)

**Motor UCI local (sin puerto):**

```bash
./tools/macos/run.sh
```

En modo UCI, enviar `uci`, `isready`, `position startpos`, `go depth 2`;
la respuesta UCI se escribe en stdout. Al arrancar en macOS se emite diagnóstico en stderr.

**Servidor UCI/TCP (puerto predeterminado 6200):**

```bash
./tools/macos/run_listen.sh
# O bien, escuchando conexiones de otras máquinas de la LAN:
./tools/macos/run_listen.sh --host 0.0.0.0 --port 6200
```

Dirección por defecto `127.0.0.1:6200` (sólo máquina local). El listener muestra
INICIO, ESCUCHANDO, CONEXION, comandos recibidos, líneas `info` y `bestmove`,
y DESCONEXION por stderr. Cada cliente TCP obtiene un proceso independiente;
la red NNUE se carga por sesión. El puerto **6110 no es el predeterminado**.

**Smoke test TCP:**

```bash
./tools/macos/tcp_smoke.sh
```

No requiere dependencias Python externas, sólo Python 3. El ejecutable nativo
es `picoSargon/macOS/build/picoSargon` (sin `.exe`). `build.sh` permanece
bajo `picoSargon/macOS`; scripts de ejecución bajo `tools/macos`.
