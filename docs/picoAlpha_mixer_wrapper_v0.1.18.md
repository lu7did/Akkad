# picoAlpha mixer PowerShell wrapper v0.1.18

- Fix: replace `run_mixer.ps1` with a PowerShell 5.1-compatible ASCII script saved as UTF-8 BOM to prevent parser/encoding problems.
- Running without arguments uses editable defaults at the beginning of the script: `sample_history.pb`, `genus.pb`, and `mixed_history.pb` in the known `Chess_History_pb/picoAlpha` directory.
- `--in`, `--mix`, `--out`, `--batch` override those defaults.
- Input files checked before launching Python; output refuses overwrite (by mixer.py).
- No changes to mixer.py, schema, labeling, or teacher.py.

Example: `./run_mixer.ps1 --in C:\data\source.pb --mix C:\data\labeled.pb --out C:\data\mixed.pb`.

The defaults are based on previously reported local paths. Adjust them if another dataset should be used.
