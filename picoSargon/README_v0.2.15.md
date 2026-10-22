# picoSargon v0.2.15 — Corrección API mDNS Pico SDK 2.3.1

Parche incremental sobre v0.2.14. Corrige exclusivamente la firma de `mdns_resp_add_netif` en `src/pico_main.cpp` (dos argumentos, no tres). La llamada a `mdns_resp_add_service` permanece con siete argumentos. No se altera `config.h`, Grumpy ni el algoritmo de búsqueda.

Aplicación: extraer este ZIP sobre la raíz de picoSargon y ejecutar `./build.ps1` en PowerShell.

Verificación: contraste estático con las firmas visibles de `lwip/apps/mdns.h` del log de Pico SDK 2.3.1. No se ha podido ejecutar aquí la compilación cruzada completa ni prueba en placa.
