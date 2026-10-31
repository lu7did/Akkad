#include "model.hpp"
#include <tensorflow/c/c_api.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>
#include <iostream>
namespace fs = std::filesystem;
namespace ps = picoSargon;
namespace {
void check(TF_Status* st, const char* step) {
 if (TF_GetCode(st) != TF_OK) throw std::runtime_error(std::string(step)+": "+TF_Message(st));
}
struct Status { TF_Status* p=TF_NewStatus(); ~Status(){TF_DeleteStatus(p);} };
void release(void* data, size_t, void*) { std::free(data); }
}
struct Evaluator::Impl {
 TF_Graph* graph=TF_NewGraph();
 TF_Session* session=nullptr;
 TF_SessionOptions* options=TF_NewSessionOptions();
 TF_Output input{},output{};
 std::vector<int64_t> input_dims;
 std::vector<float> values;
 TF_DataType input_type=TF_FLOAT,output_type=TF_FLOAT;
 bool flat=false;
 Impl(const std::string& model_path,size_t) {
  try {
   fs::path dir(model_path);
   if(!fs::is_directory(dir)||!fs::exists(dir/"saved_model.pb"))
    throw std::runtime_error("Expected SavedModel directory (.tf with saved_model.pb); for .keras run tools/prepare_model.py first");
   Status status;
   const char* tags[]={"serve"};
   session=TF_LoadSessionFromSavedModel(options,nullptr,dir.string().c_str(),tags,1,graph,nullptr,status.p);
   check(status.p,"TF_LoadSessionFromSavedModel");
   // Signature ops can vary between exported Keras versions: supplied via --input-op / --output-op.
  } catch(...) { cleanup();throw; }
 }
 void configure(const std::string& in_name,const std::string& out_name) {
  auto resolve=[&](const std::string& spec)->TF_Output {
   auto at=spec.rfind(':');std::string name=spec.substr(0,at);
   int index=at==std::string::npos?0:std::stoi(spec.substr(at+1));
   auto* op=TF_GraphOperationByName(graph,name.c_str());
   if(!op||index<0||index>=TF_OperationNumOutputs(op))throw std::runtime_error("TensorFlow operation not found: "+spec);
   return TF_Output{op,index};
  };
  auto matches_board_input=[&](TF_Output x)->bool {
   if(TF_OperationOutputType(x)!=TF_FLOAT)return false;
   Status st;
   int n=TF_GraphGetTensorNumDims(graph,x,st.p);
   if(TF_GetCode(st.p)!=TF_OK || (n!=2 && n!=4))return false;
   std::vector<int64_t> dims(n,-1);
   TF_GraphGetTensorShape(graph,x,dims.data(),n,st.p);
   if(TF_GetCode(st.p)!=TF_OK)return false;
   return (n==2 && dims[1]==768) ||
          (n==4 && dims[1]==8 && dims[2]==8 && dims[3]==12);
  };
  auto auto_input=[&]()->TF_Output {
   // SavedModel signature input operations normally have serve_* and
   // serving_default_* prefixes; prefer the exported 'serve' signature.
   TF_Output best{};int priority=-1;
   size_t pos=0;
   while(TF_Operation* op=TF_GraphNextOperation(graph,&pos)) {
    std::string name=TF_OperationName(op);
    int rank=name.rfind("serve_",0)==0?2:
             name.rfind("serving_default_",0)==0?1:0;
    if(rank==0 || TF_OperationNumOutputs(op)<1)continue;
    TF_Output candidate{op,0};
    if(rank>priority && matches_board_input(candidate)){
     best=candidate;priority=rank;
    }
   }
   if(!best.oper)throw std::runtime_error(
      "No suitable FLOAT32 SavedModel input found. Expected [batch,768] or [batch,8,8,12]; use --input-op.");
   return best;
  };
  auto auto_output=[&]()->TF_Output {
   // For Keras SavedModel exports the 'serve' signature typically uses
   // StatefulPartitionedCall:0; _1 belongs to 'serving_default'.
   for(const char* name:{"StatefulPartitionedCall","StatefulPartitionedCall_1"}){
    auto* op=TF_GraphOperationByName(graph,name);
    if(op && TF_OperationNumOutputs(op)>0){
     TF_Output candidate{op,0};
     if(TF_OperationOutputType(candidate)==TF_FLOAT)return candidate;
    }
   }
   throw std::runtime_error("No FLOAT32 SavedModel output identified; use --output-op.");
  };
  input=in_name=="auto"?auto_input():resolve(in_name);
  output=out_name=="auto"?auto_output():resolve(out_name);
  std::cerr<<"TensorFlow bindings: input="<<TF_OperationName(input.oper)<<":"<<input.index
           <<" output="<<TF_OperationName(output.oper)<<":"<<output.index<<"\n";
  input_type=TF_OperationOutputType(input);output_type=TF_OperationOutputType(output);
  if(input_type!=TF_FLOAT || output_type!=TF_FLOAT)
   throw std::runtime_error("Desktop runtime currently requires FLOAT32 input/output. INT8 internal ops are fine if boundary is FLOAT32.");
  Status status;
  const int nd=TF_GraphGetTensorNumDims(graph,input,status.p);check(status.p,"Input tensor rank");
  if(nd!=2 && nd!=4)throw std::runtime_error("Expected input rank 2 or 4");
  input_dims.resize(nd);TF_GraphGetTensorShape(graph,input,input_dims.data(),nd,status.p);check(status.p,"Input tensor shape");
  const bool rank4=(nd==4 && input_dims[1]==8 && input_dims[2]==8 && input_dims[3]==12);
  flat=(nd==2 && input_dims[1]==768);
  if(!rank4&&!flat)throw std::runtime_error("Input must be [batch,8,8,12] or [batch,768]");
  values.resize(768);
 }
 void cleanup() noexcept {
  if(session){Status status;TF_CloseSession(session,status.p);TF_DeleteSession(session,status.p);session=nullptr;}
  if(options){TF_DeleteSessionOptions(options);options=nullptr;}
  if(graph){TF_DeleteGraph(graph);graph=nullptr;}
 }
 ~Impl(){cleanup();}
 void encode(const ps::Board& b,float* dest) {
  std::fill(dest,dest+768,0.f);
  const bool black=b.turn==-1;
  for(int sq=0;sq<64;sq++){
   const int piece=b.piece(sq);if(!piece)continue;
   const int rank=sq/8,file=sq%8;
   const int mapped_rank=black?rank:7-rank;
   int channel=(piece>0?0:6)+std::abs(piece)-1;
   if(black)channel=(channel+6)%12;
   const int idx=(mapped_rank*8+file)*12+channel;
   if(flat) dest[(idx%12)*64+idx/12]=1.f;
   else dest[idx]=1.f;
  }
 }
 std::vector<double> evaluate_batch(const std::vector<ps::Board>& boards) {
  if(boards.empty())return {};
  if(!session||!input.oper||!output.oper)throw std::runtime_error("Evaluator not configured");
  const auto count=boards.size();
  std::vector<float> data(count*768);
  for(size_t i=0;i<count;++i)encode(boards[i],data.data()+i*768);
  auto dims=input_dims;dims[0]=static_cast<int64_t>(count);
  const size_t bytes=data.size()*sizeof(float);
  TF_Tensor* x=TF_AllocateTensor(TF_FLOAT,dims.data(),static_cast<int>(dims.size()),bytes);
  if(!x)throw std::runtime_error("TF_AllocateTensor failed");
  std::memcpy(TF_TensorData(x),data.data(),bytes);
  TF_Tensor* y=nullptr;
  Status status;
  TF_SessionRun(session,nullptr,&input,&x,1,&output,&y,1,nullptr,0,nullptr,status.p);
  TF_DeleteTensor(x);
  try {check(status.p,"TF_SessionRun");
   if(!y || TF_TensorType(y)!=TF_FLOAT || TF_TensorByteSize(y)!=count*sizeof(float))
    throw std::runtime_error("Expected exactly one FLOAT32 scalar output per position");
   std::vector<double> result(count);
   const float* v=static_cast<const float*>(TF_TensorData(y));
   for(size_t i=0;i<count;++i){if(!std::isfinite(v[i]) || std::abs(v[i])>1.00001)throw std::runtime_error("Invalid network output");result[i]=std::clamp(double(v[i]),-1.,1.);}
   TF_DeleteTensor(y);return result;
  } catch(...){if(y)TF_DeleteTensor(y);throw;}
 }
};
Evaluator::Evaluator(const std::string& file,size_t arena):impl_(std::make_unique<Impl>(file,arena)){}
Evaluator::~Evaluator()=default;
void Evaluator::configure(const std::string& in,const std::string& out){impl_->configure(in,out);}
double Evaluator::eval(const ps::Board& board){return impl_->evaluate_batch({board})[0];}
std::vector<double> Evaluator::eval_batch(const std::vector<ps::Board>& boards){return impl_->evaluate_batch(boards);}
