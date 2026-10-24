#include "mcts.hpp"
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <memory>
#include <vector>
#include <limits>
#include <malloc.h>
#include <unistd.h>
#include <new>
#include <cstdint>
namespace picoalpha {
using namespace picoSargon;
// 20 bytes instead of 28. 8576 nodes fit the former 172 KiB budget.
// uint16 indices suffice for <=8576 arena entries; uint16 visits suffice for 128 simulations.
struct Node {float p=1,qsum=0;uint16_t visits=0,first=0,next=0;uint8_t count=0,flags=0;Move move{};};
static constexpr uint8_t NODE_EXPANDED=1, NODE_BLOCKED=2;
static constexpr unsigned INITIAL_CHILDREN=4, WIDEN_VISITS_PER_CHILD=8;
static_assert(sizeof(Node)==20,"MCTS compact Node must be 20 bytes");
// Restored conservative admission rule: v0.2.14 accepted aggregate fordblks
// as though it were a contiguous allocatable block. That is not guaranteed.
// Do not change this guard until growth is converted to segmented storage.
static constexpr uintptr_t STACK_GUARD = 48u * 1024u;
static bool has_growth_room(size_t new_allocation_bytes) {
#if defined(__arm__) || defined(__thumb__)
 char stack_mark;
 void* brk = sbrk(0);
 if (brk == reinterpret_cast<void*>(-1)) return false;
 const uintptr_t stack = reinterpret_cast<uintptr_t>(&stack_mark);
 const uintptr_t heap = reinterpret_cast<uintptr_t>(brk);
 if (stack <= heap || stack - heap <= STACK_GUARD) return false;
 const size_t gap = stack - heap - STACK_GUARD;
 return new_allocation_bytes <= (gap * 9u) / 10u;
#else
 (void)new_allocation_bytes; return true;
#endif
}
// PA_SEGMENTED_TREE_BEGIN: reversible node store, no monolithic vector::reserve.
#ifndef PA_SEGMENTED_TREE
#error "PA_SEGMENTED_TREE must be provided by CMake v0.2.20: old build path detected"
#endif
#if PA_SEGMENTED_TREE
#ifndef PA_BUILD_SEGMENTED_CONFIRMED
#error "Segmented storage not confirmed by current CMake target"
#endif
#else
#ifndef PA_BUILD_ALLOW_LEGACY
#error "Legacy MCTS requires explicit -DPA_LEGACY_MCTS_TREE=ON"
#endif
#endif
#if PA_SEGMENTED_TREE
// v0.2.28: One fixed SRAM arena for the only active MCTS search.
// No malloc, new or vector growth for nodes, ever. 8576*20 = 171520 B.
// Sequential UCI search only: no simultaneous Tree instances.
#ifndef PA_STATIC_TREE_NODES
#define PA_STATIC_TREE_NODES 8576
#endif
static_assert(PA_STATIC_TREE_NODES>=128, "MCTS arena too small");
static Node s_node_arena[PA_STATIC_TREE_NODES];
// Exactly one UCI search executes at a time. This persistent scratch buffer
// removes the 28 KiB automatic tensor from the recursive traverse() call.
static std::array<float,112*64> s_encode_planes{};

struct NodeStore {
 static constexpr size_t BLOCK=128;
 size_t used=0;
 size_t size() const {return used;}
 size_t capacity() const {return PA_STATIC_TREE_NODES;}
 Node& operator[](size_t i){return s_node_arena[i];}
 const Node& operator[](size_t i) const {return s_node_arena[i];}
 void emplace_back(){s_node_arena[used++]=Node{};}
 void push_back(const Node& n){s_node_arena[used++]=n;}
 bool add_block(){return false;}
};
#else
struct NodeStore : std::vector<Node> {
 bool add_block(){return false;}
};
#endif
// PA_SEGMENTED_TREE_END
// Search board constructed at startup, not on the first go.
static Board s_search_board;
static Board s_last_root_board;
#ifndef PA_MCTS_REUSE
#define PA_MCTS_REUSE 1
#endif
#if PA_MCTS_REUSE && PA_SEGMENTED_TREE && PA_COMPACT_HISTORY
// This retains verified grandchildren of the previous root. Nodes are never
// moved while referenced: if capacity runs low the next search restarts cleanly.
// No heap, no extra 172 KiB tree copy, no cross-game reuse.
static SearchHistory s_previous_history{};
static picoSargon::Move s_previous_best{};
static size_t s_previous_used=0;
static uint16_t s_previous_root=0;
static bool s_previous_valid=false;
static bool history_matches(const SearchHistory& now){
 if(!s_previous_valid || now.size()!=s_previous_history.size()+2)return false;
 for(size_t i=0;i<s_previous_history.size();++i){
  const auto& a=now[i];const auto& b=s_previous_history[i];
  if(a.packed!=b.packed||a.turn!=b.turn||a.castling!=b.castling||
     a.halfmove!=b.halfmove||a.repeated!=b.repeated)return false;
 }
 return true;
}
#endif
// PA22_TRAVERSE_GUARDS_BEGIN
struct TraverseAbort { const char* reason; };
struct NoMemoryExpansion {};
static constexpr int MAX_TRAVERSE_DEPTH=48;
struct Tree {
 NowFn now=nullptr; PumpFn pump=nullptr; ProgressFn progress=nullptr; uint64_t deadline=0,last_service=0;
 uint32_t guard_depth=0,guard_cycle=0,guard_index=0,guard_timeout=0,guard_stop=0;
 uint32_t max_depth_seen=0,visit_checks=0,service_calls=0;
 uint32_t rejected_expansions=0,aborted_simulations=0,blocked_branches=0,terminal_backups=0,nonfinite_values=0,invalid_priors=0;
 int ancestors[MAX_TRAVERSE_DEPTH]{};
 void checkpoint(int idx,int depth){
  ++visit_checks;
  if(depth>int(max_depth_seen))max_depth_seen=unsigned(depth);
  if(depth>=MAX_TRAVERSE_DEPTH){++guard_depth;throw TraverseAbort{"depth_limit"};}
  if(idx<0 || size_t(idx)>=nodes.size()){++guard_index;throw TraverseAbort{"bad_index"};}
  for(int k=0;k<depth;++k)if(ancestors[k]==idx){++guard_cycle;throw TraverseAbort{"cycle"};}
  ancestors[depth]=idx;
  const uint64_t t=now?now():0;
  if(deadline && t>=deadline){++guard_timeout;throw TraverseAbort{"timeout_inner"};}
  if(pump && (!last_service || t-last_service>=100u)){
    last_service=t;++service_calls;
    if(pump()){++guard_stop;throw TraverseAbort{"interrupted_inner"};}
  }
 }
// PA22_TRAVERSE_GUARDS_END
 const Network& net;NodeStore nodes;unsigned capacity;float cpuct;bool capped=false;bool memory_limited=false;unsigned pool_target=0,pool_reserved=0,pool_preflight_denied=0;unsigned growth_events=0;unsigned growth_attempts=0,growth_denied=0,growth_alloc_failed=0;unsigned growth_last_from=0,growth_last_to=0;unsigned growth_request_bytes=0;
 int root_idx=0;
 Tree(const Network& n,unsigned cap,float c,int reuse_idx=-1,size_t reuse_used=0):net(n),capacity(0),cpuct(c){
  const unsigned initial=std::max(128u,cap);
#if PA_SEGMENTED_TREE
  // Tree nodes live in static SRAM. Do not touch heap in constructor.
  (void)initial;
#else
  if(!has_growth_room(size_t(initial)*sizeof(Node))) throw std::bad_alloc();
  nodes.reserve(initial);
#endif
  // All nodes pre-exist in the static arena; capacity cannot expand.
  pool_target=unsigned(nodes.capacity());
  capacity=unsigned(nodes.capacity());pool_reserved=capacity;
  if(reuse_idx>=0 && reuse_used<=nodes.capacity() && size_t(reuse_idx)<reuse_used){
   nodes.used=reuse_used;root_idx=reuse_idx;
  }else nodes.emplace_back();
 }
 bool ensure(size_t required){
  if(required<=nodes.capacity()) return true;
  ++growth_attempts;growth_last_from=unsigned(nodes.capacity());
  growth_last_to=unsigned(nodes.capacity());growth_request_bytes=0;
#if PA_SEGMENTED_TREE
  ++growth_denied;memory_limited=true;return false;
#else
  const size_t next=std::max(required,nodes.capacity()+512u);
  growth_last_to=unsigned(next);growth_request_bytes=unsigned(next*sizeof(Node)+4096u);
  if(next>size_t(UINT32_MAX)/sizeof(Node)||!has_growth_room(next*sizeof(Node)+4096u)){
   memory_limited=true;++growth_denied;return false;
  }
  try{nodes.reserve(next);}catch(const std::bad_alloc&){memory_limited=true;++growth_alloc_failed;return false;}
  capacity=unsigned(nodes.capacity());++growth_events;return true;
#endif
 }
 float traverse(int idx,Board& b,SearchHistory& h,bool fen_only,int depth){
  checkpoint(idx,depth);
  // Determine legal termination before draw to preserve checkmate precedence.
  // Numeric indices remain stable across vector reallocation.
  if(!(nodes[idx].flags & NODE_EXPANDED)){
   if(progress)progress(2,unsigned(depth));
   static MoveList legal;b.legal(legal);
   if(progress)progress(3,unsigned(legal.size()));
   if(legal.empty()){nodes[idx].flags|=NODE_EXPANDED;float v=b.in_check()?-1.f:0.f; nodes[idx].visits++;nodes[idx].qsum+=v;++terminal_backups;return v;}
   if(b.draw()){nodes[idx].flags|=NODE_EXPANDED;nodes[idx].visits++;++terminal_backups;return 0.f;}
   if(progress)progress(4,unsigned(nodes.size()));
   if(!ensure(nodes.size()+std::min<size_t>(legal.size(),INITIAL_CHILDREN))){nodes[idx].flags|=NODE_BLOCKED;++rejected_expansions;++blocked_branches;throw NoMemoryExpansion{};}
   // PA21_POLICY_SELECT_BEGIN: no 4672-output policy allocation for MCTS.
   static FixedVector<int,256> policy_slots;policy_slots.clear();
   for(const auto& move:legal)policy_slots.push_back(policy_index(b,move));
   if(progress)progress(5,unsigned(depth));
   if(progress)progress(19,unsigned(depth));
#if PA_SEGMENTED_TREE
   encode_into(h,fen_only,s_encode_planes);
   if(progress)progress(20,unsigned(depth));
   auto result=net.evaluate_legal(s_encode_planes,policy_slots);
#else
   auto result=net.evaluate_legal(encode(h,fen_only),policy_slots);
#endif
   if(progress)progress(6,unsigned(depth));
   static FixedVector<float,256> prob;prob.clear();float high=-1e30f;
   if(result.count!=legal.size())throw TraverseAbort{"policy_size_mismatch"};
   for(size_t pi=0;pi<result.count;++pi){float v=result.policy[pi];prob.push_back(v);high=std::max(high,v);}
   // PA21_POLICY_SELECT_END
   if(!std::isfinite(result.q)){++nonfinite_values;throw TraverseAbort{"nonfinite_value"};}
   for(float v:prob)if(!std::isfinite(v)){++invalid_priors;throw TraverseAbort{"nonfinite_policy"};}
   float total=0;for(auto& v:prob){v=std::exp(v-high);total+=v;}
   if(!(total>0) || !std::isfinite(total))throw std::runtime_error("softmax invalid");
   // Progressive widening: allocate only top-prior edges initially.
   // Remaining legal moves are recomputed only when the node earns more visits.
   const size_t limit=std::min<size_t>(legal.size(),INITIAL_CHILDREN);
   uint16_t prev=0;
   for(size_t k=0;k<limit;++k){
    size_t chosen=legal.size();float highest=-1.f;
    for(size_t i=0;i<legal.size();++i){
     bool exists=false;for(uint16_t j=nodes[idx].first;j!=0;j=nodes[j].next)if(nodes[j].move==legal[i]){exists=true;break;}
     if(!exists && prob[i]>highest){highest=prob[i];chosen=i;}
    }
    if(chosen==legal.size())break;
    const uint16_t at=uint16_t(nodes.size());Node child;child.move=legal[chosen];child.p=prob[chosen]/total;nodes.push_back(child);
    if(prev)nodes[prev].next=at;else nodes[idx].first=at;
    prev=at;++nodes[idx].count;
   }
   nodes[idx].flags|=NODE_EXPANDED;
   nodes[idx].visits++;nodes[idx].qsum+=result.q;return result.q;
  }
  if(nodes[idx].count==0){float v=nodes[idx].qsum<0.f?-1.f:0.f; nodes[idx].visits++;nodes[idx].qsum+=v;++terminal_backups;return v;}
  // Progressive widening at visits 8,16,...; never discard a legal move permanently.
  // Re-evaluation is infrequent and uses the same input/policy as first expansion.
  if(nodes[idx].count < 255 && nodes[idx].visits >= uint32_t(nodes[idx].count)*WIDEN_VISITS_PER_CHILD){
   static MoveList candidates;b.legal(candidates);
   if(candidates.size()>nodes[idx].count){
    if(!ensure(nodes.size()+1)){nodes[idx].flags|=NODE_BLOCKED;++rejected_expansions;++blocked_branches;throw NoMemoryExpansion{};}
    static FixedVector<int,256> slots;slots.clear();for(const auto& m:candidates)slots.push_back(policy_index(b,m));
#if PA_SEGMENTED_TREE
    encode_into(h,fen_only,s_encode_planes);
    auto prediction=net.evaluate_legal(s_encode_planes,slots);
#else
    auto prediction=net.evaluate_legal(encode(h,fen_only),slots);
#endif
    if(prediction.count!=candidates.size())throw TraverseAbort{"policy_size_mismatch"};
    float mx=-1e30f;for(size_t k=0;k<prediction.count;++k){if(!std::isfinite(prediction.policy[k]))throw TraverseAbort{"nonfinite_policy"};mx=std::max(mx,prediction.policy[k]);}
    float sum=0.f;for(size_t k=0;k<prediction.count;++k)sum+=std::exp(prediction.policy[k]-mx);
    if(!(sum>0.f)||!std::isfinite(sum))throw TraverseAbort{"nonfinite_policy"};
    size_t chosen=candidates.size();float high=-1e30f;
    for(size_t k=0;k<candidates.size();++k){
     bool present=false;for(uint16_t j=nodes[idx].first;j;j=nodes[j].next)if(nodes[j].move==candidates[k]){present=true;break;}
     if(!present && prediction.policy[k]>high){high=prediction.policy[k];chosen=k;}
    }
    if(chosen<candidates.size()){
     const uint16_t at=uint16_t(nodes.size());Node child;child.move=candidates[chosen];child.p=std::exp(high-mx)/sum;nodes.push_back(child);
     uint16_t last=nodes[idx].first;while(nodes[last].next)last=nodes[last].next;
     nodes[last].next=at;++nodes[idx].count;
    }
   }
  }
  // An expanded nonterminal node was already checked for draw when expanded.
  int best=-1;float best_score=-1e30f;float n=std::sqrt(float(std::max<uint32_t>(1, nodes[idx].visits)));
  for(uint16_t j=nodes[idx].first;j!=0;j=nodes[j].next){if(j<0 || size_t(j)>=nodes.size()){++guard_index;throw TraverseAbort{"bad_child_index"};}const auto& child=nodes[j];if((child.flags & NODE_BLOCKED))continue;float q=child.visits?child.qsum/child.visits:0;float u=cpuct*child.p*n/(1+child.visits);float score=-q+u;if(score>best_score){best_score=score;best=j;}}
  if(best<0){if(!(nodes[idx].flags & NODE_BLOCKED)){nodes[idx].flags|=NODE_BLOCKED;++blocked_branches;}throw NoMemoryExpansion{};}
  if(progress)progress(7,unsigned(depth));
  b.push(nodes[best].move);
  float value;
  bool history_pushed=false;
  try {
   // PA_COMPACT_HISTORY_BEGIN: push one compact snapshot, not a Board copy.
#if PA_COMPACT_HISTORY
   h.emplace_back(b);
#else
   h.push_back(b);
#endif
   history_pushed=true; // PA_COMPACT_HISTORY_END
   value=-traverse(best,b,h,fen_only,depth+1);
  } catch (...) {
   if(history_pushed)h.pop_back();
   b.pop();
   throw;
  }
  h.pop_back();b.pop();
  if(progress)progress(8,unsigned(depth));
  nodes[idx].visits++;nodes[idx].qsum+=value;return value;
 }
};
SearchResult search(const Network& net,const Board& source_board,const SearchHistory& history,bool fen_only,unsigned simulations,float cpuct,unsigned max_nodes,unsigned timeout_ms,NowFn now,PumpFn pump,ProgressFn progress){
 SearchResult out;
 Board& board=s_search_board; board=source_board;
 static SearchHistory h;h=history;
 static MoveList root_legal;board.legal(root_legal);
 if(root_legal.empty()){out.reason=board.in_check()?"checkmate":"stalemate";return out;}
 if(board.draw()){out.reason="draw";return out;}
 int reuse_idx=-1;
#if PA_MCTS_REUSE && PA_SEGMENTED_TREE && PA_COMPACT_HISTORY
 if(history_matches(history) && s_previous_used+4096<PA_STATIC_TREE_NODES){
  const auto& root=s_node_arena[s_previous_root];
  if((root.flags & NODE_EXPANDED) && root.count){
   int played=-1;
   for(int i=0;i<root.count;++i){int j=int(root.first); for(int skip=0;skip<i;++skip)j=int(s_node_arena[j].next);
    if(j<int(s_previous_used) && s_node_arena[j].move==s_previous_best){played=j;break;}}
   if(played>=0){
    const auto& p=s_node_arena[played];
    if((p.flags & NODE_EXPANDED) && p.count){
     // Match the actual final position by replaying each previous opponent edge.
     // The prefix check above protects history-dependent network input.
     // Replay on the single retained base Board, push/pop each candidate;
     // avoid an additional 26 KiB static Board just for continuation matching.
     if(s_last_root_board.history_length()+2<256){
      s_last_root_board.push(s_previous_best);
      for(int k=0;k<p.count;++k){int j=int(p.first);for(int skip=0;skip<k;++skip)j=int(s_node_arena[j].next);
       if(j>=int(s_previous_used))break;
       s_last_root_board.push(s_node_arena[j].move);
       const bool match=s_last_root_board.position_key()==source_board.position_key() &&
         s_last_root_board.halfmove==source_board.halfmove;
       s_last_root_board.pop();
       if(match){reuse_idx=j;break;}
      }
      s_last_root_board.pop();
     }
    }
   }
  }
 }
#endif
 Tree t(net,std::max(128u,max_nodes),cpuct,reuse_idx,
#if PA_MCTS_REUSE && PA_SEGMENTED_TREE && PA_COMPACT_HISTORY
  reuse_idx>=0?s_previous_used:0
#else
  0
#endif
 );
 if(reuse_idx>=0){out.reused_root=unsigned(reuse_idx);out.reused_prior_nodes=unsigned(t.nodes.size());}
 uint64_t begin=now();t.now=now;t.pump=pump;t.progress=progress;t.deadline=timeout_ms?begin+timeout_ms:0;
 // mallinfo: heap del asignador C/C++; no mide pila, reservas estaticas ni todos los pools lwIP.
 auto sample_heap=[&](){
  const auto mi=mallinfo();
  const unsigned used=mi.uordblks>0?unsigned(mi.uordblks):0u;
  const unsigned avail=mi.fordblks>0?unsigned(mi.fordblks):0u;
  const unsigned arena=mi.arena>0?unsigned(mi.arena):0u;
  out.heap_used_peak=std::max(out.heap_used_peak,used);
  out.heap_arena_peak=std::max(out.heap_arena_peak,arena);
  if(!out.heap_free_min || avail<out.heap_free_min)out.heap_free_min=avail;
 };
 sample_heap();
 for(unsigned i=0;i<simulations;++i){
  if(pump&&pump()){out.reason="interrupted";break;}
  if(timeout_ms&&now()-begin>=timeout_ms){out.reason="timeout";break;}
  if(t.capped){out.reason=t.memory_limited?"tree_full":"tree_limit";break;}
  if(progress)progress(1,i);
  try {t.traverse(t.root_idx,board,h,fen_only,0);out.simulations++;}
  catch(const NoMemoryExpansion&){++t.aborted_simulations; out.reason="tree_full";break;}
  catch(const std::bad_alloc&){out.reason="allocation_error";break;}
  catch(const TraverseAbort& e){out.reason=e.reason;break;}
  catch(const std::exception&){out.reason="exception_inner";break;}
  sample_heap();
 }
 sample_heap();
 out.guard_depth=t.guard_depth;out.guard_cycle=t.guard_cycle;out.guard_index=t.guard_index;
 out.guard_timeout=t.guard_timeout;out.guard_stop=t.guard_stop;out.max_depth=t.max_depth_seen;
 out.traverse_checks=t.visit_checks;out.inner_service_calls=t.service_calls;
 out.rejected_expansions=t.rejected_expansions;out.aborted_simulations=t.aborted_simulations;out.blocked_branches=t.blocked_branches;out.terminal_backups=t.terminal_backups;out.nonfinite_values=t.nonfinite_values;out.invalid_priors=t.invalid_priors;
 out.pool_target=t.pool_target;out.pool_reserved=t.pool_reserved;out.pool_preflight_denied=t.pool_preflight_denied;
 out.node_bytes=unsigned(sizeof(Node));
 out.tree_nodes=unsigned(t.nodes.size());out.tree_capacity=unsigned(t.nodes.capacity());out.growth_events=t.growth_events;out.growth_attempts=t.growth_attempts;out.growth_denied=t.growth_denied;out.growth_alloc_failed=t.growth_alloc_failed;out.growth_last_from=t.growth_last_from;out.growth_last_to=t.growth_last_to;out.growth_request_bytes=t.growth_request_bytes;out.history_entries=unsigned(h.size());out.board_size_bytes=unsigned(sizeof(Board));out.history_element_bytes=unsigned(sizeof(SearchHistory::value_type));out.history_bytes=unsigned(h.capacity()*sizeof(SearchHistory::value_type));
 int best=-1;
 for(uint16_t j=t.nodes[t.root_idx].first;j!=0;j=t.nodes[j].next){if(j<0||size_t(j)>=t.nodes.size()){++out.guard_index;break;}if(best<0||t.nodes[j].visits>t.nodes[best].visits)best=j;}
 if(best>=0){const Node& n=t.nodes[best];out.move=n.move;out.has=true;out.q=n.visits?-n.qsum/n.visits:0;}
 else if(!root_legal.empty()){out.move=root_legal.front();out.has=true;if(out.reason==std::string("complete"))out.reason="no_root_expansion";}
#if PA_MCTS_REUSE && PA_SEGMENTED_TREE && PA_COMPACT_HISTORY
 // Persist only when a legal move was selected and sufficient nodes remain.
 s_previous_valid=out.has && t.nodes.size()+4096<t.nodes.capacity();
 if(s_previous_valid){
  s_previous_used=t.nodes.size();s_previous_root=uint16_t(t.root_idx);
  s_previous_history=history;s_previous_best=out.move;s_last_root_board=source_board;
 }
#endif
 return out;
}
}
