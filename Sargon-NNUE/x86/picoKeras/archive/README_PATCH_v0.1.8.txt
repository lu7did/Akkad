picoKeras v0.1.8: TFLM installer - recover Windows FlatBuffers rename failure.
Extract this ZIP in Akkad/ and overwrite scripts/install_TFLM.ps1.
Does not run network conversions, does not modify build.ps1.
After an upstream failure, only promotes an already-extracted .tmp_flatbuffers_* directory with an existing flatbuffers.h.
The installer preserves existing valid dependency directories. No execution on Windows has been verified.
