#include "multicore.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <exception>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <thread>
#include <utility>

namespace {
using Clock=std::chrono::steady_clock;
using picoSargon::Board;
using picoSargon::Move;
using TimePoint=Clock::time_point;
struct WorkerData {
 std::uint64_t nodes=0, leaves=0, batches=0, evaluations=0;
 std::int64_t inference_us=0;
};
struct SearchValue {double value=0.0; bool complete=false;};
constexpr double INF=2.0; // network evaluation is constrained to [-1,+1]

bool expired(const TimePoint& deadline) {return Clock::now()>=deadline;}
SearchValue minimax(Board& board, Evaluator& evaluator, int depth,
                    double alpha, double beta, const TimePoint& deadline,
                    WorkerData& stats) {
 if(expired(deadline))return {};
 ++stats.nodes;
 if(board.draw())return {0.0,true};
 std::vector<Move> legal;
 board.legal(legal);
 if(legal.empty())return {board.in_check()?-1.0:0.0,true};
 if(depth<=0){
  const auto start=Clock::now();
  const double v=evaluator.eval(board);
  stats.inference_us+=std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-start).count();
  ++stats.leaves; ++stats.evaluations; ++stats.batches;
  return {v,!expired(deadline)};
 }
 // Batch all sibling leaves. Avoids one neural invocation per chess move.
 if(depth==1){
  std::vector<Board> batch;
  std::vector<size_t> indices;
  std::vector<double> values(legal.size());
  batch.reserve(legal.size());indices.reserve(legal.size());
  for(size_t i=0;i<legal.size();++i){
   if(expired(deadline))return {};
   board.push(legal[i]);
   if(board.draw())values[i]=0.0;
   else {
    std::vector<Move> replies;board.legal(replies);
    if(replies.empty())values[i]=board.in_check()?-1.0:0.0;
    else {batch.push_back(board);indices.push_back(i);}
   }
   board.pop();
   ++stats.nodes; ++stats.leaves;
  }
  if(!batch.empty()){
   const auto start=Clock::now();
   auto predicted=evaluator.eval_batch(batch);
   stats.inference_us+=std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-start).count();
   if(predicted.size()!=indices.size())throw std::runtime_error("neural batch size mismatch");
   ++stats.batches; stats.evaluations+=batch.size();
   for(size_t j=0;j<indices.size();++j)values[indices[j]]=predicted[j];
  }
  if(expired(deadline))return {};
  double best=-INF;
  for(double child_value:values)best=(std::max)(best,-child_value);
  return {best,true};
 }
 double best=-INF;
 for(Move move:legal){
  if(expired(deadline))return {};
  board.push(move);
  auto child=minimax(board,evaluator,depth-1,-beta,-alpha,deadline,stats);
  board.pop();
  if(!child.complete)return {};
  const double v=-child.value;
  best=(std::max)(best,v);
  alpha=(std::max)(alpha,v);
  if(alpha>=beta)break;
 }
 return {best,true};
}
}

ParallelResult choose_multicore(const Board& board,
                                const std::vector<Evaluator*>& evaluators,
                                int depth, std::int64_t budget_ms) {
 if(evaluators.empty() || depth<2 || depth>8 || budget_ms<1)
  throw std::invalid_argument("invalid multicore search configuration");
 const auto start=Clock::now();
 const auto deadline=start+std::chrono::milliseconds(budget_ms);
 ParallelResult result;
 result.requested_depth=depth;
 std::vector<Move> moves;
 Board root=board;
 root.legal(moves);
 if(root.draw()||moves.empty())return result;
 const unsigned workers=static_cast<unsigned>((std::min)(evaluators.size(),moves.size()));
 result.workers=static_cast<int>(workers);
 result.worker_nodes.assign(workers,0);
 // A result from a partially completed iteration is NEVER eligible as bestmove.
 // Depth 1 preserves batching so the first complete iteration is inexpensive.
 for(int current_depth=1; current_depth<=depth; ++current_depth){
  if(expired(deadline)){result.timed_out=true;break;}
  const auto level_start=Clock::now();
  std::vector<double> values(moves.size(),-INF);
  std::vector<unsigned char> completed(moves.size(),0);
  std::vector<WorkerData> data(workers);
  bool complete=true;
  if(current_depth==1){
   std::vector<Board> batch;
   std::vector<size_t> indices;
   batch.reserve(moves.size());indices.reserve(moves.size());
   for(size_t i=0;i<moves.size();++i){
    if(expired(deadline)){complete=false;break;}
    Board child=board;child.push(moves[i]);
    if(child.draw()){values[i]=0.0;completed[i]=1;}
    else{
     std::vector<Move> replies;child.legal(replies);
     if(replies.empty()){values[i]=child.in_check()?1.0:0.0;completed[i]=1;}
     else{batch.push_back(std::move(child));indices.push_back(i);}
    }
    ++data[0].nodes;++data[0].leaves;
   }
   if(complete && !batch.empty()){
    const auto t0=Clock::now();
    const auto predictions=evaluators[0]->eval_batch(batch);
    data[0].inference_us+=std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-t0).count();
    if(predictions.size()!=indices.size())throw std::runtime_error("neural batch size mismatch");
    data[0].batches++;data[0].evaluations+=batch.size();
    for(size_t j=0;j<indices.size();++j){values[indices[j]]=-predictions[j];completed[indices[j]]=1;}
   }
   if(expired(deadline))complete=false;
  }else{
   std::vector<std::exception_ptr> failures(workers);
   std::atomic<size_t> next{0};
   std::vector<std::thread> threads;
   threads.reserve(workers);
   for(unsigned w=0;w<workers;++w){
    threads.emplace_back([&,w]{
     try{
      auto& evaluator=*evaluators[w];
      auto& stats=data[w];
      while(!expired(deadline)){
       const size_t i=next.fetch_add(1,std::memory_order_relaxed);
       if(i>=moves.size())break;
       Board child=board;child.push(moves[i]);
       const auto value=minimax(child,evaluator,current_depth-1,-INF,INF,deadline,stats);
       if(value.complete){values[i]=-value.value;completed[i]=1;}
      }
     }catch(...){failures[w]=std::current_exception();}
    });
   }
   for(auto& t:threads)t.join();
   for(const auto& failure:failures)if(failure)std::rethrow_exception(failure);
   complete=std::all_of(completed.begin(),completed.end(),[](unsigned char x){return x!=0;});
  }
  for(size_t w=0;w<data.size();++w){
   const auto& stats=data[w];
   result.nodes+=stats.nodes;result.leaves+=stats.leaves;
   result.batches+=stats.batches;result.evaluations+=stats.evaluations;
   result.inference_us+=stats.inference_us;
   result.worker_nodes[w]+=stats.nodes;
  }
  result.level_ms.push_back(std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-level_start).count());
  if(!complete){result.timed_out=true;break;}
  double best=-INF;
  for(size_t i=0;i<moves.size();++i){
   if(!result.found || values[i]>best){
    result.found=true;result.move=moves[i];result.score=values[i];best=values[i];
   }
  }
  result.depth=current_depth;
 }
 result.elapsed_ms=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-start).count();
 if(result.depth<depth)result.timed_out=true;
 // Only if no iteration completed; the fallback score must NOT masquerade
 // as a neural evaluation or a completed depth.
 if(!result.found){result.move=moves.front();result.found=true;result.score=0.0;result.fallback=true;}
 return result;
}
