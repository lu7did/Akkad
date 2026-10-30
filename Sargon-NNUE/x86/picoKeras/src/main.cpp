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
#include <ctime>
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
 for(const Move& m:moves){board.push(m);double v;
  try{if(terminal(board,v))++r.terminal_count;else v=eval.eval(board);}
  catch(...){board.pop();throw;}
  board.pop();++r.inspected;
  // The model estimates the position for the side to move, i.e. the opponent after our move.
  if(!r.found||v<lowest){r.found=true;r.move=m;r.rival_value=v;lowest=v;}
 }
 r.ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-st).count();return r;
}
static void position(Board& b,const std::string& command){
 Board candidate=b;
 auto cut=command.find(" moves ");std::string base=command.substr(9,cut==std::string::npos?std::string::npos:cut-9);
 if(base=="startpos")candidate.reset();else if(base.rfind("fen ",0)==0)candidate.set_fen(base.substr(4));else throw std::runtime_error("invalid position");
 if(cut!=std::string::npos){std::istringstream ms(command.substr(cut+7));std::string token;while(ms>>token){
   Move parsed=candidate.parse(token);
   std::vector<Move> legal;candidate.legal(legal);
   if(std::find(legal.begin(),legal.end(),parsed)==legal.end())throw std::runtime_error("illegal UCI move: "+token);
   candidate.push(parsed);
  }}
 b=std::move(candidate);
}
static constexpr const char* ENGINE_VERSION="0.1.20";
static std::string engine_name="picoKeras";
static std::string timestamp(){
 auto t=std::time(nullptr);std::tm tm{};
#ifdef _WIN32
 localtime_s(&tm,&t);
#else
 localtime_r(&t,&tm);
#endif
 char out[16];std::strftime(out,sizeof(out),"%H:%M:%S",&tm);return out;
}
static void notice(const std::string& icon,const std::string& text){std::cerr<<timestamp()<<" "<<icon<<" [picoKeras] "<<text<<"\n";}
struct Session {
 Board b;Evaluator& eval;std::function<void(const std::string&)> send;
 void command(const std::string& line){
  if(line=="uci"){send("id name "+engine_name+" v"+ENGINE_VERSION);send("id author Dr. Pedro E. Colla 2026");notice("🤝","UCI handshake");send("uciok");}
  else if(line=="isready")send("readyok");
  else if(line=="ucinewgame")b.reset();
  else if(line.rfind("position ",0)==0)position(b,line);
  else if(line.rfind("go",0)==0){auto r=choose(b,eval);
   std::ostringstream info;
   // Score desde la perspectiva del bando que mueve, centipeones aproximados.
   const int score=static_cast<int>(std::lround((-r.rival_value)*100.0));
   info<<"info time "<<r.ms<<" nodes "<<r.inspected<<" score cp "<<score;
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
 std::string network,host="0.0.0.0";int port=6110;bool stdio=false;size_t arena=32*1024*1024;
 for(int i=1;i<argc;++i){std::string k=argv[i];auto value=[&](){if(i+1>=argc)throw std::runtime_error("missing value for "+k);return std::string(argv[++i]);};
  if(k=="--network")network=value();else if(k=="--host")host=value();else if(k=="--port")port=std::stoi(value());else if(k=="--arena")arena=std::stoull(value());else if(k=="--stdio")stdio=true;
  else if(k=="--name")engine_name=value();else if(k=="--help"){std::cout<<"picoKeras 0.1.20 --network model.tflite [--host 0.0.0.0] [--port 6110] [--arena BYTES] [--stdio] [--name picoKeras]\nFP32 or INT8 TFLite FlatBuffer, scalar value network, searchless 1ply.\n";return 0;}
  else throw std::runtime_error("unknown argument: "+k);
 }
 if(network.empty()||port<1||port>65535)throw std::runtime_error("--network required, --port must be 1..65535");
 notice("🚀",engine_name+" v"+ENGINE_VERSION+" | Dr. Pedro E. Colla 2026");
 notice("🧠","Network "+network+" | "+(stdio?"STDIO":"TCP"));
 Evaluator ev(network,arena);
 if(stdio){Session s{Board(),ev,[](const std::string& str){std::cout<<str<<'\n'<<std::flush;}};std::string line;while(std::getline(std::cin,line)){try{s.command(line);}catch(const std::exception& e){s.send(std::string("info string ERROR ")+e.what());notice("❌",e.what());}if(line=="quit")break;}return 0;}
#ifdef _WIN32
 WSADATA wsa;if(WSAStartup(MAKEWORD(2,2),&wsa)!=0)throw std::runtime_error("WSAStartup failed");
#endif
 sock_t server=socket(AF_INET,SOCK_STREAM,IPPROTO_TCP);if(server==badsock)throw std::runtime_error("socket failed");
 sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(static_cast<unsigned short>(port));if(inet_pton(AF_INET,host.c_str(),&addr.sin_addr)!=1)throw std::runtime_error("--host must be numeric IPv4");
 int opt=1;setsockopt(server,SOL_SOCKET,SO_REUSEADDR,reinterpret_cast<const char*>(&opt),sizeof(opt));
 if(bind(server,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))!=0||listen(server,4)!=0)throw std::runtime_error("bind/listen failed");
 notice("📡","TCP listen "+host+":"+std::to_string(port));
 for(;;){sock_t client=accept(server,nullptr,nullptr);if(client==badsock)continue;notice("🔌","TCP connected");
  Session session{Board(),ev,[client](const std::string& str){auto msg=str+"\n";const char* ptr=msg.data();size_t left=msg.size();while(left){const auto chunk=static_cast<int>((std::min)(left,static_cast<size_t>((std::numeric_limits<int>::max)())));auto n=send(client,ptr,chunk,0);if(n<=0)throw std::runtime_error("socket send failed");ptr+=n;left-=static_cast<size_t>(n);}}};
  std::string pending;char buff[4096];bool done=false;
  while(!done){auto n=recv(client,buff,static_cast<int>(sizeof(buff)),0);if(n<=0)break;pending.append(buff,static_cast<size_t>(n));
   while(true){auto at=pending.find('\n');if(at==std::string::npos)break;std::string line=pending.substr(0,at);pending.erase(0,at+1);if(!line.empty()&&line.back()=='\r')line.pop_back();
    try{session.command(line);}catch(const std::exception& e){notice("❌",e.what());try{session.send(std::string("info string ERROR ")+e.what());}catch(...){done=true;}}
    if(line=="quit"){done=true;break;}
   }
   if(pending.size()>65536){notice("⚠️","UCI oversized line");break;}
  }
  closesock(client);notice("🔌","TCP disconnected");
 }
 }catch(const std::exception& e){notice("❌",std::string("FATAL ")+e.what());return 1;}
}
