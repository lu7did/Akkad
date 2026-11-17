#pragma once
struct netif{};
inline netif* netif_default=nullptr;
inline void* netif_ip4_addr(netif*){return nullptr;}
inline const char* ip4addr_ntoa(void*){return "127.0.0.1";}
