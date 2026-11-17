#pragma once
#include "mcts_arm.hpp"
namespace picoalpha_arm {
struct CombinedResult {
  picoSargon::Move best{};bool valid=false;
  uint32_t simulations=0,nodes=0,max_depth=0,elapsed_ms=0;
  uint32_t core_sims[2]{},core_nodes[2]{},core_ms[2]{},core_depth[2]{};
  uint32_t pool_failures=0,root_visits=0;
  uint32_t core1_stack_untouched=0;
  float score_value=0,root_value=0;
  const char* reason="unstarted";
};
struct SearchProgress {uint32_t simulations[2]{},depth[2]{};};
SearchProgress get_search_progress();
void init_cores();
bool core1_ready();
CombinedResult run_search(const picoSargon::Board& board,uint32_t max_sims,
  int max_depth,uint32_t timeout_ms,float cpuct,
  const std::atomic<bool>& stop,void(*service)());
}
