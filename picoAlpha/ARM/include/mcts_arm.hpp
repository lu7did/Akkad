#pragma once
#include "board.hpp"
#include "config.h"
#include <atomic>
#include <cstdint>
#include <vector>
namespace picoalpha_arm {
struct SearchReport {
  picoSargon::Move best{};bool valid=false;
  uint32_t simulations=0,nodes=0,visits=0,max_depth=0,time_ms=0;
  uint32_t root_moves=0,alloc_failures=0;
  float root_value=0,estimated_value=0;
  const char* reason="unstarted";
};
struct RootStat {uint32_t visits=0;float value_sum=0,prior=0;};
struct MCTSNode {
  picoSargon::Move move{};
  int16_t first=-1,next=-1;
  uint32_t visits=0;
  float value_sum=0,prior=0;
  uint8_t expanded=0;
};
class SearchWorker {
public:
  explicit SearchWorker(MCTSNode* nodes,uint32_t limit);
  void reserve(int depth);
  // Callback invoked by core0 to service TCP/WiFi/watchdog during search.
  SearchReport run(const picoSargon::Board& position,uint32_t simulations,int depth,
                   uint32_t deadline_ms,float cpuct,const std::atomic<bool>& stop,
                   uint32_t(*now)(),void(*service)());
  uint32_t progress_simulations() const {return progress_sims_.load(std::memory_order_relaxed);}
  uint32_t progress_depth() const {return progress_depth_.load(std::memory_order_relaxed);}
  void extract(RootStat* out,int root_count)const;
  void clear();
private:
  MCTSNode* pool_;
  uint32_t cap_,used_=0;
  std::atomic<uint32_t> progress_sims_{0},progress_depth_{0};
  picoSargon::Board board_;
  std::vector<picoSargon::Move> legal_;
  picoSargon::Move root_moves_[256]{};
  float priors_[256]{};
  int root_count_=0;
  bool append_children(int parent,const picoSargon::Move* moves,const float* priors,int count);
};
}
