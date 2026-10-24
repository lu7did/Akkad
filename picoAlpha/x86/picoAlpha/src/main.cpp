#include "net.hpp"
#ifdef PICOALPHA_HAS_PICOGYAL

#endif
#include <chrono>
#include <iostream>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <memory>
#include <deque>
#include <stdexcept>
#include <iomanip>
using namespace picoSargon;
using namespace picoalpha;
// Keep TinyGyal external pb.gz the Windows default; picoGyal is embedded INT8.
class EngineNetwork {
 std::unique_ptr<picoalpha::Network> tiny_;
 struct CacheEntry {uint64_t h1=0,h2=0,stamp=0;picoalpha::Result value;};
 mutable std::array<CacheEntry,8> cache_{};
 mutable uint64_t clock_=0;
 static uint64_t fnv(const void* p,size_t n,uint64_t h){
  const auto* b=static_cast<const unsigned char*>(p);
  for(size_t i=0;i<n;++i){h^=b[i];h*=UINT64_C(1099511628211);}return h;
 }
 static std::pair<uint64_t,uint64_t> cache_key(const std::array<float,112*64>& planes,const picoSargon::Board& board){
  const auto position=board.position_key();
  uint64_t a=fnv(planes.data(),planes.size()*sizeof(float),UINT64_C(14695981039346656037));
  uint64_t b=fnv(planes.data(),planes.size()*sizeof(float),UINT64_C(7809847782465536322));
  a=fnv(position.cells.data(),position.cells.size(),a);b=fnv(position.cells.data(),position.cells.size(),b);
  a=fnv(&position.turn,sizeof(position.turn),a);b=fnv(&position.turn,sizeof(position.turn),b);
  a=fnv(&position.castling,sizeof(position.castling),a);b=fnv(&position.castling,sizeof(position.castling),b);
  a=fnv(&position.ep,sizeof(position.ep),a);b=fnv(&position.ep,sizeof(position.ep),b);
  a=fnv(&board.halfmove,sizeof(board.halfmove),a);b=fnv(&board.halfmove,sizeof(board.halfmove),b);
  return {a,b};
 }
public:
 explicit EngineNetwork(const std::string& name,const std::string& path,bool use_int8){
  tiny_=std::make_unique<picoalpha::Network>(path,use_int8,name);
 }
 picoalpha::Result evaluate(const std::array<float,112*64>& planes,const picoSargon::Board* board=nullptr)const{
  uint64_t h1=0,h2=0;
  if(board){auto h=cache_key(planes,*board);h1=h.first;h2=h.second;
   for(auto& e:cache_)if(e.stamp&&e.h1==h1&&e.h2==h2){e.stamp=++clock_;return e.value;}
  }
  picoalpha::Result out;
  out=tiny_->evaluate(planes);
  if(board){auto* victim=&cache_[0];
   for(auto& e:cache_)if(!e.stamp||e.stamp<victim->stamp){victim=&e;if(!e.stamp)break;}
   victim->h1=h1;victim->h2=h2;victim->stamp=++clock_;victim->value=out;
  }
  return out;
 }
};
using Clock=std::chrono::steady_clock;
static int64_t ms(){return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch()).count();}
// Portable progressive widening from picoAlpha Pico: no eager allocation of every legal edge.
// All indices remain stable even when the deque grows.
struct TreeFullException {};
struct SearchTimeoutException {};
struct Candidate {Move move;float prior;};
struct Node {
 Move move{};float prior=1.f,visits=0.f,score=0.f;
 bool expanded=false,terminal=false;
 std::vector<size_t> children;
 std::vector<Candidate> pending;size_t next_pending=0;
 Node(Move m={},float p=1.f):move(m),prior(p){}
};
class Search {
 const EngineNetwork& net;float cpuct;int simulations;
 static constexpr size_t INITIAL_CHILDREN=4;
 static constexpr int VISITS_PER_EXTRA_CHILD=8;
 static constexpr size_t MAX_TREE_NODES=8576;
 std::deque<Node> pool;
 int64_t deadline_=INT64_MAX;
 std::vector<Board> previous_history_;
 bool previous_valid_=false;
 static bool equal_board(const Board& a,const Board& b){
  return a.position_key()==b.position_key() && a.halfmove==b.halfmove && a.fullmove==b.fullmove;
 }
 bool recycle_matching_subtree(const std::vector<Board>& next_history){
  if(!previous_valid_||pool.empty()||next_history.size()!=previous_history_.size()+2)return false;
  for(size_t i=0;i<previous_history_.size();++i)
   if(!equal_board(previous_history_[i],next_history[i]))return false;
  size_t current=0;
  Board probe=previous_history_.back();
  for(size_t step=0;step<2;++step){
   size_t found=SIZE_MAX;
   for(size_t child:pool[current].children){
    Board candidate=probe;candidate.push(pool[child].move);
    if(equal_board(candidate,next_history[previous_history_.size()+step])){found=child;probe=std::move(candidate);break;}
   }
   if(found==SIZE_MAX)return false;
   current=found;
  }
  // Build a contiguous, index-correct subtree. Old unreachable nodes are discarded.
  std::deque<Node> old=std::move(pool);pool.clear();
  std::vector<size_t> queue{current},map(old.size(),SIZE_MAX);
  map[current]=0;pool.push_back(old[current]);pool.back().children.clear();
  for(size_t pos=0;pos<queue.size();++pos){
   size_t old_idx=queue[pos],new_idx=map[old_idx];
   for(size_t child:old[old_idx].children){
    if(child>=old.size())throw std::runtime_error("corrupt tree child index");
    if(map[child]==SIZE_MAX){map[child]=pool.size();pool.push_back(old[child]);pool.back().children.clear();queue.push_back(child);}
    pool[new_idx].children.push_back(map[child]);
   }
  }
  return true;
 }
 size_t add_node(Move move,float prior){
  if(pool.size()>=MAX_TREE_NODES)throw TreeFullException{};
  pool.emplace_back(move,prior);return pool.size()-1;
 }
 bool widen(size_t idx){
  Node& node=pool[idx];
  if(node.next_pending>=node.pending.size())return false;
  Candidate candidate=node.pending[node.next_pending];
  size_t child=add_node(candidate.move,candidate.prior);
  pool[idx].children.push_back(child);
  ++pool[idx].next_pending;
  return true;
 }
 float expand(size_t idx,Board& b,const std::vector<Board>& h,bool fen_only){
  std::vector<Move> legal;legal.reserve(128);b.legal(legal);
  pool[idx].expanded=true;
  if(legal.empty()){pool[idx].terminal=true;return b.in_check()?-1.f:0.f;}
  if(b.draw()){pool[idx].terminal=true;return 0.f;}
  auto r=net.evaluate(encode(h,fen_only),&b);
  std::vector<Candidate> choices;choices.reserve(legal.size());float largest=-1e30f;
  for(auto m:legal){float v=r.policy[policy_index(b,m)];choices.push_back({m,v});largest=std::max(largest,v);}
  float total=0.f;for(auto &v:choices){v.prior=std::exp(v.prior-largest);total+=v.prior;}
  if(!(total>0.f)||!std::isfinite(total))throw std::runtime_error("invalid policy softmax");
  // Select top 4 without allocating the remaining children.
  const size_t count=std::min(INITIAL_CHILDREN,choices.size());
  std::sort(choices.begin(),choices.end(),[](const Candidate&a,const Candidate&b){return a.prior>b.prior;});
  for(auto& c:choices)c.prior/=total;
  pool[idx].pending=std::move(choices);
  for(size_t j=0;j<count;++j)widen(idx);
  return r.q;
 }
 float simulate(size_t idx,Board& b,std::vector<Board>& h,bool fen_only,int depth){
  if(depth>0&&ms()>=deadline_)throw SearchTimeoutException{};
  float value=0.f;
  if(!pool[idx].expanded){value=expand(idx,b,h,fen_only);}
  else if(pool[idx].terminal)value=b.draw()?0.f:b.in_check()?-1.f:0.f;
  else if(depth>=48)value=0.f;
  else {
   // Expand at most one new child per eight additional visits, preserving all old children.
   if(pool[idx].next_pending<pool[idx].pending.size() &&
      pool[idx].children.size()<size_t(4+int(pool[idx].visits)/VISITS_PER_EXTRA_CHILD))
    widen(idx);
   size_t best=SIZE_MAX;float highest=-1e30f;
   const float root=std::sqrt(std::max(1.f,pool[idx].visits));
   for(size_t ch:pool[idx].children){const Node& c=pool[ch];float q=c.visits>0?c.score/c.visits:0.f;
    float score=-q+cpuct*c.prior*root/(1.f+c.visits);
    if(score>highest){highest=score;best=ch;}}
   if(best!=SIZE_MAX){b.push(pool[best].move);h.push_back(b);
    try{value=-simulate(best,b,h,fen_only,depth+1);}
    catch(...){h.pop_back();b.pop();throw;}
    h.pop_back();b.pop();}
  }
  pool[idx].visits+=1.f;pool[idx].score+=value;return value;
 }
 public:
 Search(const EngineNetwork& n,float c,int sims):net(n),cpuct(c),simulations(sims){}
 void configure(float c,int sims){cpuct=c;simulations=sims;}
 void reset(){pool.clear();previous_history_.clear();previous_valid_=false;}
 struct Outcome {Move move{};bool has=false;int nodes=0;float q=0.f;const char* reason="complete";size_t tree_nodes=0;size_t reused=0;};
 Outcome run(Board b,std::vector<Board> h,bool fen_only,int64_t deadline){deadline_=deadline;Outcome out;
  if(recycle_matching_subtree(h))out.reused=pool.size();
  else{pool.clear();pool.emplace_back();}
  for(int i=0;i<simulations;++i){if(i>0&&ms()>=deadline){out.reason="timeout";break;}
   try{simulate(0,b,h,fen_only,0);++out.nodes;}
   catch(const TreeFullException&){out.reason="tree_full";break;}
   catch(const SearchTimeoutException&){out.reason="timeout";break;}
  }
  out.tree_nodes=pool.size();
  previous_history_=h;previous_valid_=true;
  size_t best=SIZE_MAX;
  for(size_t ch:pool[0].children)if(best==SIZE_MAX||pool[ch].visits>pool[best].visits)best=ch;
  if(best!=SIZE_MAX){const auto& child=pool[best];out.move=child.move;out.has=true;out.q=child.visits>0?-child.score/child.visits:0.f;}return out;
 }
};
int main(int argc,char** argv){
 try {
  std::string path;std::string model="tinygyal";int default_nodes=2000;float cpuct=1.5f;
#ifdef PICOALPHA_DEFAULT_INT8
  bool use_int8=true;
#else
  bool use_int8=false;
#endif
  for(int i=1;i<argc;++i){std::string a=argv[i];if((a=="--network"||a=="-n")&&i+1<argc)path=argv[++i];else if(a=="--model"&&i+1<argc)model=argv[++i];else if(a=="--simulations"&&i+1<argc)default_nodes=std::stoi(argv[++i]);else if(a=="--cpuct"&&i+1<argc)cpuct=std::stof(argv[++i]);else if(a=="--precision"&&i+1<argc){std::string mode=argv[++i];if(mode=="int8")use_int8=true;else if(mode=="fp32")use_int8=false;else throw std::runtime_error("--precision fp32|int8");}else throw std::runtime_error("uso: picoAlpha --model tinygyal|picogyal --network weights.pb.gz [--simulations N] [--cpuct C]");}
  if(path.empty())throw std::runtime_error("--network obligatorio: ruta a la red LC0 .pb.gz, tanto para tinygyal como picogyal");EngineNetwork net(model,path,use_int8);Search persistent_search(net,cpuct,default_nodes);Board board;std::vector<Board> history{board};bool fen_only=false;std::string line;
  while(std::getline(std::cin,line)){
   try {
    std::istringstream ss(line);std::string command;ss>>command;
    if(command=="uci")std::cout<<"id name picoAlpha C++ 0.6.182 (PUCT + "<<model<<" native)\nid author Dr. Pedro E. Colla\noption name Simulations type spin default "<<default_nodes<<" min 1 max 1000000\noption name Cpuct type string default "<<cpuct<<"\nuciok\n";
    else if(command=="isready")std::cout<<"readyok\n";
    else if(command=="setoption"){
     std::string s,name,value;ss>>s;if(s=="name"){while(ss>>s&&s!="value"){if(!name.empty())name+=' ';name+=s;}std::getline(ss,value);if(!value.empty()&&value[0]==' ')value.erase(0,1);if(name=="Simulations")default_nodes=std::max(1,std::stoi(value));else if(name=="Cpuct")cpuct=std::stof(value);}
    }else if(command=="ucinewgame"){board.reset();history.assign(1,board);fen_only=false;persistent_search.reset();}
    else if(command=="position"){
     std::string type;ss>>type;if(type=="startpos"){board.reset();fen_only=false;}
     else if(type=="fen"){std::string fen,s;for(int i=0;i<6&&ss>>s;++i){if(i)fen+=' ';fen+=s;}board.set_fen(fen);fen_only=true;}
     else throw std::runtime_error("position startpos|fen expected");
     history.assign(1,board);std::string word;while(ss>>word){if(word=="moves")continue;board.push(board.parse(word));history.push_back(board);}
    }else if(command=="eval"){
     std::vector<Move> lm;board.legal(lm);auto e=net.evaluate(encode(history,fen_only),&board);std::cout<<"info string q "<<std::setprecision(10)<<e.q<<"\n";float mx=-1e30f;std::vector<float> probs;for(auto m:lm){float z=e.policy[policy_index(board,m)];probs.push_back(z);mx=std::max(mx,z);}float sum=0;for(auto& v:probs){v=std::exp(v-mx);sum+=v;}for(size_t i=0;i<lm.size();++i)std::cout<<"info string policy "<<Board::notation(lm[i])<<" "<<std::setprecision(10)<<probs[i]/sum<<"\n";
    }else if(command=="go"){
     int nodes=default_nodes,movetime=0;std::string token;while(ss>>token){if(token=="nodes")ss>>nodes;else if(token=="movetime")ss>>movetime;else if(token=="depth") {int dummy;ss>>dummy;}else if(token=="wtime"||token=="btime"||token=="winc"||token=="binc"||token=="movestogo"){int dummy;ss>>dummy;}}
     nodes=std::max(1,nodes);int64_t limit=movetime>0?ms()+movetime:INT64_MAX;persistent_search.configure(cpuct,nodes);auto r=persistent_search.run(board,history,fen_only,limit);int cp=int(400.f*2.f*std::atanh(std::max(-.999f,std::min(.999f,r.q))));
     std::cout<<"info nodes "<<r.nodes<<" score cp "<<cp<<" string reason "<<r.reason<<" tree "<<r.tree_nodes<<" reuse "<<r.reused<<"\n";
     std::cout<<"bestmove "<<(r.has?Board::notation(r.move):"0000")<<"\n";
    }else if(command=="quit")break;
    else if(command=="stop"){};
   } catch(const std::exception& e){std::cout<<"info string picoAlpha error: "<<e.what()<<"\n";}
   std::cout.flush();
  }
  return 0;
 }catch(const std::exception& e){std::cerr<<"picoAlpha fatal: "<<e.what()<<"\n";return 1;}
}
