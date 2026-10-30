picoKeras v0.1.16 - Schema header bootstrap (independent of build)
Install ZIP at Akkad/.
Run: .\scripts\prepare_TFLM_schema.ps1
Then: .\build.ps1 -Clean
This replaces v0.1.15 script and does not require schema.fbs or flatc.
First tries Git at the installed local TFLM revision, then official raw file at the same revision.
An explicit -AllowMainFallback opt-in permits the unpinned upstream main schema only if needed.
No network conversion is performed. The CMakeLists.txt from v0.1.15 expects this exact overlay location.
Not validated on Windows/MSVC.
