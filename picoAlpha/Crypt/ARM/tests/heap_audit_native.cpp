#include "board.hpp"
#include "net.hpp"
#include "mcts.hpp"
#include <cstdio>
#include <atomic>
#include <new>
#include <cstdlib>
#include <chrono>
static std::atomic<int> count{0};
void* operator new(std::size_t n){auto c=++count;if(c<=12)std::fprintf(stderr,"NEW #%d size=%zu\n",int(c),n);if(void* p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void* p)noexcept {std::free(p);} 
void operator delete(void* p,std::size_t)noexcept {std::free(p);} 
uint64_t clk(){return uint64_t(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
int main(){static picoSargon::Board b;static picoalpha::Network net;static picoalpha::SearchHistory h;h.emplace_back(b);static picoSargon::MoveList moves;
 int before=count.load();for(int i=0;i<3;++i){ auto r=picoalpha::search(net,b,h,false,4,1.5f,1600,30000,clk,nullptr);std::printf("search %d sims=%u nodes=%u has=%d reason=%s new_delta=%d\n",i,r.simulations,r.tree_nodes,int(r.has),r.reason,count.load()-before); }
 for(int i=0;i<100;++i){b.legal(moves);if(moves.empty())break;b.push(moves[i%moves.size()]);}std::printf("board history=%zu heap_alloc_calls=%d\n",b.history_length(),count.load()-before);
 return 0;}
