#include "board.hpp"
#include "net.hpp"
#include "mcts.hpp"
#include <cstdio>
#include <chrono>
uint64_t clk(){return uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
int main(){static picoSargon::Board b;static picoalpha::Network net;static picoalpha::SearchHistory h;h.emplace_back(b);
 auto x=picoalpha::search(net,b,h,false,128,1.5f,8576,30000,clk,nullptr);printf("search 1 sims=%u nodes=%u reused=%u has=%u\n",x.simulations,x.tree_nodes,x.reused_prior_nodes,unsigned(x.has));
 if(!x.has)return 2;b.push(x.move);h.emplace_back(b);picoSargon::MoveList legal;b.legal(legal);if(legal.empty())return 0;
 // the continuation most likely seen by the previous tree (test all legal opponent replies)
 for(auto m:legal){b.push(m);h.emplace_back(b);auto r=picoalpha::search(net,b,h,false,16,1.5f,8576,30000,clk,nullptr);
  printf("reply %d-%d sims=%u reused=%u nodes=%u\n",m.from,m.to,r.simulations,r.reused_prior_nodes,r.tree_nodes);if(r.reused_prior_nodes>0)return 0;
  h.pop_back();b.pop();}
 return 3;
}
