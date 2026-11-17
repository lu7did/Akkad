#include "mcts_arm.hpp"
#include "nnue_int8.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
namespace picoalpha_arm {
SearchWorker::SearchWorker(MCTSNode* nodes,uint32_t limit):pool_(nodes),cap_(limit){legal_.reserve(256);board_.reserve_search(64);}
void SearchWorker::reserve(int depth){board_.reserve_search(depth+32);legal_.reserve(256);}
void SearchWorker::clear(){
 // Explicitly clear every used node including stale sibling links/priors/visits.
 for(uint32_t k=0;k<used_;++k)pool_[k]=MCTSNode{};
 used_=0;root_count_=0;legal_.clear();board_.clear_scratch();
 for(auto& m:root_moves_)m=picoSargon::Move{};
 std::memset(priors_,0,sizeof(priors_));
}
bool SearchWorker::append_children(int parent,const picoSargon::Move* moves,const float* priors,int count){
 if(count<0||used_+uint32_t(count)>cap_)return false;
 int prev=-1;
 for(int i=0;i<count;++i){int idx=int(used_++);pool_[idx]=MCTSNode{};
   pool_[idx].move=moves[i];pool_[idx].prior=priors[i];
   if(prev<0)pool_[parent].first=int16_t(idx);else pool_[prev].next=int16_t(idx);
   prev=idx;
 }
 pool_[parent].expanded=1;return true;
}
SearchReport SearchWorker::run(const picoSargon::Board& position,uint32_t sims,int depth,uint32_t deadline,float cpuct,
  const std::atomic<bool>& stop,uint32_t(*now)(),void(*service)()){
 clear();progress_sims_.store(0,std::memory_order_relaxed);progress_depth_.store(0,std::memory_order_relaxed);
 board_=position;board_.reserve_search(depth+32);
 SearchReport r;r.reason="simulations";
 pool_[0]=MCTSNode{};used_=1;
 legal_.clear();board_.legal(legal_);
 root_count_=int(legal_.size());r.root_moves=root_count_;
 if(root_count_==0){r.reason="terminal";return r;}
 if(root_count_>256){r.reason="legal-overflow";return r;}
 for(int i=0;i<root_count_;++i)root_moves_[i]=legal_[i];
 NNUE::evaluate_policy(board_,root_moves_,root_count_,priors_,&r.root_value);
 if(!append_children(0,root_moves_,priors_,root_count_)){r.reason="pool-exhausted";return r;}
 const uint32_t start=now();
 for(uint32_t k=0;k<sims;++k){
   if(service)service();
   if(stop.load(std::memory_order_acquire)){r.reason="stop";break;}
   if(int32_t(deadline-now())<=0){r.reason="timeout";break;}
   int trail[96],ntrail=1, node=0, level=0;trail[0]=0;bool aborted=false;
   while(pool_[node].expanded&&pool_[node].first>=0&&level<depth){
     if(stop.load(std::memory_order_relaxed)||int32_t(deadline-now())<=0){aborted=true;break;}
     int chosen=-1;float best=-1e30f;
     float parent_sqrt=sqrtf(float(std::max(uint32_t{1},pool_[node].visits)));
     for(int c=pool_[node].first;c>=0;c=pool_[c].next){
       const auto& x=pool_[c];
       float q=x.visits? -x.value_sum/float(x.visits):0.0f;
       float u=cpuct*x.prior*parent_sqrt/float(1+x.visits);
       float score=q+u;if(score>best){best=score;chosen=c;}
     }
     if(chosen<0)break;
     node=chosen;board_.push(pool_[node].move);trail[ntrail++]=node;++level;
     if(ntrail>=96)break;
   }
   if(aborted){for(int j=0;j<level;++j)board_.pop();r.reason=stop.load()?"stop":"timeout";break;}
   legal_.clear();board_.legal(legal_);
   float v=0;
   if(legal_.empty())v=board_.in_check()?-1.f:0.f;
   else if(board_.draw())v=0.f;
   else if(level<depth&&!pool_[node].expanded){
     float local[256];if(legal_.size()>256){r.reason="legal-overflow";for(int j=0;j<level;++j)board_.pop();break;}
     NNUE::evaluate_policy(board_,legal_.data(),int(legal_.size()),local,&v);
     if(!append_children(node,legal_.data(),local,int(legal_.size()))){
        ++r.alloc_failures;
        // At a full pool, still back up the actual NNUE leaf value; never allocate.
     }
   }else v=NNUE::evaluate_value(board_).value;
   for(int j=ntrail-1;j>=0;--j){auto& x=pool_[trail[j]];++x.visits;x.value_sum+=v;v=-v;}
   for(int j=0;j<level;++j)board_.pop();
   r.max_depth=std::max(r.max_depth,uint32_t(level));++r.simulations;
   progress_depth_.store(r.max_depth,std::memory_order_relaxed);
   progress_sims_.store(r.simulations,std::memory_order_release);
 }
 int best=-1;for(int c=pool_[0].first;c>=0;c=pool_[c].next)
   if(best<0||pool_[c].visits>pool_[best].visits||
      (pool_[c].visits==pool_[best].visits&&pool_[c].prior>pool_[best].prior))best=c;
 if(best>=0){r.best=pool_[best].move;r.valid=true;r.visits=pool_[best].visits;
   r.estimated_value=pool_[best].visits?-pool_[best].value_sum/float(pool_[best].visits):r.root_value;}
 r.nodes=used_;r.time_ms=now()-start;
 // Restore before next request while retaining pool and all vector capacities.
 return r; // Caller extracts root statistics, then calls clear().
}
void SearchWorker::extract(RootStat* out,int count)const{
 for(int i=0;i<count;++i)out[i]=RootStat{};
 if(!used_)return;
 int k=0;for(int c=pool_[0].first;c>=0&&k<count;c=pool_[c].next,++k){
   out[k].visits=pool_[c].visits;out[k].value_sum=pool_[c].value_sum;out[k].prior=pool_[c].prior;}
}
}
