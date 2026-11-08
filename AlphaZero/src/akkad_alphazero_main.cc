// AlphaZero-x86 / Akkad: autonomous UCI MCTS with LCZero inference backend.
// LCZero sources are linked into this program; neither lc0.exe nor UCI is
// used for neural inference. LCZero-derived components remain GPLv3+.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <system_error>
#if defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#elif defined(__APPLE__)
#include <mach-o/dyld.h>
#elif defined(__linux__)
#include <unistd.h>
#endif
#include <iostream>
#include <memory>
#include <mutex>
#include <tuple>
#include <optional>
#include <cstdint>
#include <limits>
#include <sstream>
#include <iomanip>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#include <exception>
#include <cctype>
#ifndef AZ_MULTICORE
#define AZ_MULTICORE 1
#endif
#include "config.h"
#include "lc0_startup_telemetry.h"
#include "chess/board.h"
#include "chess/position.h"
#include "neural/backend.h"
#include "neural/register.h"
#include "neural/shared_params.h"
#include "utils/optionsparser.h"

using namespace lczero;
namespace {
std::mutex output_mu;
// stdout is reserved for machine-readable UCI; telemetry uses stderr only.
void telemetry(const std::string& s) {
  std::lock_guard<std::mutex> lock(output_mu);
  std::cerr << s << '\n' << std::flush;
}
std::string absolute_path(const std::string& path) {
  if (path.empty()) return "(not configured)";
  std::error_code ec;
  auto p = std::filesystem::absolute(std::filesystem::path(path), ec);
  return ec ? path : p.lexically_normal().string();
}
std::string executable_path(const char* argv0) {
#if defined(_WIN32)
  std::vector<char> buf(32768);
  auto n = GetModuleFileNameA(nullptr, buf.data(), static_cast<DWORD>(buf.size()));
  if (n && n < buf.size()) return absolute_path(std::string(buf.data(), n));
#elif defined(__APPLE__)
  uint32_t sz = 0;
  _NSGetExecutablePath(nullptr, &sz);
  std::vector<char> buf(sz + 1);
  if (_NSGetExecutablePath(buf.data(), &sz) == 0) return absolute_path(buf.data());
#elif defined(__linux__)
  std::vector<char> buf(4096);
  auto n = readlink("/proc/self/exe", buf.data(), buf.size() - 1);
  if (n > 0) return absolute_path(std::string(buf.data(), static_cast<size_t>(n)));
#endif
  return absolute_path(argv0 ? argv0 : "");
}
void say(const std::string& s) {
  std::lock_guard<std::mutex> l(output_mu);
  std::cout << s << '\n' << std::flush; // UCI: no decorations on stdout.
  std::cerr << "➡️ UCI " << s << '\n' << std::flush;
}
std::string trim(std::string s) { auto a=s.find_first_not_of(" \t\r\n"); if(a==std::string::npos)return {}; auto b=s.find_last_not_of(" \t\r\n");return s.substr(a,b-a+1); }
struct Settings {
  std::string weights=az_config::kWeightsFile, backend=az_config::kBackend,
              backend_options=az_config::kBackendOptions;
  int simulations=az_config::kSimulations, max_tree_nodes=az_config::kMaxTreeNodes,
      tmax=az_config::kTMaxMs, timeout=az_config::kTimeoutMs,
      verbose=az_config::kVerbose;
  double cpuct=az_config::kCpuct;
  int batch_size=az_config::kBatchSize;
  int cores=1;
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
  bool pending=false;
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
  using Evaluation = std::pair<double,std::vector<float>>;
  std::vector<Evaluation> eval_batch(const std::vector<PositionHistory>& histories,
                                      const std::vector<std::vector<Move>>& moves) {
    if(histories.size()!=moves.size()) throw std::runtime_error("batch input size mismatch");
    if(histories.empty()) return {};
    std::vector<EvalPosition> positions;
    positions.reserve(histories.size());
    for(size_t i=0;i<histories.size();++i)
      positions.push_back(EvalPosition{histories[i].GetPositions(),
                         std::span<const Move>(moves[i].data(),moves[i].size())});
    auto outputs=backend_->EvaluateBatch(std::span<const EvalPosition>(positions.data(),positions.size()));
    if(outputs.size()!=positions.size())throw std::runtime_error("invalid LC0 batch count");
    std::vector<Evaluation> result;
    result.reserve(outputs.size());
    for(size_t i=0;i<outputs.size();++i){
      auto& r=outputs[i];
      if(r.p.size()!=moves[i].size())throw std::runtime_error("invalid LC0 policy shape");
      std::vector<float> prob=r.p;
      double sum=0.;
      for(float& p:prob){if(!std::isfinite(p)||p<0)p=0;sum+=p;}
      if(sum<=0 && !prob.empty()){float u=1.f/prob.size();for(float& p:prob)p=u;}
      else if(sum>0)for(float& p:prob)p=float(p/sum);
      result.emplace_back(std::clamp(double(r.q),-1.,1.),std::move(prob));
    }
    return result;
  }
  Evaluation eval(const PositionHistory& history,const std::vector<Move>& moves){
    auto result=eval_batch(std::vector<PositionHistory>{history},
                            std::vector<std::vector<Move>>{moves});
    return std::move(result.front());
  }
};
struct Result {
  std::string best="0000", stop_reason="completed";
  int simulations=0, visits=0, nodes=0, evaluations=0, batches=0, peak_batch=0;
  double q=0,ms=0, nn_ms=0, select_ms=0, expand_ms=0, backup_ms=0;
  std::vector<std::string> root_moves;
  std::vector<int> root_visits;
  std::vector<double> root_sums;
};
class MCTS {
  using Clock=std::chrono::steady_clock;
  using Edge=std::pair<Node*,size_t>;
  struct Request {
    Node* leaf=nullptr;
    PositionHistory history;
    std::vector<Move> moves;
    std::vector<Edge> path;
    bool terminal=false;
    double value=0.;
  };
  LC0Inference& eval_; double cpuct_;
  std::atomic<bool>& stop_;
  int nodes_=0,max_nodes_=0,batch_size_=1;
  static double milliseconds(Clock::duration d){return std::chrono::duration<double,std::milli>(d).count();}
  static double terminal(const PositionHistory& h,bool& done){
    auto r=h.ComputeGameResult();
    if(r==GameResult::UNDECIDED){done=false;return 0.;}
    done=true;
    if(r==GameResult::DRAW)return 0.;
    bool white_won=r==GameResult::WHITE_WON;
    return (white_won != h.IsBlackToMove()) ? 1. : -1.;
  }
  // Reservation of an in-flight path changes PUCT selection so the batch can
  // discover independent leaves. It is fully undone before the real backup.
  static void reserve(const std::vector<Edge>& path){
    for(const auto& [node,k]:path){++node->visits[k];node->sums[k]-=1.;}
  }
  static void release(const std::vector<Edge>& path){
    for(const auto& [node,k]:path){--node->visits[k];node->sums[k]+=1.;}
  }
  static void backup(const std::vector<Edge>& path,double v){
    for(auto it=path.rbegin();it!=path.rend();++it){
      v=-v;
      ++it->first->visits[it->second];it->first->sums[it->second]+=v;
    }
  }
  static bool select(Node& root,const PositionHistory& root_history,double cpuct,Request& req){
    req.history=root_history;
    Node* n=&root;
    while(n->expanded && !n->moves.empty()){
      auto k=n->pick(cpuct);
      req.path.emplace_back(n,k);
      req.history.Append(n->moves[k]);
      if(!n->children[k])n->children[k]=std::make_unique<Node>();
      n=n->children[k].get();
    }
    if(n->pending) return false;
    req.leaf=n;
    bool done=false;
    req.value=terminal(req.history,done);
    req.terminal=done;
    if(!done){
      auto legal=req.history.Last().GetBoard().GenerateLegalMoves();
      req.moves.assign(legal.begin(),legal.end());
      if(req.moves.empty()){req.terminal=true;req.value=0.;}
    }
    if(!req.terminal)n->pending=true;
    reserve(req.path);
    return true;
  }
 public:
  MCTS(LC0Inference& eval,double cpuct,std::atomic<bool>& stop,int max_nodes,int batch_size)
    :eval_(eval),cpuct_(cpuct),stop_(stop),max_nodes_(max_nodes),batch_size_(std::max(1,batch_size)){}
  Result choose(PositionHistory h,int simulations,int ms_limit,
                const std::vector<float>* shared_root_priors=nullptr){
    auto start=Clock::now();
    Result r;
    Node root;
    bool terminal_state=false;terminal(h,terminal_state);
    if(terminal_state){r.stop_reason="terminal";return r;}
    auto legal=h.Last().GetBoard().GenerateLegalMoves();
    std::vector<Move> lm(legal.begin(),legal.end());
    if(lm.empty()){r.stop_reason="no_moves";return r;}
    auto t=Clock::now();
    std::vector<float> priors;
    if(shared_root_priors && shared_root_priors->size()==lm.size()){
      priors=*shared_root_priors;
    }else{
      auto first=eval_.eval(h,lm);
      r.nn_ms+=milliseconds(Clock::now()-t);
      ++r.evaluations;++r.batches;r.peak_batch=1;
      priors=std::move(first.second);
    }
    root.expand(std::move(lm),std::move(priors));++nodes_;
    auto deadline=(ms_limit>0) ? start+std::chrono::milliseconds(ms_limit) : Clock::time_point::max();
    while(r.simulations<simulations && !stop_.load()){
      if(Clock::now()>=deadline){r.stop_reason="time";break;}
      if(max_nodes_>0 && nodes_>=max_nodes_){r.stop_reason="max_nodes";break;}
      const int remaining=simulations-r.simulations;
      const int capacity=(max_nodes_>0)?std::min(max_nodes_-nodes_,remaining):remaining;
      int wanted=std::min(batch_size_,capacity);
      std::vector<Request> requests;
      requests.reserve(wanted);
      // Avoid spinning indefinitely when every available path is reserved.
      int failed=0;
      while(static_cast<int>(requests.size())<wanted && failed<std::max(4,wanted*3)
            && r.simulations+static_cast<int>(requests.size())<simulations){
        if(stop_.load() || Clock::now()>=deadline)break;
        Request req;
        t=Clock::now();
        bool ok=select(root,h,cpuct_,req);
        r.select_ms+=milliseconds(Clock::now()-t);
        if(!ok){++failed;continue;}
        failed=0;
        if(req.terminal){
          t=Clock::now();
          release(req.path);backup(req.path,req.value);
          r.backup_ms+=milliseconds(Clock::now()-t);
          ++r.simulations;
          // A terminal simulation does not create a new neural evaluation.
          if(r.simulations>=simulations)break;
        }else requests.push_back(std::move(req));
      }
      if(requests.empty()){
        if(Clock::now()>=deadline){r.stop_reason="time";break;}
        if(stop_.load()){r.stop_reason="stop";break;}
        // No selectable leaf: avoid a busy loop in a fully terminal subtree.
        if(r.simulations>=simulations)break;
        r.stop_reason="no_available_leaf";break;
      }
      std::vector<PositionHistory> histories;
      std::vector<std::vector<Move>> moves;
      histories.reserve(requests.size());moves.reserve(requests.size());
      for(const auto& req:requests){histories.push_back(req.history);moves.push_back(req.moves);}
      t=Clock::now();
      auto results=eval_.eval_batch(histories,moves);
      r.nn_ms+=milliseconds(Clock::now()-t);
      ++r.batches;r.evaluations+=static_cast<int>(requests.size());
      r.peak_batch=std::max(r.peak_batch,static_cast<int>(requests.size()));
      t=Clock::now();
      for(size_t i=0;i<requests.size();++i){
        auto& req=requests[i];
        req.leaf->expand(std::move(req.moves),std::move(results[i].second));
        req.leaf->pending=false;
        ++nodes_;
      }
      r.expand_ms+=milliseconds(Clock::now()-t);
      t=Clock::now();
      for(size_t i=0;i<requests.size();++i){
        release(requests[i].path);
        backup(requests[i].path,results[i].first);
        ++r.simulations;
      }
      r.backup_ms+=milliseconds(Clock::now()-t);
    }
    if(stop_.load())r.stop_reason="stop";
    size_t best=0;
    bool visited=std::any_of(root.visits.begin(),root.visits.end(),[](int x){return x>0;});
    for(size_t i=1;i<root.moves.size();++i){
      if(visited){
        const auto x=std::make_tuple(root.visits[i],root.visits[i]?root.sums[i]/root.visits[i]:0.,root.priors[i]);
        const auto y=std::make_tuple(root.visits[best],root.visits[best]?root.sums[best]/root.visits[best]:0.,root.priors[best]);
        if(x>y)best=i;
      }else if(root.priors[i]>root.priors[best])best=i;
    }
    r.best=move_uci(root.moves[best],h.IsBlackToMove());r.visits=root.visits[best];r.nodes=nodes_;
    r.q=r.visits?root.sums[best]/r.visits:0.;
    for(size_t i=0;i<root.moves.size();++i){
      r.root_moves.push_back(move_uci(root.moves[i],h.IsBlackToMove()));
      r.root_visits.push_back(root.visits[i]);
      r.root_sums.push_back(root.sums[i]);
    }
    r.ms=milliseconds(Clock::now()-start);
    return r;
  }
};
// Root-parallel MCTS: each worker owns a private tree and LC0 backend.
// No node is accessed concurrently. The shared seed makes all roots start
// with the same policy; the coordinator consolidates root visit statistics.
struct CoreResult { Result result; int core=0, allocation=0; double wall_ms=0; };
static bool cpu_backend(std::string backend){
  std::transform(backend.begin(),backend.end(),backend.begin(),
                 [](unsigned char c){return static_cast<char>(std::tolower(c));});
  return backend=="eigen" || backend=="blas" || backend=="dnnl";
}
static int effective_cores(const Settings& cfg){
#if AZ_MULTICORE
  if(cfg.cores<2 || !cpu_backend(cfg.backend))return 1;
  const unsigned int hw=std::thread::hardware_concurrency();
  return std::max(1,std::min(cfg.cores,static_cast<int>(hw?hw:1)));
#else
  (void)cfg;
  return 1;
#endif
}
static Result run_root_parallel(const PositionHistory& h,LC0Inference& initial,const Settings& cfg,
                                std::atomic<bool>& stop,int simulations,int ms,
                                std::vector<CoreResult>& per_core,
                                const std::vector<LC0Inference*>& inference_pool){
  using Clock=std::chrono::steady_clock;
  const auto start=Clock::now();
  const int cores=effective_cores(cfg);
  if(cores==1){
    MCTS m(initial,cfg.cpuct,stop,cfg.max_tree_nodes,cfg.batch_size);
    auto result=m.choose(h,simulations,ms);
    per_core.push_back({result,0,simulations,result.ms});
    return result;
  }
  // Evaluate root once. All workers use an identical policy distribution.
  auto legal=h.Last().GetBoard().GenerateLegalMoves();
  std::vector<Move> root_moves(legal.begin(),legal.end());
  if(root_moves.empty()){
    Result empty;empty.stop_reason="no_moves";
    return empty;
  }
  auto seed=initial.eval(h,root_moves);
  const auto priors=std::move(seed.second);
  std::vector<CoreResult> work(static_cast<size_t>(cores));
  std::vector<std::exception_ptr> errors(static_cast<size_t>(cores));
  std::vector<std::thread> workers;
  workers.reserve(static_cast<size_t>(cores));
  // Split simulations and node cap deterministically, never oversubscribe.
  const int active=std::max(1,std::min({cores,simulations,
      cfg.max_tree_nodes>0?cfg.max_tree_nodes:cores}));
  // Backends (and their immutable weights) were created once by Engine.
  // Workers have exclusive access to their own backend instance.
  if(inference_pool.size()<static_cast<size_t>(active))
    throw std::runtime_error("insufficient persistent LC0 workers");
  const int started=active;
  if(started==0){ Result aborted;aborted.stop_reason="stop";return aborted; }
  const auto initialization_end=Clock::now();
  const int remaining_ms=std::max(1,ms-static_cast<int>(
    std::chrono::duration_cast<std::chrono::milliseconds>(initialization_end-start).count()));
  for(int i=0;i<started;++i){
    const int allocation=simulations/started+(i<simulations%started?1:0);
    const int node_cap=cfg.max_tree_nodes>0
      ?std::max(1,cfg.max_tree_nodes/started+(i<cfg.max_tree_nodes%started?1:0)):0;
    work[i].core=i;work[i].allocation=allocation;
    workers.emplace_back([&,i,allocation,node_cap](){
      try{
        MCTS m(*inference_pool[static_cast<size_t>(i)],cfg.cpuct,stop,node_cap,cfg.batch_size);
        auto t=Clock::now();
        work[i].result=m.choose(h,allocation,remaining_ms,&priors);
        work[i].wall_ms=std::chrono::duration<double,std::milli>(Clock::now()-t).count();
      }catch(...){errors[i]=std::current_exception();stop.store(true);}
    });
  }
  for(auto& worker:workers)worker.join();
  for(int i=0;i<started;++i)if(errors[i])std::rethrow_exception(errors[i]);
  Result aggregate;
  aggregate.stop_reason="completed";
  aggregate.root_moves=work[0].result.root_moves;
  aggregate.root_visits.assign(aggregate.root_moves.size(),0);
  aggregate.root_sums.assign(aggregate.root_moves.size(),0.);
  for(int i=0;i<started;++i){
    const auto& r=work[i].result;
    aggregate.simulations+=r.simulations;
    aggregate.nodes+=r.nodes;
    aggregate.evaluations+=r.evaluations;
    aggregate.batches+=r.batches;
    aggregate.peak_batch=std::max(aggregate.peak_batch,r.peak_batch);
    aggregate.nn_ms+=r.nn_ms;aggregate.select_ms+=r.select_ms;
    aggregate.expand_ms+=r.expand_ms;aggregate.backup_ms+=r.backup_ms;
    if(r.stop_reason!="completed")aggregate.stop_reason=r.stop_reason;
    // Defensive mapping by move instead of assuming identical ordering.
    for(size_t j=0;j<r.root_moves.size();++j){
      auto it=std::find(aggregate.root_moves.begin(),aggregate.root_moves.end(),r.root_moves[j]);
      if(it==aggregate.root_moves.end())throw std::runtime_error("root move mismatch across workers");
      auto k=static_cast<size_t>(it-aggregate.root_moves.begin());
      aggregate.root_visits[k]+=r.root_visits[j];
      aggregate.root_sums[k]+=r.root_sums[j];
    }
  }
  size_t best=0;
  for(size_t i=1;i<aggregate.root_moves.size();++i){
    if(aggregate.root_visits[i]>aggregate.root_visits[best])best=i;
  }
  aggregate.best=aggregate.root_moves[best];
  aggregate.visits=aggregate.root_visits[best];
  aggregate.q=aggregate.visits?aggregate.root_sums[best]/aggregate.visits:0.;
  aggregate.ms=std::chrono::duration<double,std::milli>(Clock::now()-start).count();
  telemetry("⚙️ AlphaZero multicore setup=" + std::to_string(
    std::chrono::duration<double,std::milli>(initialization_end-start).count()) +
    " msecs workers=" + std::to_string(started));
  per_core.assign(work.begin(),work.begin()+started);
  return aggregate;
}
class Engine {
  Settings settings_;
  PositionHistory history_;
  int current_ply_=0;
  std::unique_ptr<LC0Inference> eval_;
  std::vector<std::unique_ptr<LC0Inference>> secondary_evals_;
  std::thread search_;
  void invalidate_inference(){
    secondary_evals_.clear();
    eval_.reset();
    telemetry("⚙️ AlphaZero inference cache invalidated (weights/backend changed)");
  }
  std::vector<LC0Inference*> prepare_inference(int active){
    ready();
    const auto start=std::chrono::steady_clock::now();
    const int cached_before=(eval_?1:0)+static_cast<int>(secondary_evals_.size());
    while(static_cast<int>(secondary_evals_.size())<active-1)
      secondary_evals_.push_back(std::make_unique<LC0Inference>(settings_));
    std::vector<LC0Inference*> pool;
    pool.reserve(static_cast<size_t>(active));
    pool.push_back(eval_.get());
    for(int i=1;i<active;++i)pool.push_back(secondary_evals_[static_cast<size_t>(i-1)].get());
    telemetry("⚙️ AlphaZero backend new="+std::to_string(
                static_cast<int>(secondary_evals_.size())+1-cached_before)+
              "/"+std::to_string(std::min(active,cached_before))+
              "/"+std::to_string(pool.size())+
              "/"+std::to_string(secondary_evals_.size()+1)+
              " preparation="+std::to_string(std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now()-start).count())+
              " weights="+absolute_path(settings_.weights));
    return pool;
  }
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
      say("option name BatchSize type spin default "+std::to_string(settings_.batch_size)+" min 1 max 256");
      say("option name Cores type spin default "+std::to_string(settings_.cores)+" min 1 max 256");
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
    if(line=="ucinewgame"){cancel();return;} // Reset game history elsewhere; retain immutable weights.
    if(line=="stop"){stop_=true;return;}
    if(line.rfind("setoption name ",0)==0){
      cancel();auto rest=line.substr(15); auto p=rest.find(" value ");
      auto name=trim(rest.substr(0,p)),value=p==std::string::npos?"":trim(rest.substr(p+7));
      const bool reload = (name=="WeightsFile" && value!=settings_.weights) ||
                          (name=="Backend" && value!=settings_.backend) ||
                          (name=="BackendOptions" && value!=settings_.backend_options);
      if(name=="WeightsFile"){
        settings_.weights=value;
        telemetry("⚙️ network=" + absolute_path(settings_.weights));
    telemetry("⚙️ backend=" + settings_.backend + " backend_options=" + settings_.backend_options);
    telemetry("⚙️ MULTICORE=" + std::string(AZ_MULTICORE ? "ON" : "OFF") +
              " requested="+std::to_string(settings_.cores)+
              " available="+std::to_string(std::max(1u,std::thread::hardware_concurrency()))+
              " active="+std::to_string(effective_cores(settings_))+
              " backend="+settings_.backend);
      }
      else if(name=="Backend")settings_.backend=value;
      else if(name=="BackendOptions")settings_.backend_options=value;
      else if(name=="BatchSize")settings_.batch_size=std::clamp(std::stoi(value),1,256);
      else if(name=="Cores")settings_.cores=std::clamp(std::stoi(value),1,256);
      else if(name=="Simulations")settings_.simulations=std::clamp(std::stoi(value),1,10000000);
      else if(name=="MaxTreeNodes")settings_.max_tree_nodes=std::clamp(std::stoi(value),0,10000000);
      else if(name=="Timeout")settings_.timeout=std::clamp(std::stoi(value),0,3600000);
      else if(name=="Cpuct")settings_.cpuct=std::max(0.0001,std::stod(value));
      else if(name=="TMax")settings_.tmax=std::clamp(std::stoi(value),0,3600000);
      else if(name=="Verbose")settings_.verbose=std::clamp(std::stoi(value),0,2);
      if(reload)invalidate_inference();return;
    }
    if(line.rfind("position ",0)==0){
      cancel();auto s=line.substr(9);std::string fen,moves;
      if(s.rfind("startpos",0)==0){fen=ChessBoard::kStartposFen;s=s.substr(8);}
      else if(s.rfind("fen ",0)==0){s=s.substr(4);auto p=s.find(" moves ");fen=trim(s.substr(0,p));s=p==std::string::npos?"":s.substr(p);}
      else throw std::runtime_error("unknown position command");
      auto p=s.find("moves ");moves=p==std::string::npos?"":s.substr(p+6);
      {std::istringstream fs(fen);std::string part;int idx=0,full=1;bool black=false;
       while(fs>>part){if(idx==1)black=(part=="b");if(idx==5){try{full=std::stoi(part);}catch(...){full=1;}}++idx;}
       current_ply_=2*std::max(0,full-1)+(black?1:0);}
      history_.Reset(Position::FromFen(fen));
      std::istringstream input(moves);std::string uci;
      while(input>>uci){const auto m=history_.Last().GetBoard().ParseMove(uci);
        auto legal=history_.Last().GetBoard().GenerateLegalMoves();
        if(std::find(legal.begin(),legal.end(),m)==legal.end())throw std::runtime_error("illegal UCI move: "+uci);
        history_.Append(m);++current_ply_;
      }
      return;
    }
    if(line.rfind("go",0)==0){
      cancel();try{ready();}catch(const std::exception& e){say(std::string("info string ERROR ")+e.what());say("bestmove 0000");return;}
      int sims=settings_.simulations,ms=settings_.tmax;
      int wtime=-1,btime=-1,winc=0,binc=0,movestogo=0;
      int movetime=-1;
      bool infinite=false;
      std::istringstream in(line.substr(2));std::string t;
      while(in>>t){
        if(t=="infinite"){infinite=true;continue;}
        if(t=="nodes" || t=="movetime" || t=="wtime" || t=="btime" ||
           t=="winc" || t=="binc" || t=="movestogo"){
          long long raw=0;
          if(!(in>>raw))throw std::runtime_error("go: missing integer after "+t);
          int v=static_cast<int>(std::clamp(raw,0LL,static_cast<long long>(std::numeric_limits<int>::max())));
          if(t=="nodes")sims=std::max(1,v);
          else if(t=="movetime")movetime=std::max(1,v);
          else if(t=="wtime")wtime=v;
          else if(t=="btime")btime=v;
          else if(t=="winc")winc=v;
          else if(t=="binc")binc=v;
          else movestogo=v;
        }
      }
      const bool black=history_.IsBlackToMove();
      const int remaining=black?btime:wtime;
      const int increment=black?binc:winc;
      std::string time_mode="tmax";
      if(movetime>=0){ms=movetime;time_mode="movetime";}
      else if(!infinite && remaining>=0){
        // Conservative Fischer clock budget. Reserve 5% or 100 ms (whichever
        // is larger), and never spend more than the available safe time.
        const int reserve=std::min(remaining,std::max(100,remaining/20));
        const int safe=std::max(1,remaining-reserve);
        const int moves=movestogo>0?movestogo:30;
        const long long candidate=static_cast<long long>(remaining)/moves
                                  +static_cast<long long>(increment)*8/10;
        ms=static_cast<int>(std::clamp(candidate,1LL,static_cast<long long>(safe)));
        if(settings_.tmax>0)ms=std::min(ms,settings_.tmax);
        time_mode="clock";
      }
      if(settings_.timeout>0 && (ms<=0 || ms>settings_.timeout))ms=settings_.timeout;
      if(ms<=0)ms=1000; // Avoid unbounded search when no clock or limit exists.
      telemetry("⚙️ AlphaZero go mode="+time_mode+" timeout="+std::to_string(ms)+
                " remaining="+std::to_string(remaining)+" increment="+std::to_string(increment)+
                " movestogo="+std::to_string(movestogo)+" sims="+std::to_string(sims)+
                " batch="+std::to_string(settings_.batch_size)+
                " cores="+std::to_string(settings_.cores)+"/"+
                std::to_string(effective_cores(settings_)));
      auto snapshot=history_;auto cfg=settings_;const int root_ply=current_ply_;
      const bool root_black=snapshot.IsBlackToMove();
      // Create the pool once and retain it across searches and new games.
      // Preparation is serialized in the UCI command thread, outside MCTS threads.
      std::vector<LC0Inference*> pool;
      try {
        const int workers=std::max(1,std::min({effective_cores(cfg),sims,
          cfg.max_tree_nodes>0?cfg.max_tree_nodes:effective_cores(cfg)}));
        pool=prepare_inference(workers);
      }catch(const std::exception& e){
        say(std::string("info string ERROR backend pool: ")+e.what());
        say("bestmove 0000");return;
      }
      search_=std::thread([this,snapshot=std::move(snapshot),sims,ms,cfg,root_ply,root_black,pool=std::move(pool)]()mutable{
        try{
          std::vector<CoreResult> per_core;
          auto r=run_root_parallel(snapshot,*eval_,cfg,stop_,sims,ms,per_core,pool);
          for(const auto& core:per_core){
            const auto& cr=core.result;
            std::ostringstream core_log;
            core_log << "🧠 AlphaZero core[" << core.core << "] stop=" << cr.stop_reason
                     << " sims=" << cr.simulations << " alloc=" << core.allocation
                     << " nodes=" << cr.nodes << " nn_evals=" << cr.evaluations
                     << " batches=" << cr.batches
                     << " nn_ms=" << std::fixed << std::setprecision(1) << cr.nn_ms
                     << " msecs elapsed=" << core.wall_ms;
            telemetry(core_log.str());
          }
          if(true){
            auto q=std::clamp(r.q,-0.999,0.999);
            int cp=int(400*std::atanh(q));
            std::ostringstream info;
            const auto elapsed=std::max(0LL,static_cast<long long>(r.ms));
            const auto nps=elapsed>0 ? (static_cast<long long>(r.nodes)*1000/elapsed) : 0LL;
            info<<"info ply "<<root_ply<<" depth 0 score cp "<<(root_black?-cp:cp)
                <<" nodes "<<r.nodes<<" time "<<elapsed<<" nps "<<nps
                <<" string ALPHAZERO simulations="<<r.simulations<<" tree_nodes="<<r.nodes<<" elapsed_ms="<<int(r.ms)<<" best_visits="<<r.visits<<" q="<<r.q
                <<" batch_size="<<cfg.batch_size<<" cores="<<per_core.size()<<" batches="<<r.batches
                <<" evals="<<r.evaluations<<" nn_ms="<<int(r.nn_ms)
                <<" stop="<<r.stop_reason;
            // Keep the complete UCI info frame machine-readable. Human-friendly
            // short/extended renderings are emitted by the TCP listener on stderr.
            say(info.str());
            std::ostringstream detail;
            detail << "🧠 AlphaZero analysis ply=" << root_ply
                   << " cores=" << per_core.size()
                   << " nodes=" << r.nodes
                   << " simulations=" << r.simulations
                   << " elapsed_ms=" << elapsed
                   << " nps=" << nps
                   << " best_visits=" << r.visits
                   << " batches=" << r.batches << " avg_batch="
                   << (r.batches?double(r.evaluations)/r.batches:0.)
                   << " max_batch=" << r.peak_batch
                   << " nn_evals=" << r.evaluations
                   << " nn_ms=" << r.nn_ms
                   << " selection_ms=" << r.select_ms
                   << " expansion_ms=" << r.expand_ms
                   << " backup_ms=" << r.backup_ms
                   << " unaccounted_ms=" << (per_core.size()==1 ? std::max(0.,r.ms-r.nn_ms-r.select_ms-r.expand_ms-r.backup_ms) : -1.)
                   << " stop=" << r.stop_reason;
            telemetry(detail.str());
          }
          say("bestmove "+r.best);
        }catch(const std::exception& e){say(std::string("info string ERROR search: ")+e.what());say("bestmove 0000");}
      });return;
    }
  }
  void close(){cancel();}
  void cmd_batch_size(int n){settings_.batch_size=std::clamp(n,1,256);}
  void cmd_cores(int n){settings_.cores=std::clamp(n,1,256);}
  void cmd_simulations(int n){settings_.simulations=std::clamp(n,1,10000000);}
  void cmd_max_nodes(int n){settings_.max_tree_nodes=std::clamp(n,0,10000000);}
  void cmd_tmax(int n){settings_.tmax=std::clamp(n,0,3600000);}
  void cmd_timeout(int n){settings_.timeout=std::clamp(n,0,3600000);}
  void cmd_cpuct(double n){settings_.cpuct=std::max(0.0001,n);}
  void cmd_verbose(int n){settings_.verbose=std::clamp(n,0,2);}
  void cmd_weights(std::string w){settings_.weights=std::move(w);}
  void report_startup(const char* argv0) const {
    telemetry("⚙️ AlphaZero C++ " + std::string(az_config::kVersion) +
              " build=" + std::string(__DATE__) + " " + __TIME__);
#if defined(_WIN32)
    telemetry("⚙️ platform=Windows X86 compiler=MSVC " + std::to_string(_MSC_VER));
#elif defined(__APPLE__)
    telemetry("⚙️ platform=macOS compiler=" + std::string(__VERSION__));
#elif defined(__linux__)
    telemetry("⚙️ platform=Debian/Linux compiler=" + std::string(__VERSION__));
#else
    telemetry("⚙️ platform=unknown compiler=unknown");
#endif
    telemetry("⚙️ executable=" + executable_path(argv0));
    telemetry("⚙️ network=" + absolute_path(settings_.weights));
    telemetry("⚙️ MULTICORE=" + std::string(AZ_MULTICORE ? "ON" : "OFF") +
              " requested="+std::to_string(settings_.cores)+
              " available="+std::to_string(std::max(1u,std::thread::hardware_concurrency()))+
              " active="+std::to_string(effective_cores(settings_))+
              " backend="+settings_.backend);
  }
  void cmd_backend(std::string b){settings_.backend=std::move(b);}
  void cmd_backend_opts(std::string b){settings_.backend_options=std::move(b);}
};
} // namespace
int main(int argc,char**argv){
  az_lc0_telemetry::ScopedFilters lc0_diagnostic_filters;
  try{
    Engine engine;
    for(int i=1;i<argc;++i){std::string a=argv[i];
      if((a=="--weights"||a=="--backend"||a=="--backend-options")&&i+1<argc){auto v=std::string(argv[++i]);if(a=="--weights")engine.cmd_weights(v);else if(a=="--backend")engine.cmd_backend(v);else engine.cmd_backend_opts(v);}
      else if((a=="--simulations" || a=="--cores" || a=="--batch-size" || a=="--max-tree-nodes" || a=="--tmax" || a=="--timeout" || a=="--cpuct" || a=="--verbose") && i+1<argc){
        std::string v=argv[++i];
        if(a=="--batch-size")engine.cmd_batch_size(std::stoi(v));
        else if(a=="--cores")engine.cmd_cores(std::stoi(v));
        else if(a=="--simulations")engine.cmd_simulations(std::stoi(v));
        else if(a=="--max-tree-nodes")engine.cmd_max_nodes(std::stoi(v));
        else if(a=="--tmax")engine.cmd_tmax(std::stoi(v));
        else if(a=="--timeout")engine.cmd_timeout(std::stoi(v));
        else if(a=="--cpuct")engine.cmd_cpuct(std::stod(v));
        else engine.cmd_verbose(std::stoi(v));
      }
      else if(a=="--version"){
        std::cout << az_config::kUciName << " build=" << __DATE__ << " " << __TIME__ << std::endl;
        return 0;
      }
      else if(a=="--help"){std::cerr<<"AlphaZero --weights FILE.pb.gz [--backend onnx-dml|eigen] [--backend-options OPTIONS] [--simulations N] [--batch-size N] [--cores N] [--max-tree-nodes N] [--tmax MS] [--timeout MS] [--cpuct C] [--verbose N] [--version]"<<std::endl;return 0;}
      else throw std::runtime_error("unknown CLI argument: "+a);
    }
    engine.report_startup(argc > 0 ? argv[0] : nullptr);
    std::string line;while(std::getline(std::cin,line)){
      line=trim(line);if(line=="quit")break;
      telemetry("⬅️ UCI " + line);
      try{engine.process(line);}catch(const std::exception& e){say(std::string("info string ERROR command: ")+e.what());}
    }
    engine.close();return 0;
  }catch(const std::exception& e){std::cerr<<"AlphaZero fatal: "<<e.what()<<std::endl;return 1;}
}
