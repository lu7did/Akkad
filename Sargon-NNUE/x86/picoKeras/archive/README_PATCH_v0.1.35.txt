picoKeras v0.1.35 — EXPERIMENTAL MUL SQUARE EXPORT
Requires prior v0.1.34 patch. Extract from Akkad root, retaining sargon-nnue/x86/picoKeras/.

From picoKeras directory:
.\scripts\int8_pipeline.ps1 -Mode convert -Source clone -IntegerSquare -Keras "C:\Users\pedro\github\bobby\akkad\Sargon-NNUE\data\runs\keras\small.keras" -Fp32 ".\small.mul.fp32.tflite" -Int8 ".\small.mul.int8.tflite" -Report ".\int8_pipeline_v0.1.35.json" -CalibrationSamples 256 -ValidationSamples 64 -MaxInt8Error 0.20

Method: clone LayerNormalization with identical dynamic mean and variance computation, substituting centered*centered for SQUARE. Keras cloning copies pre-trained weights unchanged. This is a graph-level hypothesis, not a validated full INT8 model. Failure retains rejected FlatBuffer and JSON. No modifications to production C++ runtime.

NOTE: Keras may lower multiplication back to SQUARE; if so, the experiment fails honestly and audit identifies it. Passing numeric tolerance alone does not establish TFLM kernel compatibility.
