#include "nnue_int8.hpp"
#include "picoalpha_nnue_weights.hpp"
#include <cmath>
#include <cstdint>
#include <cstring>
namespace picoalpha_arm {
namespace {
using namespace picoalpha_nnue;
static_assert(INPUTS==780 && HIDDEN==16, "Unexpected picoAlpha NNUE architecture");
static_assert(sizeof(W_INPUT)==12480 && sizeof(W_VALUE)==16 && sizeof(W_FROM)==1024 && sizeof(W_TO)==1024,"Wrong INT8 blob dimensions");
inline int orient(int sq,int turn) {int x=sq%8,y=sq/8;int ix=(7-y)*8+x;return turn==1?ix:63-ix;}
inline void make_hidden(const picoSargon::Board& b,int32_t (&h)[HIDDEN]) {
 std::memset(h,0,sizeof(h)); const int side=b.turn;
 for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;
   int k=(p>0?p:-p)-1+(p*side>0?0:6);
   const int8_t* row=W_INPUT+(k*64+orient(sq,side))*HIDDEN;
   for(int j=0;j<HIDDEN;++j)h[j]+=row[j];
 }
 for(int k=0;k<4;++k){int color=k<2?side:-side;
   uint8_t mask=color==1?(k%2==0?1:2):(k%2==0?4:8);
   if(b.castling&mask){const int8_t* row=W_INPUT+(768+k)*HIDDEN;
     for(int j=0;j<HIDDEN;++j)h[j]+=row[j];}
 }
 if(b.ep>=0){int file=b.ep%8, idx=772+(side==1?file:7-file);
   const int8_t* row=W_INPUT+idx*HIDDEN;
   for(int j=0;j<HIDDEN;++j)h[j]+=row[j];
 }
 for(int j=0;j<HIDDEN;++j)if(h[j]<0)h[j]=0;
}
// A chess position has at most 32 active pieces + 4 castling + 1 en-passant
// feature, so |h[j]| <= 37*127 = 4699; signed 16-bit packing is lossless.
inline uint32_t pair16(int16_t a,int16_t b){
 return uint32_t(uint16_t(a)) | (uint32_t(uint16_t(b))<<16);
}
inline int32_t head_dot(const int8_t* mat,int sq,const int32_t (&h)[HIDDEN]) {
 const int8_t* row=mat+sq*HIDDEN;int32_t v=0;
#if defined(__ARM_FEATURE_DSP) && (defined(__arm__) || defined(__thumb__))
 // Cortex-M33 DSP: SMLAD performs two signed 16x16 MACs per instruction.
 for(int j=0;j<HIDDEN;j+=2){
  int32_t w=int32_t(pair16(row[j],row[j+1]));
  int32_t x=int32_t(pair16(int16_t(h[j]),int16_t(h[j+1])));
  int32_t result;
  __asm__ volatile("smlad %0, %1, %2, %3" : "=r"(result) : "r"(w),"r"(x),"r"(v));
  v=result;
 }
#else
 for(int j=0;j<HIDDEN;++j)v+=int32_t(row[j])*h[j];
#endif
 return v;
}
inline float value_of(const int32_t (&h)[HIDDEN]) {
 return tanhf(float(head_dot(W_VALUE,0,h))*W_INPUT_SCALE*W_VALUE_SCALE);
}
}
NNPrediction NNUE::evaluate_value(const picoSargon::Board& b){int32_t h[HIDDEN];make_hidden(b,h);return {value_of(h)};}
void NNUE::evaluate_policy(const picoSargon::Board& b,const picoSargon::Move* legal,int count,float* priors,float* value_out){
 int32_t h[HIDDEN];make_hidden(b,h);if(value_out)*value_out=value_of(h);
 if(count<=0)return;
 // Compute each used square once. Only legal moves enter the softmax.
 float from[64],to[64];uint8_t seen_from[64]={},seen_to[64]={};
 float peak=-1e30f;
 for(int i=0;i<count;++i){int f=orient(picoSargon::from120(legal[i].from),b.turn);
   int t=orient(picoSargon::from120(legal[i].to),b.turn);
   if(!seen_from[f]){from[f]=float(head_dot(W_FROM,f,h))*W_INPUT_SCALE*W_FROM_SCALE;seen_from[f]=1;}
   if(!seen_to[t]){to[t]=float(head_dot(W_TO,t,h))*W_INPUT_SCALE*W_TO_SCALE;seen_to[t]=1;}
   priors[i]=from[f]+to[t];if(priors[i]>peak)peak=priors[i];
 }
 float total=0;
 for(int i=0;i<count;++i){priors[i]=expf(priors[i]-peak);total+=priors[i];}
 if(total<=0){float uniform=1.0f/float(count);for(int i=0;i<count;++i)priors[i]=uniform;}
 else {float inv=1.0f/total;for(int i=0;i<count;++i)priors[i]*=inv;}
}
}
