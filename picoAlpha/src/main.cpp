#include "board.hpp"
#include "nnue.hpp"
#include "mcts.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace {
constexpr const char* VERSION="0.1.42";
std::mutex io_mtx;
void uci(const std::string& s){std::lock_guard<std::mutex> lock(io_mtx);std::cout<<s<<'\n'<<std::flush;}
void log(const std::string& s){std::lock_guard<std::mutex> lock(io_mtx);std::cerr<<s<<'\n'<<std::flush;}
int positive(const std::string& s,const char* key){try{size_t n=0;long long v=std::stoll(s,&n);if(n!=s.size()||v<1||v>1000000000LL)throw std::invalid_argument("range");return int(v);}catch(...){throw std::runtime_error(std::string("Invalid ")+key+": "+s);}}
struct Options{std::string network;int depth=12,timeout=15000,sims=200;double cpuct=1.4;};
void help(){std::cout<<"picoAlpha C++ v"<<VERSION<<" (MCTSP+MCTSE UCI)\n"
 <<" --network FILE     Portable INT8 .bin weights (mandatory)\n"
 <<" --depth N          MCTS maximum plies, default 12\n"
 <<" --timeout MS       Maximum analysis time, default 15000\n"
 <<" --sim N            Maximum simulations, default 200\n"
 <<" --cpuct X          PUCT exploration constant, default 1.4\n"
 <<" --help             Show this help\n"
 <<"UCI: position, go (depth/movetime/nodes), stop, isready, ucinewgame, quit\n";}
Options parse(int argc,char**argv){Options o;for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--help"||k=="-h"){help();std::exit(0);}if(i+1==argc)throw std::runtime_error("Missing value for "+k);std::string v=argv[++i];if(k=="--network"||k=="--weights")o.network=v;else if(k=="--depth")o.depth=positive(v,"depth");else if(k=="--timeout")o.timeout=positive(v,"timeout");else if(k=="--sim"||k=="--sims")o.sims=positive(v,"sim");else if(k=="--cpuct"){o.cpuct=std::stod(v);if(!std::isfinite(o.cpuct)||o.cpuct<=0)throw std::runtime_error("Invalid cpuct");}else throw std::runtime_error("Unknown argument: "+k);}if(o.network.empty())throw std::runtime_error("--network FILE is mandatory");return o;}
std::vector<std::string> tokens(const std::string& s){std::istringstream in(s);std::string w;std::vector<std::string> v;while(in>>w)v.push_back(w);return v;}
void setup_position(picoSargon::Board& board,const std::vector<std::string>& t){
 if(t.size()<2)throw std::runtime_error("position without startpos/fen");size_t at=1;
 if(t[at]=="startpos"){board.reset();++at;}
 else if(t[at]=="fen"){
  ++at;std::string fen;while(at<t.size()&&t[at]!="moves"){if(!fen.empty())fen+=' ';fen+=t[at++];}
  board.set_fen(fen);
 }else throw std::runtime_error("Unsupported position command");
 if(at<t.size()){if(t[at++]!="moves")throw std::runtime_error("Expected moves");for(;at<t.size();++at){auto m=board.parse(t[at]);board.push(m);}}
}
void process_option(Options& o,const std::vector<std::string>& t){
 size_t ni=0,vi=0;for(size_t i=1;i<t.size();++i){if(t[i]=="name")ni=i;if(t[i]=="value")vi=i;}
 if(!ni||!vi||vi<=ni+1||vi+1>=t.size())return;
 std::string name,value=t[ni+1],v=t[vi+1];for(size_t i=ni+2;i<vi;++i)name+=' '+t[i];
 if(name=="Depth")o.depth=positive(v,"Depth");else if(name=="Simulations")o.sims=positive(v,"Simulations");else if(name=="Timeout")o.timeout=positive(v,"Timeout");else if(name=="Cpuct")o.cpuct=std::stod(v);
}
}
int main(int argc,char**argv){
#ifdef _WIN32
 SetConsoleOutputCP(CP_UTF8);
#endif
 try{
  Options opt=parse(argc,argv);picoalpha::Network net;net.load(opt.network);
  log(std::string("[BOOT] picoAlpha MCTSP+MCTSE C++ v")+VERSION+" platform=x86/UCI");
  log("[NNUE] INT8 780x16 from_to/tanh model="+opt.network+" weights=14544 scales=4");
  log("[SEARCH] PUCT depth="+std::to_string(opt.depth)+" sims="+std::to_string(opt.sims)+" timeout_ms="+std::to_string(opt.timeout));
  picoSargon::Board board;
  std::thread worker;std::atomic<bool> stop(false);
  auto join=[&](){stop.store(true);if(worker.joinable())worker.join();stop.store(false);};
  std::string line;
  while(std::getline(std::cin,line)){
   auto t=tokens(line);if(t.empty())continue;const auto& command=t.front();
   if(command=="uci"){
    uci(std::string("id name picoAlpha MCTSP-MCTSE v")+VERSION);uci("id author Akkad");
    uci("option name Depth type spin default 12 min 1 max 256");
    uci("option name Simulations type spin default 200 min 1 max 1000000000");
    uci("option name Timeout type spin default 15000 min 1 max 1000000000");
    uci("option name Cpuct type string default 1.4");uci("uciok");
   }else if(command=="isready")uci("readyok");
   else if(command=="ucinewgame"){join();board.reset();log("[UCI] ucinewgame");}
   else if(command=="position"){join();try{setup_position(board,t);log("[UCI] position moves="+std::to_string(board.history_length()-1));}catch(const std::exception& e){log(std::string("[ERROR] ")+e.what());}}
   else if(command=="setoption"){join();try{process_option(opt,t);}catch(const std::exception&e){log(std::string("[ERROR] ")+e.what());}}
   else if(command=="go"){
    join();int depth=opt.depth,sims=opt.sims,ms=opt.timeout;
    try{
     for(size_t i=1;i<t.size();++i){
      if((t[i]=="depth"||t[i]=="movetime"||t[i]=="nodes")&&i+1<t.size()){
       const std::string key=t[i++];int n=positive(t[i],key.c_str());
       if(key=="depth")depth=(std::min)(depth,n);
       else if(key=="movetime")ms=(std::min)(ms,n);
       else sims=(std::min)(sims,n);
      }
     }
     picoSargon::Board position=board;stop.store(false);
     worker=std::thread([&,position,depth,sims,ms]()mutable{
      try{picoalpha::Search search;auto result=search.run(position,net,sims,depth,ms,opt.cpuct,&stop);
       double x=std::clamp(result.value,-0.999999,0.999999);int cp=int(std::round(400.0*std::atanh(x)));
       // UCI centipawns are always from the side-to-move perspective.
       uci("info depth "+std::to_string(result.depth)+" nodes "+std::to_string(result.nodes)+" time "+std::to_string(result.elapsed_ms)+" nps "+std::to_string(result.nodes*1000LL/(std::max)(1,result.elapsed_ms))+" score cp "+std::to_string(cp));
       uci("bestmove "+(result.valid?picoSargon::Board::notation(result.move):std::string("(none)")));
       log("[MCTS] sims="+std::to_string(result.simulations)+" visits="+std::to_string(result.visits)+" nodes="+std::to_string(result.nodes)+" depth="+std::to_string(result.depth)+" nn_value_stm="+std::to_string(result.root_value)+" elapsed_ms="+std::to_string(result.elapsed_ms)+" reason="+result.reason);
      }catch(const std::exception& e){log(std::string("[ERROR] search: ")+e.what());uci("bestmove (none)");}
     });
    }catch(const std::exception&e){log(std::string("[ERROR] go: ")+e.what());uci("bestmove (none)");}
   }else if(command=="stop")join();
   else if(command=="quit"){join();break;}
   else if(command=="d")log("[UCI] debug board key: "+std::to_string(board.history_length()));
   else log("[UCI] ignored: "+command);
  }
  join();return 0;
 }catch(const std::exception& e){log(std::string("[FATAL] ")+e.what());return 2;}
}
