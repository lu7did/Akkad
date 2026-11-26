#include "engine.hpp"
#include <atomic>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <thread>
using namespace picoSargon;
static uint64_t ms(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main(int argc,char** argv){
 try{
  require(argc==2,"model argument missing");
  Grumpy na,nb;na.load(argv[1]);nb.load(argv[1]);
  Board a,b;auto initial=a.position_key();
  std::vector<Move> all,left,right;a.legal(all);
  for(size_t i=0;i<all.size();++i)(i%2?right:left).push_back(all[i]);
  std::atomic<bool> stop{false};std::atomic<int> alpha{-1000000};
  Engine ea(na,ms,[&]{return stop.load();},{},4),eb(nb,ms,[&]{return stop.load();},{},4);
  SearchResult ra,rb;std::exception_ptr error;
  auto deadline=ms()+5000;
  std::thread t([&]{try{rb=eb.search_partition(b,right,1,deadline,alpha);}catch(...){error=std::current_exception();}});
  try{ra=ea.search_partition(a,left,1,deadline,alpha);}catch(...){t.join();throw;}t.join();if(error)std::rethrow_exception(error);
  require(ra.depth==1&&rb.depth==1,"partition depth 1 incomplete");
  require(ra.twin_allocations<30&&rb.twin_allocations<30,"eager allocation regression");
  require(a.position_key()==initial&&b.position_key()==initial,"board not restored");
  std::cout<<"TWINS concurrent depth=1 allocations="<<ra.twin_allocations<<","<<rb.twin_allocations<<" OK\n";
  stop.store(true);alpha.store(-1000000);
  auto cancelled=eb.search_partition(b,right,3,0,alpha);
  require(cancelled.depth==0&&cancelled.reason=="stop","stop not honored");
  stop.store(false);alpha.store(-1000000);
  auto expired=eb.search_partition(b,right,3,ms(),alpha);
  require(expired.depth==0&&expired.reason=="stop","deadline not honored");
  alpha.store(-1000000);auto resumed=eb.search_partition(b,right,1,ms()+5000,alpha);
  require(resumed.depth==1&&resumed.twin_allocations==0,"recovery or reuse failed");
  require(b.position_key()==initial,"board changed on cancellation");
  std::cout<<"TWINS stop, deadline, buffer reuse and recovery OK\n";
  return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
