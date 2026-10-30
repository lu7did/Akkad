#include "board.hpp"
#include "engine.hpp"
#include "grumpy.hpp"
#include <chrono>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <fstream>
#include <filesystem>
#include <cctype>
#include <map>
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
 const char* primary="debian";
#endif
 for(const char* k:{primary,"linux","default"}){
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
 for(const fs::path& base:{file,file/"scripts",file.parent_path()/"scripts"}){
  auto candidate=(base/path).lexically_normal();if(fs::is_regular_file(candidate))return candidate.string();
 }
 throw std::runtime_error("brains.json: no existe network para "+brain+": "+network);
}
std::string weights_argument(int argc,char** argv){
 std::string weights,brains,brain="tinySargon";
 for(int i=1;i<argc;++i){std::string a=argv[i];
  if(a=="--brains"||a=="--brain"||a=="--weights"){
   if(++i>=argc)throw std::runtime_error("falta valor para "+a);
   if(a=="--brains")brains=argv[i];else if(a=="--brain")brain=argv[i];else weights=argv[i];
  }else if(!a.empty()&&a[0]=='-')throw std::runtime_error("opcion desconocida: "+a);
  else if(weights.empty())weights=a;
  else throw std::runtime_error("argumentos de pesos duplicados");
 }
 if(!weights.empty())return weights;
 if(!brains.empty())return get_weights_from_brains(brains,brain);
 throw std::runtime_error("uso: picoSargon.exe <grumpy.bin> | --weights <grumpy.bin> | --brains <brains.json> [--brain tinySargon]");
}
}

using namespace picoSargon;
static uint64_t milliseconds(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
int main(int argc,char**argv){
 try{
  const auto weights=weights_argument(argc,argv);
  Grumpy net;net.load(weights);Board board;
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
