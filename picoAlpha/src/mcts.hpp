#pragma once
#include "nnue.hpp"
#include <chrono>
#include <atomic>
#include <memory>
#include <string>
#include <vector>
namespace picoalpha {
struct Result {
 picoSargon::Move move{};bool valid=false;
 int simulations=0,nodes=0,depth=0,visits=0,elapsed_ms=0;
 double value=0,root_value=0;
 std::string reason;
};
class Search {
public:
 Result run(picoSargon::Board& board,const Network& net,int simulations,int depth,int time_ms,double cpuct=1.4,const std::atomic<bool>* stop=nullptr);
private:
 struct Node {picoSargon::Move move{};double prior=0,value_sum=0;int visits=0;bool expanded=false;std::vector<std::unique_ptr<Node>> children;};
 static Node* select(Node& n,double cpuct);
 static bool terminal(picoSargon::Board& board,double& value);
 static void expand(Node& n,const std::vector<picoSargon::Move>& moves,const std::vector<double>& priors,int& nodes);
};
}
