# picoSargon v0.2.13 — corrección de enlace wifi_tick

Base requerida: v0.2.12.

## Error confirmado

`undefined reference to (anonymous namespace)::wifi_tick()` al enlazar picoSargon.elf.

`service()` llamaba una declaración de `wifi_tick()` dentro del namespace anónimo, pero la definición estaba fuera de él, porque el bloque se cerraba antes de `close_tcp_after_wifi_loss()`.

## Corrección

Se mueve el cierre del namespace anónimo justo antes de `main()`. Los componentes de Wi-Fi, TCP, mDNS, LED y `wifi_tick()` quedan en el mismo ámbito que `service()`. No se altera el cuerpo de ninguna función ni los parámetros de config.h.

## Instalación

Copiar `src/pico_main.cpp` en la raíz del proyecto picoSargon v0.2.12, reemplazando el archivo existente; conservar el config.h actual para no perder SSID y contraseña. Ejecutar `.\build.ps1` normalmente.

## Validación

Corrección verificada por inspección estructural del fuente. No se ha compilado con Pico SDK/ARM en este entorno; confirmar con la compilación real en Windows.
