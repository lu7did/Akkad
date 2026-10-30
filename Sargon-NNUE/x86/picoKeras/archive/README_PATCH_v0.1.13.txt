picoKeras v0.1.13
Fix: schema_generated.h absent from both tree and checkout. CMake restores the header from the local TFLM Git HEAD or .oss, into the build directory. No downloads or network conversions.
Extract at Akkad root, run .\build.ps1 -Clean.
