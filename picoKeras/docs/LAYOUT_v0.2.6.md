# picoKeras v0.2.6 — Unified X86/Debian source

- `src/main.cpp`, `src/board.cpp`, `src/board.hpp`, `src/model.hpp`: shared desktop engine and UCI/TCP interface.
- `src/model_tf.cpp`: TensorFlow C SavedModel backend (X86/Windows).
- `src/model_tflite.cpp`: TensorFlow Lite `.tflite` backend (Debian).
- `x86/CMakeLists.txt` and `debian/CMakeLists.txt`: separate platform targets; sources always point to `../src`.
- `x86/build/` and `debian/build/`: isolated outputs. MSVC typically places the binary under `x86/build/Release/`.
- `tools/ps/{build,run_listen,smoke_test}.ps1` and `tools/bash/{build,run_listen,smoke_test}.sh`: three platform scripts each.
- `tools/smoke_uci.py`: shared BOM-free UCI test.

**Important:** backend models are NOT interchangeable. X86 accepts a `.tf` **SavedModel directory** with `saved_model.pb` while Debian accepts a converted `.tflite` **file**. The common C++ API (Evaluator) is preserved.

`--weights` is the canonical argument and `--network` remains an alias. Default launch mode is standard UCI over stdin/stdout. Listener scripts explicitly specify `--tcp`.

`ARM/` and `assets/` are not modified. The legacy source copies in `x86/src`, `x86/include` and `debian/model_tflite.cpp` become redundant and should be removed only after the new platform builds pass, using the provided safe cleanup script. Existing old entrypoints are left in place in the incremental ZIP, to avoid accidental destructive deletions.
