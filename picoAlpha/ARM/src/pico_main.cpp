#include "board.hpp"
#include "mcts.hpp"
#include "config.h"
#include "pico_build_info.hpp"
// PA_BUILD_ID_BEGIN v0.2.22: independently check compile-time storage.
#ifndef PA_SEGMENTED_TREE
#error "Missing MCTS storage selection: reconfigure with the new CMakeLists.txt"
#endif
#if PA_SEGMENTED_TREE
#ifndef PA_BUILD_SEGMENTED_CONFIRMED
#error "MCTS segmented CMake confirmation missing"
#endif
#define PA_STORAGE_NAME "SEGMENTED"
#else
#ifndef PA_BUILD_ALLOW_LEGACY
#error "Legacy MCTS was not explicitly authorized"
#endif
#define PA_STORAGE_NAME "MONOLITHIC_ROLLBACK"
#endif
// PA_BUILD_ID_END
#ifndef PA_NN_FC_INT8
#define PA_NN_FC_INT8 0
#endif
#ifndef PA_NN_DSP
#define PA_NN_DSP 1
#endif

#include "pico/stdlib.h"
#include "hardware/clocks.h"
#include "hardware/watchdog.h"
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
#ifndef PA_FIRMWARE_VERSION
#error "PA_FIRMWARE_VERSION must come from CMake"
#endif
#ifndef PA_COMPILED_NN
#error "PA_COMPILED_NN must come from CMake"
#endif
const char* VERSION=PA_FIRMWARE_VERSION;
const char* NN_NAME=PA_COMPILED_NN;
// Serial log calls are compiled out when DEBUG=false. Search statistics remain collected.
template<class... Args> void debug_log(const char* fmt, Args... args) {
 if constexpr (config::DEBUG) std::printf(fmt, args...);
}

tcp_pcb* listener=nullptr;
tcp_pcb* client=nullptr;
Board board;
picoalpha::Network neural;
// PA_COMPACT_HISTORY_BEGIN: default compact history; compile with
// -DPA_COMPACT_HISTORY=0 to return to the prior Board history.
picoalpha::SearchHistory history{picoalpha::SearchHistory::value_type(board)};
// PA_COMPACT_HISTORY_END
bool fen_only=false;
std::string pending;
bool connected=false,request_stop=false,request_quit=false,valid_position=true,go_pending=false;
bool session_error=false; uint32_t recoverable_errors=0;
uint32_t search_sequence=0;
uint32_t led_last=0; bool led_on=false;enum class LedState {Init,NoWiFi,Ready,Thinking,Fatal,Recoverable};LedState led_state=LedState::Init;
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
 if(led_state==LedState::Recoverable){const uint64_t phase=elapsed%1600;set_led((phase<120)||(phase>=240&&phase<360));return;}
 // Thinking: 2 s ON + 2 s OFF. Fatal: 200 ms ON + 200 ms OFF.
 const uint64_t interval=led_state==LedState::Thinking?2000:200;
 if(elapsed>=interval){led_last=millis();set_led(!led_on);}
}
template<class... Args> void uci_trace(const char* fmt, Args... args){
 if constexpr(config::UCI || config::DEBUG){if(stdio_usb_connected())std::printf(fmt,args...);}
}
void wifi_tick();
// PA23_WATCHDOG_DIAG_BEGIN — survives watchdog reset using scratch[0..3].
static constexpr uint32_t WD_MAGIC=0x50413233u;
static uint64_t active_deadline_ms=0;
static uint64_t last_kernel_feed_ms=0;
static uint32_t last_phase=0,last_step=0;
void progress_checkpoint(uint32_t phase,uint32_t step){
 last_phase=phase;last_step=step;
 watchdog_hw->scratch[0]=WD_MAGIC;
 watchdog_hw->scratch[2]=phase;
 watchdog_hw->scratch[3]=step;
 const uint64_t t=millis();
 // Progress is proven by an actual kernel row/FC group or MCTS phase.
 // Do not hide a search exceeding its deadline by feeding forever.
 if(active_deadline_ms && t>=active_deadline_ms)throw std::runtime_error("search_deadline_internal");
 if(t-last_kernel_feed_ms>=100u){watchdog_update();last_kernel_feed_ms=t;}
}
// PA23_WATCHDOG_DIAG_END
void service(){watchdog_update();cyw43_arch_poll();wifi_tick();update_led();}
void send_line(const std::string& s){if(!client)return;std::string data=s+"\n";if(data.size()>tcp_sndbuf(client)){debug_log("UCI TX overflow %u\n",unsigned(data.size()));return;}err_t e=tcp_write(client,data.data(),data.size(),TCP_WRITE_FLAG_COPY);if(e!=ERR_OK){debug_log("UCI TX error %d\n",int(e));return;}tcp_output(client);uci_trace("UCI >> %s\n",s.c_str());}
void dispatch(const std::string& line);
err_t received(void*,tcp_pcb* pcb,pbuf* p,err_t){if(!p){debug_log("TCP disconnected\n");if(led_state==LedState::Thinking){session_error=true;++recoverable_errors;}connected=false;client=nullptr;status_led(session_error?LedState::Recoverable:(wifi_up?LedState::Ready:LedState::NoWiFi));tcp_close(pcb);return ERR_OK;}tcp_recved(pcb,p->tot_len);for(pbuf* q=p;q;q=q->next){auto* bytes=static_cast<const char*>(q->payload);for(int i=0;i<q->len;++i){char c=bytes[i];if(c=='\n'){std::string cmd=pending;pending.clear();if(!cmd.empty()&&cmd.back()=='\r')cmd.pop_back();if(cmd=="stop")request_stop=true;else if(cmd=="quit")request_quit=true;else if(!cmd.empty())dispatch(cmd);}else if(pending.size()<4096)pending+=c;else{request_quit=true;session_error=true;++recoverable_errors;status_led(LedState::Recoverable);}}}pbuf_free(p);return ERR_OK;}
void error_tcp(void*,err_t e){debug_log("TCP error=%d\n",int(e));client=nullptr;connected=false;request_stop=true;session_error=true;++recoverable_errors;status_led(LedState::Recoverable);}
err_t accepted(void*,tcp_pcb* pcb,err_t e){if(e!=ERR_OK)return e;if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;connected=true;status_led(LedState::Ready);request_quit=false;request_stop=false;session_error=false;pending.clear();tcp_recv(pcb,received);tcp_err(pcb,error_tcp);tcp_nagle_disable(pcb);debug_log("TCP connected\n");return ERR_OK;}
void dispatch(const std::string& line){
 uci_trace("UCI << %s\n",line.c_str());
 if(line=="uci"){
  send_line(std::string("id name ")+VERSION);send_line("id author Dr. Pedro E. Colla");send_line("uciok");
 }else if(line=="isready")send_line("readyok");
 else if(line=="ucinewgame"){board.reset();history.assign(1,picoalpha::SearchHistory::value_type(board));fen_only=false;valid_position=true;}
 else if(line.rfind("position ",0)==0){
  try {
   static Board b;static picoalpha::SearchHistory h;h.clear();bool is_fen=false;
   auto start=line.find("startpos"),fen=line.find("fen "),mv=line.find(" moves ");
   if(start!=std::string::npos)b.reset();
   else if(fen!=std::string::npos){size_t st=fen+4;b.set_fen(line.substr(st,mv==std::string::npos?std::string::npos:mv-st));is_fen=true;}
   else throw std::runtime_error("invalid position");
   h.emplace_back(b);
   if(mv!=std::string::npos){std::string args=line.substr(mv+7);size_t p=0;while(p<args.size()){
    auto n=args.find(' ',p);std::string tok=args.substr(p,n==std::string::npos?n:n-p);
    if(!tok.empty()){b.push(b.parse(tok));h.emplace_back(b);}
    if(n==std::string::npos)break;p=n+1;
   }}
   board=std::move(b);history=std::move(h);fen_only=is_fen;valid_position=true;
  }catch(const std::exception& e){valid_position=false;session_error=true;++recoverable_errors;status_led(LedState::Recoverable);debug_log("position rejected: %s\n",e.what());}
 }else if(line.rfind("go",0)==0){if(valid_position){go_pending=true;request_stop=false;}}
}
struct HeapSnapshot { unsigned used, free_blocks, arena; };
HeapSnapshot heap_snapshot(){
 const auto m=mallinfo();
 return {m.uordblks>0?unsigned(m.uordblks):0u,
         m.fordblks>0?unsigned(m.fordblks):0u,
         m.arena>0?unsigned(m.arena):0u};
}
void run_search(){
 go_pending=false;if(!connected||!valid_position)return;
 status_led(LedState::Thinking);
 const uint32_t search_id=++search_sequence;
 watchdog_hw->scratch[1]=search_id;
 progress_checkpoint(1,0);
 debug_log("SEARCH ID=%lu phase=begin repetitions=%d halfmove=%d draw=%d in_check=%d history=%u\n",(unsigned long)search_id,board.repetitions(),board.halfmove,int(board.draw()),int(board.in_check()),unsigned(history.size()));
 neural.reset_profile();
 picoalpha::dual_core_reset_profile();
 const HeapSnapshot mem_before=heap_snapshot();
 const uint64_t start=millis();
 const unsigned budget=config::TMAX_MS;
#if PA_TELEM_MCTS
 debug_log("MCTS begin ID=%lu\n",(unsigned long)search_id);
#endif
#if PA_TELEM_MEM
 debug_log("MEM static=1 nodes=%u dyn_tree=0 scratch=%u board=1 buff=1 net=1\n",unsigned(PA_STATIC_TREE_NODES),unsigned(112u*64u*sizeof(float)));
#endif
 active_deadline_ms=start+budget+500u;
 last_kernel_feed_ms=millis();
 neural.set_progress_hook(progress_checkpoint);
 try {
  auto result=picoalpha::search(neural,board,history,fen_only,config::AZ_SIMULATIONS,config::AZ_CPUCT,config::AZ_MAX_NODES,budget,millis,[]{service();return request_stop||request_quit||!connected;},progress_checkpoint);
  const uint64_t elapsed=millis()-start;
  neural.set_progress_hook(nullptr);active_deadline_ms=0;
  // Retain high-water-mark workspace buffers across moves: repeated heap
  // free/reallocate was fragmenting the allocator during long games.
  const HeapSnapshot mem_after=heap_snapshot();
  const auto np=neural.profile();
  const auto dp=picoalpha::dual_core_profile();
#if PA_TELEM_NN
  debug_log("NN/FC1 mode=%s math=%s dual(%u) Jobs(%lu) wait(%llu) core1=%llu tout=%lu\n",PA_DUAL_CORE_NN?"CORE0":"LEGACY",PA_NN_FC_INT8?"INT8":"FP32",unsigned(dp.active),(unsigned long)dp.jobs,(unsigned long long)dp.wait_us,(unsigned long long)dp.core1_us,(unsigned long)dp.timeouts);
#if PA_NN_PROFILE
  debug_log("NN_PROFILE calls=%u time=%llu conv=%llu policy=%llu value=%llu fc1=%llu fc2=%llu fc/math=%s dsp=%u\n",np.inferences,(unsigned long long)np.total_us,(unsigned long long)np.conv_res_us,(unsigned long long)np.policy_us,(unsigned long long)np.value_conv_us,(unsigned long long)np.fc1_us,(unsigned long long)np.fc2_us,PA_NN_FC_INT8?"INT8":"FP32",unsigned(PA_NN_DSP));
#endif
#endif
  debug_log("SEARCH ID=%lu phase=finished reason=%s\n",(unsigned long)search_id,result.reason);
  debug_log("SEARCH ID=%lu sims=%u reason=%s elapsed=%llu ms nodes=%u/%u q=%f\n",(unsigned long)search_id,result.simulations,result.reason,(unsigned long long)elapsed,result.tree_nodes,result.tree_capacity,double(result.q));
#if PA_TELEM_MCTS
  debug_log("MCTS done sims=%u reason=%s nodes=%u/%u growth=%u elapsed=%llu q=%f\n",result.simulations,result.reason,result.tree_nodes,result.tree_capacity,result.growth_events,(unsigned long long)elapsed,double(result.q));
#endif
#if PA_TELEM_MCTS
  debug_log("MCTS REUSE prior_nodes=%u root=%u cache_hits=%u cache_misses=%u\n",result.reused_prior_nodes,result.reused_root,neural.cache_hits(),neural.cache_misses());
#endif
#if PA_TELEM_MEM
  debug_log("MEM BEFORE heap used=%u free=%u arena=%u peak=%u min_free=%u peak_arena=%u\n",mem_before.used,mem_before.free_blocks,mem_before.arena,result.heap_used_peak,result.heap_free_min,result.heap_arena_peak);
  debug_log("MEM AFTER heap used=%u free=%u arena=%u size=%u tree=%u\n",mem_after.used,mem_after.free_blocks,mem_after.arena,result.node_bytes,result.tree_nodes*result.node_bytes);
#endif
#if PA_TELEM_MCTS
  debug_log("MCTS GUARDS reason=%s search=%lu depth_err=%u cycle=%u index=%u tout=%u stop=%u depth=%u checks=%u inner=%u\n",result.reason,(unsigned long)search_id,result.guard_depth,result.guard_cycle,result.guard_index,result.guard_timeout,result.guard_stop,result.max_depth,result.traverse_checks,result.inner_service_calls);
  debug_log("MCTS INTEGRITY search=%lu completed=%u aborted=%u rejected=%u blocked=%u terminal=%u invalid_priors=%u nonfinite=%u root_q=%f\n",(unsigned long)search_id,result.simulations,result.aborted_simulations,result.rejected_expansions,result.blocked_branches,result.terminal_backups,result.invalid_priors,result.nonfinite_values,double(result.q));
#endif
#if PA_TELEM_MEM
  debug_log("MEM FIXED search=%lu capacity undo=256 key=256 history=256 legal=256 policy=256 net=4672 heap/delta=%ld\n",(unsigned long)search_id,long(mem_after.used)-long(mem_before.used));
  debug_log("MEM ARENA search=%lu target=%u res=%u used=%u denied=%u heap=0 static=%u\n",(unsigned long)search_id,result.pool_target,result.pool_reserved,result.tree_nodes,result.pool_preflight_denied,result.pool_reserved*result.node_bytes);
  debug_log("MEM GROWTH search=%lu try=%u ok=%u deny=%u failed=%u from=%u to=%u request=%u board=%u hist=%u element=%u bytes=%u\n",(unsigned long)search_id,result.growth_attempts,result.growth_events,result.growth_denied,result.growth_alloc_failed,result.growth_last_from,result.growth_last_to,result.growth_request_bytes,result.board_size_bytes,result.history_entries,result.history_element_bytes,result.history_bytes);
#endif
  if(!request_quit&&connected){send_line("info move "+std::to_string(board.fullmove)+" nodes "+std::to_string(result.tree_nodes)+" time "+std::to_string(elapsed)+" sims "+std::to_string(result.simulations));send_line("bestmove "+(result.has?Board::notation(result.move):"0000"));}
 }catch(const std::exception& ex){neural.set_progress_hook(nullptr);active_deadline_ms=0;debug_log("SEARCH ID=%lu phase=exception\n",(unsigned long)search_id);debug_log("SEARCH ERROR: %s\n",ex.what());session_error=true;++recoverable_errors;if(connected){send_line(std::string("info string error MCTS ")+ex.what());picoSargon::MoveList fallback;try {board.legal(fallback);} catch(...) {} send_line("bestmove "+(fallback.empty()?std::string("0000"):Board::notation(fallback.front())));}}
 watchdog_hw->scratch[0]=0;
 status_led(session_error?LedState::Recoverable:(wifi_up?LedState::Ready:LedState::NoWiFi));
}

// No configurar engine por TCP: el firmware fija DEPTH/QDEPTH/TMAX_MS.
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
 picoalpha::dual_core_start();
 if constexpr(config::DEBUG){
  while(!stdio_usb_connected())sleep_ms(100);
  sleep_ms(100);
  const bool wd_reset=watchdog_caused_reboot();
  debug_log("%s watchdog(%u) sims(%u) cpuct=%.3f tout=%u nodes max(%u) tree(%u)\n",VERSION,unsigned(wd_reset),config::AZ_SIMULATIONS,double(config::AZ_CPUCT),config::TMAX_MS,config::AZ_MAX_NODES,unsigned(PA_STATIC_TREE_NODES));
  debug_log("BUILD NN=%s (compile-time)\n",NN_NAME);
  if(wd_reset && watchdog_hw->scratch[0]==WD_MAGIC)
   debug_log("WD_LAST search=%lu phase=%lu step=%lu\n",(unsigned long)watchdog_hw->scratch[1],(unsigned long)watchdog_hw->scratch[2],(unsigned long)watchdog_hw->scratch[3]);
#if PA_TELEM_MEM || PA_TELEM_NN
  debug_log("BUILD STORAGE=%s capacity=%u nodes FC1/INT8=%u NN/DSP=%u DUAL/CORE=%u\n",PA_STORAGE_NAME,unsigned(PA_STATIC_TREE_NODES),unsigned(PA_NN_FC_INT8),unsigned(PA_NN_DSP),unsigned(PA_DUAL_CORE_NN));
#endif

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
 watchdog_hw->scratch[0]=0;
 watchdog_enable(8000,true); // Se alimenta solo desde el bucle principal y service().
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
