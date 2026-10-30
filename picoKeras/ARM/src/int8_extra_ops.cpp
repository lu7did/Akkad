#include "int8_extra_ops.hpp"
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <limits>
#include "tensorflow/lite/micro/micro_context.h"
#include "tensorflow/lite/micro/kernels/kernel_util.h"
#include "tensorflow/lite/micro/micro_common.h"

namespace pico_int8 {
namespace {
struct GeluData { int8_t lut[256]; };
void* GeluInit(TfLiteContext* c,const char*,size_t) {
  return c->AllocatePersistentBuffer(c,sizeof(GeluData));
}
int Count(const TfLiteIntArray* d) {
  if(!d)return -1;int64_t n=1;
  for(int i=0;i<d->size;i++){if(d->data[i]<0)return -1;n*=d->data[i];if(n>INT32_MAX)return -1;}
  return static_cast<int>(n);
}
TfLiteStatus GeluPrepare(TfLiteContext* c,TfLiteNode* n) {
  auto* m=static_cast<tflite::MicroContext*>(c->impl_);
  auto* a=m->AllocateTempInputTensor(n,0);
  auto* b=m->AllocateTempOutputTensor(n,0);
  if(!a||!b)return kTfLiteError;
  bool ok=a->type==kTfLiteInt8&&b->type==kTfLiteInt8&&
    a->params.scale>0&&b->params.scale>0&&Count(a->dims)==Count(b->dims);
  if(ok){
    auto* lut=static_cast<GeluData*>(n->user_data);
    // LUT is generated once during AllocateTensors; Invoke uses integer lookup only.
    for(int q=-128;q<=127;q++){
      double x=(q-a->params.zero_point)*a->params.scale;
      double y=0.5*x*(1.0+std::tanh(0.7978845608028654*(x+0.044715*x*x*x)));
      int v=static_cast<int>(std::lround(y/b->params.scale))+b->params.zero_point;
      lut->lut[q+128]=static_cast<int8_t>(std::clamp(v,-128,127));
    }
  }
  m->DeallocateTempTfLiteTensor(a);m->DeallocateTempTfLiteTensor(b);
  return ok?kTfLiteOk:kTfLiteError;
}
TfLiteStatus GeluInvoke(TfLiteContext* c,TfLiteNode* n) {
  const auto* a=tflite::micro::GetEvalInput(c,n,0);
  auto* b=tflite::micro::GetEvalOutput(c,n,0);
  if(!a||!b||a->type!=kTfLiteInt8||b->type!=kTfLiteInt8)return kTfLiteError;
  int count=Count(a->dims);if(count<0||count!=Count(b->dims))return kTfLiteError;
  const auto* lut=static_cast<GeluData*>(n->user_data);
  for(int i=0;i<count;i++)b->data.int8[i]=lut->lut[static_cast<int>(a->data.int8[i])+128];
  return kTfLiteOk;
}
TfLiteStatus ProductPrepare(TfLiteContext* c,TfLiteNode* n) {
  auto* m=static_cast<tflite::MicroContext*>(c->impl_);
  auto* a=m->AllocateTempInputTensor(n,0);
  auto* axes=m->AllocateTempInputTensor(n,1);
  auto* b=m->AllocateTempOutputTensor(n,0);
  if(!a||!axes||!b)return kTfLiteError;
  bool ok=a->type==kTfLiteInt32&&axes->type==kTfLiteInt32&&b->type==kTfLiteInt32&&
    Count(a->dims)>=0&&Count(b->dims)>=0;
  m->DeallocateTempTfLiteTensor(a);m->DeallocateTempTfLiteTensor(axes);m->DeallocateTempTfLiteTensor(b);
  return ok?kTfLiteOk:kTfLiteError;
}
TfLiteStatus ProductInvoke(TfLiteContext* c,TfLiteNode* n) {
  const auto* x=tflite::micro::GetEvalInput(c,n,0);
  const auto* axes=tflite::micro::GetEvalInput(c,n,1);
  auto* y=tflite::micro::GetEvalOutput(c,n,0);
  if(!x||!axes||!y||x->type!=kTfLiteInt32||axes->type!=kTfLiteInt32||y->type!=kTfLiteInt32)return kTfLiteError;
  int rank=x->dims->size,na=Count(axes->dims),num=Count(x->dims),out=Count(y->dims);
  if(rank>8||rank<1||na<0||num<0||out<0)return kTfLiteError;
  bool reduced[8]={};
  for(int i=0;i<na;i++){
    int k=axes->data.i32[i];if(k<0)k+=rank;
    if(k<0||k>=rank)return kTfLiteError;reduced[k]=true;
  }
  int remaining[8]={},nr=0;
  for(int i=0;i<rank;i++)if(!reduced[i])remaining[nr++]=i;
  for(int i=0;i<out;i++)y->data.i32[i]=1;
  int64_t accum[8]={};
  // Check product value for overflow rather than silently wrapping an int32 shape.
  for(int linear=0;linear<num;linear++){
    int rem=linear;
    for(int d=rank-1;d>=0;d--){int s=x->dims->data[d];if(s<=0)return kTfLiteError;accum[d]=rem%s;rem/=s;}
    int idx=0;
    for(int t=0;t<nr;t++)idx=idx*x->dims->data[remaining[t]]+static_cast<int>(accum[remaining[t]]);
    if(idx<0||idx>=out)return kTfLiteError;
    int64_t v=static_cast<int64_t>(y->data.i32[idx])*x->data.i32[linear];
    if(v<INT32_MIN||v>INT32_MAX)return kTfLiteError;
    y->data.i32[idx]=static_cast<int32_t>(v);
  }
  return kTfLiteOk;
}
}
TFLMRegistration RegisterGelu(){return tflite::micro::RegisterOp(GeluInit,GeluPrepare,GeluInvoke);}
TFLMRegistration RegisterReduceProd(){return tflite::micro::RegisterOp(nullptr,ProductPrepare,ProductInvoke);}
}
