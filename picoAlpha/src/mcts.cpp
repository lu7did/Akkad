#include "mcts.hpp"
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <memory>
namespace picoalpha {
using namespace picoSargon;
struct Node {Move move{};float p=1,qsum=0;uint32_t visits=0;int first=-1,count=0;bool expanded=false;};
struct Tree {
 const Network& net;std::vector<Node> nodes;const unsigned max_nodes;float cpuct;bool capped=false;
 Tree(const Network& n,unsigned cap,float c):net(n),max_nodes(cap),cpuct(c){nodes.reserve(cap);nodes.emplace_back();}
 float traverse(int idx,Board& b,std::vector<Board>& h,bool fen_only,int depth){
  if(depth>=96)return 0;
  if(b.draw())return 0;
  // Numeric indices are stable even if vector reallocates (reserve upfront).
  if(!nodes[idx].expanded){
   std::vector<Move> legal;b.legal(legal);nodes[idx].expanded=true;
   if(legal.empty())return b.in_check()?-1.f:0.f;
   if(legal.size()>max_nodes-nodes.size()){capped=true;return 0;}
   auto result=net.evaluate(encode(h,fen_only));
   std::vector<float> prob;prob.reserve(legal.size());float high=-1e30f;
   for(auto m:legal){float v=result.policy[policy_index(b,m)];prob.push_back(v);high=std::max(high,v);}
   float total=0;for(auto& v:prob){v=std::exp(v-high);total+=v;}
   if(!(total>0) || !std::isfinite(total))throw std::runtime_error("softmax invalid");
   nodes[idx].first=int(nodes.size());nodes[idx].count=int(legal.size());
   for(size_t i=0;i<legal.size();++i){Node n;n.move=legal[i];n.p=prob[i]/total;nodes.push_back(n);}
   nodes[idx].visits++;nodes[idx].qsum+=result.q;return result.q;
  }
  if(nodes[idx].count==0)return b.in_check()?-1.f:0.f;
  int best=-1;float best_score=-1e30f;float n=std::sqrt(float(std::max<uint32_t>(1, nodes[idx].visits)));
  for(int i=0;i<nodes[idx].count;++i){int j=nodes[idx].first+i;const auto& child=nodes[j];float q=child.visits?child.qsum/child.visits:0;float u=cpuct*child.p*n/(1+child.visits);float score=-q+u;if(score>best_score){best_score=score;best=j;}}
  if(best<0)return 0;
  b.push(nodes[best].move);h.push_back(b);float value=-traverse(best,b,h,fen_only,depth+1);h.pop_back();b.pop();
  nodes[idx].visits++;nodes[idx].qsum+=value;return value;
 }
};
SearchResult search(const Network& net,Board board,const std::vector<Board>& history,bool fen_only,unsigned simulations,float cpuct,unsigned max_nodes,unsigned timeout_ms,NowFn now,PumpFn pump){
 SearchResult out;Tree t(net,std::max(128u,max_nodes),cpuct);auto h=history;uint64_t begin=now();
 for(unsigned i=0;i<simulations;++i){
  if(pump&&pump()){out.reason="interrupted";break;}
  if(timeout_ms&&now()-begin>=timeout_ms){out.reason="timeout";break;}
  if(t.capped){out.reason="tree_limit";break;}
  t.traverse(0,board,h,fen_only,0);out.simulations++;
 }
 int best=-1;
 for(int i=0;i<t.nodes[0].count;++i){int j=t.nodes[0].first+i;if(best<0||t.nodes[j].visits>t.nodes[best].visits)best=j;}
 if(best>=0){const Node& n=t.nodes[best];out.move=n.move;out.has=true;out.q=n.visits?-n.qsum/n.visits:0;}
 return out;
}
}
