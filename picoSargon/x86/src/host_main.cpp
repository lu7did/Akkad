#include "board.hpp"
#include "engine.hpp"
#include "grumpy.hpp"
#include <chrono>
#include <ctime>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <fstream>
#include <filesystem>
#include <cctype>
#include <map>
#include <iomanip>
#include <algorithm>
#ifdef PICOSARGON_MULTICORE
#include <thread>
#include <set>
#if defined(__APPLE__)
#include <sys/types.h>
#elif defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#else
#include <fstream>
#endif
#endif
#if defined(__APPLE__)
#include <sys/sysctl.h>
#endif
#ifndef PICOSARGON_VERSION
#define PICOSARGON_VERSION "0.2.50"
#endif
// Minimal JSON reader restricted to strings/objects/arrays and scalar skipping.
// No LC0 dependency; only retrieves brains[brain]["network"].
namespace {
struct JsonCursor {
 const std::string& s; size_t i=0;
 void ws(){while(i<s.size() && std::isspace(static_cast<unsigned char>(s[i])))++i;}
 void expect(char c){ws();if(i>=s.size()||s[i]!=c)throw std::runtime_error("brains.json: formato JSON incorrecto");++i;}
 std::string str(){expect('"');std::string out;bool closed=false;
  while(i<s.size()){char c=s[i++];if(c=='"'){closed=true;break;}if(c=='\\'){
    if(i>=s.size())throw std::runtime_error("brains.json: escape incompleto");
    c=s[i++];switch(c){case 'n':c='\n';break;case 't':c='\t';break;case 'r':c='\r';break;
      case '"':break;case '\\':break;case '/':break;
      case 'u':throw std::runtime_error("brains.json: escape unicode no soportado en rutas");
      default:throw std::runtime_error("brains.json: escape invalido");}
  }out+=c;}if(!closed)throw std::runtime_error("brains.json: cadena incompleta");return out;}
 void skip(){ws();if(i>=s.size())throw std::runtime_error("brains.json: valor incompleto");
  if(s[i]=='"'){str();return;}
  if(s[i]=='{'||s[i]=='['){char open=s[i++],close=open=='{'?'}':']';ws();
   if(i<s.size()&&s[i]==close){++i;return;}
   while(true){ws();if(i>=s.size())throw std::runtime_error("brains.json: estructura incompleta");
    if(open=='{'){str();expect(':');}skip();ws();
    if(i<s.size()&&s[i]==close){++i;break;}expect(',');}
   return;}
  size_t start=i;while(i<s.size()&&s[i]!=','&&s[i]!=']'&&s[i]!='}'&&!std::isspace(static_cast<unsigned char>(s[i])))++i;
  if(start==i)throw std::runtime_error("brains.json: valor invalido");
 }
 // Reads one exact string key from object; leaves cursor at value if found.
 bool key(const std::string& wanted){expect('{');ws();if(i<s.size()&&s[i]=='}'){++i;return false;}
  while(true){auto k=str();expect(':');if(k==wanted)return true;skip();ws();
   if(i<s.size()&&s[i]=='}'){++i;return false;}expect(',');}
 }
};
std::string platform_path(JsonCursor& j){
 j.ws(); if(j.i>=j.s.size())throw std::runtime_error("brains.json: network incompleta");
 if(j.s[j.i]=='"')return j.str();
 if(j.s[j.i]!='{')throw std::runtime_error("brains.json: network debe ser cadena u objeto");
 j.expect('{');std::map<std::string,std::string> paths;
 j.ws();if(j.i<j.s.size()&&j.s[j.i]=='}')++j.i;
 else while(true){auto k=j.str();j.expect(':');paths[k]=j.str();j.ws();
  if(j.i<j.s.size()&&j.s[j.i]=='}'){++j.i;break;}j.expect(',');}
#ifdef _WIN32
 const char* primary="windows";
#else
 #if defined(__APPLE__)
 const char* primary="macos";
#else
 const char* primary="debian";
#endif
#endif
 #if defined(__APPLE__)
 for(const char* k:{"macos","darwin","default"})
#else
 for(const char* k:{primary,"linux","default"})
#endif
 {
  auto it=paths.find(k);if(it!=paths.end()&&!it->second.empty())return it->second;
 }
 throw std::runtime_error(std::string("brains.json: falta network para plataforma ")+primary);
}
std::string get_weights_from_brains(const std::string& filename,const std::string& brain){
 std::ifstream in(filename,std::ios::binary);if(!in)throw std::runtime_error("no se puede abrir brains.json: "+filename);
 std::string contents((std::istreambuf_iterator<char>(in)),std::istreambuf_iterator<char>());
 JsonCursor j{contents};if(!j.key("brains")||!j.key(brain)||!j.key("network"))
  throw std::runtime_error("brains.json: falta brains."+brain+".network");
 const auto network=platform_path(j);if(network.empty())throw std::runtime_error("brains.json: network vacio");
 namespace fs=std::filesystem;fs::path path(network);
 if(path.is_absolute())return path.string();
 // Prefer the original working-directory convention used by Sargon-NNUE scripts.
 if(fs::is_regular_file(path))return fs::absolute(path).string();
 fs::path file=fs::absolute(filename).parent_path();
 for(const fs::path& base:{file,file/"scripts",file.parent_path()/"scripts",file.parent_path().parent_path()/"src"}){
  auto candidate=(base/path).lexically_normal();if(fs::is_regular_file(candidate))return candidate.string();
 }
 throw std::runtime_error("brains.json: no existe network para "+brain+": "+network);
}
struct HostOptions {
 std::string weights, brains, brain="tinySargon";
 int depth=4, qdepth=2;
 uint64_t timeout=15000;
#ifdef PICOSARGON_MULTICORE
 unsigned cores=2;
#endif
};
int checked_number(const std::string& raw,const std::string& name,int lo,int hi){
 if(raw.empty()||raw.find_first_not_of("0123456789")!=std::string::npos)
  throw std::runtime_error(name+" debe ser un entero decimal");
 unsigned long long v=0;
 try{v=std::stoull(raw);}catch(const std::exception&){throw std::runtime_error(name+" fuera de rango");}
 if(v<static_cast<unsigned>(lo)||v>static_cast<unsigned>(hi))
  throw std::runtime_error(name+" fuera de rango "+std::to_string(lo)+".."+std::to_string(hi));
 return static_cast<int>(v);
}
// Read one numeric field from the selected brain. A missing/null field is ignored.
// A fresh cursor is required because JsonCursor::key consumes preceding properties.
bool brain_number(const std::string& contents,const std::string& brain,const std::string& field,int& value){
 JsonCursor j{contents};
 if(!j.key("brains")||!j.key(brain)||!j.key(field))return false;
 j.ws();const auto first=j.i;
 while(j.i<j.s.size()&&std::isdigit(static_cast<unsigned char>(j.s[j.i])))++j.i;
 if(first==j.i){
  if(j.s.compare(j.i,4,"null")==0)return false;
  throw std::runtime_error("brains.json: "+field+" debe ser un numero entero");
 }
 const auto raw=j.s.substr(first,j.i-first);
 const int lo=field=="qdepth"?0:1;
 const int hi=field=="depth"?40:(field=="qdepth"?32:2147483647);
 value=checked_number(raw,"brains.json "+field,lo,hi);
 j.ws();if(j.i<j.s.size()&&j.s[j.i]!=','&&j.s[j.i]!='}')
  throw std::runtime_error("brains.json: numero invalido en "+field);
 return true;
}
HostOptions parse_options(int argc,char** argv){
 HostOptions opt;
 bool cliDepth=false,cliQdepth=false,cliTimeout=false;
 for(int i=1;i<argc;++i){const std::string a=argv[i];
  if(a=="--help"||a=="-h"){
   std::cout<<"picoSargon v"<<PICOSARGON_VERSION<<"\n";
   std::cout<<"Uso: picoSargon --weights <grumpy.bin> [--depth 1..40] [--qdepth 0..32] [--timeout MS]";
#ifdef PICOSARGON_MULTICORE
   std::cout<<" [--cores 1..1024]";
#endif
   std::cout<<"\n       picoSargon --brains <brains.json> [--brain tinySargon] [mismas opciones]\n";
   std::cout<<"Prioridad: argumentos > brains.json > defaults; go depth/movetime y setoption QDepth prevalecen.\n";
   std::exit(0);
  }
  if(a=="--depth"||a=="--qdepth"||a=="--timeout"||a=="--brain"||a=="--brains"||a=="--weights"
#ifdef PICOSARGON_MULTICORE
   ||a=="--cores"
#endif
   ){
   if(++i>=argc)throw std::runtime_error("falta valor para "+a);
   const std::string value=argv[i];
   if(a=="--depth"){opt.depth=checked_number(value,a,1,40);cliDepth=true;}
   else if(a=="--qdepth"){opt.qdepth=checked_number(value,a,0,32);cliQdepth=true;}
   else if(a=="--timeout"){opt.timeout=static_cast<uint64_t>(checked_number(value,a,1,2147483647));cliTimeout=true;}
   else if(a=="--brain")opt.brain=value;
   else if(a=="--brains")opt.brains=value;
   else if(a=="--weights")opt.weights=value;
#ifdef PICOSARGON_MULTICORE
   else if(a=="--cores")opt.cores=static_cast<unsigned>(checked_number(value,a,1,1024));
#endif
  }else if(!a.empty()&&a[0]=='-')throw std::runtime_error("opcion desconocida: "+a);
  else if(opt.weights.empty())opt.weights=a;
  else throw std::runtime_error("argumentos de pesos duplicados");
 }
 if(!opt.brains.empty()){
  std::ifstream in(opt.brains,std::ios::binary);
  if(!in)throw std::runtime_error("no se puede abrir brains.json: "+opt.brains);
  const std::string contents((std::istreambuf_iterator<char>(in)),std::istreambuf_iterator<char>());
  int value=0;
  if(!cliDepth&&brain_number(contents,opt.brain,"depth",value))opt.depth=value;
  if(!cliQdepth&&brain_number(contents,opt.brain,"qdepth",value))opt.qdepth=value;
  if(!cliTimeout){
   if(brain_number(contents,opt.brain,"timeout",value)||brain_number(contents,opt.brain,"tmax",value))
    opt.timeout=static_cast<uint64_t>(value);
  }
  if(opt.weights.empty())opt.weights=get_weights_from_brains(opt.brains,opt.brain);
 }
 if(opt.weights.empty())throw std::runtime_error("falta --weights <red> o --brains <brains.json>; usar --help");
 return opt;
}
}


namespace {
std::string trim_uci(std::string x) {
 auto b=x.find_first_not_of(" \t\r\n");
 if(b==std::string::npos)return {};
 auto e=x.find_last_not_of(" \t\r\n");
 x=x.substr(b,e-b+1);
 if(x.size()>=2 && x.front()=='"' && x.back()=='"')x=x.substr(1,x.size()-2);
 for(char& c:x)if(c=='\n'||c=='\r')c=' ';
 return x;
}
std::string system_release(){
#ifdef _WIN32
 return "Windows";
#elif defined(__APPLE__)
 char name[256]; size_t len=sizeof(name);
 if(sysctlbyname("kern.osproductversion",name,&len,nullptr,0)==0) return std::string("macOS ")+name;
 return "macOS";
#else
 std::ifstream in("/etc/os-release");
 std::string line;
 while(std::getline(in,line)){
  constexpr const char* k="PRETTY_NAME=";
  if(line.compare(0,12,k)==0)return trim_uci(line.substr(12));
 }
 return "Linux";
#endif
}
std::string total_memory(){
#ifdef _WIN32
 // Keep the Windows identifier stable without introducing new OS dependencies.
 return "RAM n/d";
#elif defined(__APPLE__)
 uint64_t bytes=0;size_t size=sizeof(bytes);
 if(sysctlbyname("hw.memsize",&bytes,&size,nullptr,0)==0){
  std::ostringstream os;os<<std::fixed<<std::setprecision(2)<<(static_cast<double>(bytes)/1073741824.0)<<" GiB RAM";return os.str();
 }
 return "RAM n/d";
#else
 std::ifstream in("/proc/meminfo");
 std::string name,unit;unsigned long long kib=0;
 while(in>>name>>kib>>unit){
  if(name=="MemTotal:"){
   std::ostringstream os;os<<std::fixed<<std::setprecision(2)<<(static_cast<double>(kib)/1048576.0)<<" GiB RAM";
   return os.str();
  }
 }
 return "RAM n/d";
#endif
}
std::string uci_identity(){
#ifdef _WIN32
 return std::string("picoSargon C++ v")+PICOSARGON_VERSION+" (Windows)";
#else
 #if defined(__APPLE__)
 return std::string("picoSargon C++ v")+PICOSARGON_VERSION+" ("+system_release()+" / "+total_memory()+")";
#else
 return std::string("picoSargon C++ v")+PICOSARGON_VERSION+" (debian "+system_release()+" / "+total_memory()+")";
#endif
#endif
}
}

using namespace picoSargon;
#ifdef PICOSARGON_MULTICORE
namespace {
unsigned physical_cores(){
#if defined(__APPLE__)
 int n=0;size_t length=sizeof(n);
 if(sysctlbyname("hw.physicalcpu",&n,&length,nullptr,0)==0&&n>0)return static_cast<unsigned>(n);
#elif defined(_WIN32)
 DWORD bytes=0;GetLogicalProcessorInformation(nullptr,&bytes);
 if(bytes){std::vector<unsigned char> buffer(bytes);
  auto* info=reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION>(buffer.data());
  if(GetLogicalProcessorInformation(info,&bytes)){
   unsigned n=0;for(DWORD i=0;i<bytes/sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION);++i)
    if(info[i].Relationship==RelationProcessorCore)++n;
   if(n)return n;
  }}
#else
 // Linux sysfs topology: one distinct (package, core) pair per physical core.
 std::set<std::pair<int,int>> topology;
 const unsigned logical=std::max(1u,std::thread::hardware_concurrency());
 for(unsigned i=0;i<logical*4&&i<4096;++i){
  const std::string dir="/sys/devices/system/cpu/cpu"+std::to_string(i)+"/topology/";
  std::ifstream core(dir+"core_id"),package(dir+"physical_package_id");int c,p=0;
  if(core>>c){if(!(package>>p))p=0;topology.insert({p,c});}
 }
 if(!topology.empty())return static_cast<unsigned>(topology.size());
#endif
 return std::max(1u,std::thread::hardware_concurrency());
}
}
#endif
static uint64_t milliseconds(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){
 try{
#ifdef PICOSARGON_MULTICORE
  const HostOptions options=parse_options(argc,argv);
  unsigned cores=options.cores;
  const auto& weights=options.weights;
#else
  const HostOptions options=parse_options(argc,argv);
  const auto& weights=options.weights;
#endif
  Grumpy net;net.load(weights);Board board;
#ifdef __APPLE__
  std::cerr << "[picoSargon " << PICOSARGON_VERSION
            << "] macOS UCI/stdin iniciado; red=" << weights
            << "; TCP=no (usar picoSargon/tools/macos/run_listen.sh para escuchar)" << std::endl;
#endif
  int qdepth=options.qdepth;std::string line;
  while(std::getline(std::cin,line)){
   std::istringstream ss(line);std::string cmd;ss>>cmd;
   if(cmd=="uci"){
    std::cout<<"id name "<<uci_identity()<<"\nid author Dr. Pedro E. Colla\noption name QDepth type spin default "<<qdepth<<" min 0 max 32\n"
#ifdef PICOSARGON_MULTICORE
             <<"option name Cores type spin default 2 min 1 max 1024\n"
#endif
             <<"uciok\n";
   }else if(cmd=="isready")std::cout<<"readyok\n";
   else if(cmd=="setoption"){
    std::string name,parameter,value;ss>>name>>parameter>>value;
#ifdef PICOSARGON_MULTICORE
    if(name=="name"&&parameter=="Cores"&&value=="value"){
     int next;if(ss>>next&&next>=1&&next<=1024)cores=static_cast<unsigned>(next);
    }
#endif
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
    int depth=options.depth;uint64_t timelimit=options.timeout;std::string t;
    while(ss>>t){if(t=="depth")ss>>depth;else if(t=="movetime")ss>>timelimit;}
    if(depth<1||depth>40)throw std::runtime_error("depth out of range");
    if(timelimit==0||timelimit>2147483647ULL)throw std::runtime_error("movetime fuera de rango");
    Engine engine(net,milliseconds,[]{return false;},{},qdepth);
    const auto search_start=std::chrono::steady_clock::now();
#ifdef PICOSARGON_MULTICORE
    auto result=cores>1?engine.search_parallel(board,depth,timelimit,std::min(cores,physical_cores())):engine.search(board,depth,timelimit);
#else
    auto result=engine.search(board,depth,timelimit);
#endif
    const auto elapsed_ms=std::chrono::duration_cast<std::chrono::milliseconds>(
      std::chrono::steady_clock::now()-search_start).count();
    const int ply=2*(board.fullmove-1)+(board.turn==-1?1:0);
    const int white_cp=(board.turn==1?result.score:-result.score);
    const auto nps=elapsed_ms>0 ? (result.nodes*1000ULL/static_cast<unsigned long long>(elapsed_ms)) : 0ULL;
    // Build once. Only these two unadorned lines enter UCI stdout.
    std::ostringstream info_line;
    info_line<<"info ply "<<ply<<" depth "<<result.depth<<" score cp "<<white_cp
             <<" nodes "<<result.nodes<<" time "<<elapsed_ms<<" nps "<<nps;
    const std::string best_line="bestmove "+(result.has_move?Board::notation(result.best):"0000");
    // Worker telemetry was printed to stderr by the coordinator before
    // search_parallel returned. Publish these human diagnostics on the SAME
    // stderr stream, preserving core[] -> info -> bestmove order.
    const auto diagnostic=[&](const std::string& text){
      std::time_t now=std::time(nullptr);std::tm tm{};
#if defined(_WIN32)
      localtime_s(&tm,&now);
#else
      localtime_r(&now,&tm);
#endif
      char stamp[16]{};
      std::strftime(stamp,sizeof(stamp),"%H:%M:%S",&tm);
      std::fprintf(stderr,"[%s] 🧠 %s\n",stamp,text.c_str());
      std::fflush(stderr);
    };
    diagnostic(info_line.str());
    diagnostic(best_line);
    std::cout<<info_line.str()<<"\n";
    std::cout<<best_line<<"\n";
   }else if(cmd=="quit")break;
   std::cout.flush();
  }
  return 0;
 }catch(const std::exception& e){std::cerr<<"picoSargon host fatal: "<<e.what()<<"\n";return 1;}
}
