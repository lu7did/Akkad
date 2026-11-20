# picoGen PGPE v0.1.46 — MON 1 dependency conflicts

Base: apply on top of v0.1.44 + v0.1.45.
Only file changed: picoGen/tools/train/gen_pgpe_deps.py.

Mandatory imports: numpy, python-chess, torch, evotorch. Missing modules are installed with --install or fail explicitly. torch XPU/CUDA detection remains.

Global `pip check` is diagnostic only; warnings are displayed in full, but unrelated installed packages (e.g. larq 0.14.0 requiring numpy<2.0) do not stop the NNUE PGPE genesis. No automatic changes to NumPy/Larq.

After applying: `./run_genesis_binpack.ps1 --mon 1` (PowerShell). If previous MON 1 failed before advancing MON.state, rerun the same command.

This is not proof all EvoTorch GPU features work with installed versions; any actual PGPE failure should be handled as a separate confirmed error.
