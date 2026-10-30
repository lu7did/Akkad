picoKeras x86 v0.1.38 - parche incremental GATHER INT32

Aplicar sobre v0.1.37 desde raiz Akkad.

Causa reproducida en salida de picoKeras.exe:
 Type 'INT32' is not supported by gather.
 Node GATHER (number 5) failed to prepare with status 1

El GATHER de TFLM solo validaba FLOAT32/INT8 para tensor de datos, aun cuando
su rutina Gather<InputT,CoordsT> acepta cualquier tipo POD. Se habilita INT32
como dato y se despacha Gather<int32_t,int32_t>. Los indices siguen siendo
INT32. No se modifican pesos, modelo TFLite, cuantizacion ni pipelines.
Se actualizan ambas copias existentes de TFLM para que la seleccion de arbol
por CMake no cambie el resultado.

Compilar (desde picoKeras):
 cmake --build build --config Release --target picoKeras

Probar (PowerShell):
 $exe = '.\build\Release\picoKeras.exe'
 $network = (Resolve-Path '.\small.mul.int8.tflite').Path
 @('uci','isready','position startpos','go','quit') | & $exe --network $network --stdio

No ejecutado en Windows/MSVC en este entorno. Esta correccion elimina el
rechazo especifico del kernel GATHER para datos INT32; pueden existir otros
bloqueos de kernels que deben reportarse sin asumir que la integracion termina aqui.
