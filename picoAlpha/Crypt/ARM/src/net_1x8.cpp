// TinyGyal-compatible 1x8 inference. Generated from the stable net.cpp kernels;
// model dimensions and FC1 export differ, encoding and policy mapping identical.
#include "net.hpp"
#include "picoGyal.hpp"
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <algorithm>
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
#include "pico/multicore.h"
#include "pico/stdlib.h"
#endif
#if defined(PICO_ON_DEVICE)
#include "pico/time.h"
#else
#include <chrono>
#endif
#include "picoGyal_fc_int8.hpp"
using namespace picoalpha;
namespace {
// Model resides in FLASH. Access weights and FC matrices without RAM copies.
const uint8_t* cur=PICOALPHA_MODEL_DATA;
const uint8_t* const end=PICOALPHA_MODEL_DATA+PICOALPHA_MODEL_SIZE;
void need(size_t n){if(n>size_t(end-cur))throw std::runtime_error("embedded model truncated");}
unsigned read32(){need(4);unsigned x=unsigned(cur[0])|(unsigned(cur[1])<<8)|(unsigned(cur[2])<<16)|(unsigned(cur[3])<<24);cur+=4;return x;}
const float* floatarray(size_t n){need(n*4);auto* p=reinterpret_cast<const float*>(cur);cur+=n*4;return p;}
Layer layer(){Layer l;l.in=int(read32());l.out=int(read32());l.k=int(read32());size_t n=size_t(l.in)*l.out*l.k*l.k;need(n);l.weights=reinterpret_cast<const int8_t*>(cur);cur+=n;cur+=(-size_t(cur-PICOALPHA_MODEL_DATA))%4;l.scale=floatarray(l.out);l.bias=floatarray(l.out);return l;}
// PA_NN_OPT_BEGIN: reusable workspace; one inference at a time (single-core search).
#ifndef PA_BINARY_FIRST_CONV
#define PA_BINARY_FIRST_CONV 1
#endif
#ifndef PA_INT8_ACTIVATIONS
#define PA_INT8_ACTIVATIONS 1
#endif
#ifndef PA_FC1_PREPACK
#define PA_FC1_PREPACK 1
#endif
#ifndef PA_FC1_DSP_PACKED
#define PA_FC1_DSP_PACKED 1
#endif
#ifndef PA_FC1_FLASH_PREFETCH
#define PA_FC1_FLASH_PREFETCH 1
#endif
#ifndef PA_FC1_CORE0_GROUPS
#define PA_FC1_CORE0_GROUPS 17
#endif
#ifndef PA_NN_PROFILE
#define PA_NN_PROFILE 1
#endif
#ifndef PA_NN_WORKSPACE
#define PA_NN_WORKSPACE 1
#endif
#ifndef PA_NN_FC_FAST
#define PA_NN_FC_FAST 1
#endif
#ifndef PA_NN_FC_INT8
#define PA_NN_FC_INT8 1
#endif
#ifndef PA_NN_DSP
#define PA_NN_DSP 1
#endif
#if defined(PICO_ON_DEVICE)
static uint64_t micros_now(){return time_us_64();}
#else
static uint64_t micros_now(){return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
#endif
// PA24_DUAL_CORE_BEGIN: one inference, disjoint output slices; MCTS stays on core 0.
#ifndef PA_DUAL_CORE_NN
#define PA_DUAL_CORE_NN 1
#endif
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
struct ParallelJob {void (*fn)(void*,int,int)=nullptr; void* ctx=nullptr; int half=0; int count=0;};
static ParallelJob parallel_job;
static volatile uint32_t published_generation=0;
static volatile uint32_t finished_generation=0;
// Dedicated 16 KiB stack: the Pico SDK default core-1 stack may be insufficient
// for the quantized DSP kernels and diagnostic call chains.
#ifndef PA_CORE1_STACK_BYTES
#define PA_CORE1_STACK_BYTES 16384
#endif
static_assert(PA_CORE1_STACK_BYTES >= 8192 && (PA_CORE1_STACK_BYTES % 8)==0,
              "Invalid core 1 stack size");
alignas(8) static uint32_t pa_core1_stack[PA_CORE1_STACK_BYTES / sizeof(uint32_t)];
static constexpr uint32_t PA_CORE1_STACK_GUARD=0xC01DCAFEu;
static bool worker_ready=false;
static volatile uint32_t worker_started=0;
static uint64_t parallel_wait_us=0,parallel_core1_us=0;
static uint32_t parallel_jobs=0,parallel_timeouts=0;
static void core1_loop(){
 uint32_t handled=0;
 __atomic_store_n(&worker_started,1u,__ATOMIC_RELEASE);
 for(;;){
  uint32_t incoming=__atomic_load_n(&published_generation,__ATOMIC_ACQUIRE);
  if(incoming==handled){__asm__ volatile("nop" ::: "memory");continue;}
  handled=incoming;
  ParallelJob job=parallel_job;
  const uint64_t t=micros_now();
  job.fn(job.ctx,job.half,job.count);
  const uint64_t elapsed=micros_now()-t;
  __atomic_fetch_add(&parallel_core1_us,elapsed,__ATOMIC_RELAXED);
  __atomic_store_n(&finished_generation,handled,__ATOMIC_RELEASE);
  __asm__ volatile("sev");
 }
}
#endif
} // close anonymous namespace for qualified picoalpha definitions
void picoalpha::dual_core_start(){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 if(!worker_ready){
  // The SDK API expects the low-address stack base and total stack size.
  // A guard at the low end is checked before and after every parallel job.
  pa_core1_stack[0]=PA_CORE1_STACK_GUARD;
  multicore_launch_core1_with_stack(core1_loop,pa_core1_stack,sizeof(pa_core1_stack));
  const uint64_t deadline=micros_now()+1000000u;
  while(!__atomic_load_n(&worker_started,__ATOMIC_ACQUIRE) && micros_now()<deadline){
   __asm__ volatile("nop" ::: "memory");
  }
  worker_ready=__atomic_load_n(&worker_started,__ATOMIC_ACQUIRE)!=0;
 }
#endif
}
picoalpha::DualCoreProfile picoalpha::dual_core_profile(){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 return {worker_ready,parallel_jobs,parallel_wait_us,parallel_core1_us,parallel_timeouts};
#else
 return {false,0,0,0,0};
#endif
}
void picoalpha::dual_core_reset_profile(){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 parallel_jobs=parallel_timeouts=0;parallel_wait_us=parallel_core1_us=0;
#endif
}
namespace {
static uint64_t fc_quant_us=0,fc_core0_us=0,fc_core1_us=0;
static uint32_t fc_core0_groups=0,fc_core1_groups=0,fc_calls=0;
static uint64_t fc_flash_bytes=0, fc_flash_prefetches=0,fc_mac_pairs=0;
}
picoalpha::FC1Detail picoalpha::fc1_detail_profile(){return {fc_quant_us,__atomic_load_n(&fc_core0_us,__ATOMIC_RELAXED),__atomic_load_n(&fc_core1_us,__ATOMIC_RELAXED),__atomic_load_n(&fc_core0_groups,__ATOMIC_RELAXED),__atomic_load_n(&fc_core1_groups,__ATOMIC_RELAXED),fc_calls,__atomic_load_n(&fc_flash_bytes,__ATOMIC_RELAXED),__atomic_load_n(&fc_flash_prefetches,__ATOMIC_RELAXED),__atomic_load_n(&fc_mac_pairs,__ATOMIC_RELAXED)};}
void picoalpha::fc1_detail_reset(){fc_quant_us=0;fc_calls=0;__atomic_store_n(&fc_flash_bytes,0ull,__ATOMIC_RELAXED);__atomic_store_n(&fc_flash_prefetches,0ull,__ATOMIC_RELAXED);__atomic_store_n(&fc_mac_pairs,0ull,__ATOMIC_RELAXED);__atomic_store_n(&fc_core0_us,0ull,__ATOMIC_RELAXED);__atomic_store_n(&fc_core1_us,0ull,__ATOMIC_RELAXED);__atomic_store_n(&fc_core0_groups,0u,__ATOMIC_RELAXED);__atomic_store_n(&fc_core1_groups,0u,__ATOMIC_RELAXED);}
namespace {
template<class F> static inline void parallel_slices(int count,F& fn){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 if(worker_ready && count>=2){
  if(*reinterpret_cast<const volatile uint32_t*>(pa_core1_stack)!=PA_CORE1_STACK_GUARD)
   throw std::runtime_error("core1 stack guard corrupted");
  const int half=(count==32 ? PA_FC1_CORE0_GROUPS : count/2);
  parallel_job={[](void* p,int a,int b){(*static_cast<F*>(p))(a,b);},&fn,half,count};
  __atomic_thread_fence(__ATOMIC_RELEASE);
  const uint32_t generation=__atomic_add_fetch(&published_generation,1u,__ATOMIC_RELEASE);
  __asm__ volatile("sev");
  fn(0,half);
  const uint64_t start=micros_now();
  uint64_t last_progress=start;
  while(__atomic_load_n(&finished_generation,__ATOMIC_ACQUIRE)!=generation){
   const uint64_t now=micros_now();
   if(now-last_progress>=2000){
    // Do not unwind a live worker job; watchdog remains the recovery for a hung worker.
    last_progress=now;
   }
   if(now-start>2000000u && !parallel_timeouts)++parallel_timeouts;
   __asm__ volatile("nop" ::: "memory");
  }
  if(*reinterpret_cast<const volatile uint32_t*>(pa_core1_stack)!=PA_CORE1_STACK_GUARD)
   throw std::runtime_error("core1 stack overflow");
  parallel_wait_us+=micros_now()-start;
  ++parallel_jobs;
  return;
 }
#endif
 fn(0,count);
}
// PA24_DUAL_CORE_END
static void (*s_kernel_progress)(uint32_t,uint32_t)=nullptr;
static inline void kernel_progress(uint32_t phase,uint32_t step){if(s_kernel_progress)s_kernel_progress(phase,step);}
// Four independent integer accumulators hide load/ALU latency without changing sums.
static inline int32_t dot_int8(const int8_t* x,const int8_t* w,int n){
 int32_t a0=0,a1=0,a2=0,a3=0;int j=0;
#if PA_NN_DSP && defined(__ARM_FEATURE_DSP) && (defined(__arm__) || defined(__thumb__))
 for(;j+7<n;j+=8){
  for(int lane=0;lane<4;++lane){
   const int k=j+lane*2;
   const uint32_t xx=uint16_t(int16_t(x[k]))|(uint32_t(uint16_t(int16_t(x[k+1])))<<16);
   const uint32_t ww=uint16_t(int16_t(w[k]))|(uint32_t(uint16_t(int16_t(w[k+1])))<<16);
   int32_t* acc=lane==0?&a0:lane==1?&a1:lane==2?&a2:&a3;
   int32_t next;
   __asm__ volatile("smlad %0, %1, %2, %3":"=r"(next):"r"(xx),"r"(ww),"r"(*acc));*acc=next;
  }
 }
#endif
 for(;j+3<n;j+=4){a0+=int32_t(x[j])*w[j];a1+=int32_t(x[j+1])*w[j+1];a2+=int32_t(x[j+2])*w[j+2];a3+=int32_t(x[j+3])*w[j+3];}
 int32_t acc=(a0+a1)+(a2+a3);
 for(;j<n;++j)acc+=int32_t(x[j])*w[j];return acc;
}

static inline unsigned core_index(){
#if defined(PICO_ON_DEVICE)
 return get_core_num() & 1u;
#else
 return 0;
#endif
}

// PA56: fixed-point activation pipeline. Scales are compile-time parameters of
// an external calibration header; no per-position max scans in this pipeline.
#if PA_INT8_ACTIVATIONS
#include "pa56_calibration.hpp"
static inline int32_t pa56_round_shift(int64_t a, int bits) {
 if(bits<=0)return int32_t(a);const int64_t r=int64_t(1)<<(bits-1);
 return int32_t(a>=0?(a+r)>>bits:-(((-a)+r)>>bits));
}
static QuantStageStats* pa57_stage=nullptr; // core 1 does not run when recovery is enabled
static uint64_t pa59_observe_us=0;
static inline void pa57_observe(QuantStageStats* st,int32_t raw){
#if !PA_CALIBRATION_TELEMETRY
 (void)st;(void)raw;return;
#else
 if(!st)return;
 const uint64_t obs_start=micros_now();
 const int32_t clamped=std::max<int32_t>(-127,std::min<int32_t>(127,raw));
 __atomic_fetch_add(&st->samples,uint64_t(1),__ATOMIC_RELAXED);
 if(raw < -127)__atomic_fetch_add(&st->saturated_neg,uint64_t(1),__ATOMIC_RELAXED);
 if(raw > 127)__atomic_fetch_add(&st->saturated_pos,uint64_t(1),__ATOMIC_RELAXED);
 int32_t prev=__atomic_load_n(&st->min_q,__ATOMIC_RELAXED);
 while(clamped<prev&&!__atomic_compare_exchange_n(&st->min_q,&prev,clamped,false,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){}
 prev=__atomic_load_n(&st->max_q,__ATOMIC_RELAXED);
 while(clamped>prev&&!__atomic_compare_exchange_n(&st->max_q,&prev,clamped,false,__ATOMIC_RELAXED,__ATOMIC_RELAXED)){}
 const uint32_t a=uint32_t(clamped<0?-clamped:clamped);
 const uint32_t bin=std::min<uint32_t>(15u,a/8u);
 __atomic_fetch_add(&st->abs_hist[bin],uint64_t(1),__ATOMIC_RELAXED);
 __atomic_fetch_add(&pa59_observe_us, micros_now()-obs_start, __ATOMIC_RELAXED);
#endif
}
static inline int8_t pa56_clip(int32_t a){pa57_observe(pa57_stage,a);return int8_t(std::max<int32_t>(-127,std::min<int32_t>(127,a)));}
static inline int32_t pa56_mulq(int32_t a,int32_t multiplier){return pa56_round_shift(int64_t(a)*multiplier,24);}
static inline int32_t pa56_quant(float v,float scale){return int32_t(std::nearbyint(v/scale));}
// Conv weights remain symmetric INT8, inputs/outputs INT8, accumulation INT32.
// Floating weight/bias scales are converted once per layer into Q24 factors.
struct Pa56Coefficients { std::array<int32_t,128> mul{};std::array<int32_t,128> bias{}; };
static Pa56Coefficients pa56_coeff(const Layer& l,float in_scale,float out_scale){
 Pa56Coefficients c{};if(l.out>128)throw std::runtime_error("pa56: channel limit");
 for(int o=0;o<l.out;++o){
  const double factor=double(in_scale)*l.scale[o]/out_scale;
  if(!std::isfinite(factor)||factor>=127.0)throw std::runtime_error("pa56: multiplier range");
  c.mul[o]=int32_t(std::llround(factor*16777216.0));
  c.bias[o]=pa56_quant(l.bias[o],out_scale);
 }return c;
}
template<class Input,class Output> static void pa56_conv(const Input& x,const Layer& l,float in_scale,float out_scale,bool relu,Output& y){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 if(K>1024||x.size()!=size_t(l.in)*64)throw std::runtime_error("pa56 conv dimensions");
 const Pa56Coefficients coeff=pa56_coeff(l,in_scale,out_scale);
 y.resize(size_t(l.out)*64);
 auto work=[&](int begin,int end){
  static std::array<std::array<int8_t,1024>,2> patches{};
  auto& patch=patches[core_index()];
  for(int sq=begin;sq<end;++sq){
   const int row=sq/8,col=sq%8;
   std::fill_n(patch.data(),K,int8_t(0));
   for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){const int rr=row+kr-pad;if(rr<0||rr>=8)continue;
    for(int kc=0;kc<l.k;++kc){const int cc=col+kc-pad;if(cc>=0&&cc<8)patch[(ch*l.k+kr)*l.k+kc]=x[ch*64+rr*8+cc];}}
   for(int o=0;o<l.out;++o){const int32_t acc=dot_int8(patch.data(),l.weights+size_t(o)*K,K);
    int32_t z=pa56_mulq(acc,coeff.mul[o])+coeff.bias[o];if(relu)z=std::max<int32_t>(0,z);
    y[size_t(o)*64+sq]=pa56_clip(z);
   }
  }
 };parallel_slices(64,work);
}
// SE dense matrices quantized to Q12 coefficients and computed on integers.
// Pooled activations are Q0 (INT8); SE internal representation Q8.
static inline int32_t pa56_sigmoid_q15(int32_t xq8){
 // LUT from -8 to +8 in steps of 1/16. No expf in hot path.
 static const std::array<uint16_t,257> lut=[](){std::array<uint16_t,257> t{};
  for(int i=0;i<257;++i){const double z=(double(i)-128.0)/16.0;t[i]=uint16_t(std::lround(32767.0/(1.0+std::exp(-z))));}return t;}();
 const int idx=std::max<int32_t>(0,std::min<int32_t>(256,pa56_round_shift(int64_t(xq8),4)+128));return lut[idx];
}
template<class Tensor,class Scratch,class Pool,class Hidden,class Excitation>
static void pa56_se(Tensor& skip,const Scratch& residual,float tensor_scale,
 const SE& se,Pool& pool,Hidden& hidden,Excitation& excite){
 pool.resize(8);hidden.resize(8);excite.resize(16);
 // Mean pool still represents activation with scale tensor_scale.
 for(int c=0;c<8;++c){int32_t total=0;for(int i=0;i<64;++i)total+=residual[c*64+i];pool[c]=total;}
 // Q8: se1 = relu(W1 * (pool/64)*tensor_scale + b1).
 for(int o=0;o<8;++o){int64_t sum=int64_t(std::llround(se.b1[o]*256.0));
  for(int c=0;c<8;++c){const int32_t w=int32_t(std::llround(double(se.w1[o*8+c])*tensor_scale*4096.0/64.0));sum+=int64_t(pool[c])*w/16;}
  hidden[o]=std::max<int32_t>(0,int32_t(std::max<int64_t>(-0x3fffffff,std::min<int64_t>(0x3fffffff,sum))));
 }
 for(int o=0;o<16;++o){int64_t sum=int64_t(std::llround(se.b2[o]*256.0));
  for(int c=0;c<8;++c){const int32_t w=int32_t(std::llround(double(se.w2[o*8+c])*4096.0));sum+=int64_t(hidden[c])*w/4096;}
  excite[o]=int32_t(std::max<int64_t>(-0x3fffffff,std::min<int64_t>(0x3fffffff,sum)));
 }
 for(int c=0;c<8;++c){const int32_t gate=pa56_sigmoid_q15(excite[c]);
  const int32_t bias=pa56_quant(float(excite[c+8])/256.0f,tensor_scale);
  for(int i=0;i<64;++i){const int k=c*64+i;
   const int32_t v=int32_t(skip[k])+pa56_round_shift(int64_t(gate)*residual[k],15)+bias;
   skip[k]=pa56_clip(std::max<int32_t>(0,v));
  }
 }
}
#endif

template<class Input,class Output,class Quant,class Patch> static void conv_into(const Input& x,const Layer& l,bool relu,Output& y,Quant& input,Patch& patch,float* scale_cache=nullptr,bool reuse_quant=false){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 float xs;
 if(reuse_quant){
  if(!scale_cache||input.size()!=x.size())throw std::runtime_error("invalid reused quantization");
  xs=*scale_cache;
 }else{
  float mx=0;for(float v:x)mx=std::max(mx,std::abs(v));xs=mx>0?mx/127.f:1.f;
  input.resize(x.size());for(size_t i=0;i<x.size();++i)input[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
  if(scale_cache)*scale_cache=xs;
 }
 y.resize(size_t(l.out)*64);
 auto work=[&](int begin,int end){static std::array<std::array<int8_t,1024>,2> patch_per_core{};auto& local_patch=patch_per_core[core_index()];if(K>1024)throw std::runtime_error("kernel patch exceeds fixed scratch");for(int sq=begin;sq<end;++sq){int row=sq/8,col=sq%8;
  std::fill_n(local_patch.data(),K,int8_t(0));
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){int cc=col+kc-pad;if(cc>=0&&cc<8)local_patch[(ch*l.k+kr)*l.k+kc]=input[ch*64+rr*8+cc];}}
  for(int out=0;out<l.out;++out){int32_t acc=dot_int8(local_patch.data(),l.weights+size_t(out)*K,K);
   float value=xs*l.scale[out]*float(acc)+l.bias[out];y[out*64+sq]=relu?std::max(0.f,value):value;
  }
 } };parallel_slices(64,work);
}
// PA21_SPARSE_INPUT_BEGIN: first convolution, quantized nonzero elements only.
// PA31: first-layer defensive implementation. All scratch lives in static SRAM,
// not on the recursive search stack. Breadcrumbs identify an exact sub-phase.
template<class Input,class Output,class Quant> static void conv_sparse_first(const Input& x,const Layer& l,Output& y,Quant& quant){
#if PA_BINARY_FIRST_CONV
 kernel_progress(21,0);
 if(l.in!=112 || l.out!=8 || l.k!=3 || x.size()!=112u*64u || !l.weights || !l.scale || !l.bias)
  throw std::runtime_error("binary first convolution: invalid model");
 // Preserve the original dynamic symmetric quantizer, including the non-binary
 // halfmove plane (109). Instead of materializing 7,168 quantized bytes and
 // a sparse index list, accumulate directly from each occupied input plane.
 float maxabs=0.f;
 for(float v:x){if(!std::isfinite(v))throw std::runtime_error("non-finite input");maxabs=std::max(maxabs,std::abs(v));}
 const float xs=maxabs>0.f?maxabs/127.f:1.f;
 const int8_t qone=int8_t(std::max(-127,std::min(127,int(std::nearbyint(1.f/xs)))));
 // All planes except 109 are strictly binary from encode_into().
 y.resize(8u*64u);
 auto work=[&](int begin,int finish){
  for(int pos=begin;pos<finish;++pos){
   const int row=pos/8,col=pos%8;
   int32_t sums[8]={};
   for(int ch=0;ch<112;++ch){
    for(int kr=0;kr<3;++kr){const int rr=row+kr-1;if(rr<0||rr>=8)continue;
     for(int kc=0;kc<3;++kc){const int cc=col+kc-1;if(cc<0||cc>=8)continue;
      const float v=x[size_t(ch)*64+rr*8+cc];if(v==0.f)continue;
      const int8_t q=(ch==109 || (v!=1.f))?
       int8_t(std::max(-127,std::min(127,int(std::nearbyint(v/xs))))):qone;
      if(!q)continue;
      const int k=(ch*3+kr)*3+kc;
      for(int o=0;o<8;++o)sums[o]+=int32_t(q)*int32_t(l.weights[o*1008+k]);
     }
    }
   }
   for(int o=0;o<8;++o)y[o*64+pos]=std::max(0.f,xs*l.scale[o]*float(sums[o])+l.bias[o]);
  }
 };
 parallel_slices(64,work);
 kernel_progress(25,64);
 return;
#else
 kernel_progress(21,0); // entry, before touching input/output memory
 if(l.in!=112 || l.out!=8 || l.k!=3 || x.size()!=112u*64u ||
    size_t(l.in)*l.k*l.k>1024u || size_t(l.out)*64u>y.capacity() ||
    x.size()>quant.capacity() || !l.weights || !l.scale || !l.bias)
   throw std::runtime_error("first_conv: invalid dimensions or buffers");
 const int K=l.in*l.k*l.k,pad=l.k/2;
 float mx=0;
 for(size_t i=0;i<x.size();++i){
   const float v=x[i];
   if(!std::isfinite(v))throw std::runtime_error("first_conv: nonfinite input");
   mx=std::max(mx,std::abs(v));
 }
 const float xs=mx>0?mx/127.f:1.f;
 kernel_progress(22,0); // begin input quantization
 quant.resize(x.size());
 for(size_t i=0;i<x.size();++i){
   const float normalized=x[i]/xs;
   quant[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(normalized)))));
   if((i&1023u)==1023u)kernel_progress(22,unsigned(i+1));
 }
 y.resize(size_t(l.out)*64);
 kernel_progress(23,0); // quantization finished, convolution begins
 struct Active {uint16_t offset;int8_t value;};
 // One invocation at a time in single-core mode; no dynamic or stack allocation.
 static std::array<std::array<Active,1024>,2> active_per_core{};
 auto work=[&](int begin,int end){
 auto& active=active_per_core[core_index()];
 for(int sq=begin;sq<end;++sq){
  int count=0;const int row=sq/8,col=sq%8;
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){
   const int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){
    const int cc=col+kc-pad;if(cc<0||cc>=8)continue;
    const int8_t val=quant[size_t(ch)*64+rr*8+cc];
    if(val){
     if(count>=int(active.size()))throw std::runtime_error("first_conv: sparse scratch overflow");
     active[count++]={uint16_t((ch*l.k+kr)*l.k+kc),val};
    }
   }
  }
  for(int o=0;o<l.out;++o){
   const int8_t* weights=l.weights+size_t(o)*K;
   int32_t acc=0;
   if(count>700){
    // Dense path: reconstruct quantized patch without heap; same integer sum.
    static std::array<std::array<int8_t,1024>,2> dense_per_core{};auto& dense=dense_per_core[core_index()];
    std::fill_n(dense.data(),K,int8_t(0));
    for(int ai=0;ai<count;++ai)dense[active[ai].offset]=active[ai].value;
    acc=dot_int8(dense.data(),weights,K);
   }else for(int ai=0;ai<count;++ai){const auto& v=active[ai];
    acc+=int32_t(v.value)*int32_t(weights[v.offset]);}
   y[size_t(o)*64+sq]=std::max(0.f,xs*l.scale[o]*float(acc)+l.bias[o]);
  }
  if((sq&7)==7)kernel_progress(24,unsigned(sq+1));
 }
 };
 parallel_slices(64,work);
 kernel_progress(25,64);
#endif
}
// PA21_SPARSE_INPUT_END
// PA21_POLICY_SELECT_BEGIN: evaluate final policy convolution only at legal action indices.
template<class Input,class Indices,class Output,class Quant,class Patch> static void conv_policy_selected(const Input& x,const Layer& l,const Indices& indices,
 Output& result,Quant& quant,Patch& patch){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 float mx=0;for(float v:x)mx=std::max(mx,std::abs(v));const float xs=mx>0?mx/127.f:1.f;
 quant.resize(x.size());for(size_t i=0;i<x.size();++i)quant[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
 result.resize(indices.size());
 auto work=[&](int begin,int end){static std::array<std::array<int8_t,1024>,2> patch_per_core{};auto& local_patch=patch_per_core[core_index()];if(K>1024)throw std::runtime_error("kernel patch exceeds fixed scratch");for(int z=begin;z<end;++z){const int ix=indices[z],out=ix/64,sq=ix%64;
  if(ix<0||out>=l.out)throw std::runtime_error("invalid legal policy index");
  const int row=sq/8,col=sq%8;std::fill_n(local_patch.data(),K,int8_t(0));
  for(int ch=0;ch<l.in;++ch)for(int kr=0;kr<l.k;++kr){const int rr=row+kr-pad;if(rr<0||rr>=8)continue;
   for(int kc=0;kc<l.k;++kc){const int cc=col+kc-pad;if(cc>=0&&cc<8)local_patch[(ch*l.k+kr)*l.k+kc]=quant[ch*64+rr*8+cc];}}
  const int32_t acc=dot_int8(local_patch.data(),l.weights+size_t(out)*K,K);
  result[z]=xs*l.scale[out]*float(acc)+l.bias[out];
 } };parallel_slices(int(indices.size()),work);
}
// PA21_POLICY_SELECT_END
template<class Input,class Output> static void fc_into(const Input& x,const float* w,const float* b,int out,bool relu,Output& y){
 y.resize(out);
 auto work=[&](int begin,int end){for(int o=begin;o<end;++o){float v=b[o];const float* row=w+size_t(o)*x.size();
#if PA_NN_FC_FAST
  // Accumulate 4 independent lanes to expose ILP to Cortex-M33 FPU.
  float a0=0,a1=0,a2=0,a3=0;size_t j=0;
  for(;j+3<x.size();j+=4){a0+=row[j]*x[j];a1+=row[j+1]*x[j+1];a2+=row[j+2]*x[j+2];a3+=row[j+3]*x[j+3];}
  v+=((a0+a1)+(a2+a3));for(;j<x.size();++j)v+=row[j]*x[j];
#else
  for(size_t j=0;j<x.size();++j)v+=row[j]*x[j];
#endif
  y[o]=relu?std::max(0.f,v):v;
 } };if(out>=64)parallel_slices(out,work);else work(0,out);
}
#if PA_FC1_DSP_PACKED && PA_NN_DSP && defined(__ARM_FEATURE_DSP) && (defined(__arm__) || defined(__thumb__))
static inline uint32_t pa69_unpack_pair(uint16_t packed){
  uint32_t lo,hi;
  __asm__ volatile("sxtb %0, %2\n\tsxtb %1, %2, ror #8" : "=&r"(lo),"=&r"(hi) : "r"(uint32_t(packed)));
  return (lo & 0xffffu) | (hi << 16);
}
#endif
template<class Input,class Output,class Quant> static void fc_int8_into(const Input& x,const float* bias,Output& y,Quant& quant){
 // PA_FC_INT8_BEGIN: symmetric per-row weights + per-inference activation scale.
 const uint64_t quant_start=micros_now();
 float maxabs=0.f;
 for(float v:x)maxabs=std::max(maxabs,std::abs(v));
 const float scale=maxabs>0.f?maxabs/127.f:1.f;
 quant.resize(x.size());
 for(size_t j=0;j<x.size();++j)quant[j]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[j]/scale)))));
 y.resize(128);
 fc_quant_us+=micros_now()-quant_start;
 ++fc_calls;
 // Four-output tiling reduces repeated activation loads; each row stays sequential in FLASH.
 // The exported FC1 layout is already packed in 4x32 tiles. PA_FC1_PREPACK
 // selects the shared-activation tile kernel vs per-row dot products.
 auto work=[&](int group_begin,int group_end){
 const uint64_t group_start=micros_now();
 for(int ob=group_begin*4;ob<group_end*4;ob+=4){
  const int N=int(x.size());
  const int8_t* block=picoalpha::PA_FC1_INT8_WEIGHTS+size_t(ob/4)*4*N;
  int32_t a0=0,a1=0,a2=0,a3=0;
  // Four rows share each 32-element activation tile. Accumulate all rows in
  // one traversal, avoiding four separate dot-product calls per tile.
  // Weight order/layout, quantization and integer sums remain unchanged.
#if PA_FC1_PREPACK
  for(int tile=0;tile<N;tile+=32){
   const int8_t* q=quant.data()+tile;
   const int8_t* r0=block+size_t(tile/32)*128;
#if PA_FC1_FLASH_PREFETCH && (defined(__GNUC__) || defined(__clang__))
   // Prefetch the NEXT Flash tile; never dereference past the matrix.
   if(tile+32<N){
    __builtin_prefetch(block+size_t(tile/32+1)*128,0,2);
    __builtin_prefetch(block+size_t(tile/32+1)*128+64,0,2);
   }
#endif
   const int8_t* r1=r0+32;
   const int8_t* r2=r1+32;
   const int8_t* r3=r2+32;
#if PA_NN_DSP && defined(__ARM_FEATURE_DSP) && (defined(__arm__) || defined(__thumb__))
   // RP2350 Cortex-M33: signed dual 16-bit MAC (SMLAD). Each INT8 element
   // is sign extended before packing to preserve the exact dot product.
   for(int j=0;j<32;j+=2){
#if PA_FC1_DSP_PACKED
    uint16_t qb,wb0,wb1,wb2,wb3;
    std::memcpy(&qb,q+j,2);
    std::memcpy(&wb0,r0+j,2);std::memcpy(&wb1,r1+j,2);
    std::memcpy(&wb2,r2+j,2);std::memcpy(&wb3,r3+j,2);
    const uint32_t qq=pa69_unpack_pair(qb);
    const uint32_t w0=pa69_unpack_pair(wb0);
    const uint32_t w1=pa69_unpack_pair(wb1);
    const uint32_t w2=pa69_unpack_pair(wb2);
    const uint32_t w3=pa69_unpack_pair(wb3);
#else
    const uint32_t qq=uint16_t(int16_t(q[j])) | (uint32_t(uint16_t(int16_t(q[j+1])))<<16);
    const uint32_t w0=uint16_t(int16_t(r0[j])) | (uint32_t(uint16_t(int16_t(r0[j+1])))<<16);
    const uint32_t w1=uint16_t(int16_t(r1[j])) | (uint32_t(uint16_t(int16_t(r1[j+1])))<<16);
    const uint32_t w2=uint16_t(int16_t(r2[j])) | (uint32_t(uint16_t(int16_t(r2[j+1])))<<16);
    const uint32_t w3=uint16_t(int16_t(r3[j])) | (uint32_t(uint16_t(int16_t(r3[j+1])))<<16);
#endif
    __asm__ volatile("smlad %0, %1, %2, %0":"+r"(a0):"r"(qq),"r"(w0));
    __asm__ volatile("smlad %0, %1, %2, %0":"+r"(a1):"r"(qq),"r"(w1));
    __asm__ volatile("smlad %0, %1, %2, %0":"+r"(a2):"r"(qq),"r"(w2));
    __asm__ volatile("smlad %0, %1, %2, %0":"+r"(a3):"r"(qq),"r"(w3));
   }
#else
   for(int j=0;j<32;++j){
    const int32_t v=q[j];
    a0+=v*r0[j]; a1+=v*r1[j]; a2+=v*r2[j]; a3+=v*r3[j];
   }
#endif
  }
#else
  for(int tile=0;tile<N;tile+=32){
   const int8_t* q=quant.data()+tile;
   const int8_t* base=block+size_t(tile/32)*128;
   a0+=dot_int8(q,base,32);
   a1+=dot_int8(q,base+32,32);
   a2+=dot_int8(q,base+64,32);
   a3+=dot_int8(q,base+96,32);
  }
#endif
  const int32_t sums[4]={a0,a1,a2,a3};
  for(int k=0;k<4;++k){const int o=ob+k;
   y[o]=std::max(0.f,bias[o]+float(sums[k])*(scale*picoalpha::PA_FC1_INT8_SCALES[o]));}
 }
 const uint64_t group_elapsed=micros_now()-group_start;
 const uint64_t tiles=uint64_t(group_end-group_begin)*uint64_t(x.size()/32);
 __atomic_fetch_add(&fc_flash_bytes,tiles*128u,__ATOMIC_RELAXED);
 __atomic_fetch_add(&fc_mac_pairs,tiles*64u,__ATOMIC_RELAXED);
#if PA_FC1_FLASH_PREFETCH && PA_FC1_PREPACK
 __atomic_fetch_add(&fc_flash_prefetches,tiles*2u-uint64_t(group_end-group_begin)*2u,__ATOMIC_RELAXED);
#endif
#if defined(PICO_ON_DEVICE)
 if(get_core_num()==1){__atomic_fetch_add(&fc_core1_us,group_elapsed,__ATOMIC_RELAXED);__atomic_fetch_add(&fc_core1_groups,uint32_t(group_end-group_begin),__ATOMIC_RELAXED);}
 else
#endif
 {__atomic_fetch_add(&fc_core0_us,group_elapsed,__ATOMIC_RELAXED);__atomic_fetch_add(&fc_core0_groups,uint32_t(group_end-group_begin),__ATOMIC_RELAXED);}
 };
 // FC1 has 32 independent 4-output tiles. Work is partitioned into
 // disjoint outputs; shared activations and weights are read-only.
 parallel_slices(32,work);

 // PA_FC_INT8_END
}

// PA35: eight-entry allocation-free cache. Hash covers ALL 112 history planes and
// the ordered requested policy slots; not merely the position's 64 squares.
#ifndef PA_NN_CACHE
#define PA_NN_CACHE 1
#endif
#if PA_NN_CACHE
struct CacheEntry {
 uint64_t key1=0,key2=0; uint32_t stamp=0; uint16_t count=0;
 float q=0; std::array<float,256> policy{};
};
static std::array<CacheEntry,8> s_cache{};
static uint32_t s_cache_clock=0;
static uint64_t hash_bytes(const void* p,size_t n,uint64_t seed){
 const auto* b=static_cast<const uint8_t*>(p);
 for(size_t i=0;i<n;++i){seed^=b[i];seed*=UINT64_C(1099511628211);}
 return seed;
}
static void cache_keys(const std::array<float,112*64>& planes,
 const FixedVector<int,256>* indices,uint64_t& a,uint64_t& b){
 a=hash_bytes(planes.data(),sizeof(float)*planes.size(),UINT64_C(14695981039346656037));
 b=hash_bytes(planes.data(),sizeof(float)*planes.size(),UINT64_C(7809847782465536322));
 const uint32_t count=indices?uint32_t(indices->size()):0xFFFFFFFFu;
 a=hash_bytes(&count,sizeof(count),a);b=hash_bytes(&count,sizeof(count),b);
 if(indices)for(size_t i=0;i<indices->size();++i){const int index=(*indices)[i];
  a=hash_bytes(&index,sizeof(index),a);b=hash_bytes(&index,sizeof(index),b);}
}
#endif
// PA_NN_OPT_END

}
Network::Network(){cur=PICOALPHA_MODEL_DATA;
 input_=layer();residual_[0]=layer();residual_[1]=layer();p1_=layer();pol_=layer();vconv_=layer();
 {auto& se=se_[0];se.w1=floatarray(64);se.b1=floatarray(8);se.w2=floatarray(128);se.b2=floatarray(16);}
 v1w_=nullptr;v1b_=floatarray(128);v2w_=floatarray(128);v2b_=floatarray(1);
 if(cur!=end)throw std::runtime_error("unexpected embedded model byte count");
}
void Network::reset_profile() const { profile_ = {};calibration_={};cache_hits_=cache_misses_=0;
#if PA_INT8_ACTIVATIONS
 pa59_observe_us=0;
#endif
}
NNProfile Network::profile() const {auto p=profile_;
#if PA_INT8_ACTIVATIONS
 p.calibration_observe_us=pa59_observe_us;
#endif
 return p;}
QuantCalibrationProfile Network::calibration_profile() const {return calibration_;}
void Network::release_workspace() const { workspace_=Workspace{}; }
Result Network::evaluate(const std::array<float,112*64>& planes) const {
 return evaluate_impl(planes,nullptr);
}
Result Network::evaluate_legal(const std::array<float,112*64>& planes,const FixedVector<int,256>& indices) const {
 return evaluate_impl(planes,&indices);
}
Result Network::evaluate_impl(const std::array<float,112*64>& planes,const FixedVector<int,256>* legal_indices) const {
 const uint64_t begin=micros_now();
#if PA_NN_CACHE
 const bool cacheable=legal_indices && legal_indices->size()<=256;
 uint64_t key1=0,key2=0;
 if(cacheable){
  cache_keys(planes,legal_indices,key1,key2);
  for(auto& slot:s_cache)if(slot.stamp&&slot.key1==key1&&slot.key2==key2&&slot.count==legal_indices->size()){
   ++cache_hits_;slot.stamp=++s_cache_clock;
   return {slot.policy.data(),slot.count,slot.q};
  }
  ++cache_misses_;
 }
#endif
 struct KernelHookScope {KernelHookScope(void (*fn)(uint32_t,uint32_t)){s_kernel_progress=fn;} ~KernelHookScope(){s_kernel_progress=nullptr;}} hook_scope(progress_hook_);
 kernel_progress(9,0);
 kernel_progress(16,0); // entering workspace selection; persistent post-watchdog breadcrumb
 // PA_NN_WORKSPACE_BEGIN: persistent buffers, no heap churn per convolution.
#if PA_NN_WORKSPACE
 auto& w=workspace_;
#else
 static Workspace local_workspace;
 auto& w=local_workspace;
#endif
 kernel_progress(17,0); // workspace resolved; first_conv phases 21-25 follow
 const uint64_t t0=micros_now();
 conv_sparse_first(planes,input_,w.b,w.quant);
 const uint64_t after_first=micros_now();
 kernel_progress(18,0); // first convolution returned
#if PA_INT8_ACTIVATIONS
 // The first convolution remains the validated binary-input kernel. Convert
 // its output once, then keep the residual in INT8, including SE and skip.
 const uint64_t pa56_quant_start=micros_now();
 pa57_stage=&calibration_.trunk_input;
 w.quant_b.resize(w.b.size());
 for(size_t k=0;k<w.b.size();++k)w.quant_b[k]=pa56_clip(pa56_quant(w.b[k],PA56_TRUNK_SCALE));
 profile_.int8_requant_us+=micros_now()-pa56_quant_start;
 pa57_stage=nullptr;
 for(int j=0;j<1;++j){
  pa57_stage=&calibration_.residual_conv1;
  pa56_conv(w.quant_b,residual_[j*2],PA56_TRUNK_SCALE,PA56_RES1_SCALE,true,w.quant);
  pa57_stage=nullptr;
  const uint64_t pa56_t1=micros_now();
  pa57_stage=&calibration_.residual_conv2;
  pa56_conv(w.quant,residual_[j*2+1],PA56_RES1_SCALE,PA56_TRUNK_SCALE,false,w.qres);
  pa57_stage=nullptr;
  const uint64_t pa56_t2=micros_now();
  pa57_stage=&calibration_.residual_output;
  pa56_se(w.quant_b,w.qres,PA56_TRUNK_SCALE,se_[j],w.pool_i,w.hidden_i,w.se_i);
  pa57_stage=nullptr;
  const uint64_t pa56_t3=micros_now();
  profile_.int8_conv_us+=pa56_t2-pa56_t1;profile_.int8_se_us+=pa56_t3-pa56_t2;
 }
#else
 for(int j=0;j<1;++j){
  conv_into(w.b,residual_[j*2],true,w.c,w.quant,w.patch);
#if PA_INT8_ACTIVATIONS
  // Quantize once at the producer boundary, then reuse the INT8 tensor in
  // the consumer kernel (no second scan/quantization inside conv_into).
  float mx=0.f;for(float v:w.c)mx=std::max(mx,std::abs(v));
  float activation_scale=mx>0.f?mx/127.f:1.f;
  w.quant.resize(w.c.size());
  for(size_t qi=0;qi<w.c.size();++qi)w.quant[qi]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(w.c[qi]/activation_scale)))));
  conv_into(w.c,residual_[j*2+1],false,w.d,w.quant,w.patch,&activation_scale,true);
#else
  conv_into(w.c,residual_[j*2+1],false,w.d,w.quant,w.patch);
#endif
  w.pool.assign(8,0.f);
  for(int c=0;c<8;++c)for(int i=0;i<64;++i)w.pool[c]+=w.d[c*64+i]/64;
  fc_into(w.pool,se_[j].w1,se_[j].b1,8,true,w.se1);
  fc_into(w.se1,se_[j].w2,se_[j].b2,16,false,w.se2);
  for(int c=0;c<8;++c){float scale=1.f/(1.f+std::exp(-w.se2[c]));
   for(int i=0;i<64;++i){int k=c*64+i;w.b[k]=std::max(0.f,w.b[k]+scale*w.d[k]+w.se2[c+8]);}}
 }
#endif
 kernel_progress(12,0);
#if PA_INT8_ACTIVATIONS
 const uint64_t pa56_convert_start=micros_now();
 w.b.resize(w.quant_b.size());for(size_t k=0;k<w.b.size();++k)w.b[k]=float(w.quant_b[k])*PA56_TRUNK_SCALE;
 profile_.int8_convert_us+=micros_now()-pa56_convert_start;
#endif
 const uint64_t after_res=micros_now();
 float input_shared_scale=1.f;
 conv_into(w.b,p1_,true,w.c,w.quant_b,w.patch,&input_shared_scale);
 if(legal_indices)conv_policy_selected(w.c,pol_,*legal_indices,w.policy,w.quant,w.patch);
 else conv_into(w.c,pol_,false,w.policy,w.quant,w.patch);
 kernel_progress(11,0);
 const uint64_t after_policy=micros_now();
 conv_into(w.b,vconv_,true,w.c,w.quant_b,w.patch,&input_shared_scale,true);
 kernel_progress(13,0);
 const uint64_t after_value_conv=micros_now();
#if 1 // 1x8 export mandates INT8 FC1; floating FC1 not embedded.
 fc_int8_into(w.c,v1b_,w.hidden,w.quant);
#else
 fc_into(w.c,v1w_,v1b_,128,true,w.hidden);
#endif
 kernel_progress(14,0);
 const uint64_t after_fc=micros_now();
 fc_into(w.hidden,v2w_,v2b_,1,false,w.scalar);
 kernel_progress(15,0);
 const uint64_t done=micros_now();
 Result result{w.policy.data(),w.policy.size(),std::tanh(w.scalar[0])};
#if PA_NN_CACHE
 if(cacheable){
  CacheEntry* victim=&s_cache[0];
  for(auto& entry:s_cache)if(!entry.stamp || entry.stamp<victim->stamp){victim=&entry; if(!entry.stamp)break;}
  victim->key1=key1;victim->key2=key2;victim->count=uint16_t(result.count);
  victim->q=result.q;
  for(size_t i=0;i<result.count;++i)victim->policy[i]=result.policy[i];
  victim->stamp=++s_cache_clock;
 }
#endif
 // PA_NN_WORKSPACE_END
#if PA_NN_PROFILE
 ++profile_.inferences;
 profile_.first_conv_us+=after_first-t0;
 profile_.residual_us+=after_res-after_first;
 profile_.conv_res_us+=after_res-t0;
 profile_.policy_us+=after_policy-after_res;
 profile_.value_conv_us+=after_value_conv-after_policy;
 profile_.fc1_us+=after_fc-after_value_conv;
 profile_.fc2_us+=done-after_fc;
 profile_.total_us+=done-begin;
#endif
 return result;
}

void picoalpha::encode_into(const std::vector<picoSargon::Board>& states,bool fen_only,std::array<float,112*64>& x){if(states.empty())throw std::runtime_error("history vacio");x.fill(0.f);const auto& curr=states.back();int count=std::min(int(states.size()),8);for(int j=0;j<8;++j){if(j>=count&&!fen_only)break;const auto& b=states[j<count?int(states.size())-1-j:0];for(int sq=0;sq<64;++sq){int p=b.piece(sq);if(!p)continue;int color=p*curr.turn>0?0:6;int kind=std::abs(p)-1;int rr=curr.turn==1?sq/8:7-sq/8;int idx=(j*13+color+kind)*64+rr*8+sq%8;x[idx]=1.f;}if(b.repetitions()>=2)for(int i=0;i<64;++i)x[(j*13+12)*64+i]=1;}
 auto fill=[&](int plane,bool yes){if(yes)for(int i=0;i<64;++i)x[plane*64+i]=1;};int own=curr.turn==1?0:2,opp=curr.turn==1?2:0;fill(104,bool(curr.castling&(own==0?2:8)));fill(105,bool(curr.castling&(own==0?1:4)));fill(106,bool(curr.castling&(opp==0?2:8)));fill(107,bool(curr.castling&(opp==0?1:4)));fill(108,curr.turn==-1);for(int i=0;i<64;++i)x[109*64+i]=float(curr.halfmove);fill(111,true);return;}
// PA_COMPACT_HISTORY_BEGIN: equivalent planes from packed historical states.
void picoalpha::encode_into(const CompactHistory& states,bool fen_only,std::array<float,112*64>& x){
 if(states.empty())throw std::runtime_error("history vacio");
 x.fill(0.f);
 const auto& curr=states.back();int count=std::min(int(states.size()),8);
 for(int j=0;j<8;++j){
  if(j>=count&&!fen_only)break;
  const auto& b=states[j<count?int(states.size())-1-j:0];
  for(int sq=0;sq<64;++sq){
   int p=b.piece(sq);if(!p)continue;
   int color=p*curr.turn>0?0:6,kind=std::abs(p)-1;
   int rr=curr.turn==1?sq/8:7-sq/8;
   x[(j*13+color+kind)*64+rr*8+sq%8]=1.f;
  }
  if(b.repeated)for(int i=0;i<64;++i)x[(j*13+12)*64+i]=1.f;
 }
 auto fill=[&](int plane,bool yes){if(yes)for(int i=0;i<64;++i)x[plane*64+i]=1;};
 int own=curr.turn==1?0:2,opp=curr.turn==1?2:0;
 fill(104,bool(curr.castling&(own==0?2:8)));
 fill(105,bool(curr.castling&(own==0?1:4)));
 fill(106,bool(curr.castling&(opp==0?2:8)));
 fill(107,bool(curr.castling&(opp==0?1:4)));
 fill(108,curr.turn==-1);
 for(int i=0;i<64;++i)x[109*64+i]=float(curr.halfmove);
 fill(111,true);return;
}
std::array<float,112*64> picoalpha::encode(const std::vector<picoSargon::Board>& history,bool fen_only){std::array<float,112*64> out{};encode_into(history,fen_only,out);return out;}
std::array<float,112*64> picoalpha::encode(const CompactHistory& history,bool fen_only){std::array<float,112*64> out{};encode_into(history,fen_only,out);return out;}
// PA_COMPACT_HISTORY_END
int picoalpha::policy_index(const picoSargon::Board& b,picoSargon::Move m){int fr=m.from,to=m.to;if(std::abs(b.piece(fr))==6&&std::abs(to-fr)==2)to=fr/8*8+(to>fr?7:0);int f0=fr%8,r0=b.turn==1?fr/8:7-fr/8;int f1=to%8,r1=b.turn==1?to/8:7-to/8;int dx=f1-f0,dy=r1-r0;int plane=-1;
 if(m.promo==5||m.promo==4||m.promo==3){if(dy!=1||std::abs(dx)>1)throw std::runtime_error("promotion invalid");plane=64+(dx+1)*3+(m.promo==4?0:m.promo==3?1:2);}
 else{static const int kn[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};for(int j=0;j<8;++j)if(kn[j][0]==dx&&kn[j][1]==dy)plane=56+j;if(plane<0){static const int rays[8][2]={{0,1},{1,1},{1,0},{1,-1},{0,-1},{-1,-1},{-1,0},{-1,1}};int steps=std::max(std::abs(dx),std::abs(dy));if(steps<1||steps>7)throw std::runtime_error("invalid ray");int sx=(dx>0)-(dx<0),sy=(dy>0)-(dy<0);for(int j=0;j<8;++j)if(sx==rays[j][0]&&sy==rays[j][1])plane=j*7+steps-1;}}
 if(plane<0)throw std::runtime_error("no policy slot");return plane*64+r0*8+f0;
}
