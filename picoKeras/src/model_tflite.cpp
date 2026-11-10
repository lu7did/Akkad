#include "model.hpp"
#include <tensorflow/lite/interpreter.h>
#include <tensorflow/lite/kernels/register.h>
#include <tensorflow/lite/model.h>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <cstdint>

namespace ps = picoSargon;
namespace {
void require(bool ok, const std::string& msg) { if (!ok) throw std::runtime_error(msg); }
}
struct Evaluator::Impl {
 std::unique_ptr<tflite::FlatBufferModel> model;
 std::unique_ptr<tflite::Interpreter> interpreter;
 bool flat=false;
 explicit Impl(const std::string& path,size_t) {
  require(std::filesystem::path(path).extension()==".tflite", "Debian engine accepts only converted .tflite networks: "+path);
  require(std::filesystem::is_regular_file(path),"Debian TFLite requires a .tflite file: "+path);
  model=tflite::FlatBufferModel::BuildFromFile(path.c_str());
  require(bool(model),"Cannot load TFLite model: "+path);
  tflite::ops::builtin::BuiltinOpResolver resolver;
  tflite::InterpreterBuilder(*model,resolver)(&interpreter);
  require(bool(interpreter),"TFLite interpreter creation failed (unsupported op?)");
  require(interpreter->inputs().size()==1 && interpreter->outputs().size()==1,"Exactly one input and one output required");
  interpreter->SetNumThreads(1);
  auto* in=interpreter->input_tensor(0);
  require(in && in->dims,"Invalid input tensor");
  const auto* d=in->dims;
  flat=d->size==2 && d->data[1]==768;
  const bool spatial=d->size==4 && d->data[1]==8 && d->data[2]==8 && d->data[3]==12;
  require(flat||spatial,"Input must be [N,768] or [N,8,8,12]");
  require(in->type==kTfLiteFloat32||in->type==kTfLiteInt8||in->type==kTfLiteUInt8,"Input must be FLOAT32, INT8 or UINT8");
 }
 void configure(const std::string& input,const std::string& output) {
  // TensorFlow SavedModel operation names do not exist in TFLite flatbuffers.
  require(input=="auto" && output=="auto","For .tflite use --input-op auto --output-op auto");
 }
 void encode(const ps::Board& b,float* dest){
  std::fill(dest,dest+768,0.f);
  const bool black=b.turn==-1;
  for(int sq=0;sq<64;++sq){
   const int piece=b.piece(sq);if(!piece)continue;
   const int rank=sq/8,file=sq%8,mapped_rank=black?rank:7-rank;
   int channel=(piece>0?0:6)+std::abs(piece)-1;
   if(black)channel=(channel+6)%12;
   const int idx=(mapped_rank*8+file)*12+channel;
   if(flat)dest[(idx%12)*64+idx/12]=1.f; else dest[idx]=1.f;
  }
 }
 std::vector<double> evaluate_batch(const std::vector<ps::Board>& boards){
  if(boards.empty())return {};
  require(boards.size()<=static_cast<size_t>(INT32_MAX),"Batch too large");
  auto* input=interpreter->input_tensor(0);
  std::vector<int> dims;for(int k=0;k<input->dims->size;++k)dims.push_back(input->dims->data[k]);
  dims[0]=static_cast<int>(boards.size());
  require(interpreter->ResizeInputTensor(interpreter->inputs()[0],dims)==kTfLiteOk,"TFLite resize failed");
  require(interpreter->AllocateTensors()==kTfLiteOk,"TFLite AllocateTensors failed (memory or unsupported op)");
  input=interpreter->input_tensor(0);
  std::vector<float> vals(boards.size()*768);
  for(size_t i=0;i<boards.size();++i)encode(boards[i],vals.data()+768*i);
  require(input->bytes==vals.size()*(input->type==kTfLiteFloat32?sizeof(float):sizeof(uint8_t)),"Input tensor byte size mismatch");
  if(input->type==kTfLiteFloat32)std::copy(vals.begin(),vals.end(),interpreter->typed_input_tensor<float>(0));
  else {
   require(input->params.scale>0.f,"Invalid input quantization scale");
   const float inv=1.f/input->params.scale;
   if(input->type==kTfLiteInt8){auto* p=interpreter->typed_input_tensor<int8_t>(0);for(size_t i=0;i<vals.size();++i)p[i]=static_cast<int8_t>(std::clamp(std::lround(vals[i]*inv)+long(input->params.zero_point),-128L,127L));}
   else {auto* p=interpreter->typed_input_tensor<uint8_t>(0);for(size_t i=0;i<vals.size();++i)p[i]=static_cast<uint8_t>(std::clamp(std::lround(vals[i]*inv)+long(input->params.zero_point),0L,255L));}
  }
  require(interpreter->Invoke()==kTfLiteOk,"TFLite Invoke failed");
  const TfLiteTensor* out=interpreter->output_tensor(0);
  require(out && out->dims,"Invalid output tensor");
  int64_t elements=1;for(int i=0;i<out->dims->size;++i)elements*=out->dims->data[i];
  require(elements==static_cast<int64_t>(boards.size()),"Output must contain exactly one scalar per board");
  std::vector<double> result(boards.size());
  for(size_t i=0;i<result.size();++i){
   double v;
   if(out->type==kTfLiteFloat32)v=interpreter->typed_output_tensor<float>(0)[i];
   else if(out->type==kTfLiteInt8){require(out->params.scale>0.f,"Invalid output quantization");v=(double(interpreter->typed_output_tensor<int8_t>(0)[i])-out->params.zero_point)*out->params.scale;}
   else if(out->type==kTfLiteUInt8){require(out->params.scale>0.f,"Invalid output quantization");v=(double(interpreter->typed_output_tensor<uint8_t>(0)[i])-out->params.zero_point)*out->params.scale;}
   else throw std::runtime_error("Output must be FLOAT32, INT8 or UINT8");
   require(std::isfinite(v)&&std::abs(v)<=1.00001,"Invalid network output (expected [-1,1])");
   result[i]=std::clamp(v,-1.,1.);
  }
  return result;
 }
};
Evaluator::Evaluator(const std::string& path,size_t arena):impl_(std::make_unique<Impl>(path,arena)){}
Evaluator::~Evaluator()=default;
void Evaluator::configure(const std::string& input,const std::string& output){impl_->configure(input,output);}
double Evaluator::eval(const ps::Board& b){return impl_->evaluate_batch({b})[0];}
std::vector<double> Evaluator::eval_batch(const std::vector<ps::Board>& bs){return impl_->evaluate_batch(bs);}
