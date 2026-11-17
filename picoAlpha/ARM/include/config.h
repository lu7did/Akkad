#pragma once
#include <cstdint>
// SINGLE source of identity and engine / transport configuration.
namespace picoalpha_config {
inline constexpr char UCI_NAME[]="picoAlpha-ARM";
inline constexpr char VERSION[]="0.1.46";
inline constexpr char AUTHOR[]="Akkad / Dr. Pedro E. Colla";
inline constexpr char MDNS_NAME[]="picoalpha";
inline constexpr char MDNS_SERVICE[]="picoalpha-uci";
inline constexpr uint16_t PORT=6200;
inline constexpr bool MDNS_ENABLED=true;
inline constexpr uint32_t WIFI_RETRY_MS=10000;
inline constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS=30000;
inline constexpr uint32_t SIMULATIONS=256;
inline constexpr uint32_t TIMEOUT_MS=1500;
inline constexpr int MAX_DEPTH=10;
inline constexpr float C_PUCT=1.4f;
// Independent trees would otherwise repeat near-identical deterministic paths.
// Core 1 explores slightly more broadly; set to 1.0 to match X86 PUCT exactly.
inline constexpr float CORE1_PUCT_MULTIPLIER=1.12f;
inline constexpr uint32_t NODE_POOL_PER_CORE=4096;
inline constexpr uint32_t CORE1_STACK_BYTES=12288;
inline constexpr uint32_t MIN_APPROX_HEAP_GAP_BYTES=24*1024;
inline constexpr bool DEBUG=true;
inline constexpr uint32_t TELEMETRY_INTERVAL_SIMS=32;
inline constexpr bool TWO_CORES=true;
// Supply credentials locally, never commit secrets to the repository.
// Create picoAlpha/ARM/include/wifi_secrets.h (excluded from version control).
#if __has_include("wifi_secrets.h")
#include "wifi_secrets.h"
#else
inline constexpr char WIFI_SSID[]="";
inline constexpr char WIFI_PASSWORD[]="";
#endif
}
