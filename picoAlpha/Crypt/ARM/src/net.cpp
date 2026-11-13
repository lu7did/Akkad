#include "net.hpp"
#include "generated_tinygyal.hpp"
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
#include "generated_tinygyal_fc_int8.hpp"
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
picoalpha::FC1Detail picoalpha::fc1_detail_profile(){return {};}
void picoalpha::fc1_detail_reset(){}
void picoalpha::dual_core_start(){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 if(!worker_ready){
  pa_core1_stack[0]=PA_CORE1_STACK_GUARD;
  multicore_launch_core1_with_stack(core1_loop,pa_core1_stack,sizeof(pa_core1_stack));
  const uint64_t deadline=micros_now()+1000000u;
  while(!__atomic_load_n(&worker_started,__ATOMIC_ACQUIRE) && micros_now()<deadline)
   __asm__ volatile("nop" ::: "memory");
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
template<class F> static inline void parallel_slices(int count,F& fn){
#if PA_DUAL_CORE_NN && defined(PICO_ON_DEVICE)
 if(worker_ready && count>=2){
  const int half=count/2;
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
   __asm__ volatile("wfe");
  }
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
 auto work=[&](int begin,int end){static std::array<int8_t,1024> local_patch{};if(K>1024)throw std::runtime_error("kernel patch exceeds fixed scratch");for(int sq=begin;sq<end;++sq){int row=sq/8,col=sq%8;
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
 kernel_progress(21,0); // entry, before touching input/output memory
 if(l.in!=112 || l.out!=16 || l.k!=3 || x.size()!=112u*64u ||
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
 static std::array<Active,1024> active{};
 auto work=[&](int begin,int end){
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
    static std::array<int8_t,1024> dense{};
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
}
// PA21_SPARSE_INPUT_END
// PA21_POLICY_SELECT_BEGIN: evaluate final policy convolution only at legal action indices.
template<class Input,class Indices,class Output,class Quant,class Patch> static void conv_policy_selected(const Input& x,const Layer& l,const Indices& indices,
 Output& result,Quant& quant,Patch& patch){
 const int K=l.in*l.k*l.k,pad=l.k/2;
 float mx=0;for(float v:x)mx=std::max(mx,std::abs(v));const float xs=mx>0?mx/127.f:1.f;
 quant.resize(x.size());for(size_t i=0;i<x.size();++i)quant[i]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[i]/xs)))));
 result.resize(indices.size());
 auto work=[&](int begin,int end){static std::array<int8_t,1024> local_patch{};if(K>1024)throw std::runtime_error("kernel patch exceeds fixed scratch");for(int z=begin;z<end;++z){const int ix=indices[z],out=ix/64,sq=ix%64;
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
template<class Input,class Output,class Quant> static void fc_int8_into(const Input& x,const float* bias,Output& y,Quant& quant){
 // PA_FC_INT8_BEGIN: symmetric per-row weights + per-inference activation scale.
 float maxabs=0.f;
 for(float v:x)maxabs=std::max(maxabs,std::abs(v));
 const float scale=maxabs>0.f?maxabs/127.f:1.f;
 quant.resize(x.size());
 for(size_t j=0;j<x.size();++j)quant[j]=int8_t(std::max(-127,std::min(127,int(std::nearbyint(x[j]/scale)))));
 y.resize(128);
 // Four-output tiling reduces repeated activation loads; each row stays sequential in FLASH.
 for(int ob=0;ob<128;ob+=4){
  const int N=int(x.size());
  const int8_t* block=picoalpha::PA_FC1_INT8_WEIGHTS+size_t(ob/4)*4*N;
  int32_t a0=0,a1=0,a2=0,a3=0;
  for(int tile=0;tile<N;tile+=32){
   const int8_t *r0=block+size_t(tile/32)*128;
   const int8_t *r1=r0+32,*r2=r1+32,*r3=r2+32;
   // Load four sequential flash runs for a common 32-element activation tile.
   a0+=dot_int8(quant.data()+tile,r0,32);
   a1+=dot_int8(quant.data()+tile,r1,32);
   a2+=dot_int8(quant.data()+tile,r2,32);
   a3+=dot_int8(quant.data()+tile,r3,32);
  }
  const int32_t sums[4]={a0,a1,a2,a3};
  for(int k=0;k<4;++k){const int o=ob+k;
   y[o]=std::max(0.f,bias[o]+float(sums[k])*(scale*picoalpha::PA_FC1_INT8_SCALES[o]));}
 }

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
 input_=layer();for(auto& l:residual_)l=layer();p1_=layer();pol_=layer();vconv_=layer();
 for(auto& se:se_){se.w1=floatarray(256);se.b1=floatarray(16);se.w2=floatarray(512);se.b2=floatarray(32);}
 v1w_=floatarray(32*64*128);v1b_=floatarray(128);v2w_=floatarray(128);v2b_=floatarray(1);
 if(cur!=end)throw std::runtime_error("unexpected embedded model byte count");
}
void Network::reset_profile() const { profile_ = {};cache_hits_=cache_misses_=0; }
NNProfile Network::profile() const {return profile_;}
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
 kernel_progress(18,0); // first convolution returned
 for(int j=0;j<2;++j){
  conv_into(w.b,residual_[j*2],true,w.c,w.quant,w.patch);
  conv_into(w.c,residual_[j*2+1],false,w.d,w.quant,w.patch);
  w.pool.assign(16,0.f);
  for(int c=0;c<16;++c)for(int i=0;i<64;++i)w.pool[c]+=w.d[c*64+i]/64;
  fc_into(w.pool,se_[j].w1,se_[j].b1,16,true,w.se1);
  fc_into(w.se1,se_[j].w2,se_[j].b2,32,false,w.se2);
  for(int c=0;c<16;++c){float scale=1.f/(1.f+std::exp(-w.se2[c]));
   for(int i=0;i<64;++i){int k=c*64+i;w.b[k]=std::max(0.f,w.b[k]+scale*w.d[k]+w.se2[c+16]);}}
 }
 kernel_progress(12,0);
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
#if PA_NN_FC_INT8
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
