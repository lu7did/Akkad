# picoAlpha v0.2.38 — boot version and neural model identity

Incremental patch, applied over picoAlpha with v0.2.37 integration.

- Version defined by `project(... VERSION 0.2.38)` in CMake and passed to `pico_main.cpp` via `PA_FIRMWARE_VERSION`. Boot and UCI `id name` therefore use the same version.
- Model identity from `PICOALPHA_NET` is compiled into `PA_COMPILED_NN` and printed as `BUILD NN=1x8 (compile-time)` or `BUILD NN=2x16 (compile-time)` when DEBUG is enabled.
- The existing neural inference implementation, weights, MCTS, connectivity and build selection are unchanged.
- Default remains `1x8` in CMake. No network runtime switching.

Use the existing build directory:

    cmake -S . -B build-pico2-w -DPICOALPHA_NET=1x8
    cmake --build build-pico2-w

Expected boot lines:

    picoAlpha v0.2.38 watchdog(...)
    BUILD NN=1x8 (compile-time)

UCI returns `id name picoAlpha v0.2.38`.

Note: the telemetry confirms identity in firmware only if the freshly produced UF2 was installed. The log source `NN/FC1 mode=LEGACY` is legacy profiling terminology, not proof of selected architecture.

No Pico SDK compilation or on-board hardware test was performed in this environment.
