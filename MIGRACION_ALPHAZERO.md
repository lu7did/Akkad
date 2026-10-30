# AlphaZero directory migration (Akkad)

Extract this ZIP into the **Akkad repository root**. The new project is `Akkad/AlphaZero/` and retains all source, build and test scripts. No compiled `build/` artifacts are included.

After extraction run `powershell -ExecutionPolicy Bypass -File .\tools\migrate_alphazero.ps1` on Windows (or `bash tools/migrate_alphazero.sh` on Linux/macOS) to stage the removal of tracked files from the old location, and add new ones. Review `git diff --cached --stat` before committing. If the old folder has untracked `build/` artifacts, move/back them up separately; these scripts deliberately do not remove them.

Build from `AlphaZero/`: `powershell -ExecutionPolicy Bypass -File .\build.ps1` on Windows, or `bash build_debian.sh` / `bash build_macos.sh` on the supported ARM64 hosts. The existing build scripts resolve the source root through their own script location.

**brains.json**: update each AlphaZero engine path to the new executable location. For example on Windows `C:/Users/pedro/github/bobby/akkad/AlphaZero/build/AlphaZero.exe`; on Linux ARM64 `<akkad>/AlphaZero/build/AlphaZero`. Do not alter neural-network weights paths unless they also moved. The root-specific path needs configuring on each installation; this patch intentionally does not overwrite personal `brains.json`.

This migration is based on the supplied Akkad snapshot; validate builds on your Windows toolchain and other desired platforms.
