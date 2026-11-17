#pragma once
inline int cyw43_arch_init(){return 0;}
inline void cyw43_arch_enable_sta_mode(){}
inline void cyw43_arch_poll(){}
inline void cyw43_arch_gpio_put(int,bool){}
inline int cyw43_arch_wifi_connect_async(const char*,const char*,int){return 0;}
