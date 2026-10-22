# Parche incremental Akkad picoAlpha v0.6.186

**Base:** v0.6.185. Aplicar desde el directorio padre de `Akkad`.

## Fallos corregidos, confirmados en el log de compilacion ARM

1. Faltaba `lwipopts.h` (Pico SDK 2.3.1, lwIP con `pico_cyw43_arch_lwip_poll`). Se incluye `picoAlpha/config/lwipopts.h`, reutilizando la configuracion probada en picoSargon, y se agrega `config` a `target_include_directories`.
2. `std::max(1u, nodes[idx].visits)` mezcla `unsigned int` con `uint32_t` (ARM GCC: `unsigned long`). Se fija el tipo explicitamente con `std::max<uint32_t>(1, nodes[idx].visits)` sin alterar la funcion.

No se modifican red, arbol MCTS, configuraciones ni funcionalidad UCI. No fue posible certificar una compilacion ARM completa en esta sesion; recompilar en Windows y, ante un nuevo fallo, compartir el primer error del compilador.
