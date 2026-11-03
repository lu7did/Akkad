#include "board.hpp"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>

extern const unsigned char g_tflite_model[];
extern const unsigned int g_tflite_model_size;

#ifndef PICOKERAS_ARENA_BYTES
#define PICOKERAS_ARENA_BYTES 98304
#endif
static_assert(PICOKERAS_ARENA_BYTES>=8192 && PICOKERAS_ARENA_BYTES<=262144,
              "Invalid arena size for RP2350");
namespace {
alignas(16) static uint8_t arena[PICOKERAS_ARENA_BYTES];
// Reference TFLM kernels: only the operations registered here are supported.
tflite::MicroMutableOpResolver<24> resolver;
tflite::MicroInterpreter* interpreter = nullptr;
}

bool pico_model_init() {
  const auto* model = tflite::GetModel(g_tflite_model);
  if (model->version()!=TFLITE_SCHEMA_VERSION) { std::printf("MODEL schema mismatch\n"); return false; }
  if (resolver.AddAdd()!=kTfLiteOk || resolver.AddMul()!=kTfLiteOk ||
      resolver.AddSub()!=kTfLiteOk || resolver.AddFullyConnected()!=kTfLiteOk ||
      resolver.AddSoftmax()!=kTfLiteOk || resolver.AddReshape()!=kTfLiteOk ||
      resolver.AddTranspose()!=kTfLiteOk || resolver.AddMean()!=kTfLiteOk ||
      resolver.AddConcatenation()!=kTfLiteOk || resolver.AddStridedSlice()!=kTfLiteOk ||
      resolver.AddPack()!=kTfLiteOk || resolver.AddGather()!=kTfLiteOk ||
      resolver.AddQuantize()!=kTfLiteOk || resolver.AddDequantize()!=kTfLiteOk ||
      resolver.AddLogistic()!=kTfLiteOk || resolver.AddTanh()!=kTfLiteOk ||
      resolver.AddMaximum()!=kTfLiteOk || resolver.AddMinimum()!=kTfLiteOk ||
      resolver.AddBatchMatMul()!=kTfLiteOk || resolver.AddRsqrt()!=kTfLiteOk ||
      resolver.AddSqrt()!=kTfLiteOk || resolver.AddSquare()!=kTfLiteOk ||
      resolver.AddExp()!=kTfLiteOk) {std::printf("MODEL resolver overflow/invalid\n"); return false;}
  // Place the interpreter in static storage to avoid heap fragmentation.
  alignas(tflite::MicroInterpreter) static unsigned char interpreter_mem[sizeof(tflite::MicroInterpreter)];
  interpreter = new (interpreter_mem) tflite::MicroInterpreter(model,resolver,arena,sizeof(arena));
  if (interpreter->AllocateTensors()!=kTfLiteOk) { std::printf("MODEL AllocateTensors failed (arena/unsupported op)\n"); interpreter=nullptr;return false;}
  TfLiteTensor* input=interpreter->input(0),*output=interpreter->output(0);
  if (!input || !output) return false;
  int elements=1;
  for(int i=0;i<input->dims->size;i++)elements*=input->dims->data[i];
  int output_elements=1;
  for(int i=0;i<output->dims->size;i++)output_elements*=output->dims->data[i];
  if(elements!=768 || output_elements!=1 ||
     (input->type!=kTfLiteInt8 && input->type!=kTfLiteUInt8 && input->type!=kTfLiteFloat32) ||
     (output->type!=kTfLiteInt8 && output->type!=kTfLiteUInt8 && output->type!=kTfLiteFloat32)) {
    std::printf("MODEL unsupported tensor shape/type\n");interpreter=nullptr;return false;
  }
  std::printf("MODEL ready model_bytes=%u arena_bytes=%u\n",g_tflite_model_size,(unsigned)sizeof(arena));
  return true;
}

bool pico_model_eval(const picoSargon::Board& board, double& value) {
  if(!interpreter)return false;
  auto* in=interpreter->input(0);
  float tensor[768]{};
  const bool black=board.turn==-1;
  for(int sq=0;sq<64;sq++) {
    int p=board.piece(sq);if(!p)continue;
    int rank=sq/8,file=sq%8;
    int mapped=black?rank:7-rank;
    int channel=(p>0?0:6)+std::abs(p)-1;
    if(black)channel=(channel+6)%12;
    tensor[(mapped*8+file)*12+channel]=1.0f;
  }
  if(in->type!=kTfLiteFloat32 && in->params.scale<=0)return false;
  for(int i=0;i<768;i++) {
    float v=(in->dims->size==2)?tensor[(i%64)*12+i/64]:tensor[i];
    if(in->type==kTfLiteFloat32)in->data.f[i]=v;
    else {
      int q=int(std::lround(v/in->params.scale))+in->params.zero_point;
      if(in->type==kTfLiteInt8)in->data.int8[i]=static_cast<int8_t>(std::clamp(q,-128,127));
      else in->data.uint8[i]=static_cast<uint8_t>(std::clamp(q,0,255));
    }
  }
  if(interpreter->Invoke()!=kTfLiteOk)return false;
  auto* out=interpreter->output(0);
  if(out->type==kTfLiteFloat32)value=out->data.f[0];
  else if(out->type==kTfLiteInt8)value=(out->data.int8[0]-out->params.zero_point)*out->params.scale;
  else value=(out->data.uint8[0]-out->params.zero_point)*out->params.scale;
  return std::isfinite(value) && value>=-1.00001 && value<=1.00001;
}
