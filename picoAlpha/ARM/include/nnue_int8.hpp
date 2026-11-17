#pragma once
#include "board.hpp"
#include <cstdint>
namespace picoalpha_arm {
struct NNPrediction { float value=0; };
// No mutable state, weights remain read-only in Flash.
class NNUE final {
public:
  static NNPrediction evaluate_value(const picoSargon::Board& b);
  static void evaluate_policy(const picoSargon::Board& b, const picoSargon::Move* legal,
                              int n, float* priors, float* value_out=nullptr);
};
}
