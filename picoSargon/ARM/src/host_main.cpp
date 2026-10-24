//================================================================================================================*
//* Proyecto sargon-nnue
//* Chess player using different Neural Networks as the game evaluation engine
//*
//* A new mind for the old buddy
//* Created as a learning experience
//*
//* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
//* License: CC AS BY 4.0
//*================================================================================================================*
//* host_main.cpp
//* Entry point de ejecución de host 
//*=================================================================================================================*
#include "board.hpp"
#include "engine.hpp"
#include "config.h"
#include "grumpy.hpp"
#include <iostream>
#include <chrono>
#include <sstream>
using namespace picoSargon;
static uint64_t ms(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
uint64_t perft(Board& b,int depth){if(depth==0)return 1;std::vector<Move> moves;b.legal(moves);uint64_t n=0;for(Move m:moves){b.push(m);n+=perft(b,depth-1);b.pop();}return n;}
int main(int argc,char**argv){try{if(argc>=2&&std::string(argv[1])=="--perft"){int depth=argc>2?std::stoi(argv[2]):3;Board b;std::cout<<"perft="<<perft(b,depth)<<"\n";return 0;}Grumpy net;net.load(argc>1?argv[1]:"assets/grumpy.bin");Board b;std::cout<<"picoSargon C++ v0.2.10 net="<<net.evaluate(b)<<"\n";std::string line;while(std::getline(std::cin,line)){std::istringstream ss(line);std::string cmd;ss>>cmd;if(cmd=="uci"){std::cout<<"id name "<<config::UCI_NAME<<"\nid author Dr. Pedro E. Colla\nuciok\n";}else if(cmd=="isready")std::cout<<"readyok\n";else if(cmd=="ucinewgame")b.reset();else if(cmd=="position"){std::string t;ss>>t;if(t=="startpos")b.reset();else if(t=="fen"){std::string f,part;for(int i=0;i<6&&ss>>part;++i){if(i)f+=" ";f+=part;}b.set_fen(f);}while(ss>>t){if(t=="moves")continue;b.push(b.parse(t));}}else if(cmd=="go"){auto r=Engine(net,ms,[]{return false;},{},config::QDEPTH).search(b,config::DEPTH,config::TIMEOUT_MS);for(auto& l:r.levels)std::cerr<<"LEVEL depth="<<l.depth<<" status="<<(l.complete?"complete":"aborted")<<" elapsed_ms="<<l.ms<<" nodes="<<l.nodes<<"\n";std::cout<<"info depth "<<r.depth<<" score cp "<<r.score<<" nodes "<<r.nodes<<"\nbestmove "<<(r.has_move?Board::notation(r.best):"0000")<<"\n";}else if(cmd=="quit")break;std::cout.flush();}}catch(const std::exception& e){std::cerr<<"FATAL "<<e.what()<<"\n";return 1;}}
