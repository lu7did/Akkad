#include "board.hpp"
#include "model.hpp"
#include <algorithm>
#include <chrono>
#include <limits>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <iomanip>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#endif
using namespace picoSargon;
static bool terminal(Board& b,double& val){
 std::vector<Move> moves;b.legal(moves);
 if(moves.empty()){val=b.in_check()?-1.0:0.0;return true;}
 if(b.draw()){val=0.0;return true;}
 return false;
}
struct Result {Move move{};bool found=false;double rival_value=0;int inspected=0,terminal_count=0;long long ms=0;};
static Result choose(Board& board,Evaluator& eval){
 auto st=std::chrono::steady_clock::now();Result r;std::vector<Move> moves;board.legal(moves);
 if(board.draw()||moves.empty())return r;
 double lowest=1e9;
 std::vector<Board> batch_boards;
 std::vector<size_t> batch_indices;
 std::vector<double> vals(moves.size());
 for(size_t i=0;i<moves.size();++i){
  board.push(moves[i]);double v;
  if(terminal(board,v)){++r.terminal_count;vals[i]=v;}
  else {batch_boards.push_back(board);batch_indices.push_back(i);}
  board.pop();
 }
 if(!batch_boards.empty()){
  auto predictions=eval.eval_batch(batch_boards);
  for(size_t j=0;j<predictions.size();++j)vals[batch_indices[j]]=predictions[j];
 }
 for(size_t i=0;i<moves.size();++i){
  ++r.inspected;double v=vals[i];
  if(!r.found||v<lowest){r.found=true;r.move=moves[i];r.rival_value=v;lowest=v;}
 }
 r.ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-st).count();return r;
}
static void position(Board& b,const std::string& command){
 auto cut=command.find(" moves ");std::string base=command.substr(9,cut==std::string::npos?std::string::npos:cut-9);
 Board next=b;
 if(base=="startpos")next.reset();else if(base.rfind("fen ",0)==0)next.set_fen(base.substr(4));else throw std::runtime_error("invalid position");
 if(cut!=std::string::npos){std::istringstream ms(command.substr(cut+7));std::string token;
  while(ms>>token){std::vector<Move> legal;next.legal(legal);const Move m=next.parse(token);
   if(std::none_of(legal.begin(),legal.end(),[&](const Move& x){return Board::notation(x)==Board::notation(m);}))throw std::runtime_error("illegal move "+token);
   next.push(m);
  }
 }
 b=std::move(next);
}
struct Session {
 Board b;Evaluator& eval;std::function<void(const std::string&)> send;
 void command(const std::string& line){
  if(line=="uci"){send("id name picoKeras v0.2.3");send("id author Dr. Pedro E. Colla 2026");send("uciok");}
  else if(line=="isready")send("readyok");
  else if(line=="ucinewgame")b.reset();
  else if(line.rfind("position ",0)==0)position(b,line);
  else if(line.rfind("go",0)==0){auto r=choose(b,eval);
   std::ostringstream info;info<<"info nodes "<<r.inspected<<" time "<<r.ms<<" score cp "<<std::lround(-r.rival_value*100.0);
   send(info.str());send(std::string("bestmove ")+(r.found?Board::notation(r.move):"(none)"));

  }else if(line=="stop"){}else if(line=="quit"){}else if(line=="d")send("info string mailbox120 position available");
 }
};
#ifdef _WIN32
using sock_t=SOCKET;static void closesock(sock_t s){closesocket(s);}static constexpr sock_t badsock=INVALID_SOCKET;
#else
using sock_t=int;static void closesock(sock_t s){close(s);}static constexpr sock_t badsock=-1;
#endif
int main(int argc,char**argv){try{
 std::string network,host="0.0.0.0",input_op="auto",output_op="auto";int port=6110;bool stdio=false;size_t arena=32*1024*1024;
 for(int i=1;i<argc;++i){std::string k=argv[i];auto value=[&](){if(i+1>=argc)throw std::runtime_error("missing value for "+k);return std::string(argv[++i]);};
  if(k=="--network")network=value();else if(k=="--host")host=value();else if(k=="--port")port=std::stoi(value());else if(k=="--arena")arena=std::stoull(value());else if(k=="--stdio")stdio=true;else if(k=="--input-op")input_op=value();else if(k=="--output-op")output_op=value();
  else if(k=="--help"){std::cout<<"picoKeras 0.2.3 --network model.tf [--host 0.0.0.0] [--port 6110] [--arena BYTES] [--stdio]\nTensorFlow SavedModel with FLOAT32 boundary; --input-op and --output-op are configurable.\n";return 0;}
  else throw std::runtime_error("unknown argument: "+k);
 }
 if(network.empty()||port<1||port>65535)throw std::runtime_error("--network required, --port must be 1..65535");
 std::cerr<<"picoKeras v0.2.3 network="<<network<<" host="<<host<<" port="<<port<<" arena="<<arena<<" mode="<<(stdio?"stdin":"TCP")<<"\n";
 Evaluator ev(network,arena);ev.configure(input_op,output_op);
 if(stdio){Session s{Board(),ev,[](const std::string& str){std::cout<<str<<'\n'<<std::flush;}};std::string line;while(std::getline(std::cin,line)){try{s.command(line);}catch(const std::exception& e){s.send(std::string("info string ERROR ")+e.what());std::cerr<<"ERROR "<<e.what()<<'\n';}if(line=="quit")break;}return 0;}
#ifdef _WIN32
 WSADATA wsa;if(WSAStartup(MAKEWORD(2,2),&wsa)!=0)throw std::runtime_error("WSAStartup failed");
#endif
 sock_t server=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);if(server==badsock)throw std::runtime_error("socket failed");
 sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(static_cast<unsigned short>(port));if(inet_pton(AF_INET,host.c_str(),&addr.sin_addr)!=1)throw std::runtime_error("--host must be numeric IPv4");
 int opt=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,reinterpret_cast<const char*>(&opt),sizeof(opt));
 if(bind(server,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))!=0||listen(server,4)!=0)throw std::runtime_error("bind/listen failed");
 std::cerr<<"TCP LISTEN "<<host<<":"<<port<<"\n";
 for(;;){sock_t client=accept(server,nullptr,nullptr);if(client==badsock)continue;std::cerr<<"TCP CONNECT\n";
  Session session{Board(),ev,[client](const std::string& str){auto msg=str+"\n";const char* ptr=msg.data();size_t left=msg.size();while(left){const auto chunk=static_cast<int>((std::min)(left,static_cast<size_t>((std::numeric_limits<int>::max)())));auto n=send(client,ptr,chunk,0);if(n<=0)throw std::runtime_error("socket send failed");ptr+=n;left-=static_cast<size_t>(n);}}};
  std::string pending;char buff[4096];bool done=false;
  while(!done){auto n=recv(client,buff,static_cast<int>(sizeof(buff)),0);if(n<=0)break;pending.append(buff,static_cast<size_t>(n));
   while(true){auto at=pending.find('\n');if(at==std::string::npos)break;std::string line=pending.substr(0,at);pending.erase(0,at+1);if(!line.empty()&&line.back()=='\r')line.pop_back();
    try{session.command(line);}catch(const std::exception& e){std::cerr<<"UCI ERROR "<<e.what()<<'\n';try{session.send(std::string("info string ERROR ")+e.what());}catch(...){done=true;}}
    if(line=="quit"){done=true;break;}
   }
   if(pending.size()>65536){std::cerr<<"UCI oversized line\n";break;}
  }
  closesock(client);std::cerr<<"TCP DISCONNECT\n";
 }
 }catch(const std::exception& e){std::cerr<<"FATAL "<<e.what()<<'\n';return 1;}
}
