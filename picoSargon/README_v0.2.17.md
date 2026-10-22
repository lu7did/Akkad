# picoSargon v0.2.17 — corrección de plazo Wi-Fi

Parche incremental sobre v0.2.16. Sólo cambia `src/pico_main.cpp`.

**Defecto reproducible:** el intento asíncrono se interrumpía a los 10 s porque `next_wifi_attempt` (pausa entre intentos) era utilizado también como deadline del intento activo, aunque el comentario indicaba 30 s. En `CYW43_LINK_NOIP` la espera era especialmente perjudicial para DHCP.

**Corrección:** variable independiente `wifi_attempt_deadline` y límite `WIFI_CONNECT_TIMEOUT_MS=30000`. Si no llega a `CYW43_LINK_UP` dentro del plazo, se abandona el intento y se espera `config::WIFI_RETRY_MS` (10 s) antes del siguiente. No cambia SSID, PASSWORD, mDNS, Grumpy, LED ni búsqueda.

Aplicar desde la raíz de picoSargon: `Expand-Archive -LiteralPath <ruta_zip> -DestinationPath . -Force` y `./build.ps1`.

**No hay compilación física Pico SDK ni prueba de conexión real en este entorno.** El cambio corrige un fallo temporal demostrado, no garantiza que la red y DHCP tengan configuración correcta. Si se repite `status=2` durante los 30 s, investigar DHCP/seguridad router y registrar IP/máscara/gateway.
