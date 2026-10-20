#pragma once
#include "board.hpp"
#include "grumpy.hpp"
#include <array>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>
namespace picoSargon {
struct MemoryStat {int32_t heap_used=-1,heap_free=-1,stack_margin=-1;};
struct Level {int depth=0; uint64_t ms=0,nodes=0,qnodes=0;bool complete=false;MemoryStat mem{};};
struct SearchResult {Move best{};bool has_move=false;int score=0,depth=0;uint64_t elapsed_ms=0,nodes=0,qnodes=0,tt_hits=0,tt_stores=0,cutoffs=0;std::vector<Level> levels;std::string reason="depth-limit";};
using ClockFn=std::function<uint64_t()>;
using StopFn=std::function<bool()>;
using MemoryFn=std::function<MemoryStat()>;
class Engine {
 const Grumpy& net_; ClockFn clock_;StopFn stop_;MemoryFn memory_;
 uint64_t nodes_=0,qnodes_=0,deadline_=0,tt_hits_=0,tt_stores_=0,cutoffs_=0;
 int qdepth_=2;static constexpr int MAX_PLY=40, TT_SIZE=256;
 struct Entry {uint64_t key=0;int32_t score=0;int8_t depth=-1;uint8_t bound=0;Move best{};};
 std::array<Entry,TT_SIZE> tt_{};
 std::array<std::array<Move,2>,MAX_PLY> killers_{};
 std::array<std::array<std::array<uint16_t,64>,64>,2> history_{};
 void check();uint64_t hash(const Board&)const;
 int negamax(Board&,int depth,int qleft,int alpha,int beta,int ply,bool pv);
 void order(Board&,std::vector<Move>&,int ply,Move ttmove);
public:
 Engine(const Grumpy& net,ClockFn clock,StopFn stop,MemoryFn memory={},int qdepth=2):net_(net),clock_(clock),stop_(stop),memory_(memory),qdepth_(qdepth){}
 SearchResult search(Board& board,int max_depth=4,uint64_t time_limit_ms=0);
};
}
