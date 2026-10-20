//================================================================================================================*
//* Proyecto sargon-nnue
//* Chess player using different Neural Networks as the game evaluation engine
//*
//* A new mind for the old buddy
//* Created as a learning experience
//*
//* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
//* License: CC AS BY 4.0
//*================================================================================================================*
//* pico_main.cpp
//* Gestión de includes y configuración de placa 
//*=================================================================================================================*
#include "board.hpp"
#include "engine.hpp"
#include "grumpy.hpp"
#include "config.h"
#include "generated_grumpy.hpp"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/cyw43_arch.h"
#include "lwip/tcp.h"
#include "lwip/ip4_addr.h"
#if defined(PICOSARGON_MDNS_COMPILED) && PICOSARGON_MDNS_COMPILED
#include "lwip/apps/mdns.h"
#endif
#include <cstdio>
#include <cstring>
#include <string>
#include <stdexcept>
#include <exception>
#include <vector>
#include <malloc.h>
#include <unistd.h>
using namespace picoSargon;
namespace {
const char* VERSION=config::UCI_NAME;
// Serial log calls are compiled out when DEBUG=false. Search statistics remain collected.
template<class... Args> void debug_log(const char* fmt, Args... args) {
 if constexpr (config::DEBUG) std::printf(fmt, args...);
}

tcp_pcb* listener=nullptr;
tcp_pcb* client=nullptr;
Board board;
Grumpy neural;
std::string pending;
bool connected=false,request_stop=false,request_quit=false,valid_position=true,go_pending=false;
uint32_t led_last=0; bool led_on=false;enum class LedState {Init,Ready,Thinking,Fatal};LedState led_state=LedState::Init;
uint64_t millis(){return to_ms_since_boot(get_absolute_time());}
MemoryStat read_memory(){
 MemoryStat s;struct mallinfo m=mallinfo();s.heap_used=m.uordblks;s.heap_free=m.fordblks;
 // Approximate stack/heap gap on single-core RP2040; not exact free SRAM.
 char stack_marker;void* brk=sbrk(0);s.stack_margin=int32_t(reinterpret_cast<uintptr_t>(&stack_marker)-reinterpret_cast<uintptr_t>(brk));return s;
}
void status_led(LedState state){led_state=state;led_last=millis();led_on=true;cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,true);}
void update_led(){unsigned interval=led_state==LedState::Init?0:led_state==LedState::Ready?1000:led_state==LedState::Thinking?3000:100;if(!interval){cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,true);return;}if(millis()-led_last>=interval){led_last=millis();led_on=!led_on;cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,led_on);}}
void service(){cyw43_arch_poll();update_led();}
void send_line(const std::string& s){if(!client)return;std::string data=s+"\n";if(data.size()>tcp_sndbuf(client)){debug_log("UCI TX overflow %u\n",unsigned(data.size()));return;}err_t e=tcp_write(client,data.data(),data.size(),TCP_WRITE_FLAG_COPY);if(e!=ERR_OK){debug_log("UCI TX error %d\n",int(e));return;}tcp_output(client);debug_log("UCI >> %s\n",s.c_str());}
void dispatch(const std::string& line);
err_t received(void*,tcp_pcb* pcb,pbuf* p,err_t){if(!p){debug_log("TCP disconnected\n");connected=false;client=nullptr;tcp_close(pcb);return ERR_OK;}tcp_recved(pcb,p->tot_len);for(pbuf* q=p;q;q=q->next){auto* bytes=static_cast<const char*>(q->payload);for(int i=0;i<q->len;++i){char c=bytes[i];if(c=='\n'){std::string cmd=pending;pending.clear();if(!cmd.empty()&&cmd.back()=='\r')cmd.pop_back();if(cmd=="stop")request_stop=true;else if(cmd=="quit")request_quit=true;else if(!cmd.empty())dispatch(cmd);}else if(pending.size()<4096)pending+=c;else{request_quit=true;}}}pbuf_free(p);return ERR_OK;}
void error_tcp(void*,err_t e){debug_log("TCP error=%d\n",int(e));client=nullptr;connected=false;request_stop=true;}
err_t accepted(void*,tcp_pcb* pcb,err_t e){if(e!=ERR_OK)return e;if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;connected=true;request_quit=false;request_stop=false;pending.clear();tcp_recv(pcb,received);tcp_err(pcb,error_tcp);tcp_nagle_disable(pcb);debug_log("TCP connected\n");return ERR_OK;}
void dispatch(const std::string& line){debug_log("UCI << %s\n",line.c_str());if(line=="uci"){send_line(std::string("id name ")+VERSION);send_line("id author Dr. Pedro E. Colla");send_line("uciok");}else if(line=="isready")send_line("readyok");else if(line=="ucinewgame"){board.reset();valid_position=true;}else if(line.rfind("position ",0)==0){try{Board b;auto start=line.find("startpos");auto fen=line.find("fen ");auto mv=line.find(" moves ");if(start!=std::string::npos)b.reset();else if(fen!=std::string::npos){size_t st=fen+4;b.set_fen(line.substr(st,mv==std::string::npos?std::string::npos:mv-st));}else throw std::runtime_error("invalid position");if(mv!=std::string::npos){std::string args=line.substr(mv+7),tok;size_t p=0;while(p<args.size()){auto n=args.find(' ',p);tok=args.substr(p,n==std::string::npos?n:n-p);if(!tok.empty())b.push(b.parse(tok));if(n==std::string::npos)break;p=n+1;}}board=std::move(b);valid_position=true;}catch(const std::exception& ex){valid_position=false;debug_log("position rejected: %s\n",ex.what());}}else if(line.rfind("go",0)==0){if(!valid_position){debug_log("go rejected: previous position invalid\n");return;}go_pending=true;request_stop=false;} }
void run_search(){
 go_pending=false;
 if(!connected||!valid_position)return;
 status_led(LedState::Thinking);
 debug_log("SEARCH begin max_depth=%d qdepth=%d timeout_ms=%u\n",config::DEPTH,config::QDEPTH,config::TIMEOUT_MS);
 Engine e(neural,millis,[]{service();return request_stop||request_quit||!connected;},read_memory,config::QDEPTH);
 auto r=e.search(board,config::DEPTH,config::TIMEOUT_MS);
 for(const auto& l:r.levels)debug_log("LEVEL depth=%d status=%s elapsed_ms=%llu nodes=%llu qnodes=%llu heap_used=%ld heap_free=%ld stack_gap_approx=%ld\n",l.depth,l.complete?"complete":"aborted",(unsigned long long)l.ms,(unsigned long long)l.nodes,(unsigned long long)l.qnodes,(long)l.mem.heap_used,(long)l.mem.heap_free,(long)l.mem.stack_margin);
 debug_log("SEARCH elapsed_ms=%llu nodes=%llu qnodes=%llu nps=%llu depth=%d tt_hits=%llu tt_stores=%llu cutoffs=%llu reason=%s\n",(unsigned long long)r.elapsed_ms,(unsigned long long)r.nodes,(unsigned long long)r.qnodes,(unsigned long long)(r.nodes*1000/(r.elapsed_ms?r.elapsed_ms:1)),r.depth,(unsigned long long)r.tt_hits,(unsigned long long)r.tt_stores,(unsigned long long)r.cutoffs,r.reason.c_str());
 if(!request_quit&&connected){send_line("info depth "+std::to_string(r.depth)+" score cp "+std::to_string(r.score)+" nodes "+std::to_string(r.nodes));send_line("bestmove "+(r.has_move?Board::notation(r.best):"0000"));}
 status_led(LedState::Ready);
}

}
int main(){stdio_init_all();
 if constexpr (config::DEBUG) {
  while (!stdio_usb_connected()) { sleep_ms(100); }
  sleep_ms(100);
  debug_log("%s BOOT (USB debug connected)\n", config::UCI_NAME);
 }if(cyw43_arch_init()){debug_log("FATAL cyw43 init\n");while(true){sleep_ms(100);}}status_led(LedState::Init);try{neural.load_blob(GRUMPY_DATA,GRUMPY_LENGTH);}catch(const std::exception& e){debug_log("FATAL Grumpy: %s\n",e.what());status_led(LedState::Fatal);while(true){service();sleep_ms(10);}}cyw43_arch_enable_sta_mode();debug_log("WiFi connecting SSID=%s\n",config::SSID);int wifi=cyw43_arch_wifi_connect_timeout_ms(config::SSID,config::PASSWORD,CYW43_AUTH_WPA2_AES_PSK,30000);if(wifi){debug_log("FATAL WiFi=%d\n",wifi);status_led(LedState::Fatal);while(true){service();sleep_ms(10);}}listener=tcp_new_ip_type(IPADDR_TYPE_ANY);if(!listener||tcp_bind(listener,IP_ANY_TYPE,static_cast<u16_t>(config::PORT))!=ERR_OK){debug_log("FATAL TCP bind\n");status_led(LedState::Fatal);while(true){service();sleep_ms(10);}}listener=tcp_listen_with_backlog(listener,1);tcp_accept(listener,accepted);
#if defined(PICOSARGON_MDNS_COMPILED) && PICOSARGON_MDNS_COMPILED
 if constexpr (config::MDNS_ENABLED) {
  // lwIP raw MDNS API must run in the cyw43/lwIP polling context.
  mdns_resp_init();
  err_t mdns_err = mdns_resp_add_netif(netif_default, config::MDNS_HOSTNAME, 120);
  if (mdns_err == ERR_OK) {
   auto service_id = mdns_resp_add_service(netif_default, config::MDNS_SERVICE_NAME,
       "_uci", DNSSD_PROTO_TCP, static_cast<u16_t>(config::PORT), 120, nullptr, nullptr);
   debug_log("mDNS hostname=%s.local service=_uci._tcp port=%u result=%d\n",
       config::MDNS_HOSTNAME, config::PORT, int(service_id));
  } else {
   debug_log("mDNS registration failed err=%d\n", int(mdns_err));
  }
 }
#endif
 debug_log("UCI ready TCP port %u IP %s\n",config::PORT,ip4addr_ntoa(netif_ip4_addr(netif_default)));status_led(LedState::Ready);while(true){service();if(go_pending)run_search();sleep_ms(1);} }
