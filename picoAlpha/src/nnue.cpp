#include "nnue.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace picoalpha {
namespace {
// Portable, little-endian, versioned binary: magic[8], version(u32), dims[2](u32),
// four float32 scales, four raw INT8 matrices (row-major). No interpreter at runtime.
const unsigned char magic[8]={'P','A','N','N','I','8','\r','\n'};
uint32_t read_u32(std::istream& in){unsigned char b[4];if(!in.read((char*)b,4))throw std::runtime_error("Truncated INT8 header");return uint32_t(b[0])|(uint32_t(b[1])<<8)|(uint32_t(b[2])<<16)|(uint32_t(b[3])<<24);}
float read_f32(std::istream& in){uint32_t raw=read_u32(in);float f;static_assert(sizeof(float)==4,"IEEE754 float32 required");std::memcpy(&f,&raw,4);return f;}
int orient(int sq,int turn){int x=sq%8,y=sq/8;int ix=(7-y)*8+x;return turn==1?ix:63-ix;}
}
void Network::load(const std::string& file){
 loaded_=false;std::ifstream in(file,std::ios::binary);if(!in)throw std::runtime_error("Cannot open INT8 model: "+file);
 unsigned char b[8];if(!in.read((char*)b,8)||std::memcmp(b,magic,8))throw std::runtime_error("Invalid model magic: expected PANni8 binary (convert .pt first)");
 if(read_u32(in)!=1||read_u32(in)!=features||read_u32(in)!=hidden)throw std::runtime_error("Unsupported INT8 model version/architecture");
 for(auto& s:scale_){s=read_f32(in);if(!std::isfinite(s)||s<=0)throw std::runtime_error("Invalid INT8 quantization scale");}
 if(!in.read((char*)input_.data(),input_.size())||!in.read((char*)value_.data(),value_.size())||!in.read((char*)from_.data(),from_.size())||!in.read((char*)to_.data(),to_.size()))throw std::runtime_error("Truncated INT8 model weights");
 if(in.peek()!=std::char_traits<char>::eof())throw std::runtime_error("Unexpected trailing bytes in model");
 loaded_=true;
}
Network::Prediction Network::evaluate(const picoSargon::Board& b,const std::vector<picoSargon::Move>* moves)const{
 if(!loaded_)throw std::runtime_error("Model not loaded");
 int32_t h[hidden]={};const int side=b.turn;
 for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;int kind=(std::abs(p)-1)+(p*side>0?0:6);int ix=kind*64+orient(sq,side);const int8_t* row=input_.data()+ix*hidden;for(int j=0;j<hidden;++j)h[j]+=row[j];}
 const auto rights=[&](int color,bool king){uint8_t mask=color==1?(king?1:2):(king?4:8);return (b.castling&mask)!=0;};
 // Same order as mcts_nnue.feature_indices: own K,Q then opponent K,Q.
 for(int k=0;k<4;++k){int color=(k<2?side:-side);if(rights(color,k%2==0)){const int8_t* row=input_.data()+(768+k)*hidden;for(int j=0;j<hidden;++j)h[j]+=row[j];}}
 if(b.ep>=0){int f=b.ep%8;int ix=772+(side==1?f:7-f);const int8_t* row=input_.data()+ix*hidden;for(int j=0;j<hidden;++j)h[j]+=row[j];}
 for(int j=0;j<hidden;++j)h[j]=std::max<int32_t>(0,h[j]);
 int32_t v=0;for(int j=0;j<hidden;++j)v+=int32_t(value_[j])*h[j];
 Prediction out;out.value=std::tanh(double(v)*double(scale_[0])*double(scale_[1]));
 if(!moves||moves->empty())return out;
 double frm[64],dst[64];
 for(int i=0;i<64;++i){int32_t f=0,t=0;for(int j=0;j<hidden;++j){f+=int32_t(from_[i*hidden+j])*h[j];t+=int32_t(to_[i*hidden+j])*h[j];}frm[i]=double(f)*double(scale_[0])*double(scale_[2]);dst[i]=double(t)*double(scale_[0])*double(scale_[3]);}
 out.priors.resize(moves->size());double maxlogit=-1e300;
 for(size_t k=0;k<moves->size();++k){const auto m=(*moves)[k];double logit=frm[orient(picoSargon::from120(m.from),side)]+dst[orient(picoSargon::from120(m.to),side)];out.priors[k]=logit;maxlogit=std::max(maxlogit,logit);}
 double z=0;for(auto& p:out.priors){p=std::exp(p-maxlogit);z+=p;}for(auto& p:out.priors)p/=z;
 return out;
}
}
