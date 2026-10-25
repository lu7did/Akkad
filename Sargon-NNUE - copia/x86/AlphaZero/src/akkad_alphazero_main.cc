// AlphaZero-x86 / Akkad: autonomous UCI MCTS with LCZero inference backend.
// LCZero sources are linked into this program; neither lc0.exe nor UCI is
// used for neural inference. LCZero-derived components remain GPLv3+.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#include "config.h"
#include "chess/board.h"
#include "chess/position.h"
#include "neural/backend.h"
#include "neural/register.h"
#include "neural/shared_params.h"
#include "utils/optionsparser.h"

using namespace lczero;
namespace {
std::mutex output_mu;
void say(const std::string& s) { std::lock_guard<std::mutex> l(output_mu); std::cout << s << '\n' << std::flush; }
std::string trim(std::string s) { auto a=s.find_first_not_of(" \t\r\n"); if(a==std::string::npos)return {}; auto b=s.find_last_not_of(" \t\r\n");return s.substr(a,b-a+1); }
struct Settings {
  std::string weights=az_config::kWeightsFile, backend=az_config::kBackend,
              backend_options=az_config::kBackendOptions;
  int simulations=az_config::kSimulations, max_tree_nodes=az_config::kMaxTreeNodes,
      tmax=az_config::kTMaxMs, timeout=az_config::kTimeoutMs,
      verbose=az_config::kVerbose;
  double cpuct=az_config::kCpuct;
};
std::string move_uci(Move move, bool black) {
  if (black) move.Flip();
  return move.ToString(false);
}
struct Node {
  std::vector<Move> moves;
  std::vector<float> priors;
  std::vector<int> visits;
  std::vector<double> sums;
  std::vector<std::unique_ptr<Node>> children;
  bool expanded=false;
  void expand(std::vector<Move> m, std::vector<float> p) {
    moves=std::move(m); priors=std::move(p);
    visits.assign(moves.size(),0); sums.assign(moves.size(),0.0);
    children.resize(moves.size()); expanded=true;
  }
  size_t pick(double cpuct) const {
    int total=0; for(int n:visits) total+=n;
    double root=std::sqrt(double(std::max(1,total)));
    size_t best=0; double best_v=-1e99;
    for(size_t i=0;i<moves.size();++i) {
      double q=visits[i]?sums[i]/visits[i]:0.;
      double p=q+cpuct*priors[i]*root/(visits[i]+1.);
      if(p>best_v){best_v=p; best=i;}
    }
    return best;
  }
};
class LC0Inference {
  OptionsParser parser_;
  std::unique_ptr<Backend> backend_;
 public:
  explicit LC0Inference(const Settings& s) {
    SharedBackendParams::Populate(&parser_);
    auto* o=parser_.GetMutableOptions();
    o->Set<std::string>(SharedBackendParams::kWeightsId,s.weights);
    o->Set<std::string>(SharedBackendParams::kBackendId,s.backend);
    o->Set<std::string>(SharedBackendParams::kBackendOptionsId,s.backend_options);
    backend_=BackendManager::Get()->CreateFromName(s.backend,parser_.GetOptionsDict());
    if(!backend_) throw std::runtime_error("LC0 backend was not created");
  }
  std::pair<double,std::vector<float>> eval(const PositionHistory& h,const std::vector<Move>& m) {
    EvalPosition pos{h.GetPositions(),std::span<const Move>(m.data(),m.size())};
    auto results=backend_->EvaluateBatch(std::span<const EvalPosition>(&pos,1));
    if(results.size()!=1 || results[0].p.size()!=m.size()) throw std::runtime_error("invalid LC0 batch output");
    auto& r=results[0];
    // In LC0 q is already from the side-to-move perspective; when WDL is
    // available q = P(win) - P(loss), d = P(draw).
    double sum=0.; std::vector<float> prob=m.empty()?std::vector<float>{}:r.p;
    for(float& p:prob){if(!std::isfinite(p)||p<0)p=0;sum+=p;}
    if(sum<=0 && !prob.empty()) {float u=1.f/prob.size();for(float& p:prob)p=u;}
    else if(sum>0) for(float& p:prob)p=float(p/sum);
    return {std::clamp(double(r.q),-1.,1.),std::move(prob)};
  }
};
struct Result { std::string best="0000"; int simulations=0, visits=0, nodes=0; double q=0,ms=0; };
class MCTS {
  LC0Inference& eval_; double cpuct_;
  std::atomic<bool>& stop_;
  int nodes_=0;
  int max_nodes_=0;
  static double terminal(const PositionHistory& h, bool& done){
    auto r=h.ComputeGameResult();
    if(r==GameResult::UNDECIDED){done=false;return 0.;}
    done=true;
    if(r==GameResult::DRAW)return 0.;
    bool white_won=r==GameResult::WHITE_WON;
    return (white_won != h.IsBlackToMove()) ? 1. : -1.;
  }
  double simulation(Node& n, PositionHistory& h) {
    bool done=false; double value=terminal(h,done); if(done)return value;
    if(!n.expanded){
      if(max_nodes_>0 && nodes_>=max_nodes_) return 0.;
      auto list=h.Last().GetBoard().GenerateLegalMoves();
      std::vector<Move> moves(list.begin(),list.end());
      if(moves.empty())return 0.;
      auto r=eval_.eval(h,moves);
      n.expand(std::move(moves),std::move(r.second)); ++nodes_;
      return r.first;
    }
    if(n.moves.empty())return 0.;
    auto k=n.pick(cpuct_);
    h.Append(n.moves[k]);
    if(!n.children[k])n.children[k]=std::make_unique<Node>();
    double child=simulation(*n.children[k],h);
    h.Pop();
    double v=-child;
    ++n.visits[k]; n.sums[k]+=v;
    return v;
  }
 public:
  MCTS(LC0Inference& eval,double cpuct,std::atomic<bool>& stop,int max_nodes):eval_(eval),cpuct_(cpuct),stop_(stop),max_nodes_(max_nodes){}
  Result choose(PositionHistory h,int simulations,int ms_limit) {
    auto start=std::chrono::steady_clock::now();
    Node root;
    // Matches the Python player: root expansion precedes simulations.
    bool terminal_state=false;terminal(h,terminal_state);
    if(terminal_state)return {};
    auto legal=h.Last().GetBoard().GenerateLegalMoves();
    std::vector<Move> lm(legal.begin(),legal.end());
    if(lm.empty())return {};
    auto first=eval_.eval(h,lm);
    root.expand(std::move(lm),std::move(first.second));++nodes_;
    int done=0;
    while(done<simulations && !stop_.load()) {
      if(max_nodes_>0 && nodes_>=max_nodes_) break;
      if(done && ms_limit>0 && std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count()>=ms_limit)break;
      simulation(root,h);++done;
    }
    size_t best=0;
    bool visited=std::any_of(root.visits.begin(),root.visits.end(),[](int x){return x>0;});
    for(size_t i=1;i<root.moves.size();++i) {
      if(visited){
        const auto x=std::make_tuple(root.visits[i], root.visits[i]?root.sums[i]/root.visits[i]:0.,root.priors[i]);
        const auto y=std::make_tuple(root.visits[best],root.visits[best]?root.sums[best]/root.visits[best]:0.,root.priors[best]);
        if(x>y)best=i;
      } else if(root.priors[i]>root.priors[best])best=i;
    }
    Result r; r.best=move_uci(root.moves[best],h.IsBlackToMove());r.simulations=done;r.visits=root.visits[best];r.nodes=nodes_;
    r.q=r.visits?root.sums[best]/r.visits:0.;
    r.ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    return r;
  }
};
class Engine {
  Settings settings_;
  PositionHistory history_;
  std::unique_ptr<LC0Inference> eval_;
  std::thread search_;
  std::atomic<bool> stop_{false};
  void cancel(){stop_=true;if(search_.joinable())search_.join();stop_=false;}
  void ready(){
    if(settings_.weights.empty())throw std::runtime_error("WeightsFile is required");
    if(!std::filesystem::exists(settings_.weights))throw std::runtime_error("weights file not found: "+settings_.weights);
    if(!eval_)eval_=std::make_unique<LC0Inference>(settings_);
  }
 public:
  Engine(){InitializeMagicBitboards();history_.Reset(Position::FromFen(ChessBoard::kStartposFen));}
  ~Engine(){cancel();}
  void process(const std::string& line) {
    if(line=="uci"){
      say(std::string("id name ")+az_config::kUciName);say(std::string("id author ")+az_config::kUciAuthor);
      say(std::string("option name WeightsFile type string default ")+settings_.weights);
      say("option name Backend type string default "+settings_.backend);
      say("option name BackendOptions type string default "+settings_.backend_options);
      say("option name Simulations type spin default "+std::to_string(settings_.simulations)+" min 1 max 10000000");
      say("option name MaxTreeNodes type spin default "+std::to_string(settings_.max_tree_nodes)+" min 0 max 10000000");
      say("option name Cpuct type string default "+std::to_string(settings_.cpuct));
      say("option name TMax type spin default "+std::to_string(settings_.tmax)+" min 0 max 3600000");
      say("option name Timeout type spin default "+std::to_string(settings_.timeout)+" min 0 max 3600000");
      say("option name Verbose type spin default "+std::to_string(settings_.verbose)+" min 0 max 2");say("uciok");return;
    }
    if(line=="isready"){
      try{ready();}catch(const std::exception& e){say(std::string("info string ERROR ")+e.what());}
      say("readyok");return;
    }
    if(line=="ucinewgame"){cancel();eval_.reset();return;}
    if(line=="stop"){stop_=true;return;}
    if(line.rfind("setoption name ",0)==0){
      cancel();auto rest=line.substr(15); auto p=rest.find(" value ");
      auto name=trim(rest.substr(0,p)),value=p==std::string::npos?"":trim(rest.substr(p+7));
      if(name=="WeightsFile")settings_.weights=value;
      else if(name=="Backend")settings_.backend=value;
      else if(name=="BackendOptions")settings_.backend_options=value;
      else if(name=="Simulations")settings_.simulations=std::clamp(std::stoi(value),1,10000000);
      else if(name=="MaxTreeNodes")settings_.max_tree_nodes=std::clamp(std::stoi(value),0,10000000);
      else if(name=="Timeout")settings_.timeout=std::clamp(std::stoi(value),0,3600000);
      else if(name=="Cpuct")settings_.cpuct=std::max(0.0001,std::stod(value));
      else if(name=="TMax")settings_.tmax=std::clamp(std::stoi(value),0,3600000);
      else if(name=="Verbose")settings_.verbose=std::clamp(std::stoi(value),0,2);
      eval_.reset();return;
    }
    if(line.rfind("position ",0)==0){
      cancel();auto s=line.substr(9);std::string fen,moves;
      if(s.rfind("startpos",0)==0){fen=ChessBoard::kStartposFen;s=s.substr(8);}
      else if(s.rfind("fen ",0)==0){s=s.substr(4);auto p=s.find(" moves ");fen=trim(s.substr(0,p));s=p==std::string::npos?"":s.substr(p);}
      else throw std::runtime_error("unknown position command");
      auto p=s.find("moves ");moves=p==std::string::npos?"":s.substr(p+6);
      history_.Reset(Position::FromFen(fen));
      std::istringstream input(moves);std::string uci;
      while(input>>uci){const auto m=history_.Last().GetBoard().ParseMove(uci);
        auto legal=history_.Last().GetBoard().GenerateLegalMoves();
        if(std::find(legal.begin(),legal.end(),m)==legal.end())throw std::runtime_error("illegal UCI move: "+uci);
        history_.Append(m);
      }
      return;
    }
    if(line.rfind("go",0)==0){
      cancel();try{ready();}catch(const std::exception& e){say(std::string("info string ERROR ")+e.what());say("bestmove 0000");return;}
      int sims=settings_.simulations,ms=settings_.tmax;
      std::istringstream in(line.substr(2));std::string t;
      while(in>>t){if(t=="nodes"){int v;in>>v;sims=std::max(1,v);}else if(t=="movetime"){int v;in>>v;ms=std::max(1,v);}}
      if(settings_.timeout>0 && (ms<=0 || ms>settings_.timeout))ms=settings_.timeout;
      auto snapshot=history_;auto cfg=settings_;
      search_=std::thread([this,snapshot=std::move(snapshot),sims,ms,cfg]()mutable{
        try{
          MCTS m(*eval_,cfg.cpuct,stop_,cfg.max_tree_nodes);
          auto r=m.choose(std::move(snapshot),sims,ms);
          if(true){
            auto q=std::clamp(r.q,-0.999,0.999);
            int cp=int(400*std::atanh(q));
            std::ostringstream info;
            info<<"info depth 0 nodes "<<r.simulations<<" time "<<int(r.ms)<<" score cp "<<cp
                <<" string ALPHAZERO simulations="<<r.simulations<<" tree_nodes="<<r.nodes<<" elapsed_ms="<<int(r.ms)<<" best_visits="<<r.visits<<" q="<<r.q;
            say(info.str());
          }
          say("bestmove "+r.best);
        }catch(const std::exception& e){say(std::string("info string ERROR search: ")+e.what());say("bestmove 0000");}
      });return;
    }
  }
  void close(){cancel();}
  void cmd_simulations(int n){settings_.simulations=std::clamp(n,1,10000000);}
  void cmd_max_nodes(int n){settings_.max_tree_nodes=std::clamp(n,0,10000000);}
  void cmd_tmax(int n){settings_.tmax=std::clamp(n,0,3600000);}
  void cmd_timeout(int n){settings_.timeout=std::clamp(n,0,3600000);}
  void cmd_cpuct(double n){settings_.cpuct=std::max(0.0001,n);}
  void cmd_verbose(int n){settings_.verbose=std::clamp(n,0,2);}
  void cmd_weights(std::string w){settings_.weights=std::move(w);}
  void cmd_backend(std::string b){settings_.backend=std::move(b);}
  void cmd_backend_opts(std::string b){settings_.backend_options=std::move(b);}
};
} // namespace
int main(int argc,char**argv){
  try{
    Engine engine;
    for(int i=1;i<argc;++i){std::string a=argv[i];
      if((a=="--weights"||a=="--backend"||a=="--backend-options")&&i+1<argc){auto v=std::string(argv[++i]);if(a=="--weights")engine.cmd_weights(v);else if(a=="--backend")engine.cmd_backend(v);else engine.cmd_backend_opts(v);}
      else if((a=="--simulations" || a=="--max-tree-nodes" || a=="--tmax" || a=="--timeout" || a=="--cpuct" || a=="--verbose") && i+1<argc){
        std::string v=argv[++i];
        if(a=="--simulations")engine.cmd_simulations(std::stoi(v));
        else if(a=="--max-tree-nodes")engine.cmd_max_nodes(std::stoi(v));
        else if(a=="--tmax")engine.cmd_tmax(std::stoi(v));
        else if(a=="--timeout")engine.cmd_timeout(std::stoi(v));
        else if(a=="--cpuct")engine.cmd_cpuct(std::stod(v));
        else engine.cmd_verbose(std::stoi(v));
      }
      else if(a=="--help"){std::cerr<<"AlphaZero.exe --weights FILE.pb.gz [--backend onnx-dml|eigen] [--backend-options OPTIONS] [--simulations N] [--max-tree-nodes N] [--tmax MS] [--timeout MS] [--cpuct C] [--verbose N]"<<std::endl;return 0;}
      else throw std::runtime_error("unknown CLI argument: "+a);
    }
    std::string line;while(std::getline(std::cin,line)){
      line=trim(line);if(line=="quit")break;
      try{engine.process(line);}catch(const std::exception& e){say(std::string("info string ERROR command: ")+e.what());}
    }
    engine.close();return 0;
  }catch(const std::exception& e){std::cerr<<"AlphaZero fatal: "<<e.what()<<std::endl;return 1;}
}
