// picoSargon Debian native TCP/UCI gateway v0.2.51
// One child engine per client. stdout is wired directly to the TCP socket;
// stderr is inherited by the listener and remains diagnostic-only.
#include <arpa/inet.h>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <filesystem>
#include <iostream>
#include <map>
#include <netinet/in.h>
#include <string>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

#ifndef PICOSARGON_VERSION
#define PICOSARGON_VERSION "0.2.51"
#endif
namespace {
volatile sig_atomic_t stopping=0;
void signal_stop(int){stopping=1;}
void signal_chld(int){} // Interrupt select; reap in the main loop.
std::string stamp(){
 std::time_t now=std::time(nullptr);std::tm t{};localtime_r(&now,&t);
 char b[16];std::strftime(b,sizeof(b),"%H:%M:%S",&t);return b;
}
void log(const char* symbol,const std::string& line){
 std::fprintf(stderr,"[%s] %s %s\n",stamp().c_str(),symbol,line.c_str());
 std::fflush(stderr);
}
int number(const std::string& arg,const char* name,int min,int max){
 if(arg.empty()||arg.find_first_not_of("0123456789")!=std::string::npos)
  throw std::runtime_error(std::string("invalid ")+name);
 const auto value=std::stoll(arg);
 if(value<min||value>max)throw std::runtime_error(std::string("invalid ")+name);
 return static_cast<int>(value);
}
struct Options {
 std::string host="0.0.0.0",engine,weights,brains,brain="tinySargon";
 int port=6200,depth=-1,qdepth=-1,timeout=-1,cores=-1;
};
void usage(){
 std::cout<<"picoSargon Debian UCI/TCP v"<<PICOSARGON_VERSION<<" (native C++, no Python)\n"
  <<"Usage: picoSargon_listen [--host IP] [--port 6200] --engine PATH "
  <<"[--weights FILE | --brains FILE --brain NAME] "
  <<"[--depth N] [--qdepth N] [--timeout MS] "
#ifdef PICOSARGON_MULTICORE
  <<"--cores N "
#endif
  <<"[--help]\nDefault host: 0.0.0.0; port: 6200.\n";
}
Options parse(int argc,char**argv){
 Options o;
 for(int i=1;i<argc;i++){
  std::string k=argv[i];if(k=="--help"||k=="-h"){usage();std::exit(0);}
  if(++i>=argc)throw std::runtime_error("missing value for "+k);
  std::string v=argv[i];
  if(k=="--host")o.host=v;
  else if(k=="--port")o.port=number(v,"--port",1,65535);
  else if(k=="--engine")o.engine=v;
  else if(k=="--weights")o.weights=v;
  else if(k=="--brains")o.brains=v;
  else if(k=="--brain")o.brain=v;
  else if(k=="--depth")o.depth=number(v,"--depth",1,40);
  else if(k=="--qdepth")o.qdepth=number(v,"--qdepth",0,32);
  else if(k=="--timeout")o.timeout=number(v,"--timeout",1,2147483647);
  else if(k=="--cores")o.cores=number(v,"--cores",1,1024);
  else throw std::runtime_error("unknown option: "+k);
 }
 if(o.engine.empty()||(!o.weights.empty()&&!o.brains.empty())||(o.weights.empty()&&o.brains.empty()))
  throw std::runtime_error("--engine and exactly one of --weights/--brains are required");
#ifdef PICOSARGON_MULTICORE
 if(o.cores<1)throw std::runtime_error("MULTICORE=ON: --cores N required");
#else
 if(o.cores!=-1)throw std::runtime_error("MULTICORE=OFF: --cores is not accepted");
#endif
 if(!std::filesystem::is_regular_file(o.engine))throw std::runtime_error("engine not found: "+o.engine);
 if(!o.weights.empty()&&!std::filesystem::is_regular_file(o.weights))throw std::runtime_error("NNUE not found: "+o.weights);
 if(!o.brains.empty()&&!std::filesystem::is_regular_file(o.brains))throw std::runtime_error("brains not found: "+o.brains);
 return o;
}
std::vector<std::string> engine_args(const Options& o){
 std::vector<std::string> a{o.engine};
 if(!o.weights.empty()){a.push_back("--weights");a.push_back(o.weights);}
 if(!o.brains.empty()){a.push_back("--brains");a.push_back(o.brains);a.push_back("--brain");a.push_back(o.brain);}
 for(auto p: {std::make_pair(o.depth,"--depth"),{o.qdepth,"--qdepth"},{o.timeout,"--timeout"},{o.cores,"--cores"}})
  if(p.first>=0){a.emplace_back(p.second);a.push_back(std::to_string(p.first));}
 return a;
}
void reap(std::map<pid_t,std::string>& clients){
 int status=0;pid_t pid;
 while((pid=waitpid(-1,&status,WNOHANG))>0){
  auto it=clients.find(pid);if(it!=clients.end()){
   log("❌","Client disconnected fm "+it->second);clients.erase(it);
  }
 }
}
} // namespace
int main(int argc,char**argv){
 try {
  auto o=parse(argc,argv);auto args=engine_args(o);
  // Resolve executable and file paths before starting sessions, since cwd can vary.
  for(size_t i=0;i<args.size();i++)if(i==0 || (i>0&&(args[i-1]=="--weights"||args[i-1]=="--brains")))
   args[i]=std::filesystem::absolute(args[i]).string();
  int sock=socket(AF_INET,SOCK_STREAM,0);
  if(sock<0)throw std::runtime_error(std::strerror(errno));
  int yes=1;setsockopt(sock,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes));
  sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(static_cast<uint16_t>(o.port));
  if(inet_pton(AF_INET,o.host.c_str(),&addr.sin_addr)!=1){close(sock);throw std::runtime_error("invalid IPv4 host");}
  if(bind(sock,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))!=0){
   auto err=std::string(std::strerror(errno));close(sock);throw std::runtime_error("bind: "+err);
  }
  if(listen(sock,32)!=0){close(sock);throw std::runtime_error("listen failed");}
  struct sigaction sa{};sa.sa_handler=signal_stop;sigemptyset(&sa.sa_mask);
  sigaction(SIGINT,&sa,nullptr);sigaction(SIGTERM,&sa,nullptr);
  struct sigaction sc{};sc.sa_handler=signal_chld;sigemptyset(&sc.sa_mask);sigaction(SIGCHLD,&sc,nullptr);
  signal(SIGPIPE,SIG_IGN);
  log("💻",std::string("picoSargon Debian UCI/TCP v")+PICOSARGON_VERSION);
  log("⚙️",std::string("Motor: ")+args[0]);
  log("⚙️",std::string("NNUE: ")+(o.weights.empty()?"from brains.json":o.weights));
#ifdef PICOSARGON_MULTICORE
  log("⚙️","MULTICORE=True CORE="+std::to_string(o.cores));
#else
  log("⚙️","MULTICORE=False CORE=1");
#endif
  log("🌐","Listener started TCP "+o.host+":"+std::to_string(o.port));
  std::map<pid_t,std::string> clients;
  while(!stopping){
   reap(clients);
   fd_set readfds;FD_ZERO(&readfds);FD_SET(sock,&readfds);
   timeval tv{0,300000};int ready=select(sock+1,&readfds,nullptr,nullptr,&tv);
   if(ready<0){if(errno==EINTR)continue;log("❌",std::string("select error: ")+std::strerror(errno));break;}
   if(ready==0)continue;
   sockaddr_in remote{};socklen_t length=sizeof(remote);
   int conn=accept(sock,reinterpret_cast<sockaddr*>(&remote),&length);
   if(conn<0){if(errno==EINTR)continue;log("❌","accept failed");continue;}
   char ip[INET_ADDRSTRLEN]{};inet_ntop(AF_INET,&remote.sin_addr,ip,sizeof(ip));
   std::string endpoint=std::string(ip)+":"+std::to_string(ntohs(remote.sin_port));
   pid_t pid=fork();
   if(pid<0){close(conn);log("❌","fork failed");continue;}
   if(pid==0){
    // Child: client socket becomes UCI stdin/stdout, stderr remains diagnostic.
    close(sock);
    if(dup2(conn,STDIN_FILENO)<0||dup2(conn,STDOUT_FILENO)<0)_exit(126);
    if(conn>STDERR_FILENO)close(conn);
    std::vector<char*> av;av.reserve(args.size()+1);
    for(auto& s:args) av.push_back(const_cast<char*>(s.c_str()));
    av.push_back(nullptr);
    execv(av[0],av.data());
    std::fprintf(stderr,"picoSargon exec failed: %s\n",std::strerror(errno));_exit(127);
   }
   close(conn);clients.emplace(pid,endpoint);log("✅","Client connected fm "+endpoint);
  }
  close(sock);
  for(auto& entry:clients)kill(entry.first,SIGTERM);
  for(auto& entry:clients)waitpid(entry.first,nullptr,0);
  log("🌐","Listener detenido");return 0;
 }catch(const std::exception& e){log("❌",e.what());return 1;}
}
