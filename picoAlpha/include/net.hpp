#pragma once
#include "board.hpp"
#include <vector>
#include <array>
#include <cstdint>
namespace picoalpha {
struct Layer {int in=0,out=0,k=0;const int8_t* weights=nullptr;const float* scale=nullptr;const float* bias=nullptr;};
struct SE {const float *w1=nullptr,*b1=nullptr,*w2=nullptr,*b2=nullptr;};
struct Result {std::vector<float> policy;float q=0;};
class Network {
 Layer input_,p1_,pol_,vconv_;
 std::array<Layer,4> residual_{};std::array<SE,2> se_{};
 const float *v1w_=nullptr,*v1b_=nullptr,*v2w_=nullptr,*v2b_=nullptr;
 public:
 Network();
 Result evaluate(const std::array<float,112*64>& planes)const;
};
std::array<float,112*64> encode(const std::vector<picoSargon::Board>& history,bool fen_only);
int policy_index(const picoSargon::Board& b,picoSargon::Move move);
}
