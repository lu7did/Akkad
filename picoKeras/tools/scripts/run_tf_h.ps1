
python ..\tools\tflite_to_header.py `
  .\small.int8.tflite `
  --output .\picoKeras\ARM\include\model_data.h `
  --symbol pico_keras_model `
  --require-int8
