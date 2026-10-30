# picoSargon Debian/Raspberry Pi v0.2.21

Parche incremental. Extraer en la raíz de Akkad. La compilación Windows permanece disponible; el parser compartido de brains.json admite ahora objetos de rutas.

## Compilación (Debian 12/13, Raspberry Pi OS 64-bit)
`sudo apt-get install -y build-essential cmake python3`
`bash picoSargon/tools/bash/build.sh`

## Verificación
`bash picoSargon/tools/bash/uci_smoke.sh`

## Ejecución
`bash picoSargon/tools/bash/run.sh` (UCI por stdin/stdout)
`bash picoSargon/tools/bash/run_brain.sh tinySargon` (requiere brains.json configurado)

## Formato de brains.json
Para claves de ruta se admite un valor cadena clásico o un objeto:

```json
"network": {"windows": "C:/Akkad/picoSargon/x86/picoSargon/assets/grumpy.bin", "debian": "/home/pi/Akkad/picoSargon/debian/picoSargon/assets/grumpy.bin"}
```

Para ejecutar desde Sargon-NNUE el brain `tinySargon`, configurar también `engine-path` como objeto con los ejecutables Windows y Linux respectivos. Las rutas son ejemplos y deben adaptarse a la instalación. También se permiten rutas relativas en las herramientas Python existentes, y se resuelven según las convenciones originales.

La compilación Linux utiliza directamente `picoSargon/x86/picoSargon/src` y `include`, sin duplicar el núcleo C++. El modelo incluido coincide byte a byte con el grumpy.bin de la rama Windows entregada. La arquitectura de pesos no depende del endianness porque el código usa bytes y desplazamientos.

**Alcance:** compilación Linux nativa del host UCI. No se incluye servidor TCP del firmware ARM. La compilación y prueba sobre una Raspberry Pi real está pendiente; el smoke test se realizó sobre Debian x86_64 si el entorno lo permite.
