#include "search_coordinator.hpp"
#include "nnue_int8.hpp"
#include <atomic>
#include <cassert>
#include <cstdio>
#include <thread>
#include <chrono>
#include <vector>
using namespace picoalpha_arm;
int main(){
 init_cores();
 for(int i=0;i<2000&&!core1_ready();++i)std::this_thread::sleep_for(std::chrono::milliseconds(1));
 assert(core1_ready());
 picoSargon::Board board;
 std::atomic<bool> stop{false};
 for(int n=0;n<10;++n){
  auto r=run_search(board,120,7,4000,1.4f,stop,nullptr);
  assert(r.simulations==120 && r.valid && r.core_sims[0]==60 && r.core_sims[1]==60);
  assert(r.nodes>0 && r.max_depth<=7 && r.elapsed_ms<=4000);
  std::vector<picoSargon::Move> moves;board.legal(moves);
  bool found=false;for(auto m:moves)if(m==r.best)found=true;
  assert(found);
  printf("iteration=%d bestmove=%s simulations=%u nodes=%u core0=%u core1=%u\n",
    n,picoSargon::Board::notation(r.best).c_str(),r.simulations,r.nodes,r.core_nodes[0],r.core_nodes[1]);
 }
 puts("PASS picoAlpha-ARM two-core coordination test");
}
