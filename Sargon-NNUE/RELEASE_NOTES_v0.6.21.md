# Sargon-NNUE v0.6.21

## Consolidación SargonCore / SARGON+

- El SARGON canónico pasa a estar implementado por `SargonCore`; `SargonPlayer` queda como alias compatible.
- `SargonPlusPlayer` hereda directamente de `SargonCore`.
- Con `--boost 0 --turbo 0`, SARGON+ utiliza deliberadamente el mismo camino de iteración del Core.

## Nueva política de timeout

- Depth 1 es obligatorio y nunca es interrumpido por el `tmax` interno.
- `tmax` sigue siendo presupuesto total desde el comienzo de la jugada.
- Una vez terminado D1, sólo se intenta D2+ con el presupuesto restante.
- Si D1 consume o supera `tmax`, se juega D1 y se emite `❗ BASELEVEL ...`; no es GUARDRAIL porque el nivel quedó completo.
- Si D2+ es interrumpido, se conserva el último nivel completo y se emite `⚠️ GUARDRAIL`.

## `--boost` como máscara de 16 bits

- Semántica acumulativa anterior eliminada.
- Se conservan 13 algoritmos, cada uno en un bit independiente (bits 0..12).
- Se aceptan decimal, hexadecimal (`0x...`) y binario con sufijo `b` (`1010b`), además de `0b...`.
- Cada bit activo se anuncia una vez al inicio con `🚀`.
- La ruta avanzada deja de implicar PVS: las ventanas PVS sólo se usan si está encendido el bit PVS.

## `--turbo` como máscara de 8 bits

- Nueva interfaz estable `--turbo 0..255`, con los mismos formatos numéricos.
- `0x01`: Adaptive Full Width (registrado / staged).
- `0x02`: Adaptive Candidate Selection (registrado / staged).
- Bits 2..7 reservados.
- v0.6.21 no activa todavía los actuadores adaptativos; la máscara y telemetría quedan preparadas para la siguiente implementación después de validar paridad de Core.

## Documentación

El README incorpora el análisis consolidado de Clock Controller, Complexity Model, Full Width adaptativo, Candidate Selection, interacción BOOST/TURBO, riesgos de selectividad y política de telemetría `❗ / ⚠️ / 🚀 / ⚡`.
