# picoKeras ARM v0.1.27 — incremental correction

Apply this ZIP from the Akkad project root over v0.1.26. This changes only the build integration and version strings.

## Fixed

The `tensorflow_microlite` target compiles `src/tflm_pico_port.cpp`, which includes `pico/time.h`. Previous CMake configuration linked Pico SDK libraries only to `picoKeras`, so the separate TFLM target lacked the Pico SDK include directories during compilation.

The TFLM library now links `pico_time` and `pico_stdlib` as PUBLIC dependencies. That propagates their SDK include directories to TFLM at compilation and their linker requirements to consumers.

## Build

From `picoKeras/ARM`, run `./build.ps1 -Clean` in PowerShell. No Bash or MSYS2 is needed. This patch does not claim to validate the firmware on actual RP2350 hardware.
