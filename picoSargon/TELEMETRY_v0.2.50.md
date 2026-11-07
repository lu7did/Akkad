# picoSargon v0.2.50 — UCI / diagnostic separation

Applies on top of v0.2.49. Extract at the `akkad` repository root.

- C++ stdout: only unmodified UCI protocol records (such as `info` and `bestmove`).
- C++ stderr: `🧮 core` diagnostics followed by timestamped `🧠 info` and `🧠 bestmove` duplicates. Each record starts with `[HH:MM:SS]`.
- macOS listener: stdout is forwarded to TCP unchanged; human messages are taken only from engine stderr, serialized on one reader. No dependence on inter-pipe read ordering. The listener itself writes startup, connection and input logs to stderr with `[HH:MM:SS]`.
- The listener never waits for diagnostic output before delivering UCI to the TCP client.
- Rebuild macOS/Windows/Debian binaries after applying this patch.

Regression test (from repository root):

```sh
python3 picoSargon/tools/tests/test_uci_channels_v0.2.50.py --engine picoSargon/debian/build/picoSargon --weights picoSargon/x86/assets/grumpy.bin --cores 2
```

No ARM changes.
