#pragma once
#include "board.hpp"
#include "compact_history.hpp"
#include <vector>
#include <array>
#include <cstdint>
namespace picoalpha {
struct Layer {int in=0,out=0,k=0;const int8_t* weights=nullptr;const float* scale=nullptr;const float* bias=nullptr;};
struct SE {const float *w1=nullptr,*b1=nullptr,*w2=nullptr,*b2=nullptr;};
struct Result {const float* policy=nullptr;size_t count=0;float q=0;};
struct DualCoreProfile {bool active=false;uint32_t jobs=0;uint64_t wait_us=0,core1_us=0;uint32_t timeouts=0;};
void dual_core_start();
DualCoreProfile dual_core_profile();
void dual_core_reset_profile();
struct NNProfile {uint32_t inferences=0;uint64_t total_us=0,conv_res_us=0,policy_us=0,value_conv_us=0,fc1_us=0,fc2_us=0;};
class Network {
 struct Workspace {
 FixedVector<float,2048> a,b,c,d;
 FixedVector<float,32> pool,se1,se2;
 FixedVector<float,4672> policy;
 FixedVector<float,128> hidden;
 FixedVector<float,8> scalar;
 FixedVector<int8_t,7168> quant;
 FixedVector<int8_t,2048> quant_b;
 FixedVector<int8_t,1024> patch;
};
 mutable Workspace workspace_;
 mutable NNProfile profile_{};
 mutable uint32_t cache_hits_=0,cache_misses_=0;
 mutable void (*progress_hook_)(uint32_t,uint32_t)=nullptr;
 Layer input_,p1_,pol_,vconv_;
 std::array<Layer,4> residual_{};std::array<SE,2> se_{};
 const float *v1w_=nullptr,*v1b_=nullptr,*v2w_=nullptr,*v2b_=nullptr;
 public:
 Network();
 void set_progress_hook(void(*hook)(uint32_t,uint32_t)) const {progress_hook_=hook;}
 void reset_profile() const;
 void release_workspace() const;
 NNProfile profile() const;
 uint32_t cache_hits()const{return cache_hits_;}
 uint32_t cache_misses()const{return cache_misses_;}
 Result evaluate(const std::array<float,112*64>& planes)const;
 Result evaluate_legal(const std::array<float,112*64>& planes,const FixedVector<int,256>& indices)const;
 private:
 Result evaluate_impl(const std::array<float,112*64>& planes,const FixedVector<int,256>* indices)const;
};
std::array<float,112*64> encode(const std::vector<picoSargon::Board>& history,bool fen_only);
std::array<float,112*64> encode(const CompactHistory& history,bool fen_only);
// Fills a caller-owned input buffer; avoids a 28 KiB stack temporary in MCTS.
void encode_into(const CompactHistory& history,bool fen_only,std::array<float,112*64>& out);
void encode_into(const std::vector<picoSargon::Board>& history,bool fen_only,std::array<float,112*64>& out);
int policy_index(const picoSargon::Board& b,picoSargon::Move move);
}
