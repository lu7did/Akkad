# picoKeras: restructuring stage v0.2.0

## Structure
- `ARM/`: preserved original TFLM desktop prototype, NOT RP2350-compilable firmware. It requires an ARM port of network, memory, SDK, and CMake.
- `x86/picoKeras/`: C++ desktop engine linked in-process to TensorFlow C API; meant for Windows and future Linux/macOS ARM64 builds.
- `tools/prepare_model.py`: **offline** `.keras` -> SavedModel export. No Python in inference.

## Models
Existing `small.tf` and `medium.tf` in Sargon-NNUE are SavedModel **directories**, loaded directly. `.keras` files must be exported first via `python tools/prepare_model.py model.keras --output model.tf`. Passing raw `.keras` to the current C++ loader is deliberately rejected rather than falsely claiming native loading.

**INT8 limitation:** quantized internal TensorFlow operations with FLOAT32 boundary can run; fully INT8 input/output is not implemented. `.int8.tf` is accepted only when it contains a compatible saved_model.pb and has FLOAT32 boundary. This must be tested with the actual file.

## Build
Use a TensorFlow C API runtime distribution with headers and linker library (and matching DLL/.so/.dylib runtime). On Windows:
```
cd picoKeras/x86/picoKeras
./build.ps1 -TensorFlowRoot C:/tensorflow-c
./build/Release/picoKeras.exe --network ../../../../sargon-NNUE/data/runs/keras/small.tf --input-op serving_default_inputs:0 --output-op StatefulPartitionedCall:0
```
Operation names are export/version-dependent; inspect the model with `saved_model_cli show --dir path --all`. The generic names shown above are **not guaranteed**. Launch default port 6110, `--stdio` for terminal testing. On Linux/macOS: `TENSORFLOW_ROOT=/path ./build.sh` with a compatible native TensorFlow C distribution.

## Limits / validation
- CMake requires TensorFlow C binary distribution and this patch does not bundle it.
- No native Windows runtime/link/build verification in current Linux environment.
- Batch inference currently submits one call for all nonterminal successor positions. Some model signatures have fixed batch=1 and will reject batch>1; use a SavedModel signature with dynamic batch for this optimization.
- This is a stage toward a portable desktop runtime, **not a completed tested build**. There is no model-export conversion at executable startup; prepare the `.keras` offline.
- `ARM/` is a preservation copy, not a finished ARM build.
