cd ..

.\scripts\keras_to_tflite.ps1 `
    -In  "..\..\data\runs\keras\small.keras" `
    -Out "..\..\data\runs\keras\small.tflite"

.\scripts\keras_to_tflite.ps1 `
    -In  "..\..\data\runs\keras\medium.keras" `
    -Out "..\..\data\runs\keras\medium.tflite"

cd .\scripts
