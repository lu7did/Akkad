#pragma once
#include "board.hpp"
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace picoalpha {
// Exactly the same INT8 780x16 + (value, from, to) head contract as Nurse MCTSE.
class Network {
public:
 static constexpr int features=780, hidden=16, weights_count=14544;
 void load(const std::string& filename);
 struct Prediction { double value=0; std::vector<double> priors; };
 Prediction evaluate(const picoSargon::Board& board,const std::vector<picoSargon::Move>* legal=nullptr)const;
 bool loaded()const{return loaded_;}
private:
 std::array<int8_t,12480> input_{};
 std::array<int8_t,16> value_{};
 std::array<int8_t,1024> from_{},to_{};
 std::array<float,4> scale_{};
 bool loaded_=false;
};
}
