# picoGen v0.1.39 — MON explicit reentry

Base: `lu7did/Akkad` main commit `85a4cc36e55ebb884002224ec36b6bcedaf8efbf`.

- `--mon 7` executes NNUE training from generation 1 even if the complete checkpoint exists; then executes MON 8.
- `--mon 6` analogously executes PST training from generation 1; then 7 and 8. Subsequent stages follow the original pipeline behavior.
- Running without `--mon` keeps the existing checkpoint resume/skip behavior, driven by `MON.state`.
- Explicit replay does not delete old checkpoint files; checkpoint filenames for the same generation may be overwritten by a successful new generation. Existing best model files may also be overwritten.
- No changes to fitness, genetics, FP32 architecture, fixed datasets, or config lock.

Test on Windows PowerShell 5.1 (not available in the build environment):

```powershell
.\run_genesis_binpack.ps1 --mon 7
.\run_genesis_binpack.ps1 --status
```

Expected: `MON 7 explicit replay` followed by `EXEC python ...genNNUE.py` and `NNUE FP32 G00001...`; finally `MON 8` and next `MON=9`.
