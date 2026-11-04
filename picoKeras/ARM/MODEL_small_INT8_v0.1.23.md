# picoKeras ARM - modelo predeterminado small.int8.tflite (paquete v0.1.23)

Fuente del modelo: archivo aportado por el usuario en la conversación.
Fuente del sistema de compilación: Akkad(10).zip más parches ARM v0.1.20-v0.1.22 expresamente utilizados en la conversación.

## Instalación
Extraer desde la raíz Akkad. Se instalará `picoKeras/ARM/assets/model.tflite`.
No se modifica ningún archivo de código ni ninguna otra plataforma. El script `build.ps1` v0.1.22 selecciona ese archivo automáticamente al invocarse sin `-Model`.

## Verificación estructural del modelo
- Tamaño: 2871888 bytes
- SHA256: 331b2e4e7562263802c37bc8dbbafb1203c91b2995e2cd1ac06b56dce4e36664
- Identificador FlatBuffer: TFL3; esquema versión 3.
- Entrada: [1,8,8,12], INT8, escala 0.003921568859368563, zero_point -128.
- Salida: [1,1], INT8, escala 0.0078125, zero_point 0.
- Un subgrafo, 342 operaciones y 18 códigos de operador.

## Advertencias críticas
- El modelo es compatible con la FORMA esperada por `pico_model.cpp`, pero todavía NO está confirmada su compatibilidad con el registro de operadores de TensorFlow Lite Micro. Por ejemplo, el modelo emplea SHAPE (código 77), no registrado por `pico_model.cpp` v0.1.20; requiere auditoría del resto de operaciones.
- Los 2.87 MB de datos embebidos reducen significativamente el espacio disponible en la memoria flash de Pico 2 W y podrían superar las restricciones al agregar firmware y TFLM.
- Tampoco se verificó que la arena de 98,304 bytes alcance; debe medirse `AllocateTensors()` en hardware.
- `INT8` se refiere a los tensores de entrada y salida; no certifica por sí solo que todos los nodos tengan ejecución INT8 ni que el modelo quepa en RP2350.
- Este paquete solo resuelve la selección del modelo predeterminado. No asegura compilación o inferencia exitosa.
