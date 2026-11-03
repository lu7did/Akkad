# picoKeras ARM v0.1.22 - autodescarga controlada

Base: akkad(10).zip + parches de picoKeras ARM v0.1.20 y v0.1.21.
Aplicar este ZIP en la raiz de Akkad. Solo se reemplaza picoKeras/ARM/build.ps1.

## Funcionalidad
- Detecta modelo .tflite en assets/model.tflite o unico .tflite en assets.
- Si no hay modelo y se proporciona -ModelUrl (o PICOKERAS_MODEL_URL), lo descarga por HTTPS.
- Permite verificar SHA-256 con -ModelSha256 o PICOKERAS_MODEL_SHA256.
- Comprueba encabezado FlatBuffer TFL3; esta comprobacion NO garantiza INT8 ni compatibilidad de operadores.
- Descarga TFLM desde el repositorio oficial cuando no encuentra sus fuentes y se permite descarga.
- Conserva la compilacion de la biblioteca ARM TFLM existente en v0.1.21.
- No descarga automaticamente un modelo arbitrario, porque no existe ninguno en la linea de base.
- No instala automaticamente toolchains, Pico SDK o GNU Make: requieren version y configuracion adecuadas.
- No modifica git index. Se recomienda ignorar /picoKeras/ARM/third_party/tflm-tree/ en .gitignore.

## Uso
.\build.ps1 -Help
.\build.ps1 -Model ".\assets\model.tflite"
.\build.ps1 -ModelUrl "https://servidor/modelo-int8.tflite" -ModelSha256 "<SHA256_HEX>"
$env:PICOKERAS_MODEL_URL="https://servidor/modelo-int8.tflite"
.\build.ps1

## Limitacion
No se ha compilado con ARM GCC ni ejecutado firmware fisico en este entorno. No se garantiza que cualquier .tflite sea compatible con RP2350.
