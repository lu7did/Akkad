#pragma once
#include "lwip/tcp.h"
#include "lwip/ip4_addr.h"
constexpr int DNSSD_PROTO_TCP=0;
inline void mdns_resp_init(){}
inline err_t mdns_resp_add_netif(netif*,const char*){return 0;}
inline int mdns_resp_add_service(netif*,const char*,const char*,int,u16_t,void*,void*){return 0;}
