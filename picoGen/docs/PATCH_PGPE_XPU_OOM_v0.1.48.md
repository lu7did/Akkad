# picoGen PGPE v0.1.48 — Intel XPU Adam out-of-device-memory

## Base and scope

Apply over incremental patches v0.1.44–v0.1.47 on the authorized Akkad baseline commit `24b107e9d689438dbbb1a47c386bf4a12443052a`. Paths in ZIP are relative to root `akkad/`.

**Observed failure**: PGPE generations 1 and 2 finish, then EvoTorch 0.6.1 / PyTorch 2.14.0+xpu raises `UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY (39)` in `_multi_tensor_adam` during center update. This is not a malformed Stockfish dataset or the previous `ReadOnlyTensor` exception.

**Change only in genPGPE.py**:

- Preserve training pool of 500,000 sparse positions in **CPU RAM**; transfer only the sampled 20,000-position current generation batch to XPU. Validation stays in NumPy on CPU.
- When `device=xpu`, create the EvoTorch `Problem`, PGPE distribution, and Adam optimizer on **CPU**. The vectorized `objective` moves the solution population to XPU, runs `population_fitness` on XPU, and returns one fitness per candidate back on CPU. With CUDA/CPU the existing device placement is unchanged.
- The stable anchor batch is transferred once. Anchor comparisons transfer just 2 candidate vectors to XPU.
- Resume and checkpoint restoration map distributions and Adam states to the **optimizer device** (CPU when XPU is used).
- Log both `distribution+Adam` and `fitness` device placements.
- PGPE output and manifest format are unmodified; no change to `genNNUE.py`, `gen_pgpe_core.py`, Nurse or previous checkpoints.

The v0.1.47 ReadOnlyTensor fix remains required and unchanged.

## Checkpoint and rerun

The checkpoint `best.pgpe-v1.latest.pt` from the interrupted run should be compatible: `--resume` loads optimizer state on CPU. If it fails, run MON 7 explicitly to start a new run, which archives the old NNUE outputs. The standard `run_genesis_binpack.ps1` auto-resume continues from the latest binary checkpoint when MON.state remains at 7.

## Verification

`python -m py_compile picoGen/tools/train/genPGPE.py` passed. Four static integration assertions passed on CPU. **Intel XPU training has not been run in this environment.** On Windows verify that the new log reads `distribution+Adam=cpu, fitness=xpu` and that PGPE passes G00003 without a GPU OOM. This removes Adam's XPU allocation but cannot guarantee XPU fitness allocation never exceeds physical memory.
