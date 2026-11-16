#include "mcts.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <limits>
namespace picoalpha {
Search::Node* Search::select(Node& n,double cpuct){
 const double root=std::sqrt(double(std::max(1,n.visits)));
 Node* best=nullptr;double bv=-std::numeric_limits<double>::infinity();
 for(auto& ptr:n.children){Node* c=ptr.get();double q=c->visits?-c->value_sum/double(c->visits):0.0;
  double v=q+cpuct*c->prior*root/double(1+c->visits);if(v>bv){best=c;bv=v;}}
 return best;
}
void Search::expand(Node& n,const std::vector<picoSargon::Move>& moves,const std::vector<double>& priors,int& nodes){
 if(moves.size()!=priors.size())throw std::runtime_error("Policy/legal move mismatch");
 n.children.reserve(moves.size());for(size_t i=0;i<moves.size();++i){auto child=std::make_unique<Node>();child->move=moves[i];child->prior=priors[i];n.children.push_back(std::move(child));}
 n.expanded=true;nodes+=int(moves.size());
}
bool Search::terminal(picoSargon::Board& b,double& value){
 std::vector<picoSargon::Move> legal;b.legal(legal);
 if(legal.empty()){value=b.in_check()?-1.0:0.0;return true;}
 if(b.draw()){value=0;return true;}
 return false;
}
Result Search::run(picoSargon::Board& b,const Network& net,int sims,int depth,int time_ms,double cpuct,const std::atomic<bool>* stop){
 if(sims<1||depth<1||time_ms<1||!std::isfinite(cpuct)||cpuct<=0)throw std::invalid_argument("Invalid search limits");
 auto start=std::chrono::steady_clock::now();auto deadline=start+std::chrono::milliseconds(time_ms);
 Result r;r.nodes=1;Node root;
 std::vector<picoSargon::Move> root_moves;b.legal(root_moves);
 if(root_moves.empty()){r.reason="terminal";return r;}
 const auto pred=net.evaluate(b,&root_moves);r.root_value=pred.value;
 expand(root,root_moves,pred.priors,r.nodes);
 for(int k=0;k<sims && !(stop && stop->load()) && std::chrono::steady_clock::now()<deadline;++k){
  std::vector<Node*> trail;trail.reserve(depth+1);Node* node=&root;trail.push_back(node);int level=0;
  // RAII is unnecessary: all pushes are balanced before leaving the iteration.
  while(node->expanded&&!node->children.empty()&&level<depth&& !(stop && stop->load()) && std::chrono::steady_clock::now()<deadline){
   node=select(*node,cpuct);b.push(node->move);trail.push_back(node);++level;
  }
  if((stop && stop->load()) || std::chrono::steady_clock::now()>=deadline){while(level--)b.pop();break;}
  double v=0;std::vector<picoSargon::Move> legal;b.legal(legal);
  if(legal.empty())v=b.in_check()?-1.0:0.0;
  else if(b.draw())v=0.0;
  else{
   if(level<depth && !node->expanded){auto p=net.evaluate(b,&legal);v=p.value;expand(*node,legal,p.priors,r.nodes);}
   else v=net.evaluate(b).value;
  }
  for(auto it=trail.rbegin();it!=trail.rend();++it){(*it)->visits++;(*it)->value_sum+=v;v=-v;}
  for(int n=0;n<level;++n)b.pop();
  r.depth=std::max(r.depth,level);r.simulations++;
 }
 Node* best=nullptr;for(auto& ch:root.children)if(!best||ch->visits>best->visits||(ch->visits==best->visits&&ch->prior>best->prior))best=ch.get();
 r.move=best->move;r.valid=true;r.visits=best->visits;
 r.value=best->visits?-best->value_sum/double(best->visits):pred.value;
 r.elapsed_ms=std::max(1,int(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count()));
 r.reason=r.simulations>=sims?"sims":(stop&&stop->load()?"stop":"timeout");
 return r;
}
}
