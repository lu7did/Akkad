#pragma once
// picoSargon: lwIP NO_SYS configuration for Pico SDK cyw43_arch_lwip_poll.
#define NO_SYS                         1
#define SYS_LIGHTWEIGHT_PROT           0
#define LWIP_SOCKET                    0
#define LWIP_NETCONN                   0
#define LWIP_IPV4                      1
#define LWIP_IPV6                      0
#define LWIP_TCP                       1
#define LWIP_UDP                       1
#define LWIP_DHCP                      1
#define LWIP_DNS                       1
#define LWIP_ICMP                      1
#define LWIP_RAW                       1
#define LWIP_ETHERNET                  1
#define MEM_ALIGNMENT                  4
#define MEM_SIZE                       (16 * 1024)
#define MEMP_NUM_TCP_PCB               8
#define MEMP_NUM_TCP_PCB_LISTEN        4
#define MEMP_NUM_TCP_SEG               32
#define PBUF_POOL_SIZE                 24
#define TCP_MSS                        1460
#define TCP_WND                        (4 * TCP_MSS)
#define TCP_SND_BUF                    (2 * TCP_MSS)
#define TCP_SND_QUEUELEN               (4 * TCP_SND_BUF / TCP_MSS)
#define LWIP_TCP_KEEPALIVE             1
#define LWIP_NETIF_STATUS_CALLBACK     1
#define LWIP_NETIF_LINK_CALLBACK       1
#define LWIP_STATS                     0
#define LWIP_PROVIDE_ERRNO             1

// Built only when config.h enables MDNS_ENABLED. CMake selects the library.
#if defined(PICOSARGON_MDNS_COMPILED) && PICOSARGON_MDNS_COMPILED
#define LWIP_MDNS_RESPONDER             1
#define LWIP_IGMP                       1
#define MEMP_NUM_UDP_PCB                5
#define LWIP_NUM_NETIF_CLIENT_DATA      1
// mDNS schedules additional timers beyond lwIP core defaults.
// Reserve explicit timer slots to prevent MEMP_SYS_TIMEOUT exhaustion.
#define MEMP_NUM_SYS_TIMEOUT            16
#else
#define LWIP_MDNS_RESPONDER             0
#endif
