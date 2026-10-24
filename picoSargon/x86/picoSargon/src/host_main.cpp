#include "board.hpp"
#include "engine.hpp"
#include "grumpy.hpp"
#include <chrono>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
using namespace picoSargon;
static uint64_t milliseconds(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){
 try{
  if(argc<2)throw std::runtime_error("uso: picoSargon_host <grumpy.bin>");
  Grumpy net;net.load(argv[1]);Board board;
  int qdepth=2;std::string line;
  while(std::getline(std::cin,line)){
   std::istringstream ss(line);std::string cmd;ss>>cmd;
   if(cmd=="uci"){
    std::cout<<"id name picoSargon C++ native / Pico W search core\nid author Dr. Pedro E. Colla\noption name QDepth type spin default 2 min 0 max 32\nuciok\n";
   }else if(cmd=="isready")std::cout<<"readyok\n";
   else if(cmd=="setoption"){
    std::string name,parameter,value;ss>>name>>parameter>>value;
    if(name=="name"&&parameter=="QDepth"&&value=="value"){
     int next;if(ss>>next&&next>=0&&next<=32)qdepth=next;
    }
   }else if(cmd=="ucinewgame")board.reset();
   else if(cmd=="position"){
    std::string t;ss>>t;
    if(t=="startpos")board.reset();
    else if(t=="fen"){
     std::string fen,part;for(int i=0;i<6&&ss>>part;++i){if(i)fen+=' ';fen+=part;}
     board.set_fen(fen);
    }else throw std::runtime_error("position expects fen/startpos");
    while(ss>>t){if(t=="moves")continue;board.push(board.parse(t));}
   }else if(cmd=="go"){
    int depth=4;uint64_t timelimit=15000;std::string t;
    while(ss>>t){if(t=="depth")ss>>depth;else if(t=="movetime")ss>>timelimit;}
    if(depth<1||depth>40)throw std::runtime_error("depth out of range");
    Engine engine(net,milliseconds,[]{return false;},{},qdepth);
    auto result=engine.search(board,depth,timelimit);
    std::cout<<"info depth "<<result.depth<<" score cp "<<result.score<<" nodes "<<result.nodes<<"\n";
    std::cout<<"bestmove "<<(result.has_move?Board::notation(result.best):"0000")<<"\n";
   }else if(cmd=="quit")break;
   std::cout.flush();
  }
  return 0;
 }catch(const std::exception& e){std::cerr<<"picoSargon host fatal: "<<e.what()<<"\n";return 1;}
}
