picoKeras v0.1.5 - Separacion de procesos

Ubicacion: Akkad/sargon-NNUE/x86/picoKeras

1. Instalacion TFLM (independiente; solo si falta la dependencia):
   .\scripts\install_TFLM.ps1
2. Compilacion SOLO de picoKeras.exe (nunca instala TFLM ni convierte redes):
   .\build.ps1
3. Conversiones independientes (no se llaman desde build.ps1):
   .\scripts\keras_to_tflite.ps1 -In .\models\small.keras -Out .\models\small.tflite
   .\scripts\tflite_to_int8.ps1 -In .\models\small.tflite -Out .\models\small.int8.tflite

Herramientas Python preexistentes en tools/: keras_to_tflite.py y tflite_to_int8.py.
La segunda requiere el manifest de procedencia del primer conversor y el archivo .keras original.
Las conversiones TFLite de ViT deben superar validacion de operadores.
