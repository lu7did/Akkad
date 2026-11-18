// picoBit native BNN v0.1.10: fixed point and true XNOR/popcount inference.
// No TensorFlow, BLAS, OpenMP, or other runtime dependencies.
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <limits>
#include <new>
#include <vector>
#if defined(_MSC_VER)
#include <intrin.h>
#endif

#if defined(_WIN32)
#define BNN_API extern "C" __declspec(dllexport)
#else
#define BNN_API extern "C" __attribute__((visibility("default")))
#endif
namespace {
constexpr uint32_t Q = 1u << 20;
constexpr int C = 64, U = 256;
constexpr int64_t MAX_CP_Q = int64_t(1600) * Q; // p clipped to [1e-4, 1-1e-4]
struct Net {
 std::array<uint16_t,9*C> w1{}; // 13 channel sign bits
 std::array<uint64_t,9*C> w2{}; // 64 input channel sign bits
 std::array<uint64_t,U*64> wd{}; // 4096 input sign bits, 64 words per output
 std::array<int64_t,C> s1{},b1{},s2{},b2{};
 std::array<int64_t,U> s3{};
 int64_t b3{};
};
inline int pc(uint64_t v) {
#if defined(_MSC_VER) && defined(_M_X64)
 return int(__popcnt64(v));
#elif defined(__GNUC__) || defined(__clang__)
 return __builtin_popcountll(v);
#else
 int k=0;while(v){v&=v-1;++k;}return k;
#endif
}
template<typename T> bool read_arr(FILE* f,T* data,size_t n){return std::fread(data,sizeof(T),n,f)==n;}
inline int64_t div_round(int64_t x,int64_t y){return x>=0?(x+y/2)/y:-((-x+y/2)/y);}
}
BNN_API void* picobit_open(const char* path) {
 if (!path)return nullptr;
 FILE* f=std::fopen(path,"rb"); if(!f)return nullptr;
 char magic[8];uint32_t v=0,q=0,c=0,u=0;uint64_t sz=0,mt=0;
 bool ok=read_arr(f,magic,8)&&read_arr(f,&v,1)&&read_arr(f,&q,1)&&read_arr(f,&c,1)&&read_arr(f,&u,1)
     &&read_arr(f,&sz,1)&&read_arr(f,&mt,1);
 if(!ok||std::memcmp(magic,"PBNI0100",8)!=0||v!=1||q!=Q||c!=C||u!=U){std::fclose(f);return nullptr;}
 Net* n=new(std::nothrow) Net();if(!n){std::fclose(f);return nullptr;}
 ok=read_arr(f,n->w1.data(),n->w1.size())&&read_arr(f,n->w2.data(),n->w2.size())
 &&read_arr(f,n->wd.data(),n->wd.size())&&read_arr(f,n->s1.data(),C)
 &&read_arr(f,n->b1.data(),C)&&read_arr(f,n->s2.data(),C)
 &&read_arr(f,n->b2.data(),C)&&read_arr(f,n->s3.data(),U)
 &&read_arr(f,&n->b3,1);
 char extra; if(std::fread(&extra,1,1,f)!=0)ok=false;
 std::fclose(f);
 if(!ok){delete n;return nullptr;}
 return n;
}
BNN_API void picobit_close(void* handle){delete static_cast<Net*>(handle);}
// squares: index rank*8+file (a1=0). Piece 0 empty, 1..6 white P N B R Q K,
// 7..12 black. turn_white: 1 or 0. out_cp White perspective.
BNN_API int picobit_eval(void* handle,const uint8_t* squares,int turn_white,int* out_cp){
 if(!handle||!squares||!out_cp||(turn_white!=0&&turn_white!=1))return -1;
 const Net& n=*static_cast<const Net*>(handle);
 for(int i=0;i<64;++i)if(squares[i]>12)return -2;
 std::array<std::array<int32_t,C>,64> a1{};
 std::array<uint64_t,64> bits{};
 // First conv uses sparse 0/1 piece channels + signed side-to-move channel.
 // Because zeros are not -1, a plain XNOR would be wrong on this layer.
 for(int sq=0;sq<64;++sq){
  int row=sq/8,col=sq%8;uint64_t packed=0;
  for(int oc=0;oc<C;++oc){
   int dot=0;
   for(int kr=0;kr<3;++kr)for(int kc=0;kc<3;++kc){
    int rr=row+kr-1,cc=col+kc-1;
    if(rr<0||rr>=8||cc<0||cc>=8)continue; // SAME zero padding
    int idx=rr*8+cc;uint16_t w=n.w1[(kr*3+kc)*C+oc];
    int p=squares[idx];if(p)dot+=((w>>(p-1))&1)?1:-1;
    dot+=(turn_white?1:-1)*(((w>>12)&1)?1:-1);
   }
   int64_t qv=int64_t(dot)*n.s1[oc]+n.b1[oc];
   if(qv<std::numeric_limits<int32_t>::min()||qv>std::numeric_limits<int32_t>::max())return -3;
   a1[sq][oc]=int32_t(qv);
   if(qv>=0)packed|=(uint64_t(1)<<oc); // 0 binarizes to +1
  }
  bits[sq]=packed;
 }
 // Second convolution: XNOR + POPCOUNT for each 64-channel 3x3 kernel.
 // Residual addition happens BEFORE dense sign binarization.
 std::array<uint64_t,64> dense_bits{};
 for(int sq=0;sq<64;++sq){
  int row=sq/8,col=sq%8;uint64_t packed=0;
  for(int oc=0;oc<C;++oc){
   int dot=0;
   for(int kr=0;kr<3;++kr)for(int kc=0;kc<3;++kc){
    int rr=row+kr-1,cc=col+kc-1;
    if(rr<0||rr>=8||cc<0||cc>=8)continue;
    uint64_t w=n.w2[(kr*3+kc)*C+oc];
    dot+=2*pc(~(bits[rr*8+cc]^w))-64;
   }
   int64_t qv=int64_t(dot)*n.s2[oc]+n.b2[oc]+a1[sq][oc];
   if(qv>=0)packed|=(uint64_t(1)<<oc);
  }
  dense_bits[sq]=packed;
 }
 // Binary dense: 4096 inputs in 64 packed words. BN3 + final Dense +
 // inverse sigmoid are algebraically folded into integer CP coefficients.
 int64_t cpq=n.b3;
 for(int oc=0;oc<U;++oc){
  int dot=0;
  for(int k=0;k<64;++k)dot+=2*pc(~(dense_bits[k]^n.wd[oc*64+k]))-64;
  cpq+=int64_t(dot)*n.s3[oc];
 }
 if(cpq>MAX_CP_Q)cpq=MAX_CP_Q;
 if(cpq< -MAX_CP_Q)cpq= -MAX_CP_Q;
 *out_cp=int(div_round(cpq,Q));
 return 0;
}
BNN_API int picobit_version(){return 110;}
