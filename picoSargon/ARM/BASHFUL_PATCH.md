# picoSargon ARM — Bashful NNUE patch

Baseline: `akkad(20261122-184526).zip`.

- Activates the user-provided `bashful.bin` in ARM firmware, both normal and TWINS variants.
- Preserves `grumpy.bin` and the `Grumpy` C++ interface as historical/format compatibility; active embedded payload is Bashful.
- The ARM build generator now updates both embedded headers (independent of TWINS selection).
- CMake ensures regeneration when the weights change, including direct builds.
- Other platforms and other evaluators remain unchanged.
- The GRMP0001 header and model length (1304 bytes) were checked; scoring equivalence/playing strength is not claimed.

Build from `picoSargon/ARM` using the existing `build.ps1` or CMake tooling.
