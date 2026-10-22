#include "engine.hpp"
#include <algorithm>
#include <cstdlib>
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
void Engine::order(Board& b,std::vector<Move>& ms,int ply,Move ttmove){
 const int side=b.turn==1?0:1;
 auto rank=[&](Move m)->int{
  if(m==ttmove)return 1000000;
  if(b.is_capture(m)||m.promo){int victim=piece_value(b.piece(m.to));if(b.is_capture(m)&&!victim)victim=100;return 100000+victim*10-piece_value(b.piece(m.from))+(m.promo?m.promo*100:0);}
  if(ply<MAX_PLY){if(m==killers_[ply][0])return 90000;if(m==killers_[ply][1])return 80000;}
  return history_[side][m.from][m.to];};
 std::stable_sort(ms.begin(),ms.end(),[&](Move a,Move c){return rank(a)>rank(c);});
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
 std::vector<Move> moves;b.legal(moves);
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
SearchResult Engine::search(Board& b,int max_depth,uint64_t time_limit_ms){
 SearchResult r;auto begin=clock_();nodes_=qnodes_=tt_hits_=tt_stores_=cutoffs_=0;
 deadline_=time_limit_ms?begin+time_limit_ms:0;
 std::vector<Move> roots;b.legal(roots);if(roots.empty())return r;
 r.best=roots.front();r.has_move=true;
 for(int depth=1;depth<=max_depth;++depth){
  auto start=clock_(),n0=nodes_,q0=qnodes_;int top=-INF;Move choice=roots[0];bool complete=false;
  // Favor previous iteration's principal move at root.
  if(depth>1){auto it=std::find(roots.begin(),roots.end(),r.best);if(it!=roots.end())std::iter_swap(roots.begin(),it);}
  try{int alpha=-INF,beta=INF;int i=0;
   for(Move m:roots){check();b.push(m);int val;
    try{if(i==0)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);
     else{val=-negamax(b,depth-1,qdepth_,-alpha-1,-alpha,1,false);
       if(val>alpha&&val<beta)val=-negamax(b,depth-1,qdepth_,-beta,-alpha,1,true);}}
    catch(...){b.pop();throw;}
    b.pop();if(val>top){top=val;choice=m;}if(val>alpha)alpha=val;++i;
   }complete=true;
  }catch(const StopSignal&){r.reason="stop";}
  Level lv;lv.depth=depth;lv.ms=clock_()-start;lv.nodes=nodes_-n0;lv.qnodes=qnodes_-q0;lv.complete=complete;if(memory_)lv.mem=memory_();r.levels.push_back(lv);
  if(complete){r.best=choice;r.score=top;r.depth=depth;}else break;
 }
 r.elapsed_ms=clock_()-begin;r.nodes=nodes_;r.qnodes=qnodes_;r.tt_hits=tt_hits_;r.tt_stores=tt_stores_;r.cutoffs=cutoffs_;return r;
}
}
