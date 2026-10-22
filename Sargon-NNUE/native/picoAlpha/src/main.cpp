#include "net.hpp"
#include <chrono>
#include <iostream>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <memory>
#include <stdexcept>
#include <iomanip>
using namespace picoSargon;
using namespace picoalpha;
using Clock=std::chrono::steady_clock;
static int64_t ms(){return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch()).count();}
struct Node {
 Move move;float prior=1.f,visits=0.f,score=0.f;bool expanded=false;std::vector<std::unique_ptr<Node>> children;
 Node(Move m={},float p=1):move(m),prior(p){}
};
class Search {
 const Network& net;float cpuct;int simulations;
 float expand(Node& n,Board& b,std::vector<Board>& h,bool fen_only){
  std::vector<Move> legal;b.legal(legal);n.expanded=true;
  if(b.draw())return 0.f;
  if(legal.empty())return b.in_check()?-1.f:0.f;
  auto r=net.evaluate(encode(h,fen_only));
  std::vector<float> logits;logits.reserve(legal.size());float max_logit=-1e30f;
  for(auto m:legal){float a=r.policy[policy_index(b,m)];logits.push_back(a);max_logit=std::max(a,max_logit);}
  float sum=0.f;for(auto& v:logits){v=std::exp(v-max_logit);sum+=v;}
  if(!std::isfinite(sum)||sum<=0)throw std::runtime_error("invalid policy softmax");
  for(size_t i=0;i<legal.size();++i)n.children.push_back(std::make_unique<Node>(legal[i],logits[i]/sum));
  return r.q;
 }
 float simulate(Node& n,Board& b,std::vector<Board>& h,bool fen_only,int depth){
  float value=0;
  if(!n.expanded){value=expand(n,b,h,fen_only);}
  else if(n.children.empty()){value=b.draw()?0.f:b.in_check()?-1.f:0.f;}
  else if(depth>=256){value=0;}
  else {
   Node* best=nullptr;float best_score=-1e30f;
   float root=std::sqrt(std::max(1.f,n.visits));
   for(auto& child:n.children){float q=child->visits>0?child->score/child->visits:0.f;float u=cpuct*child->prior*root/(1.f+child->visits);float score=-q+u;if(score>best_score){best_score=score;best=child.get();}}
   b.push(best->move);h.push_back(b);
   value=-simulate(*best,b,h,fen_only,depth+1);
   h.pop_back();b.pop();
  }
  n.visits+=1.f;n.score+=value;return value;
 }
 public:
 Search(const Network& n,float c,int sims):net(n),cpuct(c),simulations(sims){}
 struct Outcome {Move move{};bool has=false;int nodes=0;float q=0.f;};
 Outcome run(Board b,std::vector<Board> h,bool fen_only,int64_t deadline){Node root;
  for(int i=0;i<simulations;++i){if(i>0&&ms()>=deadline)break;simulate(root,b,h,fen_only,0);}
  Outcome out;out.nodes=int(root.visits);int best=-1;
  for(size_t j=0;j<root.children.size();++j)if(best<0||root.children[j]->visits>root.children[best]->visits)best=int(j);
  if(best>=0){auto& child=*root.children[best];out.move=child.move;out.has=true;out.q=child.visits>0?-child.score/child.visits:0.f;}return out;
 }
};
int main(int argc,char** argv){
 try {
  std::string path;int default_nodes=2000;float cpuct=1.5f;
#ifdef PICOALPHA_DEFAULT_INT8
  bool use_int8=true;
#else
  bool use_int8=false;
#endif
  for(int i=1;i<argc;++i){std::string a=argv[i];if((a=="--network"||a=="-n")&&i+1<argc)path=argv[++i];else if(a=="--simulations"&&i+1<argc)default_nodes=std::stoi(argv[++i]);else if(a=="--cpuct"&&i+1<argc)cpuct=std::stof(argv[++i]);else if(a=="--precision"&&i+1<argc){std::string mode=argv[++i];if(mode=="int8")use_int8=true;else if(mode=="fp32")use_int8=false;else throw std::runtime_error("--precision fp32|int8");}else throw std::runtime_error("uso: picoAlpha --network weights.pb.gz [--simulations N] [--cpuct C]");}
  if(path.empty())throw std::runtime_error("--network obligatorio");Network net(path,use_int8);Board board;std::vector<Board> history{board};bool fen_only=false;std::string line;
  while(std::getline(std::cin,line)){
   try {
    std::istringstream ss(line);std::string command;ss>>command;
    if(command=="uci")std::cout<<"id name picoAlpha C++ 0.6.178 (PUCT + TinyGyal-8 native)\nid author Sargon-NNUE\noption name Simulations type spin default "<<default_nodes<<" min 1 max 1000000\noption name Cpuct type string default "<<cpuct<<"\nuciok\n";
    else if(command=="isready")std::cout<<"readyok\n";
    else if(command=="setoption"){
     std::string s,name,value;ss>>s;if(s=="name"){while(ss>>s&&s!="value"){if(!name.empty())name+=' ';name+=s;}std::getline(ss,value);if(!value.empty()&&value[0]==' ')value.erase(0,1);if(name=="Simulations")default_nodes=std::max(1,std::stoi(value));else if(name=="Cpuct")cpuct=std::stof(value);}
    }else if(command=="ucinewgame"){board.reset();history.assign(1,board);fen_only=false;}
    else if(command=="position"){
     std::string type;ss>>type;if(type=="startpos"){board.reset();fen_only=false;}
     else if(type=="fen"){std::string fen,s;for(int i=0;i<6&&ss>>s;++i){if(i)fen+=' ';fen+=s;}board.set_fen(fen);fen_only=true;}
     else throw std::runtime_error("position startpos|fen expected");
     history.assign(1,board);std::string word;while(ss>>word){if(word=="moves")continue;board.push(board.parse(word));history.push_back(board);}
    }else if(command=="eval"){
     std::vector<Move> lm;board.legal(lm);auto e=net.evaluate(encode(history,fen_only));std::cout<<"info string q "<<std::setprecision(10)<<e.q<<"\n";float mx=-1e30f;std::vector<float> probs;for(auto m:lm){float z=e.policy[policy_index(board,m)];probs.push_back(z);mx=std::max(mx,z);}float sum=0;for(auto& v:probs){v=std::exp(v-mx);sum+=v;}for(size_t i=0;i<lm.size();++i)std::cout<<"info string policy "<<Board::notation(lm[i])<<" "<<std::setprecision(10)<<probs[i]/sum<<"\n";
    }else if(command=="go"){
     int nodes=default_nodes,movetime=0;std::string token;while(ss>>token){if(token=="nodes")ss>>nodes;else if(token=="movetime")ss>>movetime;else if(token=="depth") {int dummy;ss>>dummy;}else if(token=="wtime"||token=="btime"||token=="winc"||token=="binc"||token=="movestogo"){int dummy;ss>>dummy;}}
     nodes=std::max(1,nodes);int64_t limit=movetime>0?ms()+movetime:INT64_MAX;Search s(net,cpuct,nodes);auto r=s.run(board,history,fen_only,limit);int cp=int(400.f*2.f*std::atanh(std::max(-.999f,std::min(.999f,r.q))));
     std::cout<<"info nodes "<<r.nodes<<" score cp "<<cp<<"\n";
     std::cout<<"bestmove "<<(r.has?Board::notation(r.move):"0000")<<"\n";
    }else if(command=="quit")break;
    else if(command=="stop"){};
   } catch(const std::exception& e){std::cout<<"info string picoAlpha error: "<<e.what()<<"\n";}
   std::cout.flush();
  }
  return 0;
 }catch(const std::exception& e){std::cerr<<"picoAlpha fatal: "<<e.what()<<"\n";return 1;}
}
