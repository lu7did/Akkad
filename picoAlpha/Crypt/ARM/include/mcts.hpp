#pragma once
#include "net.hpp"
#include <cstdint>
#include <type_traits>
namespace picoalpha {
struct SearchResult {picoSargon::Move move{};bool has=false;unsigned simulations=0;unsigned pool_target=0,pool_reserved=0,pool_preflight_denied=0;unsigned tree_nodes=0;unsigned tree_capacity=0;unsigned reused_prior_nodes=0,reused_root=0;unsigned epe_guide_ms=0,epe_guide_candidates=0,epe_guide_topk=0;unsigned epe_reused_sims=0,epe_total_sims=0,epe_total_ms=0,epe_reused_nodes=0,epe_nn_calls=0,epe_terminal=0,epe_created_nodes=0,epe_covered_branches=0,epe_delta_visits=0,epe_branch_found=0,epe_compacted_nodes=0,epe_compact_ok=0;unsigned growth_events=0;unsigned growth_attempts=0,growth_denied=0,growth_alloc_failed=0;unsigned growth_last_from=0,growth_last_to=0,growth_request_bytes=0;unsigned history_entries=0,board_size_bytes=0;unsigned history_bytes=0,history_element_bytes=0;unsigned node_bytes=0;unsigned guard_depth=0,guard_cycle=0,guard_index=0,guard_timeout=0,guard_stop=0,max_depth=0,traverse_checks=0,inner_service_calls=0;unsigned rejected_expansions=0,aborted_simulations=0,blocked_branches=0,terminal_backups=0,nonfinite_values=0,invalid_priors=0;unsigned heap_used_peak=0;unsigned heap_free_min=0;unsigned heap_arena_peak=0;float q=0;const char* reason="complete";};
using SearchHistory = std::conditional_t<(PA_COMPACT_HISTORY != 0),CompactHistory,std::vector<picoSargon::Board>>;
using NowFn=uint64_t(*)();
using PumpFn=bool(*)();
using ProgressFn=void(*)(uint32_t,uint32_t);
SearchResult search(const Network& net,const picoSargon::Board& board,const SearchHistory& history,bool fen_only,unsigned simulations,float cpuct,unsigned max_nodes,unsigned timeout_ms,NowFn now,PumpFn pump,ProgressFn progress=nullptr,bool speculative=false);
}
