# picoSargon v0.2.11 — DEBUG + identificación + mDNS opcional

Parche incremental sobre v0.2.10. **No modifica** búsqueda Doc, red Grumpy, tablero Mailbox120, reglas UCI ni LED.

## Cambios

- `include/config.h`: `UCI_NAME` es la identificación única usada en UCI y en arranque USB. Agrega `MDNS_ENABLED=false`, `MDNS_HOSTNAME="picosargon"` y `MDNS_SERVICE_NAME="picoSargon UCI"`.
- `DEBUG=true`: bloquea el arranque hasta que un terminal USB CDC esté conectado y emite los mensajes habituales de arranque, red, UCI, niveles y memoria.
- `DEBUG=false`: no espera el terminal ni escribe telemetría USB. Las estadísticas **se siguen calculando y almacenando** en `SearchResult` y `Level` (incluyendo la lectura por nivel de heap y margen estimado de pila); no se han agregado señales LED nuevas. UCI TCP permanece activo.
- `MDNS_ENABLED=false`: CMake no incorpora el módulo mDNS, evitando sobrecoste en flash/RAM. `true`: compila el módulo `pico_lwip_mdns`, configura IPv4 multicast y anuncia `picosargon.local` y `_uci._tcp` sobre el puerto configurado, si la inicialización de red es exitosa.

## Instalación

Copiar los cuatro archivos del parche conservando sus rutas:

- `include/config.h`
- `src/pico_main.cpp`
- `config/lwipopts.h`
- `CMakeLists.txt`

**Importante:** el `config.h` del parche tiene valores de ejemplo. **Antes de sobrescribirlo, copiá tus SSID, PASSWORD y UCI_NAME actuales.** El paquete no incluye credenciales reales.

Desde VS Code en Windows:

```powershell
.\build.ps1 -Board pico_w
```

Con `DEBUG=false`, puede no aparecer el puerto de monitor serie como antes; para confirmar IP sin mDNS, inspeccioná los clientes DHCP del router o compilá una vez con `DEBUG=true`.

## Validación

- Código principal compilado y perft 3=8902 en Linux host.
- No hay SDK ARM en este entorno; la compilación `.uf2`, USB CDC, lwIP/mDNS y la prueba sobre placa siguen pendientes.
- Las opciones `MDNS_ENABLED=true` dependen del `pico_lwip_mdns` incluido en Pico SDK 2.3.1. Windows debe poder resolver `.local` para utilizarlo.

## Seguridad

`PASSWORD` está en texto claro dentro de `config.h` y del firmware. No publicarlo en Git.
