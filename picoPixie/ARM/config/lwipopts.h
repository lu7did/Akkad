#pragma once
// picoPixie inherits the complete lwIP setup from picoSargon.
// Only the three TLS/ALTCP additions are local to picoPixie.
#include "../../../picoSargon/ARM/config/lwipopts.h"
#define LWIP_ALTCP             1
#define LWIP_ALTCP_TLS         1
#define LWIP_ALTCP_TLS_MBEDTLS 1
