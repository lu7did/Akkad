#include "nnue.hpp"
#include <iostream>
#include <iomanip>
int main(int argc,char**argv){try{
 if(argc!=3)return 1;
 picoalpha::Network net;net.load(argv[1]);picoSargon::Board b(argv[2]);std::vector<picoSargon::Move> moves;b.legal(moves);
 auto p=net.evaluate(b,&moves);std::cout<<std::setprecision(16)<<p.value<<"\n";
 for(size_t i=0;i<moves.size();++i)std::cout<<picoSargon::Board::notation(moves[i])<<" "<<std::setprecision(16)<<p.priors[i]<<"\n";
 return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
