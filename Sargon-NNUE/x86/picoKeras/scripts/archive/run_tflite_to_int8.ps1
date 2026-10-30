cd ..\
.\scripts\tflite_to_int8.ps1 `
    -In  "..\..\data\runs\keras\small.tflite" `
    -Out  "..\..\data\runs\keras\small.int8.tflite" `


.\scripts\tflite_to_int8.ps1 `
    -In  "..\..\data\runs\keras\medium.tflite" `
    -Out  "..\..\data\runs\keras\medium.int8.tflite" `

cd .\scripts

