# AlphaZero macOS v0.1.3

Native Apple Silicon C++ build using existing `AlphaZero/build.sh --OS MacOS`.
No second C++ engine is introduced. The upstream LC0 Meson source tree is
placed under `AlphaZero/build/lc0-src` and the Akkad C++ MCTS front-end
under `AlphaZero/src/akkad_alphazero_main.cc` is built by the shared builder.

```bash
bash AlphaZero/tools/macOS/build.sh
bash AlphaZero/tools/macOS/run_alphazero.sh --weights /path/to/network.pb.gz --simulations 1200 --timeout 60000
```

The run script starts a UCI process on stdin/stdout (not TCP).
`--simulations` is the simulation limit; `--timeout` is the absolute
per-search time cap. Existing UCI `go nodes N`, `go movetime MS`,
`setoption name Simulations value N` and `setoption name Timeout value MS`
remain supported. Normal search budget `TMax` remains independent.

For Sargon-NNUE `emma`, the `engine-path`, `lc0-weights`, and backend
settings select the correct macOS platform values. Adjust `lc0-weights.macos`
if the network is located elsewhere on your Mac. The network is external,
not embedded or duplicated in this patch.

Build dependencies: Xcode CLT, meson, ninja, git, cmake, python3 and LC0
system dependencies. Set `LC0_SOURCE` for an existing local source tree.
Only Apple Silicon ARM64 is supported by the existing shared builder.
