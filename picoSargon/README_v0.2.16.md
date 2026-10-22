# picoSargon v0.2.16 — Wi-Fi / DHCP

Parche incremental sobre **v0.2.15**; modifica únicamente `src/pico_main.cpp`.

- Cambia la prueba de conexión de `cyw43_wifi_link_status()` a `cyw43_tcpip_link_status()`: el estado `CYW43_LINK_JOIN=1` indica asociación con el AP, no IP asignada.
- Espera hasta 30 s a la asignación IP (DHCP) por intento. Tras expirar, sale de la asociación y aguarda `config::WIFI_RETRY_MS` (10 s) antes del siguiente intento.
- DEBUG=true: registra transiciones de estado TCP/IP; no imprime credenciales.
- Mantiene el patrón LED y mDNS de v0.2.15.

**Antes de flashear:** revisar `include/config.h`: `SSID`, `PASSWORD`, red 2.4 GHz; el parche no reemplaza ese archivo.

Compilar desde la raíz: `.\build.ps1`.

Verificación realizada: inspección estática; NO probado con hardware ni compilado aquí con Pico SDK 2.3.1.
