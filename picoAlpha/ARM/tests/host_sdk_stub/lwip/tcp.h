#pragma once
#include <cstdint>
using err_t=int;
using u16_t=uint16_t;
constexpr int ERR_OK=0,ERR_ABRT=-1,IPADDR_TYPE_ANY=0,TCP_WRITE_FLAG_COPY=1;
struct tcp_pcb{};
struct pbuf {pbuf* next=nullptr;void* payload=nullptr;u16_t len=0,tot_len=0;};
inline const int* IP_ANY_TYPE=nullptr;
inline tcp_pcb* tcp_new_ip_type(int){return nullptr;}
inline err_t tcp_bind(tcp_pcb*,const int*,u16_t){return 0;}
inline tcp_pcb* tcp_listen_with_backlog(tcp_pcb* p,int){return p;}
inline void tcp_accept(tcp_pcb*,err_t(*)(void*,tcp_pcb*,err_t)){}
inline err_t tcp_close(tcp_pcb*){return 0;}
inline void tcp_abort(tcp_pcb*){}
inline void tcp_recv(tcp_pcb*,err_t(*)(void*,tcp_pcb*,pbuf*,err_t)){}
inline void tcp_err(tcp_pcb*,void(*)(void*,err_t)){}
inline void tcp_nagle_disable(tcp_pcb*){}
inline void tcp_recved(tcp_pcb*,u16_t){}
inline void pbuf_free(pbuf*){}
inline err_t tcp_write(tcp_pcb*,const void*,u16_t,int){return 0;}
inline err_t tcp_output(tcp_pcb*){return 0;}
inline u16_t tcp_sndbuf(tcp_pcb*){return 8192;}
