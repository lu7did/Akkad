// picoAlpha ARM transport adapted from Akkad picoSargon/ARM/src/pico_main.cpp.
// Raw lwIP TCP/UCI, CYW43 async WiFi, optional mDNS, watchdog and LED follow
// the established picoSargon transport; the search backend is picoAlpha MCTS.
#include "config.h"
#include "board.hpp"
#include "search_coordinator.hpp"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/cyw43_arch.h"
#include "pico/cyw43_driver.h"
#include "hardware/watchdog.h"
#include "lwip/tcp.h"
#include "lwip/ip4_addr.h"
#if defined(PICOALPHA_MDNS_COMPILED) && PICOALPHA_MDNS_COMPILED
#include "lwip/apps/mdns.h"
#endif
#include <atomic>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <malloc.h>
#include <unistd.h>
#include <cstdint>
using namespace picoalpha_config;
namespace {
uint32_t millis(){return to_ms_since_boot(get_absolute_time());}
struct Options {
 uint32_t simulations=SIMULATIONS, timeout=TIMEOUT_MS;
 int depth=MAX_DEPTH;
 float cpuct=C_PUCT;
} opt,go_limits;
static picoSargon::Board board;
static tcp_pcb* listener=nullptr;
static tcp_pcb* client=nullptr;
static std::atomic<bool> request_stop{false};
static bool connected=false,position_valid=true,searching=false,go_pending=false;
static bool wifi_up=false,wifi_attempt=false;
static uint32_t retry_at=0,attempt_deadline=0;
static bool mdns_registered=false;
static bool led_state=false;
static std::string rx_line,queued_position;
static uint32_t search_sequence=0,client_errors=0,last_progress_report=0;
void logmsg(const char* message){if constexpr(DEBUG){if(stdio_usb_connected())printf("%s\n",message);}}
void led(bool value){if(value!=led_state){led_state=value;cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN,value);}}
void wifi_tick();
void send_line(const std::string& s);
void service(){
 watchdog_update();
 cyw43_arch_poll();
 wifi_tick();
 if(searching && connected && TELEMETRY_INTERVAL_SIMS>0){
  auto progress=picoalpha_arm::get_search_progress();
  uint32_t total=progress.simulations[0]+progress.simulations[1];
  if(total>=last_progress_report+TELEMETRY_INTERVAL_SIMS){
   last_progress_report=total;
   send_line("info string progress sims="+std::to_string(total)
      +" core0="+std::to_string(progress.simulations[0])
      +" depth0="+std::to_string(progress.depth[0])
      +" core1="+std::to_string(progress.simulations[1])
      +" depth1="+std::to_string(progress.depth[1]));
  }
 }
 // LED: connected solid, disconnected pulses, search heartbeat.
 uint32_t t=millis();
 if(searching)led((t/500u)%2u==0);
 else if(wifi_up)led(true);
 else led((t%1750u)<150u || (t%1750u>=450u&&t%1750u<600u) || (t%1750u>=900u&&t%1750u<1050u));
}
void send_line(const std::string& s){
 if(!client)return;
 std::string message=s+"\n";
 if(message.size()>tcp_sndbuf(client)){++client_errors;logmsg("UCI TCP send-buffer overflow");return;}
 err_t e=tcp_write(client,message.data(),u16_t(message.size()),TCP_WRITE_FLAG_COPY);
 if(e==ERR_OK){tcp_output(client);if constexpr(DEBUG)if(stdio_usb_connected())printf("UCI >> %s\n",s.c_str());}
 else {++client_errors;logmsg("UCI TCP write failed");}
}
void disconnect(){
 request_stop.store(true,std::memory_order_release);
 if(client){tcp_recv(client,nullptr);tcp_err(client,nullptr);tcp_abort(client);client=nullptr;}
 if(listener){tcp_accept(listener,nullptr);tcp_close(listener);listener=nullptr;}
 connected=false;rx_line.clear();go_pending=false;
}
void tcp_error(void*,err_t){client=nullptr;connected=false;request_stop.store(true);++client_errors;}
void dispatch(const std::string& line);
err_t tcp_received(void*,tcp_pcb* pcb,pbuf* p,err_t){
 if(!p){
  if(client==pcb){client=nullptr;connected=false;request_stop.store(true);}
  tcp_close(pcb);return ERR_OK;
 }
 tcp_recved(pcb,p->tot_len);
 for(pbuf* part=p;part;part=part->next){
  const char* data=static_cast<const char*>(part->payload);
  for(unsigned k=0;k<part->len;++k){char c=data[k];
   if(c=='\n'){
    std::string line=rx_line;rx_line.clear();
    if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(!line.empty())dispatch(line);
   }else if(rx_line.size()<4096)rx_line+=c;
   else {++client_errors;rx_line.clear();send_line("info string ERROR input line exceeds 4096 bytes");}
  }
 }
 pbuf_free(p);return ERR_OK;
}
err_t on_tcp_accept(void*,tcp_pcb* pcb,err_t e){
 if(e!=ERR_OK)return e;
 if(client){tcp_abort(pcb);return ERR_ABRT;}
 client=pcb;connected=true;position_valid=true;
 rx_line.clear();queued_position.clear();request_stop.store(false);
 tcp_recv(pcb,tcp_received);tcp_err(pcb,tcp_error);tcp_nagle_disable(pcb);
 logmsg("picoAlpha-ARM UCI TCP connected");return ERR_OK;
}
bool open_listener(){
 tcp_pcb* pcb=tcp_new_ip_type(IPADDR_TYPE_ANY);
 if(!pcb)return false;
 if(tcp_bind(pcb,IP_ANY_TYPE,u16_t(PORT))!=ERR_OK){tcp_close(pcb);return false;}
 listener=tcp_listen_with_backlog(pcb,1);
 if(!listener)return false;
 tcp_accept(listener,on_tcp_accept);
 if constexpr(DEBUG)printf("picoAlpha-ARM UCI listening port=%u\n",unsigned(PORT));
 return true;
}
void init_mdns(){
#if defined(PICOALPHA_MDNS_COMPILED) && PICOALPHA_MDNS_COMPILED
 if(!mdns_registered){
  mdns_resp_init();
  err_t e=mdns_resp_add_netif(netif_default,MDNS_NAME);
  if(e==ERR_OK){auto id=mdns_resp_add_service(netif_default,MDNS_SERVICE,"_uci",DNSSD_PROTO_TCP,u16_t(PORT),nullptr,nullptr);
   mdns_registered=int(id)>=0;
  }
 }
#endif
}
void wifi_tick(){
 int status=cyw43_tcpip_link_status(&cyw43_state,CYW43_ITF_STA);
 bool up=status==CYW43_LINK_UP;
 if(up){
  wifi_attempt=false;
  if(!wifi_up){
   wifi_up=true;
   if constexpr(DEBUG)printf("picoAlpha-ARM WiFi ip=%s\n",ip4addr_ntoa(netif_ip4_addr(netif_default)));
  }
  if(!listener&&int32_t(millis()-retry_at)>=0){
   if(open_listener())init_mdns();else retry_at=millis()+WIFI_RETRY_MS;
  }
  return;
 }
 if(wifi_up){wifi_up=false;disconnect();retry_at=millis()+WIFI_RETRY_MS;}
 if(wifi_attempt){
  if(int32_t(millis()-attempt_deadline)<0)return;
  wifi_attempt=false;cyw43_wifi_leave(&cyw43_state,CYW43_ITF_STA);
  retry_at=millis()+WIFI_RETRY_MS;
  return;
 }
 if(int32_t(millis()-retry_at)<0)return;
 if(WIFI_SSID[0]=='\0'){retry_at=millis()+WIFI_RETRY_MS;return;}
 int e=cyw43_arch_wifi_connect_async(WIFI_SSID,WIFI_PASSWORD,CYW43_AUTH_WPA2_AES_PSK);
 if(e==0){wifi_attempt=true;attempt_deadline=millis()+WIFI_CONNECT_TIMEOUT_MS;}
 else retry_at=millis()+WIFI_RETRY_MS;
}
void send_identity(){
 send_line(std::string("id name ")+UCI_NAME+" v"+VERSION);
 send_line(std::string("id author ")+AUTHOR);
 send_line("option name Depth type spin default "+std::to_string(MAX_DEPTH)+" min 1 max "+std::to_string(MAX_DEPTH));
 send_line("option name Simulations type spin default "+std::to_string(SIMULATIONS)+" min 1 max 1000000");
 send_line("option name Timeout type spin default "+std::to_string(TIMEOUT_MS)+" min 1 max 600000");
 send_line("option name Cpuct type string default 1.4");
 send_line("info string picoAlpha-ARM MCTSP+MCTSE model=INT8-780x16 cores=2");
 send_line("uciok");
}
void set_position(const std::string& line){
 try {
  picoSargon::Board candidate;
  auto fen=line.find("fen "),mv=line.find(" moves ");
  if(line.find("startpos")!=std::string::npos)candidate.reset();
  else if(fen!=std::string::npos){size_t start=fen+4;
   candidate.set_fen(line.substr(start,mv==std::string::npos?std::string::npos:mv-start));}
  else {position_valid=false;send_line("info string ERROR position without startpos or fen");return;}
  if(mv!=std::string::npos){size_t off=mv+7;
   while(off<line.size()){
    size_t end=line.find(' ',off);
    std::string token=line.substr(off,end==std::string::npos?std::string::npos:end-off);
    if(!token.empty())candidate.push(candidate.parse(token));
    if(end==std::string::npos)break;
    off=end+1;
   }
  }
  board=std::move(candidate);board.reserve_search(MAX_DEPTH+32);
  position_valid=true;
 }catch(const std::exception& ex){
  position_valid=false;send_line(std::string("info string ERROR invalid position: ")+ex.what());
 }
}
void dispatch(const std::string& line){
 if constexpr(DEBUG)if(stdio_usb_connected())printf("UCI << %s\n",line.c_str());
 if(line=="stop"){request_stop.store(true,std::memory_order_release);return;}
 if(line=="quit"){request_stop.store(true,std::memory_order_release);if(!searching)disconnect();return;}
 if(line=="uci"){send_identity();return;}
 if(line=="isready"){send_line("readyok");return;}
 if(line.rfind("position ",0)==0){
  if(searching){queued_position=line;request_stop.store(true,std::memory_order_release);}
  else {go_pending=false;set_position(line);}
  return;
 }
 if(searching){send_line("info string busy search in progress");return;}
 if(line=="ucinewgame"){go_pending=false;board.reset();board.reserve_search(MAX_DEPTH+32);position_valid=true;return;}
 if(line.rfind("setoption ",0)==0){
  auto n=line.find("name "),v=line.find(" value ");
  if(n==std::string::npos||v==std::string::npos||v<=n+5)return;
  std::string key=line.substr(n+5,v-(n+5));
  std::string value=line.substr(v+7);int number=std::atoi(value.c_str());
  if(key=="Depth"&&number>=1&&number<=MAX_DEPTH)opt.depth=number;
  else if(key=="Simulations"&&number>=1&&number<=1000000)opt.simulations=uint32_t(number);
  else if(key=="Timeout"&&number>=1&&number<=600000)opt.timeout=uint32_t(number);
  else if(key=="Cpuct"){
   float v=std::strtof(value.c_str(),nullptr);if(std::isfinite(v)&&v>0)opt.cpuct=v;
  }
  return;
 }
 if(line.rfind("go",0)==0){
  if(!position_valid){send_line("info string ERROR invalid position");send_line("bestmove 0000");return;}
  // Arguments reduce configured bounds; no unbounded device-side search.
  Options next=opt;
  size_t p=2;
  while(p<line.size()){
   while(p<line.size()&&line[p]==' ')++p;
   size_t end=line.find(' ',p),keyend=end==std::string::npos?line.size():end;
   std::string key=line.substr(p,keyend-p);p=keyend;
   while(p<line.size()&&line[p]==' ')++p;
   if(key!="depth"&&key!="nodes"&&key!="movetime")continue;
   end=line.find(' ',p);std::string val=line.substr(p,end==std::string::npos?std::string::npos:end-p);
   p=end==std::string::npos?line.size():end;
   int x=std::atoi(val.c_str());if(x<1)continue;
   if(key=="depth")next.depth=std::min(next.depth,x);
   else if(key=="nodes")next.simulations=std::min(next.simulations,uint32_t(x));
   else next.timeout=std::min(next.timeout,uint32_t(x));
  }
  go_limits=next;go_pending=true;request_stop.store(false,std::memory_order_release);
  return;
 }
}
struct MemoryInfo {int32_t heap_used=0,heap_free=0,stack_gap=0;};
MemoryInfo memory_info(){
 MemoryInfo out;struct mallinfo m=mallinfo();out.heap_used=m.uordblks;out.heap_free=m.fordblks;
 char stack_here=0;void* brk=sbrk(0);
 intptr_t gap=intptr_t(&stack_here)-intptr_t(brk);
 if(gap>INT32_MAX)gap=INT32_MAX;
 if(gap<INT32_MIN)gap=INT32_MIN;
 out.stack_gap=int32_t(gap);return out;
}
void run_pending(){
 go_pending=false;
 if(!connected||!position_valid)return;
 MemoryInfo before=memory_info();
 // The stack/heap gap is an approximation, not the complete free SRAM.
 if(before.stack_gap>0 && before.stack_gap<int32_t(MIN_APPROX_HEAP_GAP_BYTES)){
  send_line("info string ERROR insufficient approximate heap-stack margin");
  send_line("bestmove 0000");return;
 }
 ++search_sequence;searching=true;last_progress_report=0;
 uint32_t selected_sims=go_limits.simulations,selected_time=go_limits.timeout;
 int selected_depth=go_limits.depth;float selected_cpuct=go_limits.cpuct;
 uint32_t t0=millis();
 picoalpha_arm::CombinedResult r;
 try {r=picoalpha_arm::run_search(board,selected_sims,selected_depth,selected_time,selected_cpuct,request_stop,service);}
 catch(const std::exception& e){
   searching=false;send_line(std::string("info string ERROR search exception: ")+e.what());
   send_line("bestmove 0000");return;
 }catch(...){searching=false;send_line("info string ERROR unexpected search exception");send_line("bestmove 0000");return;}
 searching=false;
 MemoryInfo after=memory_info();
 if(connected){
  float v=std::max(-0.999999f,std::min(0.999999f,r.score_value));
  int cp=int(lroundf(400.f*atanhf(v)));
  uint32_t nps=r.elapsed_ms?uint32_t(uint64_t(r.nodes)*1000u/r.elapsed_ms):0;
  send_line("info depth "+std::to_string(r.max_depth)
    +" seldepth "+std::to_string(r.max_depth)
    +" score cp "+std::to_string(cp)
    +" nodes "+std::to_string(r.nodes)
    +" time "+std::to_string(r.elapsed_ms)
    +" nps "+std::to_string(nps));
  send_line("info string picoAlpha-ARM sims="+std::to_string(r.simulations)
    +" root_visits="+std::to_string(r.root_visits)
    +" limit_sims="+std::to_string(selected_sims)
    +" limit_depth="+std::to_string(selected_depth)
    +" limit_ms="+std::to_string(selected_time)
    +" reason="+r.reason);
  for(int i=0;i<2;++i){send_line("info string core["+std::to_string(i)
    +"] sims="+std::to_string(r.core_sims[i])+" nodes="+std::to_string(r.core_nodes[i])
    +" depth="+std::to_string(r.core_depth[i])+" ms="+std::to_string(r.core_ms[i]));}
  send_line("info string memory heap_used="+std::to_string(after.heap_used)
    +" heap_free="+std::to_string(after.heap_free)
    +" gap_approx="+std::to_string(after.stack_gap)
    +" pool_exhaustions="+std::to_string(r.pool_failures)
    +" core1_stack_untouched="+std::to_string(r.core1_stack_untouched));
  send_line("bestmove "+(r.valid?picoSargon::Board::notation(r.best):"0000"));
 }
 if constexpr(DEBUG){
  if(stdio_usb_connected())printf("picoAlpha-ARM SEARCH #%lu sims=%lu ms=%lu depth=%lu poolfail=%lu reason=%s\n",
    (unsigned long)search_sequence,(unsigned long)r.simulations,(unsigned long)(millis()-t0),
    (unsigned long)r.max_depth,(unsigned long)r.pool_failures,r.reason);
 }
 if(!queued_position.empty()&&connected){
  std::string pending=std::move(queued_position);queued_position.clear();set_position(pending);
 }
}
} // namespace
int main(){
 stdio_init_all();
 if(cyw43_arch_init()){
  printf("picoAlpha-ARM FATAL cyw43 init\n");while(true)sleep_ms(500);
 }
 cyw43_arch_enable_sta_mode();
 watchdog_enable(8000,true);
 board.reserve_search(MAX_DEPTH+32);
 picoalpha_arm::init_cores();
 printf("picoAlpha-ARM v%s BOOT target=pico2_w cores=2 model=INT8 780x16 weights=14544 port=%u mdns=%s.local\n",
   VERSION,unsigned(PORT),MDNS_NAME);
 if(WIFI_SSID[0]=='\0')printf("picoAlpha-ARM WIFI credentials missing: create include/wifi_secrets.h\n");
 while(true){service();if(go_pending)run_pending();sleep_ms(1);}
}
