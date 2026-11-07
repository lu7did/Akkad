# picoSargon macOS - arguments v0.2.49

Use `picoSargon/macOS/build.sh` to compile. The shared x86 C++ sources are used on macOS, Debian and Windows; no ARM/Pico sources are modified.

Direct UCI process:

```bash
./picoSargon/macOS/build/picoSargon \
  --weights picoSargon/x86/assets/grumpy.bin \
  --cores 4 --depth 6 --qdepth 2 --timeout 15000
```

Read numeric settings from a `brains.json` profile (and the platform's `network` path):

```bash
./picoSargon/macOS/build/picoSargon \
  --brains Sargon-NNUE/etc/brains/brains.json --brain tinySargon --cores 4
```

Listener:

```bash
./picoSargon/tools/macos/run_listen.sh \
  --cores 4 --depth 6 --qdepth 2 --timeout 15000
```

The listener also accepts `--brains FILE --brain NAME` to load settings for each child engine. It listens on `0.0.0.0:6200` by default. `--cores` is mandatory if MULTICORE is compiled in. Use `--help` to list the listener's arguments.

Precedence in each child engine: explicit CLI arguments > fields `depth`, `qdepth`, `timeout` in the selected JSON brain > defaults (4 / 2 / 15000 ms). When `timeout` is absent, `tmax` is supported as a fallback. During UCI communication, `setoption name QDepth value N` overrides the initial qdepth; `go depth N` and `go movetime N` override the configured defaults for that particular search. `--timeout` is a search budget in milliseconds; it is not the TCP/engine supervision timeout that Sargon-NNUE separately uses when driving external engines.

No extra C++ dependencies have been introduced. A `--weights` argument can override the JSON `network` path while keeping the other JSON settings.
