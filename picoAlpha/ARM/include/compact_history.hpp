#pragma once
#include "board.hpp"
#include <array>
#include <cstdint>
#include <vector>
// PA_COMPACT_HISTORY_BEGIN v0.2.16: revert with PA_COMPACT_HISTORY=0.
#ifndef PA_COMPACT_HISTORY
#define PA_COMPACT_HISTORY 1
#endif
namespace picoalpha {
struct CompactState {
 CompactState()=default;
 std::array<uint8_t,32> packed{}; // two pieces per byte, (piece+6) in [0,12]
 int8_t turn=1;
 uint8_t castling=15;
 uint16_t halfmove=0;
 uint8_t repeated=0;
 explicit CompactState(const picoSargon::Board& b) : turn(int8_t(b.turn)),castling(b.castling),halfmove(uint16_t(b.halfmove)), repeated(uint8_t(b.repetitions()>=2)) {
  for(int i=0;i<64;++i){auto v=uint8_t(b.piece(i)+6);if(i&1)packed[i>>1]|=uint8_t(v<<4);else packed[i>>1]=v;}
 }
 int piece(int i) const {auto v=packed[i>>1];return int((i&1)?(v>>4):(v&15))-6;}
};
static_assert(sizeof(CompactState)<=40,"CompactState unexpectedly large");
using CompactHistory=FixedVector<CompactState,256>;
} // namespace picoalpha
// PA_COMPACT_HISTORY_END
