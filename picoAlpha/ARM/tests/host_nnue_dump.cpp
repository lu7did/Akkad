#include "nnue_int8.hpp"
#include "board.hpp"
#include <cstdio>
#include <vector>
int main(){
 static const char* fen[]={
 "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
 "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
 "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
 "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
 "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
 "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
 "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
 "8/P7/8/8/8/8/7p/4k2K w - - 0 1",
 };
 for(auto f:fen){
  picoSargon::Board b(f);
  std::vector<picoSargon::Move> legal;b.legal(legal);
  float probs[256]{},val=0;
  if(!legal.empty())picoalpha_arm::NNUE::evaluate_policy(b,legal.data(),int(legal.size()),probs,&val);
  else val=picoalpha_arm::NNUE::evaluate_value(b).value;
  printf("FEN\t%s\t%.9g\n",f,val);
  for(size_t i=0;i<legal.size();++i)printf("MOVE\t%s\t%.9g\n",picoSargon::Board::notation(legal[i]).c_str(),probs[i]);
  printf("END\n");
 }
}
