# Hive v0.2.3 — Arranque y diagnóstico de motores UCI

Este parche **no** modifica las reglas de distribución ni las sesiones concurrentes de Hive v0.2.2.

## Causa observada

Los tres `engine disconnected` comunicados con la configuración suministrada pueden explicarse por terminación inmediata de los ejecutables:

- Stockfish: `--threads 4` no es una opción CLI habitual. Usar `options: {Threads: 4}` en `hive.yml`.
- AlphaZero C++ de la base 20261124: reconoce `--cores`, **no** `--depth` ni `--qdepth` como argumentos de arranque. `--weights` puede ser necesario según el ejecutable y la distribución de pesos. Hive envía `go depth ... movetime ...` durante las búsquedas.
- picoSargon x86 de la base 20261124: reconoce `--cores`, `--depth`, `--qdepth`, pero requiere `--weights` o `--brains` para cargar la red.

No se confirmó la configuración final de los archivos de pesos del usuario.

## Cambios

- En las desconexiones de subprocesos UCI, ahora se informa `process exit=N` y se incluye el final de `stderr` si está disponible.
- `verbose: true` continúa registrando las líneas de `stderr` del motor en la telemetría.
- Nuevo `engines[].options`: mapa de opciones enviadas mediante `setoption name X value Y` entre `uciok` e `isready`. No se envía para un motor que no la configure.
- Comprobación temprana de que la ruta del ejecutable configurado exista.
- Ejemplo comentado corregido en `hive/etc/hive.yml`.

## Pruebas

Se agregan pruebas de salida temprana con stderr y exitcode, de `setoption` y de validación de configuración. Mantiene las pruebas de versiones anteriores.

## Limitaciones

La integración Windows con los ejecutables reales y sus archivos de pesos debe verificarse en la computadora donde están instalados. El parche no corrige una invocación CLI inválida en el archivo de configuración del usuario: ese archivo también debe actualizarse.
