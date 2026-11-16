#include "board.hpp"
#include <iostream>
#include <vector>
#include <stdexcept>
using namespace picoSargon;
long long perft(Board& b,int d){if(d==0)return 1;std::vector<Move> moves;b.legal(moves);long long n=0;for(auto m:moves){b.push(m);n+=perft(b,d-1);b.pop();}return n;}
int main(){Board b;for(int d=1;d<=3;++d){long long n=perft(b,d);std::cout<<"perft("<<d<<")="<<n<<'\n';if(n!=(d==1?20:d==2?400:8902))return 2;}return 0;}
