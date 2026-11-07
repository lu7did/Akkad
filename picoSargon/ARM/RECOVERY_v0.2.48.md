# picoSargon ARM v0.2.48 - recovery of host tools

Apply archive at Akkad repository root. This patch restores the three ARM helper tools
missing after the recovery of `picoSargon/ARM` from Git commit `397e81a`.

- `picoSargon/tools/ARM/embed_grumpy.py` embeds Grumpy weights in FLASH.
- `picoSargon/tools/ARM/build_twin.ps1` is an alternate build helper.
- `picoSargon/tools/ARM/generate_config.py` is a deprecated diagnostic utility.

The `ARM/build.ps1` dependency path is correct; it must NOT be redirected to
`akkad/tools` or into `ARM/scripts`.

Run from `picoSargon/ARM`: `./build.ps1`
Do not publish `ARM/include/config.h` (contains secrets and is Git-ignored).
No changes to the chess search algorithms, ARM multicore logic, or weights.
