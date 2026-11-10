# Nurse v0.1.9: integridad de transporte externo

Para `type=external`, `url: "host:port"` equivale a `ipaddress` + `port`. La ausencia de destino, una URL inválida o un destino contradictorio son errores de configuración. Nurse abre ese socket y debe completar `uciok` y `readyok` antes de anunciar disponibilidad. No hay motor alternativo ni sustitución silenciosa.

El campo UCI `id name` del servidor conectado se registra literalmente en `stderr` como identidad **declarada** del motor remoto, sin contrastarlo con el identificador local del brain ni con el nombre del host. `id name` no constituye prueba criptográfica de identidad ni de integridad del ejecutable. Un motor puede identificarse con cualquier nombre, y no se rechaza una conexión por ese motivo.

La respuesta UCI que Nurse envía al benchmark incluye `backend=external` como información del tipo de transporte seleccionado por Nurse; no se trata de una verificación del nombre remoto. El benchmark puede negarse a operar con una versión antigua de Nurse que no confirme ese backend, evitando resultados con un transporte distinto al configurado.

La telemetría completa del socket y del motor va a `stderr` y al registro del benchmark. Las filas compactas del benchmark no se alteran.
