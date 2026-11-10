#pragma once
#include "board.hpp"
#include "model.hpp"
#include <cstdint>
#include <vector>

struct ParallelResult {
 picoSargon::Move move{};
 bool found=false;
 bool timed_out=false;
 double score=0.0; // value from the perspective of the side to move
 int depth=0; // last fully completed depth; 0 only if no iteration completed
 int requested_depth=2;
 bool fallback=false;
 std::vector<std::int64_t> level_ms;
 int workers=0;
 std::uint64_t nodes=0, leaves=0, batches=0, evaluations=0;
 std::int64_t elapsed_ms=0, inference_us=0;
 std::vector<std::uint64_t> worker_nodes;
};

// All evaluators must belong to distinct workers (TensorFlow sessions / TFLite interpreters
// must not be invoked concurrently by multiple workers). Their thread budgets are
// configured before entry; the caller owns them for the duration of this call.
ParallelResult choose_multicore(const picoSargon::Board& board,
                                const std::vector<Evaluator*>& evaluators,
                                int depth, std::int64_t budget_ms);
