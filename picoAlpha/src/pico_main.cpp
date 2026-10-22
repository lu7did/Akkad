#include "board.hpp"
#include "mcts.hpp"
#include "config.h"

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "pico/stdio_usb.h"
#include "pico/cyw43_arch.h"
#include "pico/cyw43_driver.h"
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
picoalpha::Network neural;
std::vector<Board> history{board};bool fen_only=false;
std::string pending;
bool connected=false,request_stop=false,request_quit=false,valid_position=true,go_pending=false;
uint32_t led_last=0; bool led_on=false;enum class LedState {Init,NoWiFi,Ready,Thinking,Fatal};LedState led_state=LedState::Init;
bool wifi_up=false, wifi_attempt_active=false; uint64_t next_wifi_attempt=0, wifi_attempt_deadline=0;
constexpr uint64_t WIFI_CONNECT_TIMEOUT_MS=30000;
uint64_t millis(){return to_ms_since_boot(get_absolute_time());}
// Sin WiFi: tres pulsos de 150ms con pausas apagadas de 300ms,
// seguidos por 700ms apagado. Ciclo total 1750ms; no bloquea lwIP.
void set_led(bool on){if(led_on!=on){led_on=on;cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,on);}}
void status_led(LedState state){if(led_state==state)return;led_state=state;led_last=millis();set_led(state==LedState::Init || state==LedState::Ready);}
void update_led(){
 const uint64_t elapsed=millis()-led_last;
 if(led_state==LedState::NoWiFi){
  const uint64_t phase=elapsed%1750;
  const bool on=(phase<150)||(phase>=450&&phase<600)||(phase>=900&&phase<1050);
  set_led(on);return;
 }
 if(led_state==LedState::Init || led_state==LedState::Ready){set_led(true);return;}
 // Thinking: 2 s ON + 2 s OFF. Fatal: 200 ms ON + 200 ms OFF.
 const uint64_t interval=led_state==LedState::Thinking?2000:200;
 if(elapsed>=interval){led_last=millis();set_led(!led_on);}
}
template<class... Args> void uci_trace(const char* fmt, Args... args){
 if constexpr(config::UCI){if(stdio_usb_connected())std::printf(fmt,args...);}
}
void wifi_tick();
void service(){cyw43_arch_poll();wifi_tick();update_led();}
void send_line(const std::string& s){if(!client)return;std::string data=s+"\n";if(data.size()>tcp_sndbuf(client)){debug_log("UCI TX overflow %u\n",unsigned(data.size()));return;}err_t e=tcp_write(client,data.data(),data.size(),TCP_WRITE_FLAG_COPY);if(e!=ERR_OK){debug_log("UCI TX error %d\n",int(e));return;}tcp_output(client);uci_trace("UCI >> %s\n",s.c_str());}
void dispatch(const std::string& line);
err_t received(void*,tcp_pcb* pcb,pbuf* p,err_t){if(!p){debug_log("TCP disconnected\n");connected=false;client=nullptr;status_led(wifi_up?LedState::Ready:LedState::NoWiFi);tcp_close(pcb);return ERR_OK;}tcp_recved(pcb,p->tot_len);for(pbuf* q=p;q;q=q->next){auto* bytes=static_cast<const char*>(q->payload);for(int i=0;i<q->len;++i){char c=bytes[i];if(c=='\n'){std::string cmd=pending;pending.clear();if(!cmd.empty()&&cmd.back()=='\r')cmd.pop_back();if(cmd=="stop")request_stop=true;else if(cmd=="quit")request_quit=true;else if(!cmd.empty())dispatch(cmd);}else if(pending.size()<4096)pending+=c;else{request_quit=true;}}}pbuf_free(p);return ERR_OK;}
void error_tcp(void*,err_t e){debug_log("TCP error=%d\n",int(e));client=nullptr;connected=false;request_stop=true;status_led(wifi_up?LedState::Ready:LedState::NoWiFi);}
err_t accepted(void*,tcp_pcb* pcb,err_t e){if(e!=ERR_OK)return e;if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;connected=true;status_led(LedState::Ready);request_quit=false;request_stop=false;pending.clear();tcp_recv(pcb,received);tcp_err(pcb,error_tcp);tcp_nagle_disable(pcb);debug_log("TCP connected\n");return ERR_OK;}
void dispatch(const std::string& line){
 uci_trace("UCI << %s\n",line.c_str());
 if(line=="uci"){
  send_line(std::string("id name ")+VERSION);send_line("id author Sargon-NNUE");send_line("uciok");
 }else if(line=="isready")send_line("readyok");
 else if(line=="ucinewgame"){board.reset();history.assign(1,board);fen_only=false;valid_position=true;}
 else if(line.rfind("position ",0)==0){
  try {
   Board b;std::vector<Board> h;bool is_fen=false;
   auto start=line.find("startpos"),fen=line.find("fen "),mv=line.find(" moves ");
   if(start!=std::string::npos)b.reset();
   else if(fen!=std::string::npos){size_t st=fen+4;b.set_fen(line.substr(st,mv==std::string::npos?std::string::npos:mv-st));is_fen=true;}
   else throw std::runtime_error("invalid position");
   h.push_back(b);
   if(mv!=std::string::npos){std::string args=line.substr(mv+7);size_t p=0;while(p<args.size()){
    auto n=args.find(' ',p);std::string tok=args.substr(p,n==std::string::npos?n:n-p);
    if(!tok.empty()){b.push(b.parse(tok));h.push_back(b);}
    if(n==std::string::npos)break;p=n+1;
   }}
   board=std::move(b);history=std::move(h);fen_only=is_fen;valid_position=true;
  }catch(const std::exception& e){valid_position=false;debug_log("position rejected: %s\n",e.what());}
 }else if(line.rfind("go",0)==0){if(valid_position){go_pending=true;request_stop=false;}}
}
void run_search(){
 go_pending=false;if(!connected||!valid_position)return;
 status_led(LedState::Thinking);
 const uint64_t start=millis();
 unsigned budget=config::TIMEOUT_MS;
 if(config::TMAX_MS && (!budget||config::TMAX_MS<budget))budget=config::TMAX_MS;
 debug_log("MCTS begin simulations=%u cpuct=%.3f timeout=%u max_nodes=%u\n",config::AZ_SIMULATIONS,double(config::AZ_CPUCT),budget,config::AZ_MAX_NODES);
 try {
  auto result=picoalpha::search(neural,board,history,fen_only,config::AZ_SIMULATIONS,config::AZ_CPUCT,config::AZ_MAX_NODES,budget,millis,[]{service();return request_stop||request_quit||!connected;});
  const uint64_t elapsed=millis()-start;
  debug_log("MCTS done sims=%u elapsed_ms=%llu q=%f reason=%s\n",result.simulations,(unsigned long long)elapsed,double(result.q),result.reason);
  if(!request_quit&&connected){send_line("info nodes "+std::to_string(result.simulations)+" time "+std::to_string(elapsed));send_line("bestmove "+(result.has?Board::notation(result.move):"0000"));}
 }catch(const std::exception& ex){debug_log("MCTS error: %s\n",ex.what());if(connected)send_line("bestmove 0000");}
 status_led(wifi_up?LedState::Ready:LedState::NoWiFi);
}

// No configurar engine por TCP: el firmware fija DEPTH/QDEPTH/TIMEOUT_MS.
// El ciclo WiFi asíncrono permite mantener el LED activo durante el retry.
void close_tcp_after_wifi_loss(){
 if(client){tcp_recv(client,nullptr);tcp_err(client,nullptr);tcp_abort(client);client=nullptr;}
 if(listener){tcp_accept(listener,nullptr);tcp_close(listener);listener=nullptr;}
 connected=false;request_stop=true;go_pending=false;pending.clear();
 status_led(LedState::NoWiFi);
}
bool open_tcp_listener(){
 tcp_pcb* pcb=tcp_new_ip_type(IPADDR_TYPE_ANY);
 if(!pcb){debug_log("TCP allocation failed\n");return false;}
 if(tcp_bind(pcb,IP_ANY_TYPE,static_cast<u16_t>(config::PORT))!=ERR_OK){
  tcp_close(pcb);debug_log("TCP bind failed\n");return false;
 }
 listener=tcp_listen_with_backlog(pcb,1);
 if(!listener){debug_log("TCP listen failed\n");return false;}
 tcp_accept(listener,accepted);
 status_led(LedState::Ready);
 debug_log("TCP/UCI server ready: listening on port %u\n", unsigned(config::PORT));
 return true;
}
void init_mdns_once(){
#if defined(PICOSARGON_MDNS_COMPILED) && PICOSARGON_MDNS_COMPILED
 if constexpr(config::MDNS_ENABLED){
  static bool registered=false;
  if(!registered){
   mdns_resp_init();
   err_t r=mdns_resp_add_netif(netif_default,config::MDNS_HOSTNAME);
   if(r==ERR_OK){
    auto id=mdns_resp_add_service(netif_default,config::MDNS_SERVICE_NAME,
         "_uci",DNSSD_PROTO_TCP,static_cast<u16_t>(config::PORT),nullptr,nullptr);
    registered=(static_cast<int>(id)>=0);
    debug_log("mDNS hostname=%s.local service=_uci._tcp port=%u id=%d\n",config::MDNS_HOSTNAME,config::PORT,int(id));
   }else debug_log("mDNS failed err=%d\n",int(r));
  }
 }
#endif
}
void wifi_tick(){
 // Use TCP/IP state (incl. DHCP), not radio association state.
 const int link=cyw43_tcpip_link_status(&cyw43_state,CYW43_ITF_STA);
 const bool now_up=(link==CYW43_LINK_UP);

 if(now_up){
  wifi_attempt_active=false;
  if(!wifi_up){
   wifi_up=true;
   debug_log("WiFi connected: %s\n",ip4addr_ntoa(netif_ip4_addr(netif_default)));
   if(open_tcp_listener())init_mdns_once();
   else next_wifi_attempt=millis()+config::WIFI_RETRY_MS;
  }else if(!listener && millis()>=next_wifi_attempt){
   if(!open_tcp_listener())next_wifi_attempt=millis()+config::WIFI_RETRY_MS;
   else init_mdns_once();
  }
  return;
 }
 if(wifi_up){
  debug_log("WiFi disconnected; retry in %u ms\n",config::WIFI_RETRY_MS);
  wifi_up=false;wifi_attempt_active=false;
  close_tcp_after_wifi_loss();
  next_wifi_attempt=millis()+config::WIFI_RETRY_MS;
 }
 // Allow DHCP up to 30 seconds per attempt; retry pause remains 10 seconds.
 // CYW43_LINK_JOIN (1) is an intermediate state, not a failed connection.
 if(wifi_attempt_active){
  if(millis()<wifi_attempt_deadline)return;
  wifi_attempt_active=false;
  debug_log("WiFi connection attempt timed out (status=%d)\n",link);
  // Reset the driver state before the following attempt.
  cyw43_wifi_leave(&cyw43_state,CYW43_ITF_STA);
  next_wifi_attempt=millis()+config::WIFI_RETRY_MS;
  return;
 }
 if(millis()<next_wifi_attempt)return;
 int err=cyw43_arch_wifi_connect_async(config::SSID,config::PASSWORD,CYW43_AUTH_WPA2_AES_PSK);
 if(err!=0)debug_log("WiFi connect start failed: %d\n",err);
 if(err==0){wifi_attempt_active=true;wifi_attempt_deadline=millis()+WIFI_CONNECT_TIMEOUT_MS;}
 else next_wifi_attempt=millis()+config::WIFI_RETRY_MS;
}
} // namespace anonimo: wifi_tick y service comparten el mismo ambito
int main(){
 // Configurar el reloj antes de inicializar USB y WiFi.
 // No todas las frecuencias enteras dentro del rango son alcanzables exactamente.
 bool pll_applied = false;
 const unsigned pll_requested = config::PLL_SYS;
 if (pll_requested >= 120u && pll_requested <= 250u) {
  pll_applied = set_sys_clock_khz(pll_requested * 1000u, false);
 }
 stdio_init_all();
 if constexpr(config::DEBUG){
  while(!stdio_usb_connected())sleep_ms(100);
  sleep_ms(100);
  debug_log("%s BOOT (USB debug connected)\n",config::UCI_NAME);
  if (pll_requested != 0u) {
   if (pll_requested < 120u || pll_requested > 250u) {
    debug_log("PLL_SYS rechazado: %u MHz (rango 120..250); reloj sin cambios: %lu MHz\n",
              pll_requested, static_cast<unsigned long>(clock_get_hz(clk_sys)/1000000u));
   } else if (!pll_applied) {
    debug_log("PLL_SYS no alcanzable exactamente: %u MHz; reloj sin cambios: %lu MHz\n",
              pll_requested, static_cast<unsigned long>(clock_get_hz(clk_sys)/1000000u));
   } else {
    debug_log("PLL_SYS aplicado: solicitado=%u MHz, clk_sys=%lu MHz\n",
              pll_requested, static_cast<unsigned long>(clock_get_hz(clk_sys)/1000000u));
   }
  }
 }
 if(cyw43_arch_init()){
  debug_log("FATAL cyw43 init\n");
  // On Pico W the LED is driven through CYW43; if init fails, LED control may be unavailable.
  while(true)sleep_ms(100);
 }
 status_led(LedState::Init);
 // Neural parameters are read directly from embedded FLASH by Network constructor.
 cyw43_arch_enable_sta_mode();
 status_led(LedState::NoWiFi);
 next_wifi_attempt=0; // primer intento inmediato; reintentos cada 10s
 while(true){
  service();
  if(go_pending && connected && wifi_up)run_search();
  sleep_ms(1);
 }
}
