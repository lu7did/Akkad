# picoAlpha ARM v0.1.46 — Corrección de callback lwIP

## Fallo confirmado

`lwip/tcp.h` define una macro de compatibilidad `tcp_accepted(pcb)`; el
callback local se había declarado con el mismo identificador:
`err_t tcp_accepted(void*, tcp_pcb*, err_t)`.
Esto genera un error del preprocesador, seguido de errores derivados y
advertencias `-Wunused-*`.

## Modificación

Solo se renombra el callback a `on_tcp_accept` en su declaración y en
`tcp_accept(listener, on_tcp_accept)`. No cambia su implementación, el
protocolo UCI ni MCTS. Se actualizan los identificadores de versión en
`include/config.h` y `CMakeLists.txt`.

## Aplicación

Extraer el ZIP desde la raíz `akkad`, sobrescribiendo los archivos incluidos.
Requiere haber aplicado el parche v0.1.45. Desde `picoAlpha/ARM` ejecutar:

```powershell
.\tools\ps\build.ps1
```

## Validación

La validación de sintaxis con una macro lwIP equivalente (`tcp_accepted(pcb)`)
se completa localmente. Falta verificar la compilación ARM real con el Pico SDK.
