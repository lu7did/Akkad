# picoSargon Debian native UCI/TCP listener v0.2.51

This listener is a C++ executable (`debian/build/picoSargon_listen`). No Python runtime and no Sargon-NNUE package are required. The executable opens a TCP socket and forks one picoSargon process per client, connecting the socket to the engine's stdin/stdout; the engine's stderr goes directly to the server console. Each process has its own chess/NNUE state. This process-based design is intended for Debian/Linux on Raspberry Pi.

Build from the `akkad` root:

```bash
bash picoSargon/tools/bash/build.sh
```

Run with multicore enabled (default):

```bash
./picoSargon/tools/bash/run_listen.sh --cores 4 --depth 6 --qdepth 2 --timeout 15000
```

Listen on all IPv4 interfaces by default: `0.0.0.0:6200`. For local-only access use `--host 127.0.0.1`. Options `--host`, `--port`, `--cores`, `--depth`, `--qdepth`, `--timeout`, `--brains`, `--brain`, and `--weights` are available. `--cores N` is mandatory when built with `MULTICORE=ON`, and forbidden if it is `OFF`. Use `--help` for usage information.

The C++ frontend has no authentication. Expose the listening port only to trusted LAN clients. A TCP session ends on `quit` or when the socket closes. Shutdown with Ctrl+C. The log is on stderr only; the TCP output is raw UCI protocol. Multiclient sessions are isolated using separate processes, so multi-core settings apply **per client** and total load may be higher if several clients search at once.
