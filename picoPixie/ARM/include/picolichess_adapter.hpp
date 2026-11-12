#pragma once
#include "board.hpp"
#include <cstdint>
#include <string>
namespace picoLichess {
struct CloudOutcome {
    bool has_move=false;
    bool fallback=false;
    bool no_evaluator=false;
    std::string move;
    int cp=0;
    int depth=0;
    uint64_t time_ms=0; // remote exchange time; excludes THROTTLE waiting
    uint64_t nodes=0;   // Stockfish nodes from Chess-API debug when reported
    uint64_t nps=0;     // Stockfish nps from Chess-API debug when reported
    bool is_mate=false;
    int mate=0;
};
// Optional, platform-specific strategy. The board, NNUE, TCP, UCI, Wi-Fi,
// multicore search and all main-loop state remain owned by picoSargon.
CloudOutcome cloud_evaluate(const picoSargon::Board& board,
    uint64_t now_ms,
    bool (*interrupted)(), void (*service)());
}
