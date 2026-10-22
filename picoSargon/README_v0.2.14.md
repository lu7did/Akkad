# picoSargon v0.2.14 — parche compilación mDNS

Base: v0.2.13. Se modifica exclusivamente `src/pico_main.cpp`.

Se quita el argumento extra `120` de `mdns_resp_add_service` (API lwIP Pico SDK 2.3.1: 7 argumentos). Se conserva sin cambios `mdns_resp_add_netif(..., 120)` porque su prototipo sí incluye TTL.

No modifica `include/config.h`, las credenciales Wi-Fi ni el motor de ajedrez.

Desde la raíz de picoSargon, aplicar el ZIP sobre el proyecto y ejecutar `./build.ps1` en PowerShell. Compilación ARM real aún no verificada en este entorno.
