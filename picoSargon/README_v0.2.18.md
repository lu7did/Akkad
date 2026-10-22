# picoSargon v0.2.18 — reserva de temporizadores mDNS

Aplicar sobre v0.2.17. Solo cambia `config/lwipopts.h`.

## Motivo
Con `MDNS_ENABLED=true` el registro mDNS provoca `PANIC: sys_timeout: timeout != NULL, pool MEMP_SYS_TIMEOUT is empty`. El pool automático de lwIP cubre los temporizadores internos, pero no reserva suficientes entradas para los eventos adicionales del responder mDNS.

## Modificación
Dentro de la rama condicional `PICOSARGON_MDNS_COMPILED`, definir `MEMP_NUM_SYS_TIMEOUT 16`, además de los recursos UDP y de interfaz que ya estaban reservados. Cuando mDNS está deshabilitado, el dimensionamiento anterior no cambia.

## Compilación
Ejecutar `./build.ps1` desde la raíz de picoSargon. El resultado se debe validar en hardware; este parche no fue compilado con el SDK ARM en este entorno.

Si persiste el PANIC, registrar momento exacto y revisar nuevos temporizadores y re-inicializaciones mDNS. No se modifican el motor, la red neuronal, credenciales ni los tiempos de Wi-Fi.
