picoKeras x86 v0.1.42 PARCHE INCREMENTAL (sobre v0.1.41)
Corrige comparacion ambigua NumPy ndarray en rewrite(): la forma se compara como tupla de enteros.
No cambia pesos ni kernels, ni garantiza la ejecucion final TFLM.
Ejecutar: .\scripts\staticize_and_try.ps1 -Network .\small.mul.int8.tflite
