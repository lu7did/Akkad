# Sargon-NNUE v0.6.2

## Fix

- Corrected all PowerShell launchers so they work directly from the extracted source tree.
- Launchers no longer require `pip install -e .` or a manually configured `PYTHONPATH`.
- Each launcher invokes the corresponding wrapper under `src\`, which places the `src` directory on Python's import path naturally.
- Paths to data files are resolved relative to the script directory, so the scripts can be launched from the project root or from another current directory.

No evaluator or player algorithm was changed from v0.6.1.
