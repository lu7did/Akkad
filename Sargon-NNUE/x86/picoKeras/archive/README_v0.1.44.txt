picoKeras v0.1.44 - Minimal PowerShell entrypoints, incremental over v0.1.43.

Each .ps1 contains only a param declaration and one invocation. No assignments,
no global preferences, no validations, no extra commands.

  .\scripts\keras_download.ps1 'https://example.org/small.keras' 'small.keras'
  .\scripts\keras_tflite.ps1 '.\small.keras'
  .\scripts\keras_int8.ps1 '.\small.tflite'
  .\scripts\keras_listen.ps1 '.\small.int8.tflite' 6110

The helper tools retain the necessary model transformations. In particular,
keras_int8.ps1 requires the .source.json from keras_tflite.ps1 because the
validated quantizer needs the original .keras model; it then fixes RESHAPE
shapes and emits the final small.int8.tflite. No new quantization algorithm.

Download accepts a direct URL, and optionally a target file name.
Listen uses the existing build/Release/picoKeras.exe and TCP port 6110.

IMPORTANT: This patch has been source-checked on Linux, not run in Windows.
