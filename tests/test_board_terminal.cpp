#include "board.hpp"
#include <cassert>
#include <iostream>
#include <vector>
using namespace picoSargon;
int main(){
 const char* finalfen="8/8/8/4pp2/8/8/5k1K/8 b - - 1 49";
 Board b(finalfen);std::vector<Move> legal;b.legal(legal);assert(!legal.empty());assert(!b.draw());
 Board bare("8/8/8/8/8/8/4k3/7K w - - 0 1");assert(bare.draw());
 Board mate("7k/6Q1/5K2/8/8/8/8/8 b - - 0 1");mate.legal(legal);assert(legal.empty()&&mate.in_check());
 Board stale("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1");stale.legal(legal);assert(legal.empty()&&!stale.in_check());
 Board replay;const char* seq[]={"g1f3","g8f6","f3g1","f6g8","g1f3","g8f6","f3g1","f6g8"};for(const auto* m:seq)replay.push(replay.parse(m));assert(replay.repetitions()==3);assert(replay.draw());
 std::cout<<"OK: endgame, insufficient material, mate, stalemate, triple repetition\n";
}
