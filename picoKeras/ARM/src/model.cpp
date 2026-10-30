#include "model.hpp"
#include <fstream>
#include <stdexcept>
#include <cmath>
#include <algorithm>
#include <cstring>
#include <chrono>
#include <iostream>
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"
#include "int8_extra_ops.hpp"
namespace ps = picoSargon;
struct Evaluator::Impl {
 std::vector<unsigned char> blob;
 std::vector<unsigned char> arena;
 const tflite::Model* model=nullptr;
 tflite::MicroMutableOpResolver<32> resolver;
 std::unique_ptr<tflite::MicroInterpreter> interpreter;
 int count=0;
 Impl(const std::string& filename,size_t arena_bytes) : arena(arena_bytes) {
  // Explicit registration against the current TensorFlow Lite Micro API.
  // Missing kernel support is reported by AllocateTensors, not hidden.
  auto require = [](TfLiteStatus result, const char* name) {
    if (result != kTfLiteOk) throw std::runtime_error(std::string("TFLM op registration failed: ") + name);
  };
  require(resolver.AddAdd(), "ADD");
  require(resolver.AddMul(), "MUL");
  require(resolver.AddSub(), "SUB");
  require(resolver.AddDiv(), "DIV");
  require(resolver.AddFullyConnected(), "FULLY_CONNECTED");
  require(resolver.AddBatchMatMul(), "BATCH_MATMUL");
  require(resolver.AddSoftmax(), "SOFTMAX");
  require(resolver.AddReshape(), "RESHAPE");
  require(resolver.AddTranspose(), "TRANSPOSE");
  require(resolver.AddMean(), "MEAN");
  require(resolver.AddRsqrt(), "RSQRT");
  require(resolver.AddSqrt(), "SQRT");
  require(resolver.AddSquare(), "SQUARE");
  require(resolver.AddExp(), "EXP");
  require(resolver.AddConcatenation(), "CONCATENATION");
  require(resolver.AddStridedSlice(), "STRIDED_SLICE");
  require(resolver.AddPack(), "PACK");
  require(resolver.AddGather(), "GATHER");
  require(resolver.AddQuantize(), "QUANTIZE");
  require(resolver.AddDequantize(), "DEQUANTIZE");
  require(resolver.AddLogistic(), "LOGISTIC");
  require(resolver.AddTanh(), "TANH");
  require(resolver.AddMaximum(), "MAXIMUM");
  require(resolver.AddMinimum(), "MINIMUM");
  require(resolver.AddShape(), "SHAPE");
  require(resolver.AddCast(), "CAST");
  require(resolver.AddPicoGelu(pico_int8::RegisterGelu()), "GELU");
  require(resolver.AddPicoReduceProd(pico_int8::RegisterReduceProd()), "REDUCE_PROD");

  std::ifstream file(filename,std::ios::binary|std::ios::ate);
  if(!file) throw std::runtime_error("network inaccessible: "+filename);
  auto n=file.tellg();if(n<8||n>100000000)throw std::runtime_error("network size invalid");
  blob.resize(static_cast<size_t>(n));file.seekg(0);file.read(reinterpret_cast<char*>(blob.data()),n);
  if(!file||std::memcmp(blob.data()+4,"TFL3",4)!=0)throw std::runtime_error("--network requires a .tflite FlatBuffer (FP32 or INT8), not SavedModel .tf");
  model=tflite::GetModel(blob.data());
  if(model->version()!=TFLITE_SCHEMA_VERSION)throw std::runtime_error("TFLM FlatBuffer schema version mismatch");
  interpreter=std::make_unique<tflite::MicroInterpreter>(model,resolver,arena.data(),arena.size());
  if(interpreter->AllocateTensors()!=kTfLiteOk)throw std::runtime_error("TFLM AllocateTensors failed: unsupported op or insufficient arena; inspect TFLM diagnostics");
  auto *in=interpreter->input(0),*out=interpreter->output(0);
  if(!in||!out)throw std::runtime_error("input/output missing");
  int dims=in->dims->size; int elements=1;for(int i=0;i<dims;i++)elements*=in->dims->data[i];
  if(elements!=768 || !((dims==4&&in->dims->data[0]==1&&in->dims->data[1]==8&&in->dims->data[2]==8&&in->dims->data[3]==12)||(dims==2&&in->dims->data[0]==1&&in->dims->data[1]==768)))
   throw std::runtime_error("invalid network input: expected [1,8,8,12] or [1,768]");
  int oe=1;for(int i=0;i<out->dims->size;i++)oe*=out->dims->data[i];
  if(oe!=1)throw std::runtime_error("invalid network output: expected scalar value, not policy logits");
  if(in->type!=kTfLiteFloat32 && in->type!=kTfLiteInt8 && in->type!=kTfLiteUInt8)throw std::runtime_error("unsupported network input type");
  if(out->type!=kTfLiteFloat32 && out->type!=kTfLiteInt8 && out->type!=kTfLiteUInt8)throw std::runtime_error("unsupported network output type");
  std::cerr<<"NETWORK format=TFLite schema="<<model->version()<<" bytes="<<blob.size()<<" arena="<<arena.size()<<" input="<<in->type<<" output="<<out->type<<"\n";
 }
 double evaluate(const ps::Board& b){
  float tensor[768]{};
  // Keras source model input [1,8,8,12]; rank 8 is row 0, channel P N B R Q K p n b r q k.
  // Black-to-move: python-chess Board.mirror() = vertical rank flip and color swap, NOT 180-degree rotation.
  const bool black=b.turn==-1;
  for(int sq=0;sq<64;++sq){int piece=b.piece(sq);if(!piece)continue;
   int rank=sq/8,file=sq%8;
   int mapped_rank=black ? rank : 7-rank;
   int channel=(piece>0?0:6)+std::abs(piece)-1;
   if(black)channel=(channel+6)%12;
   tensor[(mapped_rank*8+file)*12+channel]=1.0f;
  }
  TfLiteTensor* in=interpreter->input(0);
  auto q=[&](float v)->int{if(in->params.scale<=0)throw std::runtime_error("invalid INT8 scale");return static_cast<int>(std::round(v/in->params.scale))+in->params.zero_point;};
  for(int i=0;i<768;i++){
   // In the flat interface, 12 consecutive 64-square piece planes are expected.
   const float value=(in->dims->size==2) ? tensor[(i%64)*12+i/64] : tensor[i];
   if(in->type==kTfLiteFloat32)in->data.f[i]=value;
   else if(in->type==kTfLiteInt8)in->data.int8[i]=static_cast<int8_t>(std::clamp(q(value),-128,127));
   else in->data.uint8[i]=static_cast<uint8_t>(std::clamp(q(value),0,255));
  }
  if(interpreter->Invoke()!=kTfLiteOk)throw std::runtime_error("TFLM invocation failed");
  auto* out=interpreter->output(0);double v=out->type==kTfLiteFloat32?out->data.f[0] : out->type==kTfLiteInt8 ? (out->data.int8[0]-out->params.zero_point)*out->params.scale : (out->data.uint8[0]-out->params.zero_point)*out->params.scale;
  if(!std::isfinite(v)||v < -1.00001 || v>1.00001)throw std::runtime_error("network returned nonfinite/out-of-range value");
  ++count;return std::clamp(v,-1.0,1.0);
 }
};
Evaluator::Evaluator(const std::string& file,size_t arena): impl_(std::make_unique<Impl>(file,arena)){}
Evaluator::~Evaluator()=default;
double Evaluator::eval(const ps::Board& board){return impl_->evaluate(board);}

