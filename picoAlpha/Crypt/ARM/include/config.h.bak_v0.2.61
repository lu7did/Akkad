#pragma once
// picoAlpha v0.2.12 - compilacion fija, no exponer este archivo en repositorios publicos.
namespace picoSargon { namespace config {
inline constexpr const char* UCI_NAME = "picoAlpha v0.2.12";
inline constexpr const char* SSID = "bolSPA_EXT";
inline constexpr const char* PASSWORD = "PERSONAL2025"; // texto claro solicitado
inline constexpr unsigned PORT = 6110;
inline constexpr unsigned PLL_SYS = 0; // MHz: 0 conserva frecuencia del SDK; 120..250 intenta cambiarla
inline constexpr unsigned TIMEOUT_MS = 16000; // 0 = sin limite temporal
inline constexpr bool DEBUG = true;
inline constexpr bool UCI = true;
inline constexpr unsigned WIFI_RETRY_MS = 10000;
inline constexpr bool MDNS_ENABLED = true;
inline constexpr const char* MDNS_HOSTNAME = "picoalpha";
inline constexpr const char* MDNS_SERVICE_NAME = "picoAlpha UCI";
// Estos parametros se configuran durante la compilacion.
// Simulaciones controlan trabajo; nodos controlan reserva de SRAM del arbol.
#if defined(PICOALPHA_TARGET_PICO_W)
inline constexpr unsigned AZ_SIMULATIONS = 48;
inline constexpr unsigned AZ_MAX_NODES = 320;
#else
//inline constexpr unsigned AZ_SIMULATIONS = 160;
inline constexpr unsigned AZ_SIMULATIONS = 300;
inline constexpr unsigned AZ_MAX_NODES = 8576;
#endif
inline constexpr float AZ_CPUCT = 1.5f;
inline constexpr unsigned TMAX_MS = 16000; // maximo por go; 0 = sin limite propio
} }
