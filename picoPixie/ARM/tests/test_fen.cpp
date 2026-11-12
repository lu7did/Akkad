#include "cloud_fen.hpp"
#include <cassert>
int main(){
  picoSargon::Board b;
  assert(picoLichess::board_fen(b)=="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  b.push(b.parse("e2e4"));
  assert(picoLichess::board_fen(b)=="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1");
  assert(picoLichess::board_fen(b,true)=="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1");
  picoSargon::Board reported("rnbqkbnr/ppp2p2/6p1/3pp2p/7P/6N1/PPPPPPP1/RNBQKB1R b KQkq h3 0 5");
  assert(picoLichess::board_fen(reported)=="rnbqkbnr/ppp2p2/6p1/3pp2p/7P/6N1/PPPPPPP1/RNBQKB1R b KQkq h3 0 5");
  assert(picoLichess::board_fen(reported,true)=="rnbqkbnr/ppp2p2/6p1/3pp2p/7P/6N1/PPPPPPP1/RNBQKB1R b KQkq - 0 5");
  assert(!picoLichess::chess_api_ep_unsupported(b));
  picoSargon::Board capturable("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 5");
  assert(picoLichess::chess_api_ep_unsupported(capturable));
  assert(picoLichess::board_fen(capturable,true)=="4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 5");
  // Exact position and entire legal move sequence from telemetry (12 Nov 2026).
  picoSargon::Board observed;
  for(const char* uci: {"d2d4","b8c6","d4d5","c6e5","e2e4","g8f6",
                         "f2f4","e5g6","e4e5","f6e4","d1e2","f7f5"})
      observed.push(observed.parse(uci));
  const std::string expected="r1bqkb1r/ppppp1pp/6n1/3PPp2/4nP2/8/PPP1Q1PP/RNB1KBNR w KQkq f6 0 7";
  assert(picoLichess::board_fen(observed)==expected);
  assert(picoLichess::board_fen(observed,true)==expected);
  assert(picoLichess::chess_api_ep_unsupported(observed));
  assert(picoSargon::Board::notation(observed.parse("e5f6"))=="e5f6");
  // EP targets that are not legally capturable remain canonicalized to '-'.
  picoSargon::Board not_capturable;
  not_capturable.push(not_capturable.parse("e2e4"));
  assert(!picoLichess::chess_api_ep_unsupported(not_capturable));
  assert(picoLichess::board_fen(not_capturable,true).find(" b KQkq - ")!=std::string::npos);
}

