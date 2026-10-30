# picoKeras v0.1.1 — x86 standalone C++/TFLM

This is a standalone engine located within the Akkad/sargon-NNUE repository. It does not depend on the Sargon-NNUE Python runtime. Its mailbox-120 legal chess implementation derives from the project's picoSargon C++ board module; no chess libraries are linked. Search is full-width **one ply**: for each legal move, evaluate the resulting position from the rival's perspective; select the **lowest** scalar network value. Checkmate returns -1, draw 0; a current-position game-over has no bestmove.

## Model contract

`--network` **must** point to a TensorFlow Lite **FlatBuffer** (`.tflite`) with TFL3 identifier, single `[1,8,8,12]` or `[1,768]` input and a scalar output `[1,1]` or `[1]`. Both FP32 and INT8 input/output tensor types are supported; INT8 quantization uses tensor scale and zero point. Model output must fall in [-1,1]. Feature order for NHWC is white P N B R Q K, black p n b r q k, array rows rank8 to rank1. For black turn, flip the ranks and swap the colors, equivalent to `python-chess` `board.mirror()`. The model output is from the *side to move*.

**A TensorFlow SavedModel directory (`.tf`) and a Keras (`.keras`) model cannot be loaded by TFLM.** Conversion tools are in tools/; they export native-ops TFLite models. The FP32 converter writes a `.source.json` sidecar because a TFLite FlatBuffer cannot be inverted into a trainable Keras model. The INT8 converter uses that source model and representative chess positions. The specific ViT operations (MultiHeadAttention, GELU/Erfc, normalization) may not be supported by TFLM's builtin operators: incompatible networks will fail initialization; do not claim successful inference until tested.

## Ubicación del proyecto

Extraer este ZIP **desde la raíz `Akkad/`**. El proyecto queda en `Akkad/sargon-NNUE/x86/picoKeras/`. No instalarlo en `Akkad/x86/picoKeras/`. Los scripts determinan rutas a partir de su propia ubicación.

## Building on Windows

TFLM is a separate, source-built dependency. A compatible prebuilt static TFLM library and headers are required; they are **not shipped** in this ZIP. Use a TFLM Windows build with reference kernels and a matching compiler, using https://github.com/tensorflow/tflite-micro. The project intentionally uses TFLM, not TensorFlow's desktop Lite interpreter. Build with:

```powershell
./build.ps1 -Generator 'Visual Studio 18 2026' -TflmInclude C:\src\tflite-micro -TflmLibrary C:\src\tflite-micro\path\tflm.lib
./build.ps1 -Generator Ninja -TflmInclude C:\src\tflite-micro -TflmLibrary C:\src\tflite-micro\path\tflm.lib
```

`-Clean` removes the build cache; `-Configuration Debug` selects Debug. On non-Windows host for a source smoke test, CMake can use a corresponding TFLM `.a`.

## Execution

```powershell
./scripts/run_server.ps1 -Network 'C:\models\small-int8.tflite' -Port 6110
./scripts/run_stdio.ps1 -Network 'C:\models\small-fp32.tflite'
```

Directly: `picoKeras.exe --network model.tflite --port 6110 --host 0.0.0.0 --arena 33554432`. The default arena is 32 MiB (x86 only; not intended for microcontrollers).

Each TCP client has an independent board; requests execute synchronously. UCI commands: `uci`, `isready`, `ucinewgame`, `position startpos [moves ...]`, `position fen ... [moves ...]`, `go`, `stop`, `quit`. `stop` is accepted but cannot preempt a running neural inference. There is no move time limit. The TCP server serves one client at a time; logging goes to stderr. UCI response includes `info depth 1 nodes ... time ... string eval_rival ... inspected ... terminal ... eval_ms ...`, and `bestmove ...`. The `eval_rival` value is the neural scalar, **not centipawns**. Because there is no chessmate probability head, terminal scores are -1/0; a direct terminal checkmate is preferred over any network output greater than -1.

Example Sargon-NNUE external brain after checking its TCP transport configuration:

```json
{"player":"external","evaluator":"null","url":"127.0.0.1:6110","rating_elo":400}
```

## Test coverage and limits

The mailbox board compiles and has been exercised without neural dependencies through dedicated board tests. The model adapter and TCP/UCI shell are included but cannot be validated with an actual ViT-Small/Medium TFLite model until a compatible model is available. No ARM firmware is included. This is an x86 integration baseline, not a claim that ViT inference is already viable in TFLM.


## Install and convert

```powershell
.\scripts\install_python.ps1
.\scripts\install_TFLM.ps1 -Generator 'Visual Studio 18 2026'
.\scripts\keras_to_tflite.ps1 -In C:\models\small.keras -Out C:\models\small.tflite
.\scripts\tflite_to_int8.ps1 -In C:\models\small.tflite -Out C:\models\small.int8.tflite
```

The TFLM installer downloads the upstream source, generates a TFLM source tree, builds a static archive and prints the include and library paths; this build is unverified on the user's MSVC environment. If model conversion fails on GELU Erfc/BiasAdd or other unsupported ops, the scripts fail rather than silently introducing Flex or custom operators. This is a hard constraint for TFLM portability, and ViT-Small/Medium compatibility requires actual verification.

UCI `info depth 1 nodes N time MS string eval_rival V.VV inspected N terminal T`: `nodes` is the number of evaluated legal candidates, `time` is total move processing time in milliseconds, and scalar `eval_rival` is rendered with two decimal places.
