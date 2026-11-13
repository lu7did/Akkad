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
#ifndef EPE
#define EPE 0
#endif
#ifndef PA_EPE_CLASSIC_GUIDE
#define PA_EPE_CLASSIC_GUIDE 0
#endif
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
#if EPE
bool epe_pending=false,epe_cancel=false,epe_active=false,epe_report_pending=false;
uint64_t epe_cancel_requested_ms=0;
picoSargon::Move epe_our_move{};
uint32_t epe_last_sims=0,epe_last_ms=0,epe_last_search=0;
uint32_t epe_cycles=0,epe_active_cycles=0,epe_skipped=0,epe_sims_total=0,epe_reused_total=0,epe_nn_total=0,epe_hits=0,epe_discarded_total=0,epe_stop_latency_max=0;
static picoSargon::Board epe_board;
static picoalpha::SearchHistory epe_history;
#endif
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
#ifndef PA_NN_TRACE
#define PA_NN_TRACE 0
#endif
// PA23_WATCHDOG_DIAG_BEGIN — survives watchdog reset using scratch[0..3].
static constexpr uint32_t WD_MAGIC=0x50413233u;
static uint64_t active_deadline_ms=0;
static uint64_t last_kernel_feed_ms=0;
static uint32_t last_phase=0,last_step=0;
void progress_checkpoint(uint32_t phase,uint32_t step){
 // Phase transitions from the FIRST search only: low-volume crash breadcrumbs.
 // Step counters can be high-frequency and are deliberately not printed.
 if(PA_NN_TRACE && search_sequence==1u && phase!=last_phase && phase>=9u && phase<=25u){
   debug_log("NN_TRACE phase=%lu step=%lu core=%u\n", (unsigned long)phase,
             (unsigned long)step, unsigned(get_core_num()));
 }
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
err_t received(void*,tcp_pcb* pcb,pbuf* p,err_t){if(!p){debug_log("TCP disconnected\n");if(led_state==LedState::Thinking){session_error=true;++recoverable_errors;}connected=false;client=nullptr;status_led(session_error?LedState::Recoverable:(wifi_up?LedState::Ready:LedState::NoWiFi));tcp_close(pcb);return ERR_OK;}tcp_recved(pcb,p->tot_len);for(pbuf* q=p;q;q=q->next){auto* bytes=static_cast<const char*>(q->payload);for(int i=0;i<q->len;++i){char c=bytes[i];if(c=='\n'){std::string cmd=pending;pending.clear();if(!cmd.empty()&&cmd.back()=='\r')cmd.pop_back();if(cmd=="stop"){
#if EPE
 epe_cancel=true;epe_pending=false;if(epe_active&&!epe_cancel_requested_ms)epe_cancel_requested_ms=millis();
#endif
 request_stop=true;
}else if(cmd=="quit"){
#if EPE
 epe_cancel=true;epe_pending=false;if(epe_active&&!epe_cancel_requested_ms)epe_cancel_requested_ms=millis();
#endif
 request_quit=true;
}else if(!cmd.empty())dispatch(cmd);}else if(pending.size()<4096)pending+=c;else{request_quit=true;session_error=true;++recoverable_errors;status_led(LedState::Recoverable);}}}pbuf_free(p);return ERR_OK;}
void error_tcp(void*,err_t e){debug_log("TCP error=%d\n",int(e));client=nullptr;connected=false;request_stop=true;session_error=true;++recoverable_errors;status_led(LedState::Recoverable);}
err_t accepted(void*,tcp_pcb* pcb,err_t e){if(e!=ERR_OK)return e;if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;connected=true;status_led(LedState::Ready);request_quit=false;request_stop=false;session_error=false;pending.clear();tcp_recv(pcb,received);tcp_err(pcb,error_tcp);tcp_nagle_disable(pcb);debug_log("TCP connected\n");return ERR_OK;}
void dispatch(const std::string& line){
#if EPE
 if(line=="ucinewgame" || line.rfind("position ",0)==0 || line.rfind("go",0)==0){
  epe_cancel=true;epe_pending=false;if(epe_active&&!epe_cancel_requested_ms)epe_cancel_requested_ms=millis();
 }
#endif
 uci_trace("UCI << %s\n",line.c_str());
 if(line=="uci"){
  send_line(std::string("id name ")+VERSION);send_line("id author Dr. Pedro E. Colla");send_line("uciok");
 }else if(line=="isready")send_line("readyok");
 else if(line=="ucinewgame"){
#if EPE
 debug_log("EPE SUMMARY cycles=%lu active=%lu skipped=%lu sims=%lu nn_calls=%lu reused_sims=%lu discarded_sims=%lu hits=%lu useful_pct=%.2f max_stop_latency_ms=%lu\n",
  (unsigned long)epe_cycles,(unsigned long)epe_active_cycles,(unsigned long)epe_skipped,(unsigned long)epe_sims_total,
  (unsigned long)epe_nn_total,(unsigned long)epe_reused_total,(unsigned long)epe_discarded_total,(unsigned long)epe_hits,
  epe_sims_total?100.0*epe_reused_total/epe_sims_total:0.0,(unsigned long)epe_stop_latency_max);
 epe_cycles=epe_active_cycles=epe_skipped=epe_sims_total=epe_reused_total=epe_nn_total=epe_hits=epe_discarded_total=epe_stop_latency_max=0;
#endif
 board.reset();history.assign(1,picoalpha::SearchHistory::value_type(board));fen_only=false;valid_position=true;}
 else if(line.rfind("position ",0)==0){
  try {
#if EPE
   // Reuse the existing position-parser scratch buffers for speculative search:
   // no second 26 KiB Board or 9 KiB history allocation in scarce SRAM.
   Board& b=epe_board;picoalpha::SearchHistory& h=epe_history;
#else
   static Board b;static picoalpha::SearchHistory h;
#endif
   h.clear();bool is_fen=false;
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
 picoalpha::fc1_detail_reset();
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
  const uint64_t nn_total=np.total_us;
  const uint64_t search_us=elapsed*1000u;
  const uint64_t non_nn_us=search_us>nn_total?search_us-nn_total:0;
#if PA_TELEM_NN || PA_DIAGNOSTIC_RUN
  debug_log("NN/FC1 mode=%s math=%s dual(%u) Jobs(%lu) wait(%llu) core1=%llu tout=%lu\n",PA_FC1_PREPACK?"TILED4X32":"ROW_DOT",PA_NN_FC_INT8?"INT8":"FP32",unsigned(dp.active),(unsigned long)dp.jobs,(unsigned long long)dp.wait_us,(unsigned long long)dp.core1_us,(unsigned long)dp.timeouts);
#if PA_NN_PROFILE
  debug_log("NN_PROFILE calls=%u time=%llu first=%llu residual=%llu conv=%llu policy=%llu value=%llu fc1=%llu fc2=%llu fc/math=%s dsp=%u\n",np.inferences,(unsigned long long)np.total_us,(unsigned long long)np.first_conv_us,(unsigned long long)np.residual_us,(unsigned long long)np.conv_res_us,(unsigned long long)np.policy_us,(unsigned long long)np.value_conv_us,(unsigned long long)np.fc1_us,(unsigned long long)np.fc2_us,PA_NN_FC_INT8?"INT8":"FP32",unsigned(PA_NN_DSP));
#if PA_COMPILED_IS_1X8
  const auto fc=picoalpha::fc1_detail_profile();
  debug_log("FC1_DETAIL id=%lu calls=%lu quant_us=%llu core0_us=%llu core1_us=%llu core0_groups=%lu core1_groups=%lu job_wall_us=%llu dispatch_wait_us=%llu overhead_est_us=%llu groups_per_call=32\n",
   (unsigned long)search_id,(unsigned long)fc.calls,(unsigned long long)fc.quant_us,(unsigned long long)fc.core0_us,(unsigned long long)fc.core1_us,
   (unsigned long)fc.core0_groups,(unsigned long)fc.core1_groups,(unsigned long long)np.fc1_us,(unsigned long long)dp.wait_us,
   (unsigned long long)(np.fc1_us>fc.quant_us+std::max(fc.core0_us,fc.core1_us)?np.fc1_us-fc.quant_us-std::max(fc.core0_us,fc.core1_us):0));
  debug_log("FC1_MEMORY id=%lu flash_bytes=%llu prefetches=%llu mac_pairs=%llu core0_groups_cfg=%u dsp_packed=%u prefetch_enabled=%u cal_enabled=%u cal_observe_us=%llu\n",(unsigned long)search_id,(unsigned long long)fc.flash_bytes,(unsigned long long)fc.prefetches,(unsigned long long)fc.mac_pairs,unsigned(PA_FC1_CORE0_GROUPS),unsigned(PA_FC1_DSP_PACKED),unsigned(PA_FC1_FLASH_PREFETCH),unsigned(PA_CALIBRATION_TELEMETRY),(unsigned long long)np.calibration_observe_us);
#endif
  debug_log("NN_INT8 resconv_us=%llu se_us=%llu requant_us=%llu convert_us=%llu\n",(unsigned long long)np.int8_conv_us,(unsigned long long)np.int8_se_us,(unsigned long long)np.int8_requant_us,(unsigned long long)np.int8_convert_us);
#if PA_INT8_ACTIVATIONS && PA_CALIBRATION_TELEMETRY
  const auto cal=neural.calibration_profile();
  auto emit_cal=[&](const char* name,const picoalpha::QuantStageStats& st){
   debug_log("NN_CAL stage=%s samples=%llu sat_neg=%llu sat_pos=%llu min=%ld max=%ld hist=",name,(unsigned long long)st.samples,(unsigned long long)st.saturated_neg,(unsigned long long)st.saturated_pos,(long)st.min_q,(long)st.max_q);
   for(unsigned k=0;k<16;++k)debug_log("%s%llu",k?",":"",(unsigned long long)st.abs_hist[k]);
   debug_log("\n");
  };
  emit_cal("trunk",cal.trunk_input);emit_cal("res1",cal.residual_conv1);
  emit_cal("res2",cal.residual_conv2);emit_cal("se_skip",cal.residual_output);
#endif

#endif
#endif
  debug_log("PERF ID=%lu elapsed_us=%llu nn_us=%llu other_us=%llu nn_pct=%.2f inferred=%u per_infer_us=%.1f per_sim_us=%.1f nodes=%u per_node_us=%.1f cache_hit=%lu cache_miss=%lu dual_active=%u dual_jobs=%lu dual_wait_us=%llu dual_core1_us=%llu cal_observe_us=%llu\n",(unsigned long)search_id,(unsigned long long)search_us,(unsigned long long)nn_total,(unsigned long long)non_nn_us,search_us?100.0*double(nn_total)/double(search_us):0.0,np.inferences,np.inferences?double(nn_total)/double(np.inferences):0.0,result.simulations?double(search_us)/double(result.simulations):0.0,result.tree_nodes,result.tree_nodes?double(search_us)/double(result.tree_nodes):0.0,(unsigned long)neural.cache_hits(),(unsigned long)neural.cache_misses(),unsigned(dp.active),(unsigned long)dp.jobs,(unsigned long long)dp.wait_us,(unsigned long long)dp.core1_us,(unsigned long long)np.calibration_observe_us);
  const uint64_t stage_us[]={np.first_conv_us,np.residual_us,np.policy_us,np.value_conv_us,np.fc1_us,np.fc2_us,non_nn_us};
  const char* stage_name[]={"first_conv","residual","policy","value_conv","fc1","fc2","non_neural_other"};
  unsigned dominant=0;for(unsigned k=1;k<7;++k)if(stage_us[k]>stage_us[dominant])dominant=k;
  debug_log("BOTTLENECK ID=%lu dominant=%s us=%llu pct_total=%.2f calibration_us=%llu\n",(unsigned long)search_id,stage_name[dominant],(unsigned long long)stage_us[dominant],search_us?100.0*double(stage_us[dominant])/double(search_us):0.0,(unsigned long long)np.calibration_observe_us);
  debug_log("SEARCH ID=%lu phase=finished reason=%s\n",(unsigned long)search_id,result.reason);
  debug_log("SEARCH ID=%lu sims=%u reason=%s elapsed=%llu ms nodes=%u/%u q=%f\n",(unsigned long)search_id,result.simulations,result.reason,(unsigned long long)elapsed,result.tree_nodes,result.tree_capacity,double(result.q));
#if PA_TELEM_MCTS
  debug_log("MCTS done sims=%u reason=%s nodes=%u/%u growth=%u elapsed=%llu q=%f\n",result.simulations,result.reason,result.tree_nodes,result.tree_capacity,result.growth_events,(unsigned long long)elapsed,double(result.q));
#endif
#if PA_TELEM_MCTS
  debug_log("MCTS REUSE prior_nodes=%u root=%u cache_hits=%u cache_misses=%u\n",result.reused_prior_nodes,result.reused_root,neural.cache_hits(),neural.cache_misses());
#if EPE
  debug_log("MCTS COMPACT applied=%u reclaimed_nodes=%u\n",result.epe_compact_ok,result.epe_compacted_nodes);
#endif
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
#if EPE
  // EPE may run only after a successful legitimate bestmove. No budget
  // or memory is deducted from the following normal search.
  epe_pending=result.has&&!request_stop&&!request_quit&&connected;
  epe_cancel=false;
  if(epe_pending)epe_our_move=result.move;
  if(epe_report_pending){
   const double hit_pct=epe_last_sims?100.0*result.epe_reused_sims/epe_last_sims:0.0;
   const unsigned saved_ms=epe_last_sims?unsigned(uint64_t(epe_last_ms)*result.epe_reused_sims/epe_last_sims):0u;
   debug_log("EPE REUSE id=%lu source=%lu hit=%u total_sims=%lu reused_sims=%u hit_pct=%.2f saved_ms_est=%u actual_root=%u budget_normal=%u\n",
    (unsigned long)search_id,(unsigned long)epe_last_search,unsigned(result.epe_reused_sims>0),
    (unsigned long)epe_last_sims,result.epe_reused_sims,hit_pct,saved_ms,result.reused_root,config::AZ_SIMULATIONS);
   epe_reused_total+=result.epe_reused_sims;
   epe_discarded_total+=epe_last_sims>result.epe_reused_sims?epe_last_sims-result.epe_reused_sims:0;
   if(result.epe_reused_sims)epe_hits++;
   debug_log("EPE UTIL id=%lu branch_found=%u covered_branches=%u epe_nn=%u epe_terminal=%u epe_new_nodes=%u delta_visits=%u conserved_nodes=%u compact_ok=%u pruned_nodes=%u\n",
    (unsigned long)search_id,result.epe_branch_found,result.epe_covered_branches,result.epe_nn_calls,
    result.epe_terminal,result.epe_created_nodes,result.epe_delta_visits,result.epe_reused_nodes,
    result.epe_compact_ok,result.epe_compacted_nodes);
   epe_report_pending=false;
  }
#endif
  if(!request_quit&&connected){send_line("info move "+std::to_string(board.fullmove)+" nodes "+std::to_string(result.tree_nodes)+" time "+std::to_string(elapsed)+" sims "+std::to_string(result.simulations));send_line("bestmove "+(result.has?Board::notation(result.move):"0000"));}
 }catch(const std::exception& ex){neural.set_progress_hook(nullptr);active_deadline_ms=0;debug_log("SEARCH ID=%lu phase=exception\n",(unsigned long)search_id);debug_log("SEARCH ERROR: %s\n",ex.what());session_error=true;++recoverable_errors;if(connected){send_line(std::string("info string error MCTS ")+ex.what());picoSargon::MoveList fallback;try {board.legal(fallback);} catch(...) {} send_line("bestmove "+(fallback.empty()?std::string("0000"):Board::notation(fallback.front())));}}
 watchdog_hw->scratch[0]=0;
 status_led(session_error?LedState::Recoverable:(wifi_up?LedState::Ready:LedState::NoWiFi));
}

#if EPE
void run_epe(){
 if(!epe_pending||!connected||go_pending||!valid_position)return;
 epe_pending=false;epe_cancel=false;epe_active=true;epe_cancel_requested_ms=0;
 // Single speculative session per bestmove: one existing MCTS arena, never
 // concurrent with normal search. The next position is the cancellation barrier.
 epe_board=board;
 try {epe_board.push(epe_our_move);}catch(...){epe_active=false;return;}
 epe_history=history;epe_history.emplace_back(epe_board);
 const uint64_t begin=millis();
 const unsigned budget=PA_EPE_MAX_MS;
 const uint32_t id=++search_sequence;
 ++epe_cycles;
 status_led(LedState::Thinking);
 active_deadline_ms=begin+budget+500u;
 last_kernel_feed_ms=begin;
 neural.set_progress_hook(progress_checkpoint);
 debug_log("EPE START id=%lu budget_ms=%u max_sims=%u history=%u\n",(unsigned long)id,budget,unsigned(PA_EPE_SIMULATIONS),unsigned(epe_history.size()));
 try{
  const auto r=picoalpha::search(neural,epe_board,epe_history,fen_only,
    PA_EPE_SIMULATIONS,config::AZ_CPUCT,config::AZ_MAX_NODES,budget,millis,
    [](){service();return epe_cancel||go_pending||request_quit||!connected;},progress_checkpoint,true);
#if PA_EPE_CLASSIC_GUIDE
  debug_log("EPE GUIDE id=%lu mode=CLASSIC_LITE candidates=%u topk=%u guide_ms=%u enabled=%u\n",
   (unsigned long)id,r.epe_guide_candidates,r.epe_guide_topk,r.epe_guide_ms,unsigned(r.epe_guide_topk>0));
#else
  debug_log("EPE GUIDE id=%lu mode=PUCT_BASELINE\n",(unsigned long)id);
#endif
  epe_last_sims=r.simulations;epe_last_ms=unsigned(millis()-begin);epe_last_search=id;
  epe_report_pending=epe_last_sims>0;
  if(r.simulations)epe_active_cycles++;else epe_skipped++;
  epe_sims_total+=r.simulations;epe_nn_total+=r.epe_nn_calls;
  const unsigned stop_latency=unsigned(epe_cancel_requested_ms?millis()-epe_cancel_requested_ms:0);
  epe_stop_latency_max=std::max<uint32_t>(epe_stop_latency_max,static_cast<uint32_t>(stop_latency));
  debug_log("EPE STOP id=%lu elapsed_ms=%lu sims=%u nn_calls=%u terminal=%u covered=%u new_nodes=%u nodes=%u reason=%s interrupted=%u stop_latency_ms=%u\n",
   (unsigned long)id,(unsigned long)epe_last_ms,r.simulations,r.epe_nn_calls,r.epe_terminal,r.epe_covered_branches,r.epe_created_nodes,r.tree_nodes,r.reason,unsigned(epe_cancel),stop_latency);
 }catch(const std::exception& ex){
  epe_report_pending=false;++epe_skipped;
  debug_log("EPE STOP id=%lu reason=exception error=%s\n",(unsigned long)id,ex.what());
 }
 neural.set_progress_hook(nullptr);active_deadline_ms=0;
 epe_active=false;
 status_led(wifi_up?LedState::Ready:LedState::NoWiFi);
}
#endif
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
 uint32_t pll_selected_khz = 0;
 // RP2350: buscar la frecuencia realizable mas alta <= la solicitada.
 // La prueba de divisores se efectua antes de modificar el reloj activo.
 // Resolucion de seleccion: 1 kHz, sin redondear hacia arriba.
 if (pll_requested >= 120u && pll_requested <= 250u) {
  const uint32_t desired_khz = pll_requested * 1000u;
  for (uint32_t candidate_khz = desired_khz; candidate_khz >= 120000u; --candidate_khz) {
   uint vco = 0, postdiv1 = 0, postdiv2 = 0;
   if (!check_sys_clock_khz(candidate_khz, &vco, &postdiv1, &postdiv2)) continue;
   if (set_sys_clock_khz(candidate_khz, false)) {
    pll_selected_khz = candidate_khz;
    pll_applied = true;
    break;
   }
  }
 }
 stdio_init_all();
 picoalpha::dual_core_start();
 if constexpr(config::DEBUG){
  while(!stdio_usb_connected())sleep_ms(100);
  sleep_ms(100);
  const bool wd_reset=watchdog_caused_reboot();
  debug_log("%s watchdog(%u) sims(%u) cpuct=%.3f tout=%u nodes max(%u) tree(%u)\n",VERSION,unsigned(wd_reset),config::AZ_SIMULATIONS,double(config::AZ_CPUCT),config::TMAX_MS,config::AZ_MAX_NODES,unsigned(PA_STATIC_TREE_NODES));
  debug_log("BUILD NN=%s (compile-time) EPE=%u\n",NN_NAME,unsigned(EPE));
#if !PA_COMPILED_IS_1X8
  debug_log("BUILD TinyGyal=2x16 source_pb_sha256=e55a27d8c06d0c53dea8e10a8e6ae8a03c7d594ed6413f0d7dd431543314f6c4\n");
#endif
  debug_log("RECOVERY v0.2.66 single_core=%u (0=dual enabled, 1=single-core fallback)\n",unsigned(!PA_DUAL_CORE_NN));
  debug_log("BUILD FLAGS binary=%u int8=%u fc1_prepack=%u dsp=%u dual=%u profile=%u cal=%u mcts=%u mem=%u nn=%u diag=%u clock_request=%u clock_actual_hz=%lu\n",unsigned(PA_BINARY_FIRST_CONV),unsigned(PA_INT8_ACTIVATIONS),unsigned(PA_FC1_PREPACK),unsigned(PA_NN_DSP),unsigned(PA_DUAL_CORE_NN),unsigned(PA_NN_PROFILE),unsigned(PA_CALIBRATION_TELEMETRY),unsigned(PA_TELEM_MCTS),unsigned(PA_TELEM_MEM),unsigned(PA_TELEM_NN),unsigned(PA_DIAGNOSTIC_RUN),config::PLL_SYS,(unsigned long)clock_get_hz(clk_sys));
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
    debug_log("PLL_SYS sin candidato realizable: solicitado=%u MHz, reloj conservado=%lu Hz\n",
              pll_requested, static_cast<unsigned long>(clock_get_hz(clk_sys)));
   } else {
    debug_log("PLL_SYS aplicado: solicitado=%u MHz, seleccionado=%lu.%03lu MHz, clk_sys=%lu Hz, ajuste_khz=%lu\n",
              pll_requested,
              static_cast<unsigned long>(pll_selected_khz / 1000u),
              static_cast<unsigned long>(pll_selected_khz % 1000u),
              static_cast<unsigned long>(clock_get_hz(clk_sys)),
              static_cast<unsigned long>(pll_requested * 1000u - pll_selected_khz));
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
#if EPE
  else if(epe_pending && connected && wifi_up)run_epe();
#endif
  sleep_ms(1);
 }
}
