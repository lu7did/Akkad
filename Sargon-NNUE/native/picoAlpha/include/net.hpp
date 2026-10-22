#pragma once
#include "board.hpp"
#include <vector>
#include <string>
#include <array>
#include <memory>
#include <cstdint>
namespace picoalpha {
struct Layer {int in=0,out=0,k=0;std::vector<float> w,b;std::vector<int8_t> qweights;std::vector<float> qscale;};
struct SE {std::vector<float> w1,b1,w2,b2;};
struct Result {std::vector<float> policy;float q=0;};
class Network {
 Layer input_,p1_,pol_,vconv_;
 std::array<Layer,4> residual_;std::array<SE,2> se_;
 std::vector<float> v1w_,v1b_,v2w_,v2b_;
 bool int8_=false;
public:
 explicit Network(const std::string& path,bool int8=false);
 Result evaluate(const std::array<float,112*64>& planes)const;
};
std::array<float,112*64> encode(const std::vector<picoSargon::Board>& history,bool fen_only);
int policy_index(const picoSargon::Board& b,picoSargon::Move move);
}
