#pragma once
#include "net.hpp"
#include <cstdint>
namespace picoalpha {
struct SearchResult {picoSargon::Move move{};bool has=false;unsigned simulations=0;float q=0;const char* reason="complete";};
using NowFn=uint64_t(*)();
using PumpFn=bool(*)();
SearchResult search(const Network& net,picoSargon::Board board,const std::vector<picoSargon::Board>& history,bool fen_only,unsigned simulations,float cpuct,unsigned max_nodes,unsigned timeout_ms,NowFn now,PumpFn pump);
}
