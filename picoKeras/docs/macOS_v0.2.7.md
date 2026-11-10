# picoKeras 0.2.7 — macOS / Apple Silicon

## Architecture

No duplicate chess engine exists on macOS. The CMake target shares:

- `picoKeras/src/main.cpp`: UCI stdio / explicit TCP listener
- `picoKeras/src/board.cpp`: mailbox board and legal moves
- `picoKeras/src/model_tflite.cpp`: the same TensorFlow Lite inference backend used by Debian

Only CMake build choices and `PICOKERAS_PLATFORM_MACOS` differ. The POSIX
socket code is already shared by Debian and macOS. A SIGPIPE guard has been
added for disconnected TCP peers on POSIX. Windows continues to use
`src/model_tf.cpp` and the TensorFlow C SavedModel API.

**Important:** macOS supports `.tflite` files, not `.tf` SavedModel folders.
Converting a network can require TensorFlow Python on a separate machine. Do
not rename `.tf` or `.keras` to `.tflite` — model conversion is required.

## Build

```bash
cd akkad
bash picoKeras/tools/macOS/build.sh --help
bash picoKeras/tools/macOS/build.sh
```

The script checks Apple Clang and installs `cmake`, `ninja`, and `git` through
Homebrew if absent (bootstrapping Homebrew when needed); it clones TensorFlow
v2.18.1 source if necessary and builds TFLite + picoKeras in
`picoKeras/macOS/build`. A first build needs significant disk space and network
access. Apple Command Line Tools must already be installed; if missing, run
`xcode-select --install` and complete the installation before rebuilding.
Use `--no-install-deps` to forbid automatic installation; `--native OFF`
for a binary intended for other Macs; `--xnnpack OFF` to troubleshoot.
The default optimizations are `-O3`, optional `-mcpu=native`, XNNPACK and
LTO when supported. No nonportable FP reassociation/`-ffast-math` is enabled.

## Nurse brain definition

In `akkad/nurse/etc/brains/brains.json` add a unique entry under `brains`.
The examples below assume Nurse is started from the `akkad` repository root:

```json
"picoKeras_mac": {
  "type": "uci",
  "player": {"macOS": "picoKeras/macOS/build/picoKeras"},
  "evaluator": "null",
  "args": {"macOS": ["--weights", "picoKeras/networks/example.tflite"]},
  "tmax": 15000,
  "timeout": 30000
}
```

**Replace** `picoKeras/networks/example.tflite` with the path of a model
that actually exists. Nurse rejects duplicate JSON keys. The engine consumes
`--weights` through `args.macOS`, not through a separate `network` field.

Use the Nurse TCP wrapper (one brain per listener):

```bash
bash picoKeras/tools/macOS/run_listen.sh --brains nurse/etc/brains/brains.json \
    --id picoKeras_mac --ip 0.0.0.0 --port 6200
```

Or use picoKeras' **native** UCI/TCP listener without Nurse:

```bash
bash picoKeras/tools/macOS/run_listen.sh --direct \
    --weights picoKeras/networks/example.tflite --ip 0.0.0.0 --port 6200
```

For a conventional UCI subprocess (`nurse` type `uci`), omit `--tcp`:

```bash
picoKeras/macOS/build/picoKeras --weights picoKeras/networks/example.tflite
```

## Verification and limits

`bash -n` was checked for both new scripts; `clang++` syntax checks can be
performed on common C++ files. A complete macOS/TFLite compilation needs a
macOS host (Apple Clang, SDK and the TensorFlow Lite source). No Apple Silicon
runtime benchmark is claimed without running on that host.
