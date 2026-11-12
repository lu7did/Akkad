# Akkad — picoPixie v0.1.26 (migration patch)

Base: akkad(20261112-121817).zip. Apply ZIP from Akkad repository root.

- Rename CMake project/executable target picoLichess to picoPixie.
- Generate build/picoPixie.uf2, and adjust build.ps1 expectation.
- Clear stale CMake build cache when CMAKE_HOME_DIRECTORY points to a prior directory (old picoLichess path).
- Correct affected integration tests, current project paths, visible labels, and exclusion list.
- Preserve existing picoLichess C++ namespace and picolichess_adapter source filenames: internal API is deliberately unchanged.
- Preserve picoSargon shared source, cloud hooks, engines, NNUE, and all historical benchmark records.

Build in Windows PowerShell: cd picoPixie/ARM; ./build.ps1 -Clean
Expected firmware: picoPixie/ARM/build/picoPixie.uf2

This environment does not provide Raspberry Pi Pico SDK + Windows ARM GNU toolchain: firmware build cannot be validated here.
