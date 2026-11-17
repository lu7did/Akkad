#pragma once
struct cyw43_driver_state{};
inline cyw43_driver_state cyw43_state{};
constexpr int CYW43_ITF_STA=0,CYW43_LINK_UP=3,CYW43_AUTH_WPA2_AES_PSK=0,
 CYW43_WL_GPIO_LED_PIN=0;
inline void cyw43_wifi_leave(cyw43_driver_state*,int){}
inline int cyw43_tcpip_link_status(cyw43_driver_state*,int){return 3;}
