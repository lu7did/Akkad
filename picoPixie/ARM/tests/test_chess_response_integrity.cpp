#include "cloud_pv.hpp"
#include <cassert>
int main(){
 using namespace picoLichess;
 const std::string fen="1k1r4/pp1b1R2/3q2pp/4p3/2B5/4Q3/PPP2B2/2K5 b - - 0 1";
 assert(chess_response_matches_fen("{\"fen\":\""+fen+"\",\"move\":\"d8d1\"}",fen));
 assert(!chess_response_matches_fen("{\"fen\":\"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\",\"move\":\"e2e4\"}",fen));
 assert(!chess_response_matches_fen("}{\"fen\":\""+fen+"\"}",fen));
 assert(!chess_response_matches_fen("{\"fen\":\""+fen+"\"}{\"fen\":\""+fen+"\"}",fen));
 assert(!chess_response_matches_fen("{\"fen\":\""+fen+"\"",fen));
}
