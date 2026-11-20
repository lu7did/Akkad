# picoGen v0.1.44 — EvoTorch PGPE (alternative trainer)

**Authorized code baseline:** `lu7did/akkad` `main` commit `24b107e9d689438dbbb1a47c386bf4a12443052a` (2026-11-20).

## Files and scope

- `genPGPE.py`: new PGPE trainer. The baseline `genNNUE.py` remains untouched (legacy).
- `gen_pgpe_core.py`: sparse features, Stockfish CSV contract and vectorized PyTorch fitness.
- `run_genesis_binpack.ps1`: MON 1 installs/checks NumPy, python-chess, PyTorch and EvoTorch; MON 7 calls genPGPE; MON 8 audits the PGPE output. Rust `.binpack` extractor is unchanged.
- `nurse/.../nnue.py` and `nurse/.../genus_eval.py`: support model-specific `[0,1]` clipping when a PGPE active manifest is present; legacy `[0,127]` inference stays intact.
- `genAudit.py`: recognizes both active model contracts and logs probability MSE plus cp RMSE/MAE/bias.

## Architecture and optimizer

- Input: **768** binary piece-square features, at most 32 populated per position. Color of each piece is part of the feature; side to move is not encoded (intentional original compact input).
- Hidden: **16** neurons, `clip(sum(weights) + bias, 0, 1)`.
- Output: **1** affine score in white-perspective centipawns. **12,321 FP32 weights** in the same row-major flat layout Nurse expects.
- PGPE: symmetric sampled population; EvoTorch optimizes the distribution center and diagonal stdev (via Adam for its center). No gradient backpropagation, Ridge, bias calibration, or GA crossover.
- Objective: mean squared error of `sigmoid(predicted_cp/400)` vs `sigmoid(teacher_cp/400)`.
- Source data: T79 CSV produced by the existing Rust extractor. Reservoir sampling of up to 500,000 quiet positions kept as sparse indices in RAM; drop boards in check; drop boards where **recorded `played_uci` is a legal capture**. The recorded move is *not proven* to be the teacher's best move. Unknown/illegal move records are counted and retained if otherwise valid.
- Each generation chooses 20,000 different sampled T79 positions; **every population member receives the exact same batch**. The historically best exported candidate is chosen using a constant, separately sampled T79 anchor and is evaluated on T77 only for telemetry.
- T77 is always separate; the loader detects selected board-state overlap with T79 and excludes overlapping T77 records.

## Running on Windows

From `akkad/picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 1
# Follow the pipeline normally. To replay only NNUE, with already prepared CSVs/PST:
.\run_genesis_binpack.ps1 --mon 7 --population 100 --generations 100 --pgpe-pool 500000 --pgpe-batch 20000 --pgpe-device auto
```

Use `--pgpe-device cpu` to force CPU. `auto` prefers XPU, then CUDA, then CPU. XPU requires the user's Intel-compatible PyTorch installation and driver; plain `pip install torch` **does not guarantee XPU support**. Installing EvoTorch may modify an existing PyTorch dependency; check the versions reported by MON 1.

`--fitness-sample` remains for legacy PST (MON 6), NOT the PGPE pool. `--mutation-sigma` is likewise a PST parameter; the PGPE distribution uses `--pgpe-stdev` (default 0.1). Population must be even because PGPE uses symmetric sampling.

The Rust extractor writes `score_stm_cp` and `score_white_cp`; the PGPE CSV loader checks exact conversion (`score_stm` clipped to +/-2000 with sign according to side-to-move) and validation remains on T77. No extraction change is needed because FEN and played_uci are already present.

## Artifacts

`assets/RUN_ID/nnue/best.npy` — 12,321 float32 parameters.
`assets/RUN_ID/nnue/best.active.json` — `picogen-nnue-pgpe-active-fp32-v1`, activates clipping 0..1 in Nurse.
`assets/RUN_ID/nnue/best.pgpe-v1.latest.pt` — **single rolling checkpoint** (population, distribution, optimizer, RNG and best); local trusted file only, never load checkpoints from unknown origins.
`assets/RUN_ID/nnue/best.pgpe-v1.genNNNNN.json` — compact generation telemetry; not standalone resume checkpoints. The rolling binary file is required to resume.

Explicit `--mon 7` archives the previous NNUE stage and begins at generation 1; automatic continuation uses `latest.pt` and rejects incompatible dataset/model/settings. This format is incompatible with v0.1.43 checkpoints and is not for untrusted pickle loading.

## Verification / limitations

Python tests check inference equivalence with Nurse, numerical fitness and shape; no full `.binpack` training was run in this development environment (no `evotorch`, `python-chess`, or Windows PowerShell installed here). The EvoTorch integration is therefore **not end-to-end validated**. Test MON 1 and a small complete MON 7 run on target Windows before committing to the full 500k/20k dataset.

Caveat: A sigmoid transformed fitness need not minimize RMSE in centipawns; both metrics are reported distinctly. Filtering quiet positions changes the training distribution and may reduce performance on tactical positions. All reported T77 quality metrics use the unfiltered heldout sample.

## References

- EvoTorch docs: https://docs.evotorch.ai/latest/user_guide/problems/
- PGPE API: https://docs.evotorch.ai/latest/reference/evotorch/algorithms/distributed/
- EvoTorch 0.6.1 package: https://pypi.org/project/evotorch/
