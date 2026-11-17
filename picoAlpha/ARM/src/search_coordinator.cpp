#include "search_coordinator.hpp"
#include "pico/multicore.h"
#include "pico/stdlib.h"
#include <algorithm>
#include <atomic>
#include <cstring>
#include <cmath>
namespace picoalpha_arm {
namespace {
using namespace picoalpha_config;
static_assert(NODE_POOL_PER_CORE<=32767,"Node indices use int16_t");
static_assert(MAX_DEPTH<=90,"Trail buffer max 96");
// STATIC allocation: two independent pools. Never allocate nodes during simulation.
alignas(8) MCTSNode nodes0[NODE_POOL_PER_CORE];
alignas(8) MCTSNode nodes1[NODE_POOL_PER_CORE];
static_assert(CORE1_STACK_BYTES % sizeof(uint32_t)==0,"Core1 stack must be word aligned");
alignas(8) uint32_t stack1[CORE1_STACK_BYTES/sizeof(uint32_t)];
SearchWorker worker0(nodes0,NODE_POOL_PER_CORE),worker1(nodes1,NODE_POOL_PER_CORE);
std::atomic<bool> ready{false};
std::atomic<unsigned> command{0}; // 0 idle,1 new job,2 complete
std::atomic<bool> shared_stop{false};
picoSargon::Board job_board;
uint32_t job_sims=0,job_deadline=0;
int job_depth=0;
float job_cpuct=1.4f;
SearchReport result1;
RootStat stats1[256]{};
uint32_t stack_untouched_report=0;
uint32_t ms(){return to_ms_since_boot(get_absolute_time());}
void core1_entry(){
 worker1.reserve(MAX_DEPTH);
 ready.store(true,std::memory_order_release);
 for(;;){
  if(command.load(std::memory_order_acquire)!=1){tight_loop_contents();continue;}
  try {
   result1=worker1.run(job_board,job_sims,job_depth,job_deadline,job_cpuct,shared_stop,ms,nullptr);
   worker1.extract(stats1,int(result1.root_moves));worker1.clear();
  }catch(...){
   result1=SearchReport{};result1.reason="core1-exception";
   for(auto& st:stats1)st=RootStat{};
   worker1.clear();
  }
  // Scan stack watermark on its owning core before publishing result.
  const volatile uint8_t* mem=reinterpret_cast<volatile const uint8_t*>(stack1);
  uint32_t untouched=0;
  while(untouched<sizeof(stack1) && mem[untouched]==0xA5)++untouched;
  stack_untouched_report=untouched;
  command.store(2,std::memory_order_release);
 }
}
}
void init_cores(){
 worker0.reserve(MAX_DEPTH);
 if constexpr (TWO_CORES){
  std::memset(stack1,0xA5,sizeof(stack1));
  multicore_launch_core1_with_stack(core1_entry,stack1,sizeof(stack1));
 }
}
bool core1_ready(){return ready.load(std::memory_order_acquire);}
SearchProgress get_search_progress(){
 SearchProgress p;
 p.simulations[0]=worker0.progress_simulations();
 p.simulations[1]=worker1.progress_simulations();
 p.depth[0]=worker0.progress_depth();
 p.depth[1]=worker1.progress_depth();
 return p;
}
CombinedResult run_search(const picoSargon::Board& board,uint32_t max_sims,
   int depth,uint32_t timeout_ms,float cpuct,const std::atomic<bool>& stop,void(*service)()){
 CombinedResult out;uint32_t start=ms();
 if(TWO_CORES&&!core1_ready()){out.reason="core1-not-ready";return out;}
 if(max_sims<1||timeout_ms<1||depth<1||depth>MAX_DEPTH){out.reason="invalid-parameters";return out;}
 // A single absolute deadline, independent per-core budgets, results joined after completion.
 uint32_t deadline=start+timeout_ms;
 uint32_t target0=(max_sims+1)/2,target1=max_sims/2;
 shared_stop.store(false,std::memory_order_release);
 if(TWO_CORES){
  job_board=board;job_board.reserve_search(depth+32);
  job_sims=target1;job_depth=depth;job_deadline=deadline;job_cpuct=cpuct*CORE1_PUCT_MULTIPLIER;
  for(auto& st:stats1)st=RootStat{};
  command.store(1,std::memory_order_release);
 }else target0=max_sims;
 SearchReport a;
 try { a=worker0.run(board,target0,depth,deadline,cpuct,stop,ms,service); }
 catch(...){
   a=SearchReport{};a.reason="core0-exception";
   shared_stop.store(true,std::memory_order_release);
 }
 RootStat stats0[256]{};worker0.extract(stats0,int(a.root_moves));worker0.clear();
 if(TWO_CORES){
  while(command.load(std::memory_order_acquire)!=2){
   if(service)service();
   if(stop.load(std::memory_order_acquire)||int32_t(deadline-ms())<=0)shared_stop.store(true,std::memory_order_release);
   tight_loop_contents();
  }
  command.store(0,std::memory_order_release);
 }
 const SearchReport& b=TWO_CORES?result1:a;
 out.core_sims[0]=a.simulations;out.core_nodes[0]=a.nodes;
 out.core_depth[0]=a.max_depth;out.core_ms[0]=a.time_ms;
 if(TWO_CORES){out.core_sims[1]=b.simulations;out.core_nodes[1]=b.nodes;
   out.core_depth[1]=b.max_depth;out.core_ms[1]=b.time_ms;}
 out.simulations=a.simulations+(TWO_CORES?b.simulations:0);
 out.nodes=a.nodes+(TWO_CORES?b.nodes:0);
 out.max_depth=std::max(a.max_depth,TWO_CORES?b.max_depth:uint32_t{0});
 out.pool_failures=a.alloc_failures+(TWO_CORES?b.alloc_failures:0u);
 out.elapsed_ms=ms()-start;
 if(TWO_CORES)out.core1_stack_untouched=stack_untouched_report;
 out.root_value=a.root_value;
 int best=-1;uint32_t most=0;float prior=-1;
 for(unsigned i=0;i<a.root_moves;++i){
  uint32_t v=stats0[i].visits+(TWO_CORES?stats1[i].visits:0);
  float p=stats0[i].prior;
  if(best<0||v>most||(v==most&&p>prior)){best=int(i);most=v;prior=p;}
 }
 if(best>=0){
   picoSargon::Board copy=board;
   std::vector<picoSargon::Move> legal;
   legal.reserve(256);copy.legal(legal);
   if(best<int(legal.size())){
     out.best=legal[size_t(best)];out.valid=true;out.root_visits=most;
     const float child_sum=stats0[best].value_sum+(TWO_CORES?stats1[best].value_sum:0.0f);
     out.score_value=most? -child_sum/float(most):out.root_value;
   }
 }
 out.reason=(a.reason&&std::strcmp(a.reason,"core0-exception")==0)?"core0-exception":
    (TWO_CORES && b.reason && std::strcmp(b.reason,"core1-exception")==0)?"core1-exception":
    stop.load()?"stop":(int32_t(deadline-ms())<=0?"timeout":"simulations");
 return out;
}
}
