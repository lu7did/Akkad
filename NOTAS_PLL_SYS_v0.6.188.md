# Akkad — parche incremental v0.6.188

## Alcance
- `Akkad/picoSargon/include/config.h` y `Akkad/picoAlpha/include/config.h`: nuevo parametro `PLL_SYS`, por defecto 0 (MHz).
- Ambos `src/pico_main.cpp`: ajuste opcional de `clk_sys` mediante Pico SDK antes de inicializar USB/WiFi; diagnostico serial solo con DEBUG=true.

## Semantica
- `PLL_SYS=0`: conservar clock de inicio del SDK.
- `PLL_SYS` entre 120 y 250: solicitar frecuencia exacta en MHz usando `set_sys_clock_khz(valor * 1000, false)`.
- Fuera de rango o imposible de sintetizar exactamente: conservar reloj previo. Si DEBUG=true, imprimir razon y frecuencia actual.
- Exito: informar valor solicitado y frecuencia reportada por el SDK, solo con DEBUG=true.
- No garantiza estabilidad de placa, Flash, radio o voltaje a todas las frecuencias; ensayar progresivamente.

## Aplicacion
Extraer este ZIP en el directorio padre de `Akkad`, sobreescribiendo cuatro archivos.
Es un parche de firmware Pico, no afecta la version Windows de los motores.
La compilacion cruzada y las pruebas en placa son pendientes.
