// Build with tests/run_host.sh from an Akkad checkout (host C++17).
#include "board.hpp"
#include "nnue_int8.hpp"
#include "mcts_arm.hpp"
#include <atomic>
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <chrono>
#include <vector>
using namespace picoalpha_arm;
uint32_t now(){using namespace std::chrono;return uint32_t(duration_cast<milliseconds>(steady_clock::now().time_since_epoch()).count());}
int main(){
 picoSargon::Board b;
 auto a=NNUE::evaluate_value(b);
 assert(std::isfinite(a.value));
 std::vector<picoSargon::Move> m;b.legal(m);assert(m.size()==20);
 float p[256]{};float v=0;
 NNUE::evaluate_policy(b,m.data(),int(m.size()),p,&v);
 assert(std::abs(a.value-v)<1e-6f);
 float sum=0;for(size_t i=0;i<m.size();++i){assert(p[i]>=0);sum+=p[i];}
 assert(std::abs(sum-1.f)<2e-6f);
 std::vector<MCTSNode> pool(256);
 SearchWorker engine(pool.data(),uint32_t(pool.size()));engine.reserve(8);
 std::atomic<bool> stop{false};
 for(int attempt=0;attempt<20;++attempt){
  uint32_t deadline=now()+2000;
  auto r=engine.run(b,24,5,deadline,1.4f,stop,now,nullptr);
  RootStat stats[256];engine.extract(stats,int(r.root_moves));
  assert(r.valid&&r.simulations==24&&r.nodes<=pool.size());
  bool legal=false;for(auto x:m)if(x==r.best)legal=true;
  assert(legal);
  engine.clear();
 }
 b.push(b.parse("e2e4"));b.push(b.parse("e7e5"));
 b.push(b.parse("g1f3"));b.push(b.parse("b8c6"));
 assert(std::isfinite(NNUE::evaluate_value(b).value));
 puts("PASS picoAlpha-ARM host MCTS NNUE + board tests");
}
