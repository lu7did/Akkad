# picoKeras Debian — fix v0.2.5

Base: `akkad(10).zip`. Apply this ZIP from the `akkad/` repository root.

- Correct CMake's desktop source root: `picoKeras/x86` (previously it incorrectly used `picoKeras/x86/picoKeras`).
- Regenerate CMake build if its cached absolute source/build paths belong to a different checkout.
- Bump Debian CMake project version to 0.2.5.

No TensorFlow/TFLite files, chess engine sources, x86 or ARM files are modified.

Run on Raspberry Pi:

```bash
cd ~/chess/akkad/picoKeras/tools/bash
INSTALL_DEPS=0 ./build.sh
```

To force a full CMake rebuild (costly on Raspberry Pi): `INSTALL_DEPS=0 CLEAN_BUILD=1 ./build.sh`.
Compilation and hardware inference have not been verified in this environment.
