#include "engine.hpp"
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#ifdef PICOSARGON_MULTICORE
#include <atomic>
#include <thread>
#include <mutex>
#include <exception>
#include <memory>
#include <condition_variable>
#include <ctime>
#endif
#ifdef PICOSARGON_STEROIDS
#include <cstdio>
#endif
namespace picoSargon {
namespace {constexpr int INF=1000000,MATE=30000;struct StopSignal{};int piece_value(int v){static const int values[]={0,100,320,330,500,900,20000};return values[std::abs(v)];}}
void Engine::check(){if(stop_&&stop_())throw StopSignal{};if(deadline_&&clock_()>=deadline_)throw StopSignal{};}
uint64_t Engine::hash(const Board& b)const {
 // PositionKey includes side/castling/en-passant (legal EP normalized).
 const PositionKey k=b.position_key();uint64_t h=1469598103934665603ULL;
 for(uint8_t x:k.cells){h^=x;h*=1099511628211ULL;}
 h^=uint8_t(k.turn+2);h*=1099511628211ULL;h^=k.castling;h*=1099511628211ULL;
 h^=uint8_t(k.ep+1);h*=1099511628211ULL;return h;
}
#ifdef PICOSARGON_STEROIDS
// Bounded, legal recapture sequence on one square. Estimates the best
// material continuation, allowing either player to decline the exchange.
// Called only on candidate captures; uses no Grumpy evaluation.
int Engine::see(Board& b,Move first,int limit){
 ++see_calls_;
 const int victim=b.is_capture(first)?(b.piece(first.to)?piece_value(b.piece(first.to)):100):0;
 const int promotion=first.promo?piece_value(first.promo)-100:0;
 const int target=first.to;
 if(!victim&&!promotion)return 0;
 b.push(first);
 int gains[9]{};gains[0]=victim+promotion;
 int n=0,side=-1;
 try{
  while(n<limit){
   auto& legal=legal_buffers_[MAX_PLY+1];
   auto& pseudo=pseudo_buffers_[MAX_PLY+1];
   b.legal(legal,pseudo);
   Move chosen{};int smallest=1000000;bool found=false;
   for(Move m:legal){
    if(m.to!=target||!b.is_capture(m))continue;
    int cost=piece_value(b.piece(m.from));
    if(cost<smallest){smallest=cost;chosen=m;found=true;}
   }
   if(!found)break;
   int captured=piece_value(b.piece(chosen.to));
   if(!captured)captured=100;
   ++n;gains[n]=gains[n-1]+side*captured;
   b.push(chosen);side=-side;
  }
  for(int i=0;i<=n;++i)b.pop();
 }catch(...){for(int i=0;i<=n;++i)b.pop();throw;}
 for(int i=n-1;i>=0;--i){
  if(i%2==0)gains[i]=std::min(gains[i],gains[i+1]);
  else gains[i]=std::max(gains[i],gains[i+1]);
 }
 return gains[0];
}
#endif
void Engine::order(Board& b,std::vector<Move>& ms,int ply,Move ttmove){
 const int side=b.turn==1?0:1;
 auto rank=[&](Move m)->int{
  if(m==ttmove)return 1000000;
  if(b.is_capture(m)||m.promo){int victim=piece_value(b.piece(m.to));if(b.is_capture(m)&&!victim)victim=100;return 100000+victim*10-piece_value(b.piece(m.from))+(m.promo?m.promo*100:0);}
  if(ply<MAX_PLY){if(m==killers_[ply][0])return 90000;if(m==killers_[ply][1])return 80000;}
  return history_[side][m.from][m.to];};
#ifdef PICOSARGON_STEROIDS
 // Pre-score once: SEE is too expensive inside a sort comparator.
 struct Rated {Move move;int score;};
 std::array<Rated,256> rated{};size_t used=0;
 for(Move m:ms){
  int score=rank(m);
  if((b.is_capture(m)||m.promo)&&!(m==ttmove)){
   const int material=see(b,m,6);
   if(material<0){score-=250000;++see_rejected_;}
   else score+=std::min(10000,material);
  }
  rated[used++]={m,score};
 }
 // Stable insertion sort: no internal allocation (unlike stable_sort).
 for(size_t i=1;i<used;++i){
  const Rated key=rated[i];size_t j=i;
  while(j>0&&rated[j-1].score<key.score){rated[j]=rated[j-1];--j;}
  rated[j]=key;
 }
 for(size_t i=0;i<ms.size();++i)ms[i]=rated[i].move;
#else
 // Stable insertion sort without temporary heap storage.
 for(size_t i=1;i<ms.size();++i){Move key=ms[i];const int score=rank(key);size_t j=i;
  while(j>0&&rank(ms[j-1])<score){ms[j]=ms[j-1];--j;}ms[j]=key;
 }
#endif
}
int Engine::negamax(Board& b,int depth,int qleft,int alpha,int beta,int ply,bool pv){
 ++nodes_;if(depth<=0)++qnodes_;if((nodes_&15)==0)check();
 if(b.draw())return 0;
 bool checked=b.in_check();
 if(ply>=MAX_PLY)return net_.evaluate(b)*b.turn;
 // A bounded check extension permits evasions; never extends indefinitely.
 if(depth>0&&checked&&ply<12)++depth;
 const int alpha_original=alpha;
 uint64_t key=0;Entry* slot=nullptr;Move ttmove{};
 // Repetition and fifty-move contexts can alter scores: do not cache them.
 bool tt_safe=depth>0&&b.halfmove<80&&b.repetitions()==1;
 if(tt_safe){key=hash(b);slot=&tt_[key%TT_SIZE];if(slot->key==key){ttmove=slot->best;if(slot->depth>=depth){++tt_hits_;if(slot->bound==0)return slot->score;if(slot->bound==1&&slot->score>=beta)return slot->score;if(slot->bound==2&&slot->score<=alpha)return slot->score;}}}
 auto& moves=legal_buffers_[ply];
 b.legal(moves,pseudo_buffers_[ply]);
 if(moves.empty())return checked?-MATE+ply:0;
 if(depth<=0){
  if(checked){if(qleft<=0)qleft=1;}
  else{
   int stand=net_.evaluate(b)*b.turn;
   if(stand>=beta)return stand;
   if(stand>alpha)alpha=stand;
   if(qleft<=0)return alpha;
   moves.erase(std::remove_if(moves.begin(),moves.end(),[&](Move m){return !b.is_capture(m)&&!m.promo;}),moves.end());
   if(moves.empty())return alpha;
  }
 }
 // Reverse futility only at depth 1, when not in check and outside PV.
 if(depth==1&&!checked&&!pv&&std::abs(alpha)<MATE-1000){int stand=net_.evaluate(b)*b.turn;if(stand-180>=beta)return stand;}
#ifdef PICOSARGON_STEROIDS
 // Razoring: non-PV, non-check, shallow depths only. Q-search verifies
 // the bound; protect mate scores and near-50-move positions.
 if(depth>=1&&depth<=2&&!checked&&!pv&&b.halfmove<80&&
    alpha>-MATE+1000&&alpha<MATE-1000&&beta<MATE-1000){
  ++razor_attempts_;
  const int stand=net_.evaluate(b)*b.turn;
  const int margin=240+160*depth;
  if(stand+margin<alpha){
   const int qscore=negamax(b,0,qleft,alpha-1,alpha,ply,false);
   if(qscore<=alpha){++razor_cuts_;return qscore;}
  }
 }
#endif
 order(b,moves,ply,ttmove);
 Move choice{};int best=-INF;int index=0;
 for(Move m:moves){
  bool tactical=b.is_capture(m)||m.promo;bool quiet=!tactical;
  b.push(m);int value;
  try{
   int next=depth>0?depth-1:0;int qnext=depth>0?qleft:qleft-1;
   // Late move reduction: only late, quiet moves at sufficient depth.
   if(depth>=3&&index>=4&&quiet&&!checked&&!pv&&!b.in_check()&&next>=2){
    value=-negamax(b,next-1,qnext,-alpha-1,-alpha,ply+1,false);
    if(value>alpha)value=-negamax(b,next,qnext,-beta,-alpha,ply+1,false);
   }else if(index>0&&depth>=2){
    // Principal variation search: narrow scout, then full re-search if needed.
    value=-negamax(b,next,qnext,-alpha-1,-alpha,ply+1,false);
    if(value>alpha&&value<beta)value=-negamax(b,next,qnext,-beta,-alpha,ply+1,pv);
   }else value=-negamax(b,next,qnext,-beta,-alpha,ply+1,pv&&index==0);
  }catch(...){b.pop();throw;}
  b.pop();++index;
  if(value>best){best=value;choice=m;}
  if(value>alpha)alpha=value;
  if(alpha>=beta){++cutoffs_;if(quiet&&ply<MAX_PLY){auto& k=killers_[ply];if(!(k[0]==m)){k[1]=k[0];k[0]=m;}auto& h=history_[b.turn==1?0:1][m.from][m.to];h=uint16_t(std::min(60000,int(h)+depth*depth));}break;}
 }
 if(slot&&key){slot->key=key;slot->depth=int8_t(depth);slot->score=best;slot->best=choice;slot->bound=best<=alpha_original?2:best>=beta?1:0;++tt_stores_;}
 return best;
}
void Engine::prepare_buffers(Board& board){
 if(!buffers_ready_){
  for(auto& v:legal_buffers_)v.reserve(256);
  for(auto& v:pseudo_buffers_)v.reserve(256);
  buffers_ready_=true;
 }
 board.reserve_search(MAX_PLY+8);
}
SearchResult Engine::search(Board& b,int max_depth,uint64_t time_limit_ms){
 prepare_buffers(b);
 SearchResult r;r.levels.reserve(static_cast<size_t>(std::max(0,max_depth)));auto begin=clock_();nodes_=qnodes_=tt_hits_=tt_stores_=cutoffs_=0;
 deadline_=time_limit_ms?begin+time_limit_ms:0;
#ifdef PICOSARGON_STEROIDS
 asp_attempts_=asp_retries_=asp_fail_low_=asp_fail_high_=see_calls_=see_rejected_=razor_attempts_=razor_cuts_=0;
#endif
 std::vector<Move> roots;roots.reserve(256);
 std::vector<Move> pseudo;pseudo.reserve(256);b.legal(roots,pseudo);if(roots.empty())return r;
 r.best=roots.front();r.has_move=true;
 for(int depth=1;depth<=max_depth;++depth){
  auto start=clock_(),n0=nodes_,q0=qnodes_;int top=-INF;Move choice=roots[0];bool complete=false;
  // Favor previous iteration's principal move at root.
  if(depth>1){auto it=std::find(roots.begin(),roots.end(),r.best);if(it!=roots.end())std::iter_swap(roots.begin(),it);}
  try{
#ifdef PICOSARGON_STEROIDS
   int window=60;
   int low=depth>=3?std::max(-INF,r.score-window):-INF;
   int high=depth>=3?std::min(INF,r.score+window):INF;
   if(depth>=3)++asp_attempts_;
   while(true){
    top=-INF;choice=roots[0];int alpha=low,beta=high,i=0;
    for(Move m:roots){check();b.push(m);int val;
     try{if(i==0)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);
      else{val=-negamax(b,depth-1,qdepth_,-alpha-1,-alpha,1,false);
       if(val>alpha&&val<beta)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);}}
     catch(...){b.pop();throw;}
     b.pop();if(val>top){top=val;choice=m;}if(val>alpha)alpha=val;++i;
    }
    if(depth<3||(top>low&&top<high)||(low==-INF&&high==INF))break;
    ++asp_retries_;window=std::min(INF/2,window*2);
    if(top<=low){++asp_fail_low_;low=std::max(-INF,top-window);}
    else{++asp_fail_high_;high=std::min(INF,top+window);}
    if(asp_retries_>100){low=-INF;high=INF;}
   }
#else
   int alpha=-INF,beta=INF,i=0;
   for(Move m:roots){check();b.push(m);int val;
    try{if(i==0)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);
     else{val=-negamax(b,depth-1,qdepth_,-alpha-1,-alpha,1,false);
       if(val>alpha&&val<beta)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);}}
    catch(...){b.pop();throw;}
    b.pop();if(val>top){top=val;choice=m;}if(val>alpha)alpha=val;++i;
   }
#endif
   complete=true;
  }catch(const StopSignal&){r.reason="stop";}
  Level lv;lv.depth=depth;lv.ms=clock_()-start;lv.nodes=nodes_-n0;lv.qnodes=qnodes_-q0;lv.complete=complete;if(memory_)lv.mem=memory_();
  r.levels.push_back(lv);
  if(complete){r.best=choice;r.score=top;r.depth=depth;}else break;
 }
 r.elapsed_ms=clock_()-begin;r.nodes=nodes_;r.qnodes=qnodes_;r.tt_hits=tt_hits_;r.tt_stores=tt_stores_;r.cutoffs=cutoffs_;
#ifdef PICOSARGON_STEROIDS
 r.asp_attempts=asp_attempts_;r.asp_retries=asp_retries_;r.asp_fail_low=asp_fail_low_;r.asp_fail_high=asp_fail_high_;r.see_calls=see_calls_;r.see_rejected=see_rejected_;r.razor_attempts=razor_attempts_;r.razor_cuts=razor_cuts_;
#endif
#ifdef PICOSARGON_STEROIDS
 std::fprintf(stderr,"STEROIDS asp_attempts=%llu asp_retries=%llu asp_fail_low=%llu asp_fail_high=%llu see_calls=%llu see_negative=%llu razor_attempts=%llu razor_cuts=%llu nodes=%llu\n",
  (unsigned long long)r.asp_attempts,(unsigned long long)r.asp_retries,(unsigned long long)r.asp_fail_low,(unsigned long long)r.asp_fail_high,
  (unsigned long long)r.see_calls,(unsigned long long)r.see_rejected,(unsigned long long)r.razor_attempts,(unsigned long long)r.razor_cuts,(unsigned long long)r.nodes);
#endif
 return r;
}
}

#ifdef PICOSARGON_MULTICORE
namespace picoSargon {
namespace {
struct CoreCounters {
 uint64_t nodes=0,qnodes=0,tt_hits=0,tt_stores=0,cutoffs=0;
#ifdef PICOSARGON_STEROIDS
 uint64_t asp_attempts=0,asp_retries=0,asp_fail_low=0,asp_fail_high=0,
 see_calls=0,see_rejected=0,razor_attempts=0,razor_cuts=0;
#endif
};
void core_telemetry(unsigned core,int depth,bool completed,const CoreCounters& c,uint64_t elapsed){
 std::time_t now=std::time(nullptr);std::tm tm{};
#if defined(_WIN32)
 localtime_s(&tm,&now);
#else
 localtime_r(&now,&tm);
#endif
 char when[16]{};std::strftime(when,sizeof(when),"%H:%M:%S",&tm);
 std::fprintf(stderr,"[%s] 🧮 core[%u] level=%02d status=%-9s nodes=%llu qnodes=%llu elapsed=%llu msec\n",
  when,core,depth,completed?"completed":"stopped",
  (unsigned long long)c.nodes,(unsigned long long)c.qnodes,(unsigned long long)elapsed);
 std::fflush(stderr);
}
}
SearchResult Engine::search_parallel(const Board& board,int max_depth,uint64_t time_limit_ms,unsigned requested_cores){
 SearchResult result;result.levels.reserve(static_cast<size_t>(std::max(0,max_depth)));
 const uint64_t begin=clock_();
 const uint64_t deadline=time_limit_ms?begin+time_limit_ms:0;
 Board seed=board;seed.reserve_search(MAX_PLY+8);
 std::vector<Move> moves,pseudo;moves.reserve(256);pseudo.reserve(256);
 seed.legal(moves,pseudo);
 if(moves.empty())return result;
 result.best=moves.front();result.has_move=true;
 const unsigned workers=std::min<unsigned>(std::max(1u,requested_cores),static_cast<unsigned>(moves.size()));
 // Worker state and NNUE copies are allocated exactly once per search.
 // Reused at every iterative-deepening level, including TT and history.
 struct Worker {
  Grumpy net;
  std::unique_ptr<Engine> engine;
  Board board;
  CoreCounters initial{},delta{};
  uint64_t started=0,elapsed=0;
  bool completed=false;
  Worker(const Grumpy& weights,const Board& position,Engine& owner,
         std::atomic<bool>& cancelled,uint64_t limit):net(weights),board(position){
   engine.reset(new Engine(net,owner.clock_,[&owner,&cancelled]{
    return cancelled.load(std::memory_order_relaxed)||(owner.stop_&&owner.stop_());
   },{},owner.qdepth_));
   engine->deadline_=limit;
   engine->prepare_buffers(board);
  }
 };
 std::atomic<bool> cancelled{false};
 std::vector<std::unique_ptr<Worker>> pool;pool.reserve(workers);
 for(unsigned i=0;i<workers;++i)pool.emplace_back(new Worker(net_,board,*this,cancelled,deadline));
 std::atomic<size_t> next{0};
 std::atomic<int> root_alpha{-INF};
 std::mutex task_mutex,result_mutex;
 std::condition_variable task_cv,done_cv;
 unsigned generation=0,finished=0;
 bool terminate=false;
 int depth_to_search=0,best=-INF;
 size_t best_index=0;
 std::exception_ptr failure;
 std::vector<std::thread> threads;threads.reserve(workers);
 auto run=[&](unsigned id){
  Worker& w=*pool[id];unsigned handled=0;
  for(;;){
   {
    std::unique_lock<std::mutex> lock(task_mutex);
    task_cv.wait(lock,[&]{return terminate||generation!=handled;});
    if(terminate)return;
    handled=generation;
   }
   const auto started=clock_();
   const uint64_t n0=w.engine->nodes_,q0=w.engine->qnodes_;
   const uint64_t h0=w.engine->tt_hits_,s0=w.engine->tt_stores_,c0=w.engine->cutoffs_;
#ifdef PICOSARGON_STEROIDS
   const uint64_t se0=w.engine->see_calls_,sr0=w.engine->see_rejected_,
    ra0=w.engine->razor_attempts_,rc0=w.engine->razor_cuts_;
#endif
   bool finished_normally=true;
   try{
    while(!cancelled.load(std::memory_order_relaxed)){
     const size_t idx=next.fetch_add(1,std::memory_order_relaxed);
     if(idx>=moves.size())break;
     w.engine->check();
     w.board=board; // Preserved pre-reserved vector capacities.
     w.board.push(moves[idx]);
     const int alpha=root_alpha.load(std::memory_order_acquire);
     int score=-w.engine->negamax(w.board,depth_to_search-1,qdepth_,-INF,-alpha,1,true);
     if(alpha!=-INF&&score>alpha)
      score=-w.engine->negamax(w.board,depth_to_search-1,qdepth_,-INF,INF,1,true);
     {
      std::lock_guard<std::mutex> lock(result_mutex);
      if(score>best||(score==best&&idx<best_index)){
       best=score;best_index=idx;
       int previous=root_alpha.load(std::memory_order_relaxed);
       while(score>previous&&!root_alpha.compare_exchange_weak(previous,score,
         std::memory_order_release,std::memory_order_relaxed)){}
      }
     }
    }
   }catch(const StopSignal&){finished_normally=false;cancelled.store(true,std::memory_order_relaxed);}
    catch(...){
     finished_normally=false;cancelled.store(true,std::memory_order_relaxed);
     std::lock_guard<std::mutex> lock(result_mutex);if(!failure)failure=std::current_exception();
    }
   CoreCounters& c=w.delta;
   c.nodes=w.engine->nodes_-n0;c.qnodes=w.engine->qnodes_-q0;
   c.tt_hits=w.engine->tt_hits_-h0;c.tt_stores=w.engine->tt_stores_-s0;c.cutoffs=w.engine->cutoffs_-c0;
#ifdef PICOSARGON_STEROIDS
   c.see_calls=w.engine->see_calls_-se0;c.see_rejected=w.engine->see_rejected_-sr0;
   c.razor_attempts=w.engine->razor_attempts_-ra0;c.razor_cuts=w.engine->razor_cuts_-rc0;
#endif
   w.elapsed=clock_()-started;
   w.completed=finished_normally&&!cancelled.load(std::memory_order_relaxed);
   {
    std::lock_guard<std::mutex> lock(task_mutex);++finished;
   }
   done_cv.notify_one();
  }
 };
 for(unsigned id=0;id<workers;++id)threads.emplace_back(run,id);
 for(int depth=1;depth<=max_depth;++depth){
  const uint64_t level_start=clock_();
  if((deadline&&level_start>=deadline)||(stop_&&stop_())){result.reason="stop";break;}
  if(depth>1){auto it=std::find(moves.begin(),moves.end(),result.best);if(it!=moves.end())std::iter_swap(moves.begin(),it);}
  next.store(0,std::memory_order_relaxed);root_alpha.store(-INF,std::memory_order_relaxed);
  best=-INF;best_index=moves.size();depth_to_search=depth;
  {
   std::lock_guard<std::mutex> lock(task_mutex);finished=0;++generation;
  }
  task_cv.notify_all();
  {
   std::unique_lock<std::mutex> lock(task_mutex);
   done_cv.wait(lock,[&]{return finished==workers;});
  }
  uint64_t level_nodes=0,level_qnodes=0;
  const bool complete=!cancelled.load(std::memory_order_relaxed)&&next.load(std::memory_order_relaxed)>=moves.size();
  for(unsigned id=0;id<workers;++id){
   const auto& w=*pool[id];const auto& c=w.delta;
   core_telemetry(id,depth,complete&&w.completed,c,w.elapsed);
   level_nodes+=c.nodes;level_qnodes+=c.qnodes;
   result.tt_hits+=c.tt_hits;result.tt_stores+=c.tt_stores;result.cutoffs+=c.cutoffs;
#ifdef PICOSARGON_STEROIDS
   result.see_calls+=c.see_calls;result.see_rejected+=c.see_rejected;
   result.razor_attempts+=c.razor_attempts;result.razor_cuts+=c.razor_cuts;
#endif
  }
  result.nodes+=level_nodes;result.qnodes+=level_qnodes;
  Level lv;lv.depth=depth;lv.ms=clock_()-level_start;lv.nodes=level_nodes;lv.qnodes=level_qnodes;
  lv.complete=complete;
  if(memory_)lv.mem=memory_();
  result.levels.push_back(lv);
  if(!complete){result.reason="stop";break;}
  result.best=moves[best_index];result.score=best;result.depth=depth;
 }
 {
  std::lock_guard<std::mutex> lock(task_mutex);terminate=true;
 }
 task_cv.notify_all();
 for(auto& thread:threads)thread.join();
 if(failure)std::rethrow_exception(failure);
 result.elapsed_ms=clock_()-begin;
 return result;
}
}
#endif
