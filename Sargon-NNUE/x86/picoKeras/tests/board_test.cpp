#include "board.hpp"
#include <cassert>
#include <vector>
#include <iostream>
using namespace picoSargon;
int main(){Board b;std::vector<Move> m;b.legal(m);assert(m.size()==20);
 b.push(b.parse("e2e4"));b.push(b.parse("e7e5"));b.push(b.parse("g1f3"));b.push(b.parse("b8c6"));b.legal(m);assert(!m.empty());
 Board mate("7k/6Q1/5K2/8/8/8/8/8 b - - 0 1");mate.legal(m);assert(m.empty()&&mate.in_check());
 Board stalemate("7k/5K2/6Q1/8/8/8/8/8 b - - 0 1");stalemate.legal(m);assert(m.empty()&&!stalemate.in_check());
 Board draw("8/8/8/8/8/8/4K3/7k w - - 0 1");assert(draw.draw());
 std::cout<<"BOARD TESTS OK\n";}
